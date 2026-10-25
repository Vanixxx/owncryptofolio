"""Restoring from the web page (Vanixxx, 2026-10-21): one key brings everything back."""

import json
from datetime import UTC, datetime
from decimal import Decimal

from cryptography.fernet import Fernet

from app.core.keys import get_keys
from app.modules.backup import service
from app.modules.plugins.contract import Kind, Movement
from app.modules.raw import service as raw
from tests.conftest import PASSWORD, _truncate, make_source


def _row(db, s, day):
    raw.import_movements(db, s, "file", f"r{day}", [Movement(
        timestamp=datetime(2024, 1, day, tzinfo=UTC), kind=Kind.RECEIVE,
        incoming_asset="BTC", incoming_amount=Decimal("0.1"))])  # fmt: skip


def test_a_backup_carries_the_other_keys(db):
    run = service.run_backup(db, "manual", with_probe=False)
    kf = service.keys_file(service.backup_dir() / run.dump_file)
    assert kf.exists() and b"credentials_key" not in kf.read_bytes()  # encrypted
    inside = json.loads(service.decrypt(kf))
    assert inside["credentials_key"] == get_keys().credentials_key


def test_inspect_shows_what_is_inside_and_changes_nothing(authed, db):
    s = make_source(db)
    _row(db, s, 1)
    _row(db, s, 2)
    run = service.run_backup(db, "manual", with_probe=False)
    r = authed.post("/api/backups/inspect", json={"name": run.dump_file})
    assert r.status_code == 200, r.text
    info = r.json()
    assert (info["rows"], info["sources"], info["login"], info["keys"]) == (2, 1, True, True)
    assert info["first"].startswith("2024-01-01")
    wrong = authed.post(
        "/api/backups/inspect", json={"name": run.dump_file, "key": Fernet.generate_key().decode()}
    )
    assert wrong.status_code == 400 and wrong.json()["error"]["code"] == "backup.key_wrong"
    assert authed.post("/api/backups/inspect", json={"name": "../x.dump.enc"}).status_code == 400
    listed = authed.get("/api/backups/files").json()
    assert listed[0]["name"] == run.dump_file and listed[0]["keys"] is True


def test_restore_overwrites_after_a_backup_of_the_state_before(authed, db):
    s = make_source(db)
    _row(db, s, 1)
    run = service.run_backup(db, "manual", with_probe=False)
    _row(db, s, 2)  # made after the backup: gone after the restore
    assert authed.post("/api/backups/restore", json={"name": run.dump_file}).status_code == 400
    r = authed.post("/api/backups/restore", json={"name": run.dump_file, "confirm": True})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["keys_restored"] is True and out["safety"]
    from sqlalchemy import func, select

    from app.core.db import _session_factory
    from app.modules.raw.models import RawTransaction

    with _session_factory()() as fresh:
        n = fresh.scalar(select(func.count()).select_from(RawTransaction))
    assert n == 1
    # the state before is kept and listed: the way back
    runs = authed.get("/api/backups").json()["runs"]
    assert any(x["trigger"] == "before_restore" and x["dump_file"] == out["safety"] for x in runs)


def test_first_start_from_a_backup(client, db):
    # keys on the server, the database gone: the setup code guards the backups
    code = client.app.state.boot.setup_code = "123-456"
    client.post("/api/auth/setup", json={"code": code, "password": PASSWORD})
    s = make_source(db)
    _row(db, s, 1)
    run = service.run_backup(db, "manual", with_probe=False)
    key = get_keys().backup_key
    db.close()
    # a new, empty installation
    _truncate()
    client.app.state.setup_done = False
    client.cookies.clear()
    listed = client.post("/api/auth/setup/backups", json={"code": code}).json()
    assert run.dump_file in [x["name"] for x in listed]
    assert client.post("/api/auth/setup/backups", json={"code": "000-000"}).status_code == 400
    body = {"code": code, "name": run.dump_file, "key": key}
    assert client.post("/api/auth/setup/restore-inspect", json=body).json()["rows"] == 1
    r = client.post("/api/auth/setup/restore", json=body | {"confirm": True})
    assert r.status_code == 200, r.text
    # the old password works again, the data is back
    assert client.get("/api/auth/status").json()["setup_required"] is False
    assert client.post("/api/auth/login", json={"password": PASSWORD}).status_code == 204
    assert len(client.get("/api/sources").json()) == 1


