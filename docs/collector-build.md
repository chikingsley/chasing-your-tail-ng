# Collector Build and Handoff

This is the deployable capture boundary for the first physical Tail Chasing box. It turns one Linux computer with attached radios into a reproducible Kismet collector whose profile, credentials, database, and logs stay under this repository.

It does not yet claim to identify a person or prove that two changing identifiers are one physical device. The current box records real Wi-Fi/Bluetooth evidence. Encounter recording, cluster labeling, recognition, and operator alerts are the next product slice built on those captures.

## Physical Box

The portable target is:

- one Raspberry Pi-class Linux computer;
- one external Wi-Fi adapter with an in-kernel Linux driver and working monitor mode, normally exposed as `wlan1`;
- one Linux Bluetooth HCI adapter, normally the built-in `hci0`;
- one battery or other stable power supply;
- optionally, one GNSS receiver managed by `gpsd`.

The external Wi-Fi radio matters. [Kismet requires monitor mode for passive Linux 802.11 capture](https://www.kismetwireless.net/docs/readme/datasources/wifi-linux/), and the built-in Raspberry Pi radio is not the assumed capture interface. [Kismet's Linux Bluetooth HCI datasource](https://kismetwireless.net/docs/readme/datasources/bluetooth-hci-bluetooth/) is an active scan of discoverable Classic/BLE devices; it is not passive Bluetooth packet interception.

## One-Time Pi Preparation

Install a current Kismet package, `tmux`, BlueZ, `iw`, Git, and `uv`. [Kismet's Linux installation guidance](https://www.kismetwireless.net/docs/readme/installing/linux/) explains why its capture helpers need elevated permissions; the operator account must belong to the `kismet` group, and the login session must be refreshed after that membership changes.

Clone this repository onto the Pi, stay at its root, and install the locked project environment:

```bash
uv sync --locked
```

Attach the radios and find their Linux names:

```bash
iw dev
bluetoothctl list
```

Create the collector profile. The expected first build uses the external Wi-Fi adapter as `wlan1`, built-in Bluetooth as `hci0`, bounded device/event logging, and no GPS until a receiver is attached:

```bash
uv run --locked tail-chasing collector setup \
  --name tail-chasing-portable \
  --mode portable \
  --wifi wlan1 \
  --bluetooth-interface hci0
```

This writes only repo-local state:

```text
runtime/collector/profile.json
runtime/kismet/kismet.conf
runtime/kismet/kismet_httpd.conf
runtime/kismet/home/
runtime/kismet/logs/
```

`runtime/` is ignored by Git. The HTTP password is generated once and kept with mode `0600`.

## Hardware Gate and Operation

Do not start the collector until its hardware gate passes:

```bash
uv run --locked tail-chasing collector doctor
```

The doctor checks the actual Kismet and tmux executables, current `kismet` group membership, every named Wi-Fi/Bluetooth interface, optional GPS daemon, and free runtime storage. Missing requirements return a nonzero exit code.

Operate the box with one profile:

```bash
uv run --locked tail-chasing collector start
uv run --locked tail-chasing collector status
uv run --locked tail-chasing collector stop
```

`status` reports the real tmux process, Kismet HTTP reachability, datasource packet counters, logging health, and the newest `.kismet` database. A configured profile is not proof of capture; a running datasource with advancing counters and a changing database is proof that the box is collecting.

## Optional GNSS

[Kismet GNSS records where the collector was when it saw a transmission](https://www.kismetwireless.net/docs/readme/gps/gps_intro/). It does not directly report the transmitter's location. After `gpsd` is installed and reading the attached receiver, recreate the profile with:

```bash
uv run --locked tail-chasing collector setup \
  --wifi wlan1 \
  --bluetooth-interface hci0 \
  --gps 'gpsd:host=localhost,port=2947'
```

## Optional iPhone Access over Tailscale

Keep the default loopback bind until remote access is needed. On a Pi already joined to the same tailnet as the iPhone, recreate the profile with the Pi's Tailscale IPv4 address:

```bash
uv run --locked tail-chasing collector setup \
  --wifi wlan1 \
  --bluetooth-interface hci0 \
  --http-bind-address "$(tailscale ip -4)"
```

Then open `http://<pi-tailscale-ip>:2501` from the iPhone and use the generated credentials in `runtime/kismet/kismet_httpd.conf`. Do not bind this unaudited collector UI to a public interface.

## First Physical Acceptance Run

The first useful live experiment is deliberately small:

1. Start the collector at a baseline location for five minutes.
2. Carry one owned phone through two or three named locations while recording the exact time boundaries.
3. Stop the collector and preserve the `.kismet` database plus the ground-truth notes.
4. Confirm advancing Wi-Fi/Bluetooth datasource counters and database writes.
5. Use that capture to implement and inspect encounter grouping, cluster labels, partial-cluster recognition, and alerts.

Until this run exists, the software is deployment-ready capture plumbing, not a validated tracking product.
