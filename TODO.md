# Tail Chasing TODO

Paused until the physical collector hardware is available.

- [ ] Assemble the Raspberry Pi-class computer, external monitor-mode Wi-Fi adapter, Bluetooth HCI adapter, power, and optional GNSS receiver described in `docs/collector-build.md`.
- [ ] Run `collector setup` with the Linux interface names from the real device, then make `collector doctor` pass.
- [ ] Start capture and confirm advancing datasource counters plus a changing `.kismet` database through `collector status`.
- [ ] Run the owned-phone baseline and multi-location route with exact ground-truth times.
- [ ] Build encounter grouping, named clusters, partial/full recognition, and alerts against that live capture rather than synthetic data.
