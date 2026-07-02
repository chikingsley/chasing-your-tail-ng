from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

DEFAULT_IGNORE_LIST_DIR = Path("ignore_lists")
MAC_LIST_FILENAME = "mac_list.json"
SSID_LIST_FILENAME = "ssid_list.json"

_MAC_ADDRESS_PATTERN = re.compile(r"^(?:[0-9A-F]{2}:){5}[0-9A-F]{2}$")
_PROBED_SSID_KEY = "dot11.probedssid.ssid"
_ASCII_CONTROL_LIMIT = 32
_MAX_SSID_BYTES = 32


class IgnoreListError(ValueError):
    """Raised when ignore-list input cannot be read or created."""


@dataclass(frozen=True, slots=True)
class IgnoreLists:
    macs: tuple[str, ...] = ()
    ssids: tuple[str, ...] = ()

    @classmethod
    def from_values(cls, *, macs: Iterable[object], ssids: Iterable[object]) -> IgnoreLists:
        return cls(macs=_normalize_macs(macs), ssids=_normalize_ssids(ssids))

    @property
    def total_entries(self) -> int:
        return len(self.macs) + len(self.ssids)

    def as_dict(self) -> dict[str, list[str]]:
        return {"macs": list(self.macs), "ssids": list(self.ssids)}


@dataclass(frozen=True, slots=True)
class IgnoreListPaths:
    macs: Path
    ssids: Path


def load_ignore_lists(directory: Path = DEFAULT_IGNORE_LIST_DIR) -> IgnoreLists:
    """Load JSON ignore lists from a local generated-data directory."""
    return IgnoreLists.from_values(
        macs=_read_json_list(directory / MAC_LIST_FILENAME),
        ssids=_read_json_list(directory / SSID_LIST_FILENAME),
    )


def write_ignore_lists(
    ignore_lists: IgnoreLists, directory: Path = DEFAULT_IGNORE_LIST_DIR
) -> IgnoreListPaths:
    """Write ignore lists as deterministic JSON files."""
    directory.mkdir(parents=True, exist_ok=True)
    paths = IgnoreListPaths(
        macs=directory / MAC_LIST_FILENAME,
        ssids=directory / SSID_LIST_FILENAME,
    )
    _write_json_list(paths.macs, ignore_lists.macs)
    _write_json_list(paths.ssids, ignore_lists.ssids)
    return paths


def clear_ignore_lists(directory: Path = DEFAULT_IGNORE_LIST_DIR) -> int:
    """Delete known ignore-list files and return the number removed."""
    removed = 0
    for file_path in (directory / MAC_LIST_FILENAME, directory / SSID_LIST_FILENAME):
        if file_path.exists():
            file_path.unlink()
            removed += 1
    return removed


def build_ignore_lists_from_kismet(database_path: Path) -> IgnoreLists:
    """Build local suppression lists from a Kismet SQLite capture database."""
    if not database_path.exists():
        raise IgnoreListError(f"Kismet database not found: {database_path}")
    if not database_path.is_file():
        raise IgnoreListError(f"Kismet database path is not a file: {database_path}")

    macs: list[object] = []
    ssids: list[object] = []

    try:
        with sqlite3.connect(database_path) as connection:
            macs.extend(row[0] for row in connection.execute("SELECT DISTINCT devmac FROM devices"))

            for row in connection.execute("SELECT device FROM devices"):
                ssids.extend(_extract_probe_ssids(row[0]))
    except sqlite3.Error as exc:
        raise IgnoreListError(f"Could not read Kismet database {database_path}: {exc}") from exc

    return IgnoreLists.from_values(macs=macs, ssids=ssids)


def _read_json_list(file_path: Path) -> list[object]:
    if not file_path.exists():
        return []

    try:
        loaded = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise IgnoreListError(f"Ignore list is not valid JSON: {file_path}") from exc

    if not isinstance(loaded, list):
        raise IgnoreListError(f"Ignore list must be a JSON array: {file_path}")

    return loaded


def _write_json_list(file_path: Path, values: tuple[str, ...]) -> None:
    file_path.write_text(f"{json.dumps(list(values), indent=2)}\n", encoding="utf-8")


def _normalize_macs(values: Iterable[object]) -> tuple[str, ...]:
    normalized = {
        normalized_mac for value in values if (normalized_mac := _normalize_mac(value)) is not None
    }
    return tuple(sorted(normalized))


def _normalize_mac(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    candidate = value.strip().replace("-", ":").upper()
    if not _MAC_ADDRESS_PATTERN.fullmatch(candidate):
        return None
    return candidate


def _normalize_ssids(values: Iterable[object]) -> tuple[str, ...]:
    normalized = {
        normalized_ssid
        for value in values
        if (normalized_ssid := _normalize_ssid(value)) is not None
    }
    return tuple(sorted(normalized, key=str.casefold))


def _normalize_ssid(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if "\x00" in value or any(ord(character) < _ASCII_CONTROL_LIMIT for character in value):
        return None

    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        return None

    if not encoded or len(encoded) > _MAX_SSID_BYTES:
        return None
    return value


def _extract_probe_ssids(raw_device: object) -> tuple[object, ...]:
    if not isinstance(raw_device, str) or not raw_device:
        return ()

    try:
        device_data: object = json.loads(raw_device)
    except json.JSONDecodeError:
        return ()

    return tuple(_find_values_for_key(device_data, _PROBED_SSID_KEY))


def _find_values_for_key(value: object, key: str) -> Iterator[object]:
    if isinstance(value, dict):
        for item_key, item_value in value.items():
            if item_key == key:
                yield item_value
            yield from _find_values_for_key(item_value, key)
    elif isinstance(value, list):
        for item in value:
            yield from _find_values_for_key(item, key)
