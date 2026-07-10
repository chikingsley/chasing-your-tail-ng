from __future__ import annotations

import getpass
import json
import secrets
import shlex
import shutil
import sqlite3
import subprocess
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import requests

DEFAULT_RUNTIME_DIR = Path("runtime/kismet")
DEFAULT_SESSION_NAME = "kismet-tail"
DEFAULT_HTTP_URL = "http://127.0.0.1:2501"
DEFAULT_LOG_TITLE = "tail-chasing"
DEFAULT_SERVER_LOG_NAME = "kismet-server.log"
DATABASE_STALE_AFTER_SECONDS = 90
_SQLITE_LOCK_RETRIES = 5
_SQLITE_LOCK_RETRY_DELAY_SECONDS = 0.5
_COUNT_QUERIES = {
    "devices": 'SELECT COUNT(*) FROM "devices"',
    "packets": 'SELECT COUNT(*) FROM "packets"',
    "datasources": 'SELECT COUNT(*) FROM "datasources"',
    "messages": 'SELECT COUNT(*) FROM "messages"',
    "alerts": 'SELECT COUNT(*) FROM "alerts"',
    "data": 'SELECT COUNT(*) FROM "data"',
}


class KismetRuntimeError(RuntimeError):
    """Raised when Kismet runtime state cannot be read or changed."""


@dataclass(frozen=True, slots=True)
class KismetAuth:
    username: str
    password: str


@dataclass(frozen=True, slots=True)
class KismetDatabaseSummary:
    path: Path
    size_bytes: int
    modified_at: float
    row_counts: dict[str, int]

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["path"] = str(self.path)
        return payload


@dataclass(frozen=True, slots=True)
class KismetSourceStatus:
    name: str
    definition: str
    driver: str
    running: bool
    packets: int
    error: str

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> KismetSourceStatus:
        driver = payload.get("kismet.datasource.type_driver", {})
        if not isinstance(driver, dict):
            driver = {}

        return cls(
            name=str(payload.get("kismet.datasource.name", "")),
            definition=str(payload.get("kismet.datasource.definition", "")),
            driver=str(driver.get("kismet.datasource.driver.type", "")),
            running=bool(payload.get("kismet.datasource.running", False)),
            packets=int(payload.get("kismet.datasource.num_packets", 0)),
            error=str(payload.get("kismet.datasource.error_reason", "")),
        )


@dataclass(frozen=True, slots=True)
class KismetRuntimeStatus:
    runtime_dir: Path
    session_name: str
    session_running: bool
    http_url: str
    http_reachable: bool
    system_devices: int | None
    system_version: str | None
    sources: tuple[KismetSourceStatus, ...]
    latest_database: KismetDatabaseSummary | None
    database_logging_healthy: bool | None
    database_logging_detail: str
    server_log: Path
    server_log_error: str | None

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["runtime_dir"] = str(self.runtime_dir)
        if self.latest_database is not None:
            payload["latest_database"] = self.latest_database.as_dict()
        payload["server_log"] = str(self.server_log)
        return payload


def ensure_runtime_config(
    runtime_dir: Path = DEFAULT_RUNTIME_DIR,
    *,
    sources: Sequence[str],
    username: str | None = None,
    log_title: str = DEFAULT_LOG_TITLE,
    log_packets: bool = False,
    http_bind_address: str = "127.0.0.1",
    gps_definition: str | None = None,
) -> tuple[Path, Path]:
    """Create repo-local Kismet runtime config files."""
    http_bind_address = _single_line_value(http_bind_address, name="HTTP bind address")
    if gps_definition is not None:
        gps_definition = _single_line_value(gps_definition, name="GPS definition")
    runtime_dir = runtime_dir.resolve()
    logs_dir = runtime_dir / "logs"
    home_dir = runtime_dir / "home"
    httpd_dir = home_dir / "httpd"
    for directory in (runtime_dir, logs_dir, home_dir, httpd_dir):
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(0o700)

    auth_path = runtime_dir / "kismet_httpd.conf"
    if not auth_path.exists():
        auth = KismetAuth(
            username=username or getpass.getuser(),
            password=secrets.token_urlsafe(24),
        )
        auth_path.write_text(
            f"httpd_username={auth.username}\nhttpd_password={auth.password}\n",
            encoding="utf-8",
        )
        auth_path.chmod(0o600)

    config_path = runtime_dir / "kismet.conf"
    source_lines = "\n".join(f"source={source}" for source in _normalize_sources(sources))
    gps_lines = [f"gps={gps_definition}"] if gps_definition is not None else []
    config_path.write_text(
        "\n".join(
            [
                f"httpd_bind_address={http_bind_address}",
                f"httpd_auth_file={auth_path}",
                f"httpd_session_db={runtime_dir / 'session.db'}",
                f"httpd_user_home={httpd_dir}",
                f"log_prefix={logs_dir}",
                "log_types=kismet",
                f"log_title={log_title}",
                "kis_log_devices=true",
                "kis_log_device_rate=30",
                f"kis_log_packets={str(log_packets).lower()}",
                "kis_log_messages=true",
                "kis_log_alerts=true",
                "kis_log_datasources=true",
                "kis_log_datasources_rate=30",
                *gps_lines,
                source_lines,
                "",
            ],
        ),
        encoding="utf-8",
    )
    config_path.chmod(0o600)
    return config_path, auth_path


