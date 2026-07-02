# tail-chasing TODO

Active work is unchecked. Completed work belongs in `CHANGELOG.md`; reference notes belong in
`docs/`, not here. Work is happening directly on `main` until the project is clean enough to commit
or open a PR.

## Phase 0 - Orientation and Decisions

- [x] Confirm current inherited repo shape: flat Python scripts, no `pyproject.toml`, stale
  `requirements.txt`, shell startup scripts, generated-output directories, and clean Git status.
- [x] Confirm local Python project convention: `uv`, `uv_build`, `src/` layout, Ruff `ALL`, `ty`,
  `vulture`, and focused pytest coverage.
- [x] Confirm local host baseline for Kismet trial: x86_64 Linux, no `kismet` binary currently on
  PATH, Intel CNVi Wi-Fi present as `wlo1`.
- [x] Decide the local Kismet install path for this machine: use the Arch package first. The local
  package database currently shows `extra/kismet 2025_09_R1-4`; recheck immediately before install.
  Run Kismet on the host for capture work, not in Docker, unless a later container setup proves
  cleaner for actual radio/device access.
- [x] Defer Raspberry Pi deployment planning. Treat it as a future target after local Linux capture
  and API integration work are proven.

## Phase 1 - Project Scaffold

- [x] Rename project identity to `tail-chasing` with Python module `tail_chasing`.
- [x] Add `pyproject.toml` from the maintained local template:
  - package backend: `uv_build`
  - runtime Python: current practical range after smoke testing, likely `>=3.12,<3.14`
  - runtime dependencies: start from `requests` and `cryptography`, then replace or add deliberately
  - dev dependencies: `pytest`, `ruff`, `ty`, `vulture`
  - CLI entry point: `tail-chasing = "tail_chasing.cli:main"`
- [x] Do not add `.python-version` by default. Use `requires-python` as the compatibility contract;
  add a local pin only if we need `uv` to select one exact interpreter for repeatable local runs.
- [x] Add `src/tail_chasing/` and `tests/`.
- [x] Add `.gitignore` for generated runtime files: logs, reports, KML, local databases, encrypted
  credentials, caches, `.venv`, `__pycache__`, and tool caches.
- [x] Generate `uv.lock` only after the first dependency set is real.

## Phase 2 - Inventory, Fixes, and Repackage Existing Code

- [ ] Finish the organization pass so every inherited file has one final disposition:
  - port into current package code
  - keep only as archived reference
  - delete as superseded/no longer useful
  - document any remaining external dependency or runtime assumption
- [x] Classify every inherited Python/shell file into review folders under
  `src/tail_chasing/inherited/`; rationale is in `docs/code-inventory.md`.
- [x] Move inherited files without deleting them:
  - keep/rework Kismet/security/analysis code
  - replace-candidate GUI and shell scripts
  - demo-only BlackHat script
  - delete-candidate empty ignore-list stubs
  - archived `requirements.txt`
- [x] Move inherited root documentation into `docs/archive/inherited-root/`.
- [x] Archive stale root `config.json` as `docs/archive/inherited-root/config.legacy.json`.
- [x] Remove generated-output placeholder directories from Git tracking instead of preserving empty
  roots with `gitkeep.keep`.
- [x] Remove inherited `LICENSE` and `cyt_ng_logo.png` as requested.
- [x] Replace inherited ignore-list handling with `src/tail_chasing/ignore_lists.py` and Typer
  commands:
  - `tail-chasing ignore-lists build`
  - `tail-chasing ignore-lists show`
  - `tail-chasing ignore-lists clear`
- [x] Remove inherited root `ignore_lists/*.json` from tracked source; local generated lists are now
  ignored by Git.
- [x] Classify every current Python file as keep, merge, replace, demo-only, or archive/delete:
  - `chasing_your_tail.py`
  - `cyt_gui.py`
  - `surveillance_analyzer.py`
  - `surveillance_detector.py`
  - `gps_tracker.py`
  - `probe_analyzer.py`
  - `secure_database.py`
  - `secure_credentials.py`
  - `secure_ignore_loader.py`
  - `secure_main_logic.py`
  - `input_validation.py`
  - `migrate_credentials.py`
  - `create_ignore_list.py`
  - `blackhat_demo.py`
- [ ] Move reusable code into package modules:
  - `config.py`
  - `credentials.py`
  - `kismet_db.py`
  - `kismet_api.py`
  - `events.py`
  - `detectors.py`
  - `gps.py`
  - `reports.py`
  - `wigle.py`
  - `cli.py`
  - `gui.py`
- [ ] Port useful code out of `src/tail_chasing/inherited/` one module at a time, with imports,
  tests, and CLI commands updated as each module becomes real package code.
- [ ] Keep entry points thin; no import-time config loading, credential prompts, logging setup, or
  filesystem writes.
- [ ] Replace script-global paths with config objects and explicit CLI options.
- [ ] Convert direct `print()` calls to CLI/report output boundaries or logging.

- [x] Fix ignore-list loading path by replacing config-driven legacy filenames with package
  defaults: local generated `ignore_lists/mac_list.json` and `ignore_lists/ssid_list.json`.
- [x] Decide final lifecycle for inherited root `ignore_lists/*.json`: remove from Git, ignore local
  generated lists, and manage them through CLI commands.
