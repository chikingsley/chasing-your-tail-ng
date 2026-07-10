from __future__ import annotations

import json
from ipaddress import ip_address
from pathlib import Path
from typing import Annotated, NoReturn

import typer
from pydantic import ValidationError

from tail_chasing import __version__
from tail_chasing.collector import (
    DEFAULT_BLUETOOTH_INTERFACE,
    DEFAULT_COLLECTOR_PROFILE,
    DEFAULT_WIFI_INTERFACE,
    CheckState,
    CollectorError,
    CollectorMode,
    CollectorProfile,
    configure_collector,
    inspect_collector,
    load_collector_profile,
)
from tail_chasing.kismet_runtime import (
    DEFAULT_HTTP_URL,
    DEFAULT_RUNTIME_DIR,
    DEFAULT_SESSION_NAME,
    KismetRuntimeError,
    get_runtime_status,
    latest_kismet_database,
    start_kismet,
    stop_kismet,
    summarize_kismet_database,
)

app = typer.Typer(
    no_args_is_help=True,
    help="Configure and operate a repo-local Kismet Wi-Fi/Bluetooth collector.",
)
kismet_app = typer.Typer(no_args_is_help=True, help="Run and inspect repo-local Kismet capture.")
collector_app = typer.Typer(
    no_args_is_help=True,
    help="Configure and operate one deployable Wi-Fi/Bluetooth collector.",
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"tail-chasing {__version__}")
        raise typer.Exit


@app.callback()
def root(
    version: Annotated[
        bool,
        typer.Option("--version", callback=version_callback, is_eager=True, help="Show version."),
    ] = False,
) -> None:
    _ = version


@collector_app.command("setup")
def setup_collector(
    name: Annotated[
        str,
        typer.Option("--name", help="Stable name for this physical collector."),
    ] = "tail-chasing-portable",
    mode: Annotated[
        CollectorMode,
        typer.Option("--mode", help="Portable walk-around or fixed property collector."),
    ] = CollectorMode.PORTABLE,
    wifi_interface: Annotated[
        list[str] | None,
        typer.Option(
            "--wifi",
            help="Linux Wi-Fi interface used for monitor-mode capture. Repeat for more radios.",
        ),
    ] = None,
    bluetooth: Annotated[
        bool,
        typer.Option(
            "--bluetooth/--no-bluetooth",
            help="Enable or disable Linux Bluetooth discovery.",
        ),
    ] = True,
    bluetooth_interface: Annotated[
        list[str] | None,
        typer.Option(
            "--bluetooth-interface",
            help="Linux Bluetooth HCI interface. Repeat for more adapters.",
        ),
    ] = None,
    gps_definition: Annotated[
        str | None,
        typer.Option(
            "--gps",
            help="Optional Kismet GPS definition, for example gpsd:host=localhost,port=2947.",
        ),
    ] = None,
    profile_path: Annotated[
        Path,
        typer.Option("--profile", help="Collector profile written by this command."),
    ] = DEFAULT_COLLECTOR_PROFILE,
    runtime_dir: Annotated[
        Path,
        typer.Option("--runtime-dir", help="Repo-local Kismet runtime directory."),
    ] = DEFAULT_RUNTIME_DIR,
    session_name: Annotated[
        str,
        typer.Option("--session", help="tmux session name for this collector."),
    ] = DEFAULT_SESSION_NAME,
    http_bind_address: Annotated[
        str,
        typer.Option(
            "--http-bind-address",
            help="Kismet web bind address; localhost is the safe default.",
        ),
    ] = "127.0.0.1",
    http_url: Annotated[
        str | None,
        typer.Option(
            "--http-url",
            help="Local status URL; defaults to the configured bind address on port 2501.",
        ),
    ] = None,
    log_packets: Annotated[
        bool,
        typer.Option(
            "--log-packets/--no-log-packets",
            help="Persist raw packets. Device/event logging remains enabled either way.",
        ),
    ] = False,
) -> None:
    """Write the portable profile and generated Kismet config without starting capture."""
    bluetooth_interfaces = tuple(
        bluetooth_interface or [DEFAULT_BLUETOOTH_INTERFACE] if bluetooth else [],
    )
    try:
        profile = CollectorProfile(
            name=name,
            mode=mode,
            wifi_interfaces=tuple(wifi_interface or [DEFAULT_WIFI_INTERFACE]),
            bluetooth_interfaces=bluetooth_interfaces,
            runtime_dir=runtime_dir.resolve(),
            session_name=session_name,
            http_bind_address=http_bind_address,
            http_url=http_url or _collector_http_url(http_bind_address),
            gps_definition=gps_definition,
            log_packets=log_packets,
        )
        written_profile, config_path, auth_path = configure_collector(
            profile,
            profile_path=profile_path,
        )
    except (CollectorError, KismetRuntimeError, OSError, ValidationError, ValueError) as exc:
        _abort(str(exc))

    typer.echo(f"Collector profile: {written_profile}")
    typer.echo(f"Kismet config: {config_path}")
    typer.echo(f"Kismet credentials: {auth_path}")
    typer.echo(f"Sources: {', '.join(profile.kismet_sources())}")
    typer.echo("Capture was not started.")
    typer.echo(f"Next: tail-chasing collector doctor --profile {written_profile}")