def start_kismet(
    runtime_dir: Path = DEFAULT_RUNTIME_DIR,
    *,
    sources: Sequence[str],
    session_name: str = DEFAULT_SESSION_NAME,
    log_title: str = DEFAULT_LOG_TITLE,
    log_packets: bool = False,
    http_bind_address: str = "127.0.0.1",
    gps_definition: str | None = None,
) -> None:
    """Start Kismet in a tmux session with repo-local state."""
    if tmux_session_running(session_name):
        raise KismetRuntimeError(f"tmux session already exists: {session_name}")

    config_path, _ = ensure_runtime_config(
        runtime_dir,
        sources=sources,
        log_title=log_title,
        log_packets=log_packets,
        http_bind_address=http_bind_address,
        gps_definition=gps_definition,
    )
    runtime_dir = runtime_dir.resolve()
    server_log = runtime_dir / DEFAULT_SERVER_LOG_NAME
    command = " ".join(
        [
            "cd",
            shlex.quote(str(Path.cwd())),
            "&&",
            "exec",
            "kismet",
            "--no-ncurses",
            "--no-line-wrap",
            "--homedir",
            shlex.quote(str(runtime_dir / "home")),
            "--log-title",
            shlex.quote(log_title),
            "--override",
            shlex.quote(str(config_path)),
            ">",
            shlex.quote(str(server_log)),
            "2>&1",
        ],
    )
    grouped_command = f"sg kismet -c {shlex.quote(command)}"
    _run(["tmux", "new-session", "-d", "-s", session_name, grouped_command])


def stop_kismet(session_name: str = DEFAULT_SESSION_NAME) -> bool:
    """Stop the tmux-managed Kismet session."""
    if not tmux_session_running(session_name):
        return False
    _run(["tmux", "kill-session", "-t", session_name])
    return True


def get_runtime_status(
    runtime_dir: Path = DEFAULT_RUNTIME_DIR,
    *,
    session_name: str = DEFAULT_SESSION_NAME,
    http_url: str = DEFAULT_HTTP_URL,
) -> KismetRuntimeStatus:
    """Collect runtime status from tmux, Kismet HTTP, and the latest DB."""
    auth = read_auth(runtime_dir)
    status_payload: dict[str, Any] | None = None
    sources_payload: list[dict[str, Any]] = []

    if auth is not None:
        status_payload = _get_json(http_url, "system/status.json", auth)
        source_data = _get_json(http_url, "datasource/all_sources.json", auth)
        if isinstance(source_data, list):
            sources_payload = [item for item in source_data if isinstance(item, dict)]

    database_path = latest_kismet_database(runtime_dir)
    database_summary = (
        summarize_kismet_database(database_path) if database_path is not None else None
    )
    server_log = runtime_dir / DEFAULT_SERVER_LOG_NAME
    server_log_error = _latest_server_log_error(server_log)
    session_running = tmux_session_running(session_name)
    logging_healthy, logging_detail = _database_logging_health(
        session_running=session_running,
        http_reachable=status_payload is not None,
        database=database_summary,
        server_log_error=server_log_error,
    )
    return KismetRuntimeStatus(
        runtime_dir=runtime_dir,
        session_name=session_name,
        session_running=session_running,
        http_url=http_url,
        http_reachable=status_payload is not None,
        system_devices=_optional_int(status_payload, "kismet.system.devices.count"),
        system_version=_optional_str(status_payload, "kismet.system.version"),
        sources=tuple(KismetSourceStatus.from_api(source) for source in sources_payload),
        latest_database=database_summary,
        database_logging_healthy=logging_healthy,
        database_logging_detail=logging_detail,
        server_log=server_log,
        server_log_error=server_log_error,
    )


def read_auth(runtime_dir: Path = DEFAULT_RUNTIME_DIR) -> KismetAuth | None:
    """Read the repo-local Kismet auth file."""
    auth_path = runtime_dir / "kismet_httpd.conf"
    if not auth_path.exists():
        return None

    values: dict[str, str] = {}
    for line in auth_path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key.strip()] = value.strip()

    username = values.get("httpd_username")
    password = values.get("httpd_password")
    if not username or not password:
        return None
    return KismetAuth(username=username, password=password)


def latest_kismet_database(runtime_dir: Path = DEFAULT_RUNTIME_DIR) -> Path | None:
    """Return the newest `.kismet` log database under the runtime directory."""
    logs_dir = runtime_dir / "logs"
    if not logs_dir.exists():
        return None

    databases = [path for path in logs_dir.glob("*.kismet") if path.is_file()]
    if not databases:
        return None
    return max(databases, key=lambda path: path.stat().st_mtime)


