# tail-chasing

Portable Kismet Wi-Fi and Bluetooth collector tooling.

The repository is intentionally paused at the hardware boundary. It contains the software needed to configure, check, start, inspect, and stop one repo-local collector. It does not claim device association, tracking, or alert accuracy before an owned-device field capture exists.

## When the Hardware Arrives

From the repository root on the Raspberry Pi-class collector:

```bash
uv sync --locked
uv run --locked tail-chasing collector setup \
  --name tail-chasing-portable \
  --wifi wlan1 \
  --bluetooth-interface hci0
uv run --locked tail-chasing collector doctor
uv run --locked tail-chasing collector start
uv run --locked tail-chasing collector status
```

Use the interface names actually reported by Linux. `doctor` refuses readiness when Kismet, its capture helpers, the `kismet` group membership, a configured radio, or required storage is missing. `status` reports the real session, Kismet HTTP state, datasource counters, logging health, and latest database.

Stop capture with:

```bash
uv run --locked tail-chasing collector stop
```

The full physical setup, optional GNSS and Tailscale/iPhone access, and first owned-device route are in [`docs/collector-build.md`](docs/collector-build.md).

## Repository Contents

- `src/tail_chasing/collector.py`: versioned collector profile and hardware-readiness checks.
- `src/tail_chasing/kismet_runtime.py`: repo-local Kismet configuration, process control, and status.
- `src/tail_chasing/cli.py`: `collector` and lower-level `kismet` commands.
- `config/collector.example.json`: portable example profile.
- `research/aircatch-arXiv-2602.07656v1.tar.gz`: retained AirCatch paper source only; it is not a reproduced implementation.
- `TODO.md`: the short list that begins when hardware is available.

Generated profiles, credentials, databases, logs, environments, and caches stay out of Git. The previous inherited implementation remains recoverable from repository history rather than occupying the active tree.

## Development Checks

```bash
uv run --locked ruff format --check src
uv run --locked ruff check src
uv run --locked ty check src
uv run --locked vulture --config pyproject.toml
```