@collector_app.command("show")
def show_collector(
    profile_path: Annotated[
        Path,
        typer.Option("--profile", help="Collector profile to read."),
    ] = DEFAULT_COLLECTOR_PROFILE,
) -> None:
    """Show the effective collector profile and Kismet source definitions."""
    try:
        profile = load_collector_profile(profile_path)
    except CollectorError as exc:
        _abort(str(exc))
    payload = profile.as_dict()
    payload["kismet_sources"] = list(profile.kismet_sources())
    typer.echo(json.dumps(payload, indent=2))


@collector_app.command("doctor")
def doctor_collector(
    profile_path: Annotated[
        Path,
        typer.Option("--profile", help="Collector profile to inspect."),
    ] = DEFAULT_COLLECTOR_PROFILE,
    output_json: Annotated[
        bool,
        typer.Option("--json", help="Print the readiness report as JSON."),
    ] = False,
) -> None:
    """Check the configured software, privileges, radios, and storage without changing them."""
    try:
        profile = load_collector_profile(profile_path)
        report = inspect_collector(profile, profile_path=profile_path)
    except CollectorError as exc:
        _abort(str(exc))

    if output_json:
        typer.echo(json.dumps(report.as_dict(), indent=2))
    else:
        for check in report.checks:
            color = {
                CheckState.READY: typer.colors.GREEN,
                CheckState.WARNING: typer.colors.YELLOW,
                CheckState.MISSING: typer.colors.RED,
            }[check.state]
            typer.secho(f"[{check.state.value.upper()}] {check.name}: {check.detail}", fg=color)
        typer.echo(f"Collector ready: {'yes' if report.ready else 'no'}")
    if not report.ready:
        raise typer.Exit(code=1)


@collector_app.command("start")
def start_collector(
    profile_path: Annotated[
        Path,
        typer.Option("--profile", help="Collector profile to start."),
    ] = DEFAULT_COLLECTOR_PROFILE,
) -> None:
    """Start the configured Kismet collector after a successful readiness check."""
    try:
        profile = load_collector_profile(profile_path)
        report = inspect_collector(profile, profile_path=profile_path)
        if not report.ready:
            missing = ", ".join(
                check.name for check in report.checks if check.state is CheckState.MISSING
            )
            _abort(f"collector is not ready; missing: {missing}")
        configure_collector(profile, profile_path=profile_path)
        start_kismet(
            profile.runtime_dir,
            sources=profile.kismet_sources(),
            session_name=profile.session_name,
            log_title=profile.name,
            log_packets=profile.log_packets,
            http_bind_address=profile.http_bind_address,
            gps_definition=profile.gps_definition,
        )
    except (CollectorError, KismetRuntimeError, OSError) as exc:
        _abort(str(exc))
    typer.echo(f"Started collector {profile.name} ({profile.session_name})")
    typer.echo(f"Status: tail-chasing collector status --profile {profile_path}")


