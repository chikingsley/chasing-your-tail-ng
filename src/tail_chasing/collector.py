from __future__ import annotations

import grp
import json
import os
import re
import shutil
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from tail_chasing.kismet_runtime import (
    DEFAULT_HTTP_URL,
    DEFAULT_RUNTIME_DIR,
    DEFAULT_SESSION_NAME,
    ensure_runtime_config,
)

DEFAULT_COLLECTOR_PROFILE = Path("runtime/collector/profile.json")
DEFAULT_WIFI_INTERFACE = "wlan1"
DEFAULT_BLUETOOTH_INTERFACE = "hci0"
MINIMUM_FREE_BYTES = 5 * 1024**3


class CollectorError(RuntimeError):
    """Raised when a collector profile cannot be created or loaded."""


class CollectorMode(StrEnum):
    """Supported physical collector roles."""

    PORTABLE = "portable"
    PROPERTY = "property"


class CollectorProfile(BaseModel):
    """Portable, versioned configuration for one physical collector."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    name: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    mode: CollectorMode = CollectorMode.PORTABLE
    wifi_interfaces: tuple[str, ...] = ()
    bluetooth_interfaces: tuple[str, ...] = ()
    runtime_dir: Path = DEFAULT_RUNTIME_DIR
    session_name: str = DEFAULT_SESSION_NAME
    http_bind_address: str = "127.0.0.1"
    http_url: str = DEFAULT_HTTP_URL
    gps_definition: str | None = None
    log_packets: bool = False

    @field_validator(
        "wifi_interfaces",
        "bluetooth_interfaces",
        mode="before",
    )
    @classmethod
    def _normalize_interfaces(cls, value: object) -> object:
        if not isinstance(value, (list, tuple)):
            return value
        return tuple(str(item).strip() for item in value)

    @field_validator(
        "wifi_interfaces",
        "bluetooth_interfaces",
    )
    @classmethod
    def _validate_interfaces(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(re.fullmatch(r"[A-Za-z0-9_.-]{1,15}", item) is None for item in value):
            raise ValueError("interface names must be valid Linux interface names")
        if len(value) != len(set(value)):
            raise ValueError("interface names must be unique within each radio type")
        return value

    @field_validator("session_name", "http_bind_address")
    @classmethod
    def _validate_single_line(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or "\n" in normalized or "\r" in normalized:
            raise ValueError("value must be non-empty and fit on one line")
        return normalized

    @field_validator("gps_definition")
    @classmethod
    def _validate_gps(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized or "\n" in normalized or "\r" in normalized:
            raise ValueError("GPS definition must be non-empty and fit on one line")
        return normalized

    @model_validator(mode="after")
    def _validate_radios(self) -> Self:
        if not self.wifi_interfaces and not self.bluetooth_interfaces:
            raise ValueError("at least one Wi-Fi or Bluetooth interface is required")
        duplicate_interfaces = set(self.wifi_interfaces) & set(self.bluetooth_interfaces)
        if duplicate_interfaces:
            names = ", ".join(sorted(duplicate_interfaces))
            raise ValueError(f"interfaces cannot be both Wi-Fi and Bluetooth: {names}")
        return self

    def kismet_sources(self) -> tuple[str, ...]:
        """Return the Kismet source definitions represented by this profile."""
        wifi_sources = tuple(
            f"{interface}:type=linuxwifi,name=wifi-{index}"
            for index, interface in enumerate(self.wifi_interfaces, start=1)
        )
        bluetooth_sources = tuple(
            f"{interface}:type=linuxbluetooth,name=bluetooth-{index}"
            for index, interface in enumerate(self.bluetooth_interfaces, start=1)
        )
        return (*wifi_sources, *bluetooth_sources)

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation."""
        return self.model_dump(mode="json")


class CheckState(StrEnum):
    """Readiness state for one collector prerequisite."""

    READY = "ready"
    WARNING = "warning"
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class CollectorCheck:
    name: str
    state: CheckState
    detail: str

    def as_dict(self) -> dict[str, str]:
        payload = asdict(self)
        payload["state"] = self.state.value
        return payload


@dataclass(frozen=True, slots=True)
class CollectorDoctorReport:
    profile_path: Path
    checks: tuple[CollectorCheck, ...]

    @property
    def ready(self) -> bool:
        return all(check.state is not CheckState.MISSING for check in self.checks)

    def as_dict(self) -> dict[str, object]:
        return {
            "profile_path": str(self.profile_path),
            "ready": self.ready,
            "checks": [check.as_dict() for check in self.checks],
        }


def write_collector_profile(path: Path, profile: CollectorProfile) -> Path:
    """Write a collector profile atomically with owner-only permissions."""
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_text(json.dumps(profile.as_dict(), indent=2) + "\n", encoding="utf-8")
    temporary_path.chmod(0o600)
    temporary_path.replace(path)
    return path


