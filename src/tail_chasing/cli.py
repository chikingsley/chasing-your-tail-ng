from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from tail_chasing import __version__
from tail_chasing.ignore_lists import (
    DEFAULT_IGNORE_LIST_DIR,
    IgnoreListError,
    build_ignore_lists_from_kismet,
    clear_ignore_lists,
    load_ignore_lists,
    write_ignore_lists,
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
    help="Wi-Fi probe and Kismet analysis tooling for local security research.",
)
ignore_lists_app = typer.Typer(
    no_args_is_help=True, help="Manage local MAC/SSID suppression lists."
)
kismet_app = typer.Typer(no_args_is_help=True, help="Run and inspect repo-local Kismet capture.")


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


@app.command()
def doctor() -> None:
    """Check local prerequisites for development and future Kismet runtime work."""
    typer.echo("tail-chasing doctor: scaffold ready")


@ignore_lists_app.command("show")
def show_ignore_lists(
    directory: Annotated[
        Path,
        typer.Option(
            "--directory",
            "-d",
            help="Directory containing local ignore-list JSON files.",
        ),
    ] = DEFAULT_IGNORE_LIST_DIR,
    output_json: Annotated[
        bool,
        typer.Option("--json", help="Print the loaded ignore lists as JSON."),
    ] = False,
) -> None:
    """Show local ignore-list counts and entries."""
    try:
        ignore_lists = load_ignore_lists(directory)
    except IgnoreListError as exc:
        _abort(str(exc))

    if output_json:
        typer.echo(json.dumps(ignore_lists.as_dict(), indent=2))
        return

    typer.echo(f"Directory: {directory}")
    typer.echo(f"MAC addresses: {len(ignore_lists.macs)}")
    for mac in ignore_lists.macs:
        typer.echo(f"  {mac}")

    typer.echo(f"SSIDs: {len(ignore_lists.ssids)}")
    for ssid in ignore_lists.ssids:
        typer.echo(f"  {ssid}")


@ignore_lists_app.command("build")
def build_ignore_lists(
    database: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Kismet SQLite database to baseline.",
        ),
    ],
    directory: Annotated[
        Path,
        typer.Option(
            "--directory",
            "-d",
            help="Directory where local ignore-list JSON files are written.",
        ),
    ] = DEFAULT_IGNORE_LIST_DIR,
) -> None:
    """Build local ignore lists from a Kismet SQLite database."""
    try:
        ignore_lists = build_ignore_lists_from_kismet(database)
        paths = write_ignore_lists(ignore_lists, directory)
    except IgnoreListError as exc:
        _abort(str(exc))

    typer.echo(f"Wrote {len(ignore_lists.macs)} MAC addresses to {paths.macs}")
    typer.echo(f"Wrote {len(ignore_lists.ssids)} SSIDs to {paths.ssids}")


@ignore_lists_app.command("clear")
def clear_local_ignore_lists(
    directory: Annotated[
        Path,
        typer.Option(
            "--directory",
            "-d",
            help="Directory containing local ignore-list JSON files.",
        ),
    ] = DEFAULT_IGNORE_LIST_DIR,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Clear without prompting for confirmation."),
    ] = False,
) -> None:
    """Clear generated local ignore-list files."""
    if not yes and not typer.confirm(f"Delete ignore-list files in {directory}?"):
        raise typer.Exit

    removed = clear_ignore_lists(directory)
    typer.echo(f"Removed {removed} ignore-list file(s).")


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
) -> None:
    """Start Kismet in tmux with config, auth, and logs inside the project."""
    sources = list(source or ["wlo1"])
    if bluetooth:
        sources.append("hci0:type=linuxbluetooth")

    try:
        start_kismet(runtime_dir, sources=sources, session_name=session_name)
    except KismetRuntimeError as exc:
        _abort(str(exc))

    typer.echo(f"Started {session_name}")
    typer.echo(f"Runtime: {runtime_dir}")
    typer.echo(f"Sources: {', '.join(sources)}")


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
        return

    typer.echo(f"Latest DB: {status.latest_database.path}")
    for table, count in status.latest_database.row_counts.items():
        typer.echo(f"  {table}: {count}")


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


app.add_typer(ignore_lists_app, name="ignore-lists")
app.add_typer(kismet_app, name="kismet")


if __name__ == "__main__":
    main()