@collector_app.command("stop")
def stop_collector(
    profile_path: Annotated[
        Path,
        typer.Option("--profile", help="Collector profile to stop."),
    ] = DEFAULT_COLLECTOR_PROFILE,
) -> None:
    """Stop the tmux session named by the collector profile."""
    try:
        profile = load_collector_profile(profile_path)
        stopped = stop_kismet(profile.session_name)
    except (CollectorError, KismetRuntimeError) as exc:
        _abort(str(exc))
    typer.echo(
        f"Stopped {profile.session_name}"
        if stopped
        else f"No running tmux session named {profile.session_name}",
    )


@collector_app.command("status")
def collector_status(
    profile_path: Annotated[
        Path,
        typer.Option("--profile", help="Collector profile to inspect."),
    ] = DEFAULT_COLLECTOR_PROFILE,
    output_json: Annotated[
        bool,
        typer.Option("--json", help="Print status as JSON."),
    ] = False,
) -> None:
    """Show the actual Kismet session, datasource, and database state for this collector."""
    try:
        profile = load_collector_profile(profile_path)
        status = get_runtime_status(
            profile.runtime_dir,
            session_name=profile.session_name,
            http_url=profile.http_url,
        )
    except (CollectorError, KismetRuntimeError) as exc:
        _abort(str(exc))
    if output_json:
        typer.echo(json.dumps(status.as_dict(), indent=2))
        return
    typer.echo(f"Collector: {profile.name} ({profile.mode.value})")
    typer.echo(f"Session: {'running' if status.session_running else 'stopped'}")
    typer.echo(f"Kismet HTTP: {'reachable' if status.http_reachable else 'unreachable'}")
    typer.echo(f"Configured sources: {', '.join(profile.kismet_sources())}")
    if status.sources:
        for source in status.sources:
            typer.echo(
                f"  {source.name}: {'running' if source.running else 'stopped'}, "
                f"packets={source.packets}, error={source.error or 'none'}",
            )
    typer.echo(f"Database logging: {status.database_logging_detail}")
    if status.latest_database is not None:
        typer.echo(f"Latest DB: {status.latest_database.path}")


@kismet_app.command("start")
def start_kismet_capture(
    runtime_dir: Annotated[
        Path,
        typer.Option("--runtime-dir", help="Repo-local Kismet runtime directory."),
    ] = DEFAULT_RUNTIME_DIR,
    source: Annotated[
        list[str] | None,
        typer.Option(
            "--source",
            "-s",
            help="Kismet source definition. Repeat for Wi-Fi, Bluetooth, or files.",
        ),
    ] = None,
    bluetooth: Annotated[
        bool,
        typer.Option("--bluetooth/--no-bluetooth", help="Also add hci0 Bluetooth capture."),
    ] = False,
    session_name: Annotated[
        str,
        typer.Option("--session", help="tmux session name."),
    ] = DEFAULT_SESSION_NAME,
    log_packets: Annotated[
        bool,
        typer.Option(
            "--log-packets/--no-log-packets",
            help="Persist raw packets. Disabled by default to keep event captures bounded.",
        ),
    ] = False,
) -> None:
    """Start Kismet in tmux with config, auth, and logs inside the project."""
    sources = list(source or ["wlo1"])
    if bluetooth:
        sources.append("hci0:type=linuxbluetooth")

    try:
        start_kismet(
            runtime_dir,
            sources=sources,
            session_name=session_name,
            log_packets=log_packets,
        )
    except KismetRuntimeError as exc:
        _abort(str(exc))

    typer.echo(f"Started {session_name}")
    typer.echo(f"Runtime: {runtime_dir}")
    typer.echo(f"Sources: {', '.join(sources)}")
    typer.echo(f"Raw packet logging: {'enabled' if log_packets else 'disabled'}")


@kismet_app.command("stop")
def stop_kismet_capture(
    session_name: Annotated[
        str,
        typer.Option("--session", help="tmux session name."),
    ] = DEFAULT_SESSION_NAME,
) -> None:
    """Stop the tmux-managed Kismet capture session."""
    try:
        stopped = stop_kismet(session_name)
    except KismetRuntimeError as exc:
        _abort(str(exc))

    if stopped:
        typer.echo(f"Stopped {session_name}")
        return
    typer.echo(f"No running tmux session named {session_name}")


