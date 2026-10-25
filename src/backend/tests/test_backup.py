from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.modules.backup import schedule, service
from app.modules.backup.models import BackupRun
from app.modules.plugins.contract import Kind, Movement
from app.modules.raw import service as raw
from tests.conftest import make_source


def test_backup_with_probe_and_export_roundtrip(db):
    s = make_source(db)
    raw.import_movements(
        db,
        s,
        "file",
        "a",
        [
            Movement(
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                kind=Kind.RECEIVE,
                incoming_asset="BTC",
                incoming_amount=Decimal("0.123456789012345678"),
            )
        ],
    )
    run = service.run_backup(db, "manual")
    assert run.status == "done", run.message
    assert run.probe_ok is True and run.rows == 1
    dump = service.backup_dir() / run.dump_file
    assert b"PGDMP" not in dump.read_bytes()  # encrypted, not a plain pg_dump
    (line,) = service.read_export(service.backup_dir() / run.export_file)
    assert line["incoming_amount"] == "0.123456789012345678"  # string, never float
    assert line["source"]["provider"] == "bitget"


def test_retention_keeps_daily_and_monthly():
    def r(i, days_ago):
        return BackupRun(
            id=i,
            status="done",
            deleted=False,
            started_at=datetime(2026, 10, 1, tzinfo=UTC) - timedelta(days=days_ago),
        )

    runs = [r(i, d) for i, d in enumerate([0, 0, 1, 2, 3, 40, 70, 400], start=1)]
    keep = service.keep_ids(runs, keep_daily=2, keep_monthly=3)
    # newest per day for 2 days: 1 (Oct 1), 3 (Sep 30);
    # newest per month for 3 months: 1 (Oct), 3 (Sep), 6 (Aug). July (7) and older go.
    assert keep == {1, 3, 6}


def test_schedule_due():
    tz = "Europe/Berlin"
    before = datetime(2026, 10, 3, 0, 59, tzinfo=UTC)  # 02:59 local
    after = datetime(2026, 10, 3, 1, 1, tzinfo=UTC)  # 03:01 local
    assert not schedule.due(before, "03:00", tz, None)
    assert schedule.due(after, "03:00", tz, None)
    assert not schedule.due(after, "03:00", tz, after - timedelta(minutes=1))
    assert schedule.due(after, "03:00", tz, after - timedelta(days=1))


def test_backup_job_via_api(authed):
    from app.modules.jobs import service as jobs

    assert authed.post("/api/jobs", json={"kind": "backup"}).status_code == 201
    jobs.run_one()
    assert authed.get("/api/jobs").json()[0]["status"] == "done"
    runs = authed.get("/api/backups").json()["runs"]
    assert runs[0]["probe_ok"] is True


def test_an_unmounted_backup_folder_in_the_container_is_reported(env, monkeypatch):
    from pathlib import Path

    from app.core.config import get_settings
    from app.modules.backup import service

    settings = get_settings()
    monkeypatch.setattr(settings, "backup_dir", Path("/backups"))
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(service.os.path, "ismount", lambda p: False)
    assert service.unmounted() is True
    monkeypatch.setattr(service.os.path, "ismount", lambda p: True)
    assert service.unmounted() is False
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(service.os.path, "ismount", lambda p: False)
    assert service.unmounted() is False  # development: any folder is fine
