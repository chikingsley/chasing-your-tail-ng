# Changelog

Historical record of completed work. Active work is tracked in `TODO.md`.

## [Unreleased]

### Added

- Added `TODO.md` as the active cleanup and modernization backlog for turning the inherited
  Chasing Your Tail scripts into the `tail-chasing` project.
- Added this `CHANGELOG.md` so completed work can move out of the active TODO before commits.
- Added a `uv_build` Python package scaffold for `tail-chasing` / `tail_chasing`.
- Added a Typer CLI skeleton with `tail-chasing --version` and `tail-chasing doctor`.
- Added initial pytest coverage for the CLI skeleton.
- Added `.gitignore` rules for Python caches, local environments, generated reports/logs, KML
  outputs, Kismet/SQLite captures, and encrypted credential files.
- Added `uv.lock` with runtime dependencies (`requests`, `cryptography`, `typer`) and dev tooling
  (`pytest`, `ruff`, `ty`, `vulture`).
- Added `docs/code-inventory.md` as the review map for inherited files.
- Added an archive note for inherited root docs and the stale legacy config.
- Added `tail_chasing.ignore_lists` for JSON ignore-list load/save/clear behavior and Kismet SQLite
  baseline generation.
- Added `tail-chasing ignore-lists build/show/clear` CLI commands.
- Added tests for ignore-list normalization, JSON persistence, Kismet database extraction, and CLI
  behavior.
- Added `tail_chasing.kismet_runtime` for repo-local Kismet config generation, tmux session
  start/stop, live HTTP status reads, datasource summaries, and SQLite database row counts.
- Added `tail-chasing kismet start/stop/status/db-summary` CLI commands.
- Added tests for Kismet database summary CLI output.
- Added an opt-in live Kismet pytest lane for the running tmux session, HTTP API reachability,
  datasource packet counters, and live KismetDB version checks.

### Changed

- Moved inherited Python and shell files under `src/tail_chasing/inherited/` by review status:
  `keep`, `rework`, `replace`, `demo`, `delete_candidates`, and `archive`.
- Excluded the inherited staging tree from clean scaffold lint/dead-code checks until files are
  ported into real package modules.
- Moved inherited root docs into `docs/archive/inherited-root/`.
- Archived root `config.json` as `docs/archive/inherited-root/config.legacy.json`.
- Simplified generated-output ignore rules now that empty placeholder directories are no longer
  tracked.
- Updated GUI direction to web-only for any future graphical surface; the inherited Tkinter desktop
  GUI remains replace-only.
- Replaced the inherited README with current `uv`, CLI, Kismet runtime, and project-layout docs.
- Scoped Vulture to current package code and tests while inherited scripts remain in quarantine.
- Added retry handling for transient SQLite locks when summarizing an actively written KismetDB.

### Removed

- Removed generated-output `gitkeep.keep` placeholders and their empty root directories.
- Removed inherited `LICENSE` and `cyt_ng_logo.png` as requested.
- Removed inherited root `ignore_lists/*.json` from tracked source; local generated ignore lists are
  now ignored by Git.