def load_collector_profile(path: Path = DEFAULT_COLLECTOR_PROFILE) -> CollectorProfile:
    """Load and validate one versioned collector profile."""
    try:
        payload = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CollectorError(f"Could not read collector profile {path}: {exc}") from exc
    try:
        return CollectorProfile.model_validate_json(payload)
    except ValueError as exc:
        raise CollectorError(f"Invalid collector profile {path}: {exc}") from exc


def configure_collector(
    profile: CollectorProfile,
    *,
    profile_path: Path = DEFAULT_COLLECTOR_PROFILE,
) -> tuple[Path, Path, Path]:
    """Persist a profile and generate its repo-local Kismet configuration."""
    written_profile = write_collector_profile(profile_path, profile)
    config_path, auth_path = ensure_runtime_config(
        profile.runtime_dir,
        sources=profile.kismet_sources(),
        log_title=profile.name,
        log_packets=profile.log_packets,
        http_bind_address=profile.http_bind_address,
        gps_definition=profile.gps_definition,
    )
    return written_profile, config_path, auth_path


def inspect_collector(
    profile: CollectorProfile,
    *,
    profile_path: Path = DEFAULT_COLLECTOR_PROFILE,
) -> CollectorDoctorReport:
    """Inspect software, privileges, radios, and storage without changing the host."""
    checks: list[CollectorCheck] = []
    for command in ("kismet", "tmux"):
        executable = shutil.which(command)
        checks.append(
            CollectorCheck(
                name=f"command:{command}",
                state=CheckState.READY if executable else CheckState.MISSING,
                detail=executable or f"{command} is not installed or not on PATH",
            ),
        )

    if profile.wifi_interfaces:
        checks.append(_command_check("kismet_cap_linux_wifi", required=True))
    if profile.bluetooth_interfaces:
        checks.append(_command_check("kismet_cap_linux_bluetooth", required=True))
    checks.append(_kismet_group_check())
    checks.extend(_wifi_checks(profile.wifi_interfaces))
    checks.extend(_bluetooth_checks(profile.bluetooth_interfaces))
    if profile.gps_definition is not None:
        checks.append(_command_check("gpsd", required=True))
    checks.append(_storage_check(profile.runtime_dir))
    checks.append(_command_check("tailscale", required=False))
    return CollectorDoctorReport(profile_path=profile_path.resolve(), checks=tuple(checks))


def _command_check(command: str, *, required: bool) -> CollectorCheck:
    executable = shutil.which(command)
    state = (
        CheckState.READY if executable else (CheckState.MISSING if required else CheckState.WARNING)
    )
    detail = executable or f"{command} is not installed or not on PATH"
    return CollectorCheck(name=f"command:{command}", state=state, detail=detail)


def _kismet_group_check() -> CollectorCheck:
    try:
        kismet_group = grp.getgrnam("kismet")
    except KeyError:
        return CollectorCheck(
            name="privilege:kismet-group",
            state=CheckState.MISSING,
            detail="the kismet group does not exist",
        )

    group_ids = {*os.getgroups(), os.getegid()}
    if kismet_group.gr_gid in group_ids:
        return CollectorCheck(
            name="privilege:kismet-group",
            state=CheckState.READY,
            detail=f"current process belongs to kismet (gid {kismet_group.gr_gid})",
        )
    return CollectorCheck(
        name="privilege:kismet-group",
        state=CheckState.MISSING,
        detail="current process is not in the kismet group; log out/reboot after adding it",
    )


def _wifi_checks(interfaces: tuple[str, ...]) -> list[CollectorCheck]:
    return [
        CollectorCheck(
            name=f"wifi:{interface}",
            state=(
                CheckState.READY
                if (Path("/sys/class/net") / interface / "wireless").exists()
                else CheckState.MISSING
            ),
            detail=(
                "Linux wireless interface is present"
                if (Path("/sys/class/net") / interface / "wireless").exists()
                else "Linux wireless interface is not present"
            ),
        )
        for interface in interfaces
    ]


def _bluetooth_checks(interfaces: tuple[str, ...]) -> list[CollectorCheck]:
    bluetooth_root = Path("/sys/class/bluetooth")
    return [
        CollectorCheck(
            name=f"bluetooth:{interface}",
            state=(
                CheckState.READY if (bluetooth_root / interface).exists() else CheckState.MISSING
            ),
            detail=(
                "Linux Bluetooth HCI interface is present"
                if (bluetooth_root / interface).exists()
                else "Linux Bluetooth HCI interface is not present"
            ),
        )
        for interface in interfaces
    ]


def _storage_check(runtime_dir: Path) -> CollectorCheck:
    probe = runtime_dir.resolve()
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    free_bytes = shutil.disk_usage(probe).free
    free_gib = free_bytes / 1024**3
    return CollectorCheck(
        name="storage:runtime",
        state=CheckState.READY if free_bytes >= MINIMUM_FREE_BYTES else CheckState.WARNING,
        detail=f"{free_gib:.1f} GiB free on {probe}",
    )
