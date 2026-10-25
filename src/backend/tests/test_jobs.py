from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.modules.jobs import service as jobs
from app.modules.jobs.models import Job
from app.modules.plugins import registry as reg
from app.modules.plugins.contract import Kind, Movement

SECRETS = {"api_key": "key-1234567", "api_secret": "very-secret-value", "api_passphrase": "pass-x"}


def _bitget_with_key(authed) -> int:
    authed.post("/api/sources", json={"provider": "bitget", "label": "Bitget"})
    sid = authed.get("/api/sources").json()[0]["id"]
    authed.put(f"/api/sources/{sid}/credentials", json=SECRETS)
    return sid


def test_fetch_job_imports_and_sets_api_coverage(authed, db, monkeypatch):
    sid = _bitget_with_key(authed)
    seen = {}

    def fake_fetch(creds, since, progress):
        seen["since"], seen["creds"] = since, creds
        progress({"step": "fetch", "done": 1, "total": 1})
        yield Movement(
            timestamp=datetime(2025, 1, 1, tzinfo=UTC),
            kind=Kind.RECEIVE,
            incoming_asset="USDT",
            incoming_amount=Decimal(5),
        )

    monkeypatch.setattr(reg.registry().plugins["bitget_api"].module, "fetch", fake_fetch)
    job = authed.post("/api/jobs", json={"kind": "fetch", "source_id": sid}).json()
    assert authed.post("/api/jobs", json={"kind": "fetch", "source_id": sid}).status_code == 409
    assert jobs.run_one() is True
    done = authed.get("/api/jobs").json()[0]
    assert done["id"] == job["id"] and done["status"] == "done" and done["result"]["added"] == 1
    assert done["progress"]["done"] == 1
    assert seen["since"] is None and seen["creds"]["api_secret"] == "very-secret-value"

    # Second fetch is incremental: from the last data point minus the overlap (two weeks for
    # an exchange: a deposit pending for days is still asked for).
    authed.post("/api/jobs", json={"kind": "fetch", "source_id": sid})
    jobs.run_one()
    assert seen["since"] == datetime(2025, 1, 1, tzinfo=UTC) - timedelta(days=14)


def test_failed_job_is_visible_and_scrubbed(authed, monkeypatch):
    sid = _bitget_with_key(authed)

    def boom(creds, since, progress):
        raise RuntimeError(f"rejected secret {creds['api_secret']}")
        yield  # pragma: no cover

    monkeypatch.setattr(reg.registry().plugins["bitget_api"].module, "fetch", boom)
    authed.post("/api/jobs", json={"kind": "fetch", "source_id": sid})
    jobs.run_one()
    job = authed.get("/api/jobs").json()[0]
    assert job["status"] == "failed" and "very-secret-value" not in job["message"]
    assert jobs.run_one() is False  # queue empty, the next one would run


def test_fetch_without_credentials_fails_with_code(authed):
    authed.post("/api/sources", json={"provider": "bitget", "label": "Bitget"})
    sid = authed.get("/api/sources").json()[0]["id"]
    authed.post("/api/jobs", json={"kind": "fetch", "source_id": sid})
    jobs.run_one()
    assert authed.get("/api/jobs").json()[0]["message"] == "sources.no_credentials"


def test_interrupted_jobs_are_recovered(authed, db):
    db.add(Job(kind="backup", status="running", progress={}, result={}))
    db.commit()
    assert jobs.recover_interrupted(db) == 1
    assert db.scalars(select(Job)).one().status == "failed"