- [ ] Fix hardcoded `/home/matt/Desktop/cytng` paths in startup scripts or remove the scripts after
  folding their behavior into the CLI/service docs.
- [ ] Fix `surveillance_analyzer.generate_demo_analysis()` result-key mismatch:
  `high_threat_devices` vs `high_persistence_devices`.
- [ ] Fix GPS/device correlation so devices map to locations by timestamp instead of assigning all
  appearances to `Location_1`.
- [ ] Fix probe log timestamp parsing so generated timestamps use one consistent format.
- [ ] Fix report generation so HTML output is either actually generated or not advertised.
- [ ] Remove hardcoded "95% confidence" and "< 5% false positive" claims until the project has real
  validation data.

- [x] Replace `start_kismet_clean.sh` with a `tail-chasing kismet start/status` command or clear
  systemd/user-service docs.
- [ ] Replace `start_gui.sh` with web-only UI direction or remove it after CLI coverage exists. Do
  not port Tkinter/desktop behavior.
- [ ] Replace `monitor.sh` with `tail-chasing doctor` or `tail-chasing status`.
- [ ] Delete or archive shell scripts only after equivalent CLI/docs exist.

## Phase 3 - Kismet Integration Direction

- [ ] Keep `.kismet` SQLite reading as offline/import mode.
- [ ] Replace legacy direct-Kismet assumptions with current Kismet surfaces where appropriate:
  - KismetDB as canonical offline evidence
  - device views for bounded live device pulls
  - datasource APIs for capture health
  - eventbus/websocket APIs for live events
  - official Kismet log tools for PCAP/KML/WigleCSV/device JSON exports
- [x] Add repo-local Kismet runtime commands:
  - `tail-chasing kismet start`
  - `tail-chasing kismet stop`
  - `tail-chasing kismet status`
  - `tail-chasing kismet db-summary`
- [x] Add opt-in live Kismet tests for the actual tmux session, HTTP API, datasource counters, and
  live `.kismet` database.
- [ ] Add a live Kismet client around the current REST/websocket APIs:
  - device views for bounded pulls
  - device monitor websocket for live device updates
  - eventbus for probe/GPS/message events
  - API-key based auth
- [ ] Add `tail-chasing doctor` checks for:
  - Kismet installed and version visible
  - user/group/capability setup
  - capture interface present
  - Kismet server reachable
  - API auth configured
  - latest `.kismet` log path
- [ ] Add fixtures or sample `.kismet` data before changing detector logic heavily.
- [ ] Add a GPS plan for map-capable captures:
  - real GPS source, gpsd, phone/NMEA bridge, or explicit fixed-location test mode
  - keep no-GPS captures valid for packet/device analysis

## Phase 4 - Research-Quality Detection

- [ ] Define what the project is useful for before rebuilding detectors:
  - local situational awareness while a sensor is running
  - repeat-device and repeat-probe evidence summaries
  - Wi-Fi/Bluetooth environment baselining
  - map-capable captures when GPS exists
  - privacy/randomization caveats for modern phones and laptops
  - export workflows for external inspection in Kismet/Wireshark/Google Earth/Wigle-compatible tools
- [ ] Define the event model first: device appearance, probe SSID, location sample, source, capture
  confidence, and privacy/randomization indicators.
- [ ] Track locally administered/randomized MAC addresses separately from globally administered MACs.
- [ ] Treat modern Apple/Android MAC randomization as a core limitation, not an appendix.
- [ ] Replace "surveillance/stalking confirmed" language with evidence levels and caveats.
- [ ] Add reproducible scoring tests with synthetic scenarios:
  - single local device
  - common public AP environment
  - repeated randomized MACs
  - repeated global MAC across locations
  - GPS gaps and noisy location samples
- [ ] Produce JSON/JSONL evidence output before polished Markdown/KML summaries.

## Phase 5 - Outputs and Data Lifecycle

- [ ] Decide output roots and make them configurable.
- [ ] Keep generated outputs out of Git by default:
  - `logs/`
  - `reports/`
  - `surveillance_reports/`
  - `kml_files/`
  - `analysis_logs/`
  - `secure_credentials/`
  - `ignore_lists/`
- [ ] Add machine-readable outputs: JSONL event stream, JSON summary, and GeoJSON.
- [ ] Keep KML as a visualization export, generated from the same summary model.
- [ ] Document which outputs are sensitive and how to clean or archive them.

## Phase 6 - Validation Gates

- [x] Scaffold gates pass for package/test scope:
  - `uv lock --check`
  - `uv run --locked ruff format --check src tests`
  - `uv run --locked ruff check src tests`
  - `uv run --locked ty check src tests --exclude 'src/tail_chasing/inherited/**'`
  - `uv run --locked pytest`
  - `uv run --locked vulture`
- [ ] `uv lock --check`
- [ ] `uv run --locked ruff format --check .`
- [ ] `uv run --locked ruff check .`
- [ ] `uv run --locked ty check`
- [ ] `uv run --locked pytest`
- [ ] `TAIL_CHASING_LIVE_TESTS=1 uv run --locked pytest tests/live -m live`
- [ ] `uv run --locked vulture --config pyproject.toml`
