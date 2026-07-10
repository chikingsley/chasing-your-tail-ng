# Changelog

## [Unreleased]

### Added

- Added a versioned collector profile and `tail-chasing collector setup/show/doctor/start/status/stop` commands.
- Added a real readiness gate for Kismet, its Wi-Fi/Bluetooth capture helpers, `kismet` group membership, configured radio interfaces, optional GPSD, and runtime storage.
- Added repo-local Kismet configuration, generated credentials, bounded event logging, runtime status, datasource counters, database health, and optional Tailscale/GNSS configuration.
- Added the physical collector handoff in `docs/collector-build.md` and a portable example profile in `config/collector.example.json`.
- Retained the original AirCatch arXiv source bundle as a non-executable future research reference.

### Removed

- Removed the inherited application copy from the active tree; the original implementation remains available in Git history.
- Removed the disconnected dashboard, StudentLife importer, synthetic evidence/governance/provenance models, recurrence experiment, prior-art runners, and their tests.
- Removed obsolete documentation and planning slices that no longer describe the retained collector.
- Removed the local 13 GB runtime/database tree, project virtual environment, and generated caches before the cleanup commit.
- Reduced runtime dependencies to Pydantic, Requests, and Typer, and retained only Ruff, ty, and Vulture as development tools.
