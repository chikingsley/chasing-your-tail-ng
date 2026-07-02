import json
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from tail_chasing import __version__
from tail_chasing.cli import app
from tail_chasing.ignore_lists import (
    IgnoreLists,
    build_ignore_lists_from_kismet,
    load_ignore_lists,
    write_ignore_lists,
)


def test_cli_version() -> None:
    result = CliRunner().invoke(app, ["--version"])

    assert result.exit_code == 0
    assert f"tail-chasing {__version__}" in result.stdout


def test_doctor_scaffold() -> None:
    result = CliRunner().invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "scaffold ready" in result.stdout


def test_load_ignore_lists_normalizes_and_filters_entries(tmp_path: Path) -> None:
    ignore_dir = tmp_path / "ignore_lists"
    ignore_dir.mkdir()
    (ignore_dir / "mac_list.json").write_text(
        json.dumps(["aa:bb:cc:dd:ee:ff", "AA-BB-CC-DD-EE-FF", "not-a-mac"]),
        encoding="utf-8",
    )
    (ignore_dir / "ssid_list.json").write_text(
        json.dumps(["Home", "", "Guest", "Too long " * 8]),
        encoding="utf-8",
    )

    ignore_lists = load_ignore_lists(ignore_dir)

    assert ignore_lists == IgnoreLists(
        macs=("AA:BB:CC:DD:EE:FF",),
        ssids=("Guest", "Home"),
    )


def test_build_ignore_lists_from_kismet_database(tmp_path: Path) -> None:
    database = tmp_path / "capture.kismet"
    _create_kismet_database(database)

    ignore_lists = build_ignore_lists_from_kismet(database)

    assert ignore_lists.macs == ("AA:BB:CC:DD:EE:FF", "BB:CC:DD:EE:FF:00")
    assert ignore_lists.ssids == ("Coffee WiFi", "Home")


def test_cli_ignore_lists_build_show_and_clear(tmp_path: Path) -> None:
    database = tmp_path / "capture.kismet"
    ignore_dir = tmp_path / "ignore_lists"
    _create_kismet_database(database)

    runner = CliRunner()
    build_result = runner.invoke(
        app,
        ["ignore-lists", "build", str(database), "--directory", str(ignore_dir)],
    )
    assert build_result.exit_code == 0
    assert "Wrote 2 MAC addresses" in build_result.stdout
    assert "Wrote 2 SSIDs" in build_result.stdout

    show_result = runner.invoke(
        app,
        ["ignore-lists", "show", "--directory", str(ignore_dir), "--json"],
    )
    assert show_result.exit_code == 0
    assert json.loads(show_result.stdout) == {
        "macs": ["AA:BB:CC:DD:EE:FF", "BB:CC:DD:EE:FF:00"],
        "ssids": ["Coffee WiFi", "Home"],
    }

    clear_result = runner.invoke(
        app,
        ["ignore-lists", "clear", "--directory", str(ignore_dir), "--yes"],
    )
    assert clear_result.exit_code == 0
    assert "Removed 2 ignore-list file(s)." in clear_result.stdout
    assert load_ignore_lists(ignore_dir) == IgnoreLists()


def test_cli_kismet_db_summary_reads_counts(tmp_path: Path) -> None:
    database = tmp_path / "capture.kismet"
    _create_kismet_database(database)

    result = CliRunner().invoke(app, ["kismet", "db-summary", str(database)])

    assert result.exit_code == 0
    assert f"Database: {database}" in result.stdout
    assert "devices: 4" in result.stdout
    assert "packets: 2" in result.stdout
    assert "datasources: 1" in result.stdout
    assert "messages: 1" in result.stdout


def test_cli_kismet_db_summary_can_emit_json(tmp_path: Path) -> None:
    database = tmp_path / "capture.kismet"
    _create_kismet_database(database)

    result = CliRunner().invoke(app, ["kismet", "db-summary", str(database), "--json"])

    assert result.exit_code == 0
    summary = json.loads(result.stdout)
    assert summary["path"] == str(database)
    assert summary["row_counts"]["devices"] == 4
    assert summary["row_counts"]["packets"] == 2
    assert summary["row_counts"]["datasources"] == 1
    assert summary["row_counts"]["messages"] == 1


def test_write_ignore_lists_uses_json_arrays(tmp_path: Path) -> None:
    paths = write_ignore_lists(
        IgnoreLists(macs=("AA:BB:CC:DD:EE:FF",), ssids=("Home",)),
        tmp_path / "ignore_lists",
    )

    assert json.loads(paths.macs.read_text(encoding="utf-8")) == ["AA:BB:CC:DD:EE:FF"]
    assert json.loads(paths.ssids.read_text(encoding="utf-8")) == ["Home"]


def _create_kismet_database(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE devices (devmac TEXT, device TEXT)")
        connection.execute("CREATE TABLE packets (packet BLOB)")
        connection.execute("CREATE TABLE datasources (definition TEXT)")
        connection.execute("CREATE TABLE messages (message TEXT)")
        connection.executemany(
            "INSERT INTO devices (devmac, device) VALUES (?, ?)",
            [
                (
                    "aa:bb:cc:dd:ee:ff",
                    json.dumps(
                        {
                            "dot11.device": {
                                "dot11.device.last_probed_ssid_record": {
                                    "dot11.probedssid.ssid": "Home",
                                },
                            },
                        },
                    ),
                ),
                (
                    "BB:CC:DD:EE:FF:00",
                    json.dumps({"nested": [{"dot11.probedssid.ssid": "Coffee WiFi"}]}),
                ),
                ("not-a-mac", json.dumps({"dot11.probedssid.ssid": ""})),
                ("AA-BB-CC-DD-EE-FF", "not json"),
            ],
        )
        connection.executemany("INSERT INTO packets (packet) VALUES (?)", [(b"1",), (b"2",)])
        connection.execute("INSERT INTO datasources (definition) VALUES (?)", ("wlo1",))
        connection.execute("INSERT INTO messages (message) VALUES (?)", ("started",))
