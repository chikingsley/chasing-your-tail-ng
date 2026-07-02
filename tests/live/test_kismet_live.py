import os
import sqlite3
import time

import pytest

from tail_chasing.kismet_runtime import DEFAULT_RUNTIME_DIR, get_runtime_status

pytestmark = pytest.mark.live


def test_live_kismet_runtime_is_reachable() -> None:
    _require_live_tests()

    status = get_runtime_status(DEFAULT_RUNTIME_DIR)

    assert status.session_running
    assert status.http_reachable
    assert status.system_version
    assert status.system_devices is not None
    assert status.system_devices > 0
    assert status.latest_database is not None
    assert status.latest_database.path.exists()
    assert status.latest_database.row_counts["devices"] > 0
    assert status.latest_database.row_counts["packets"] > 0
    assert status.latest_database.row_counts["datasources"] > 0


def test_live_kismet_has_running_datasources() -> None:
    _require_live_tests()

    status = get_runtime_status(DEFAULT_RUNTIME_DIR)

    running_sources = [source for source in status.sources if source.running]
    assert running_sources
    assert any(source.name == "wlo1" and source.driver == "linuxwifi" for source in running_sources)
    assert any(source.packets > 0 for source in running_sources)


def test_live_kismet_packet_counter_advances() -> None:
    _require_live_tests()

    before = get_runtime_status(DEFAULT_RUNTIME_DIR)
    before_packets = sum(source.packets for source in before.sources)

    time.sleep(3)

    after = get_runtime_status(DEFAULT_RUNTIME_DIR)
    after_packets = sum(source.packets for source in after.sources)

    assert after_packets > before_packets


def test_live_kismet_database_version_is_supported() -> None:
    _require_live_tests()

    status = get_runtime_status(DEFAULT_RUNTIME_DIR)
    assert status.latest_database is not None

    uri = f"file:{status.latest_database.path.resolve()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        db_version = connection.execute('SELECT db_version FROM "KISMET"').fetchone()

    assert db_version is not None
    assert int(db_version[0]) >= 9


def _require_live_tests() -> None:
    if os.environ.get("TAIL_CHASING_LIVE_TESTS") != "1":
        pytest.skip("set TAIL_CHASING_LIVE_TESTS=1 to run live Kismet tests")
