# tail-chasing

Local Wi-Fi, Bluetooth, and Kismet analysis tooling for security research.

This repository is being modernized from the inherited Chasing Your Tail scripts into a
`uv`-managed Python package with a Typer CLI, focused tests, and generated runtime data kept out of
Git.

## Current Status

- Package name: `tail-chasing`
- Python module: `tail_chasing`
- Runtime state: `runtime/` inside this repository, ignored by Git
- Inherited code: staged under `src/tail_chasing/inherited/` until it is ported or deleted
- Kismet capture: host Kismet package with repo-local config, auth, home, and logs
- UI: Kismet web UI only; the inherited Tkinter desktop GUI is replace-only

## Development

```bash
uv run tail-chasing --version
uv run tail-chasing doctor
uv run --locked pytest
uv run --locked ruff check src tests
uv run --locked ty check src tests --exclude 'src/tail_chasing/inherited/**'
uv run --locked vulture --config pyproject.toml
```

## Test Lanes

The default test suite uses synthetic fixtures. It checks parser behavior, CLI output, and regression
logic without requiring radio hardware:

```bash
uv run --locked pytest
```

The live suite checks this machine's running Kismet capture, HTTP API, datasource counters, and
repo-local `.kismet` database:

```bash
TAIL_CHASING_LIVE_TESTS=1 uv run --locked pytest tests/live -m live
```

Live tests are expected to fail if Kismet is stopped, the Wi-Fi source is missing, or the packet
counters are not advancing.

## Kismet Runtime

Start Kismet with repo-local runtime state:

```bash
uv run tail-chasing kismet start --bluetooth
```

Show the live server, datasource, and database status:

```bash
uv run tail-chasing kismet status
uv run tail-chasing kismet db-summary
```

Stop the tmux-managed capture session:

```bash
uv run tail-chasing kismet stop
```

The default runtime files are written under:

```text
runtime/kismet/
```

Kismet GPS/map features require a configured GPS source. A desktop/headless capture with only Wi-Fi
or Bluetooth sources can still collect devices and packets, but packets will not have usable
location data.

## Ignore Lists

Generate and inspect local ignore lists from a Kismet database:

```bash
uv run tail-chasing ignore-lists build runtime/kismet/logs/<capture>.kismet
uv run tail-chasing ignore-lists show
uv run tail-chasing ignore-lists clear
```

Generated ignore lists are local runtime data and are ignored by Git.

## Project Notes

- Active cleanup work is tracked in `TODO.md`.
- Completed work is recorded in `CHANGELOG.md`.
- Inherited root docs are archived under `docs/archive/inherited-root/`.
- The inherited code inventory is in `docs/code-inventory.md`.