def test_restoring_goes_through_a_copy_and_a_broken_dump_leaves_the_data(authed, db, monkeypatch):
    """Review 2026-10-24: the running database is never the restore target, and a dump that
    does not restore changes nothing."""
    import pytest
    from sqlalchemy import func, select

    from app.core.db import _session_factory
    from app.modules.raw.models import RawTransaction

    s = make_source(db)
    _row(db, s, 1)
    run = service.run_backup(db, "manual", with_probe=False)
    live = service._url().database
    targets = []
    real = service.restore
    monkeypatch.setattr(
        service, "restore", lambda path, name, **kw: (targets.append(name), real(path, name, **kw))
    )
    r = authed.post("/api/backups/restore", json={"name": run.dump_file, "confirm": True})
    assert r.status_code == 200, r.text
    assert live not in targets and any("_restore_" in t for t in targets)

    broken = service.backup_dir() / "broken.dump.enc"
    broken.write_bytes(Fernet(get_keys().backup_key).encrypt(b"not a dump"))
    with _session_factory()() as fresh:
        before = fresh.scalar(select(func.count()).select_from(RawTransaction))
        with pytest.raises(service.BackupError):
            service.restore_live(fresh, broken, None, safety=False)
    with _session_factory()() as fresh:
        assert fresh.scalar(select(func.count()).select_from(RawTransaction)) == before == 1


def test_the_backup_before_a_foreign_restore_is_locked_again_with_the_new_key(
    tmp_path, monkeypatch
):
    old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    monkeypatch.setattr(service, "backup_dir", lambda: tmp_path)
    for name in ("a.dump.enc", "a.raw.jsonl.gz.enc", "a.keys.enc"):
        (tmp_path / name).write_bytes(Fernet(old).encrypt(name.encode()))
    service._relock({"dump_file": "a.dump.enc", "export_file": "a.raw.jsonl.gz.enc"}, old, new)
    for name in ("a.dump.enc", "a.raw.jsonl.gz.enc", "a.keys.enc"):
        assert Fernet(new).decrypt((tmp_path / name).read_bytes()) == name.encode()


def test_only_data_objects_come_back_from_a_dump():
    keep = [
        "215; 1259 16390 TABLE public raw_transaction ocf",
        "3420; 0 16390 TABLE DATA public raw_transaction ocf",
        "3300; 2606 16400 CONSTRAINT public raw_transaction raw_transaction_pkey ocf",
        "3301; 2606 16401 FK CONSTRAINT public raw_transaction fk ocf",
        "3302; 1259 16402 INDEX public ix_raw_run ocf",
        "3303; 0 0 SEQUENCE SET public raw_transaction_id_seq ocf",
    ]
    drop = [
        "220; 1255 16500 FUNCTION public evil() ocf",
        "221; 2620 16501 TRIGGER public raw_transaction t ocf",
        "222; 3079 16502 EXTENSION - plpython3u",
        "6; 2615 2200 SCHEMA - public pg_database_owner",
        "; Archive created at 2026-10-24",
    ]
    assert all(service._allowed(x) for x in keep)
    assert not any(service._allowed(x) for x in drop)


def test_uploads_get_names_of_their_own_and_arrive_whole(authed, db):
    run = service.run_backup(db, "manual", with_probe=False)
    dump = service.backup_dir() / run.dump_file
    files = [
        ("files", ("other.dump.enc", dump.read_bytes())),
        ("files", ("other.keys.enc", service.keys_file(dump).read_bytes())),
    ]
    a = authed.post("/api/backups/upload", files=files).json()["name"]
    b = authed.post("/api/backups/upload", files=files).json()["name"]
    assert a != b  # two in one second no longer overwrite each other
    for name in (a, b):
        assert (service.backup_dir() / name).exists()
        assert service.keys_file(service.backup_dir() / name).exists()
    assert not list(service.backup_dir().glob("*.part"))