@kismet_app.command("status")
def kismet_status(
    runtime_dir: Annotated[
        Path,
        typer.Option("--runtime-dir", help="Repo-local Kismet runtime directory."),
    ] = DEFAULT_RUNTIME_DIR,
    http_url: Annotated[
        str,
        typer.Option("--http-url", help="Kismet HTTP base URL."),
    ] = DEFAULT_HTTP_URL,
    session_name: Annotated[
        str,
        typer.Option("--session", help="tmux session name."),
    ] = DEFAULT_SESSION_NAME,
    output_json: Annotated[
        bool,
        typer.Option("--json", help="Print status as JSON."),
    ] = False,
) -> None:
    """Show live Kismet, datasource, and latest database status."""
    try:
        status = get_runtime_status(runtime_dir, session_name=session_name, http_url=http_url)
    except KismetRuntimeError as exc:
        _abort(str(exc))

    if output_json:
        typer.echo(json.dumps(status.as_dict(), indent=2))
        return

    typer.echo(f"Session: {'running' if status.session_running else 'stopped'} ({session_name})")
    typer.echo(f"HTTP: {'reachable' if status.http_reachable else 'unreachable'} ({http_url})")
    if status.system_version:
        typer.echo(f"Kismet: {status.system_version}")
    if status.system_devices is not None:
        typer.echo(f"Devices in memory: {status.system_devices}")

    if status.sources:
        typer.echo("Sources:")
        for source in status.sources:
            state = "running" if source.running else "stopped"
            detail = f"  {source.name}: {state}, {source.driver}, packets={source.packets}"
            if source.error:
                detail = f"{detail}, error={source.error}"
            typer.echo(detail)
    else:
        typer.echo("Sources: none reported")

    if status.latest_database is None:
        typer.echo("Latest DB: none")
        typer.echo(f"Database logging: {status.database_logging_detail}")
        return

    typer.echo(f"Latest DB: {status.latest_database.path}")
    for table, count in status.latest_database.row_counts.items():
        typer.echo(f"  {table}: {count}")
    logging_state = {
        True: "healthy",
        False: "UNHEALTHY",
        None: "inactive",
    }[status.database_logging_healthy]
    typer.echo(f"Database logging: {logging_state} ({status.database_logging_detail})")
    typer.echo(f"Server log: {status.server_log}")


@kismet_app.command("db-summary")
def kismet_db_summary(
    database: Annotated[
        Path | None,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Kismet SQLite database. Defaults to latest runtime DB.",
        ),
    ] = None,
    runtime_dir: Annotated[
        Path,
        typer.Option("--runtime-dir", help="Repo-local Kismet runtime directory."),
    ] = DEFAULT_RUNTIME_DIR,
    output_json: Annotated[
        bool,
        typer.Option("--json", help="Print summary as JSON."),
    ] = False,
) -> None:
    """Show basic row counts for a Kismet database, including a live DB."""
    database_path = database or latest_kismet_database(runtime_dir)
    if database_path is None:
        _abort(f"No Kismet database found under {runtime_dir / 'logs'}")

    try:
        summary = summarize_kismet_database(database_path)
    except KismetRuntimeError as exc:
        _abort(str(exc))

    if output_json:
        typer.echo(json.dumps(summary.as_dict(), indent=2))
        return

    typer.echo(f"Database: {summary.path}")
    typer.echo(f"Size: {summary.size_bytes} bytes")
    for table, count in summary.row_counts.items():
        typer.echo(f"{table}: {count}")


def main() -> None:
    app()


def _abort(message: str) -> NoReturn:
    typer.secho(message, fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


def _collector_http_url(bind_address: str) -> str:
    address = bind_address.strip()
    try:
        if ip_address(address.strip("[]")).is_unspecified:
            return DEFAULT_HTTP_URL
    except ValueError:
        pass
    if ":" in address and not address.startswith("["):
        address = f"[{address}]"
    return f"http://{address}:2501"


app.add_typer(kismet_app, name="kismet")
app.add_typer(collector_app, name="collector")


if __name__ == "__main__":
    main()
