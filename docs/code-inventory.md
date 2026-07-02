# Code Inventory

This is the review map for the inherited files. Files under
`src/tail_chasing/inherited/` are not considered clean package modules yet; they are staged for
review and porting. The clean package surface remains `src/tail_chasing/cli.py` until each piece is
ported intentionally.

## Clean Package Modules

| Path | Status | Why |
| --- | --- | --- |
| `src/tail_chasing/cli.py` | keep | Typer entry point for package commands. Keep orchestration here and business logic in modules. |
| `src/tail_chasing/ignore_lists.py` | keep | Replaces inherited `exec()`/script/GUI ignore-list handling with JSON load/save/clear support and Kismet SQLite baseline generation. |

## Current Layout

| Path | Status | Why |
| --- | --- | --- |
| `src/tail_chasing/inherited/keep/kismet/secure_database.py` | keep, rework | Useful Kismet SQLite wrapper and time-window helper, but needs package imports, types, tests, and clearer offline-vs-live boundaries. |
| `src/tail_chasing/inherited/keep/kismet/secure_main_logic.py` | keep, rework | Contains the current monitoring/window logic; should become a service module behind the CLI rather than top-level script state. |
| `src/tail_chasing/inherited/keep/security/input_validation.py` | keep, rework | Useful validators, but current sanitization is broad and should be split by real input type. |
| `src/tail_chasing/inherited/keep/security/secure_credentials.py` | keep, rethink | Contains encrypted WiGLE credential storage; needs corrected return types, non-interactive behavior, and probably simpler environment-first paths. |
| `src/tail_chasing/inherited/keep/security/secure_ignore_loader.py` | keep, rework | Replaces old `exec()` ignore-list loading; current config still points at stale filenames, so this needs tests immediately. |
| `src/tail_chasing/inherited/keep/security/migrate_credentials.py` | keep as command candidate | Useful one-time migration behavior, but should become a CLI subcommand. |
| `src/tail_chasing/inherited/rework/runtime/chasing_your_tail.py` | rework | Main runtime loop has import-time config/log/file side effects. Port behavior into CLI-driven services, not as a script module. |
| `src/tail_chasing/inherited/rework/analysis/probe_analyzer.py` | rework | Useful log/WiGLE analysis, but has stale credential docs, noisy debug output, timestamp bugs, and should become a CLI subcommand. |
| `src/tail_chasing/inherited/rework/analysis/surveillance_analyzer.py` | rework | Orchestrates detector/GPS/KML, but contains result-key bugs and weak GPS correlation. |
| `src/tail_chasing/inherited/rework/analysis/surveillance_detector.py` | rework heavily | Core scoring/reporting ideas are reusable, but report language overclaims confidence and mixes detection with report generation. |
| `src/tail_chasing/inherited/rework/analysis/gps_tracker.py` | rework heavily | GPS session/KML ideas are useful, but KML generation is huge, string-heavy, and should be separated from GPS data modeling. |
| `src/tail_chasing/inherited/rework/analysis/create_ignore_list.py` | rework or fold | Duplicate ignore-list creation logic; likely becomes `tail-chasing ignore-lists build`. |
| `src/tail_chasing/inherited/replace/gui/cyt_gui.py` | replace | Tkinter GUI is orchestration around shell/script calls. Prefer future web UI or CLI-first workflows; Kismet already has its own web UI for capture/server state. |
| `src/tail_chasing/inherited/replace/shell/start_kismet_clean.sh` | replace | Hardcoded old path and interface; replace with `doctor`/docs/systemd or explicit Kismet commands. |
| `src/tail_chasing/inherited/replace/shell/start_gui.sh` | replace | Hardcoded old path and `python3`; replace with packaged CLI plus optional desktop autostart docs. |
| `src/tail_chasing/inherited/replace/shell/monitor.sh` | replace | Simple status loop; fold into `tail-chasing doctor` or `tail-chasing status`. |
| `src/tail_chasing/inherited/demo/blackhat_demo.py` | demo only | Demo script uses `shell=True` and marketing output. Keep as reference only while real CLI/report flows mature. |
| `src/tail_chasing/inherited/delete_candidates/ignore_list.py` | delete candidate | Legacy Python-format generated MAC baseline. Do not port as code or canonical data. |
| `src/tail_chasing/inherited/delete_candidates/ignore_list_ssid.py` | delete candidate | Legacy Python-format generated SSID baseline. Do not port as code or canonical data. |
| `src/tail_chasing/inherited/archive/requirements.txt` | archive | Replaced by `pyproject.toml` and `uv.lock`; kept temporarily for dependency provenance. |

## Data Inventory

| Path | Status | Why |
| --- | --- | --- |
| `ignore_lists/` | local generated data | Removed from tracked source and ignored by Git. Recreated by `tail-chasing ignore-lists build` when a local Kismet baseline is needed. |

## GUI Direction

Kismet already provides a web UI for its own server/capture state. The old Tkinter GUI mostly starts
scripts, checks process status, creates ignore lists, and opens analysis flows. That is a better fit
for:

- CLI commands first: `doctor`, `kismet status`, `ignore-lists build`, `analyze probes`,
  `analyze surveillance`.
- A later web UI only if we still want a graphical surface. This project is expected to run
  headless, so no Tkinter/desktop GUI path should be ported.

## Porting Order

1. Config loading and runtime path model.
2. Kismet offline SQLite reader.
3. Probe/log analysis.
4. Surveillance event model and scoring.
5. GPS/KML export split.
6. Runtime monitor loop.
7. Optional web UI after the CLI/service layer is useful.
