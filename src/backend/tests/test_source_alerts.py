"""Warnings that keep history from being lost unnoticed: a key the exchange refuses, a
fetch that fails, a look-back running out (Vanixxx, 2026-10-05). No expiry dates: exchanges
do not report them, and nobody keeps them up to date by hand."""

from datetime import UTC, datetime, timedelta


def _mexc(authed, db):
    from app.modules.sources.models import Source

    authed.post("/api/sources", json={"provider": "mexc", "label": "MEXC"})
    src = db.query(Source).one()
    r = authed.put(f"/api/sources/{src.id}/credentials", json={"api_key": "k", "api_secret": "s"})
    assert r.status_code == 204
    return src


def _kinds(authed):
    return {a["kind"]: a for a in authed.get("/api/sources/alerts").json()}


def test_a_refused_key_warns_once_a_fetch_fails_on_it(authed, db):
    from app.modules.jobs.models import Job
    from app.modules.sources.service import KEY_REJECTED

    src = _mexc(authed, db)
    assert _kinds(authed) == {}  # a fresh key: nothing to say
    db.add(Job(kind="fetch", source_id=src.id, status="failed", message=KEY_REJECTED))
    db.commit()
    assert set(_kinds(authed)) == {"key_rejected"}


def test_failing_fetch_and_look_back_running_out(authed, db):
    from app.modules.jobs.models import Job
    from app.modules.raw.models import ImportRun

    src = _mexc(authed, db)
    # last good API fetch 80 days ago: MEXC reaches back 89 days, 9 left
    db.add(
        ImportRun(
            source_id=src.id,
            channel="api",
            label="API",
            status="done",
            created_at=datetime.now(UTC) - timedelta(days=80),
        )
    )
    db.add(Job(kind="fetch", source_id=src.id, status="failed", message="mexc 503"))
    db.commit()
    kinds = _kinds(authed)
    assert kinds["history_at_risk"]["days"] in (8, 9, 10)
    assert kinds["fetch_failed"]["message"] == "mexc 503"


def test_ccxt_refusal_is_recorded_as_key_rejected(authed, db, monkeypatch):
    import pytest

    from app.modules.jobs import fetch
    from app.modules.jobs.models import Job
    from app.modules.plugins.registry import registry
    from app.modules.sources.service import KEY_REJECTED

    src = _mexc(authed, db)

    class AuthenticationError(Exception):  # the name is what counts, as with ccxt
        pass

    def refuse(*a, **k):
        raise AuthenticationError("mexc {'code': 10072, 'msg': 'Api key info invalid'}")

    monkeypatch.setattr(registry().find("mexc", fetch.Channel.API).module, "fetch", refuse)
    job = Job(kind="fetch", source_id=src.id, status="running")
    db.add(job)
    db.commit()
    with pytest.raises(RuntimeError, match=KEY_REJECTED):
        fetch.run_fetch(db, job, lambda p: None)