def summarize_kismet_database(database_path: Path) -> KismetDatabaseSummary:
    """Read basic table counts from a Kismet SQLite database without cleaning it."""
    if not database_path.exists():
        raise KismetRuntimeError(f"Kismet database not found: {database_path}")

    uri = f"file:{database_path.resolve()}?mode=ro"
    row_counts: dict[str, int] | None = None
    for attempt in range(_SQLITE_LOCK_RETRIES):
        try:
            with sqlite3.connect(uri, uri=True, timeout=1.0) as connection:
                connection.execute("PRAGMA query_only = ON")
                connection.execute("PRAGMA busy_timeout = 1000")
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'",
                    )
                }
                row_counts = {
                    table: _count_table(connection, table) if table in tables else 0
                    for table in (
                        "devices",
                        "packets",
                        "datasources",
                        "messages",
                        "alerts",
                        "data",
                    )
                }
            break
        except sqlite3.OperationalError as exc:
            if _is_sqlite_lock_error(exc) and attempt < _SQLITE_LOCK_RETRIES - 1:
                time.sleep(_SQLITE_LOCK_RETRY_DELAY_SECONDS)
                continue
            raise KismetRuntimeError(
                f"Could not read Kismet database {database_path}: {exc}",
            ) from exc
        except sqlite3.Error as exc:
            raise KismetRuntimeError(
                f"Could not read Kismet database {database_path}: {exc}",
            ) from exc

    if row_counts is None:
        raise KismetRuntimeError(f"Could not read Kismet database {database_path}")

    return KismetDatabaseSummary(
        path=database_path,
        size_bytes=database_path.stat().st_size,
        modified_at=database_path.stat().st_mtime,
        row_counts=row_counts,
    )


def _database_logging_health(
    *,
    session_running: bool,
    http_reachable: bool,
    database: KismetDatabaseSummary | None,
    server_log_error: str | None,
) -> tuple[bool | None, str]:
    if not session_running:
        return None, "capture is stopped"
    if not http_reachable:
        return False, "Kismet HTTP is unreachable"
    if server_log_error is not None:
        return False, server_log_error
    if database is None:
        return False, "Kismet has not created a database"

    age_seconds = max(0.0, time.time() - database.modified_at)
    if age_seconds > DATABASE_STALE_AFTER_SECONDS:
        return False, f"database has not changed for {age_seconds:.0f} seconds"
    return True, f"database changed {age_seconds:.0f} seconds ago"


def _latest_server_log_error(server_log: Path) -> str | None:
    if not server_log.exists():
        return None

    error_markers = (
        "kis_database_logfile unable",
        "unable to insert",
        "sql logic error",
        "database is locked",
        "database or disk is full",
        "disk i/o error",
    )
    with server_log.open("rb") as stream:
        stream.seek(0, 2)
        stream.seek(max(0, stream.tell() - 1_048_576))
        lines = stream.read().decode("utf-8", errors="replace").splitlines()
    for line in reversed(lines):
        if any(marker in line.lower() for marker in error_markers):
            return line.strip()
    return None


def tmux_session_running(session_name: str = DEFAULT_SESSION_NAME) -> bool:
    """Return whether a named tmux session exists."""
    tmux = _command_path("tmux")
    result = subprocess.run(
        [tmux, "has-session", "-t", session_name],
        check=False,
        stderr=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
    )
    return result.returncode == 0


def _normalize_sources(sources: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(source.strip() for source in sources if source.strip())
    if not normalized:
        raise KismetRuntimeError("At least one Kismet source is required.")
    if any("\n" in source or "\r" in source for source in normalized):
        raise KismetRuntimeError("Kismet source definitions must fit on one line.")
    return normalized


def _single_line_value(value: str, *, name: str) -> str:
    normalized = value.strip()
    if not normalized or "\n" in normalized or "\r" in normalized:
        raise KismetRuntimeError(f"{name} must be a non-empty, single-line value.")
    return normalized


def _count_table(connection: sqlite3.Connection, table: str) -> int:
    value = connection.execute(_COUNT_QUERIES[table]).fetchone()
    return int(value[0]) if value is not None else 0


def _is_sqlite_lock_error(exc: sqlite3.OperationalError) -> bool:
    message = str(exc).lower()
    return "locked" in message or "busy" in message


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    resolved_command = [_command_path(command[0]), *command[1:]]
    try:
        return subprocess.run(resolved_command, check=True, text=True, capture_output=True)
    except FileNotFoundError as exc:
        raise KismetRuntimeError(f"Required command not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        details = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise KismetRuntimeError(details) from exc


def _get_json(http_url: str, endpoint: str, auth: KismetAuth) -> Any | None:
    url = f"{http_url.rstrip('/')}/{endpoint.lstrip('/')}"
    try:
        response = requests.get(url, auth=(auth.username, auth.password), timeout=2)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, json.JSONDecodeError):
        return None


def _command_path(command: str) -> str:
    resolved = shutil.which(command)
    if resolved is None:
        raise KismetRuntimeError(f"Required command not found: {command}")
    return resolved


def _optional_int(payload: dict[str, Any] | None, key: str) -> int | None:
    if payload is None or key not in payload:
        return None
    try:
        return int(payload[key])
    except (TypeError, ValueError):
        return None


def _optional_str(payload: dict[str, Any] | None, key: str) -> str | None:
    if payload is None or key not in payload:
        return None
    return str(payload[key])
