def test_status(authed):
    s = authed.get("/api/system/status").json()
    assert s["database"]["connected"] is True
    assert s["database"]["server_version"].startswith("18")
    assert s["migration"]["up_to_date"] is True
    assert s["keys"] == {"credentials_key": "file", "session_key": "file", "backup_key": "file"}


def test_backup_key_needs_session(client):
    assert client.get("/api/system/backup-key").status_code == 401


def test_backup_key(authed):
    assert (
        authed.get("/api/system/backup-key").json()["backup_key"]
        == authed.app.state.boot.keys.backup_key
    )


def test_unknown_api_path_is_404_not_401_after_login(authed):
    assert authed.get("/api/does-not-exist").status_code == 404


def test_operations_at_a_glance(authed):
    """The system page says whether backups, fetches and prices run (M8, 2026-10-12)."""
    ops = authed.get("/api/system/status").json()["operations"]
    assert set(ops) == {"backup", "fetch", "prices", "fine", "tools", "disk"}
    assert ops["backup"]["next_at"] and ops["fetch"]["next_at"] and ops["prices"]["next_at"]
    assert ops["tools"]["server"] >= 13 and ops["tools"]["ok"] in (True, False)
    assert ops["disk"]["data"]["free"] > 0
    # what owncryptofolio itself takes: its folders and the database (2026-10-12)
    assert ops["disk"]["data"]["used"] >= 0 and ops["disk"]["database"] > 0


def test_next_slot_is_today_or_tomorrow():
    from datetime import UTC, datetime

    from app.modules.system.service import next_slot

    now = datetime(2026, 10, 12, 1, 30, tzinfo=UTC)  # 03:30 in Berlin
    assert next_slot("04:00", "Europe/Berlin", now).isoformat() == "2026-10-12T04:00:00+02:00"
    assert next_slot("03:00", "Europe/Berlin", now).isoformat() == "2026-10-13T03:00:00+02:00"
