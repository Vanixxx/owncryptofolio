from datetime import UTC, datetime

from sqlalchemy import select

from app.modules.backup import schedule
from app.modules.jobs.models import Job

SECRETS = {"api_key": "key-1234567", "api_secret": "very-secret-value", "api_passphrase": "pass-x"}
ETH = "0x" + "cd" * 20
AFTER_SLOT = datetime(2026, 10, 3, 2, 30, tzinfo=UTC)  # 04:30 in Berlin


def _setup_sources(authed):
    authed.post("/api/sources", json={"provider": "bitget", "label": "Bitget"})  # with key
    authed.post("/api/sources", json={"provider": "kraken", "label": "Kraken"})  # file only
    authed.post("/api/sources", json={"provider": "mexc", "label": "MEXC"})  # api, no key
    wid = authed.post("/api/wallets", json={"name": "Tangem"}).json()["id"]
    authed.post(
        "/api/sources",
        json={"provider": "ethereum", "label": "Ethereum", "address": ETH, "wallet_id": wid},
    )
    by = {s["provider"]: s["id"] for s in authed.get("/api/sources").json()}
    authed.put(f"/api/sources/{by['bitget']}/credentials", json=SECRETS)
    return by


def test_daily_fetch_queues_only_fetchable_sources_once(authed, db):
    by = _setup_sources(authed)
    assert schedule.fetch_once(AFTER_SLOT) == 2  # bitget (key) + ethereum (address)
    queued = {j.source_id for j in db.scalars(select(Job).where(Job.trigger == "schedule"))}
    assert queued == {by["bitget"], by["ethereum"]}
    assert schedule.fetch_once(AFTER_SLOT) == 0  # same slot: nothing again


def test_auto_fetch_can_be_switched_off_per_source(authed):
    by = _setup_sources(authed)
    assert (
        authed.patch(f"/api/sources/{by['ethereum']}", json={"auto_fetch": False}).status_code
        == 204
    )
    assert {s["provider"]: s["auto_fetch"] for s in authed.get("/api/sources").json()}[
        "ethereum"
    ] is False
    assert schedule.fetch_once(AFTER_SLOT) == 1


def test_daily_fetch_can_be_disabled(authed):
    _setup_sources(authed)
    authed.patch("/api/settings", json={"fetch.enabled": False})
    assert schedule.fetch_once(AFTER_SLOT) == 0


def test_service_keys_are_stored_but_never_returned(authed):
    listing = {s["service"]: s for s in authed.get("/api/service-keys").json()}
    assert listing["etherscan"]["stored"] is False
    assert (
        authed.put("/api/service-keys/etherscan", json={"key": "SECRETKEY123456"}).status_code
        == 204
    )
    text = authed.get("/api/service-keys").text
    assert "SECRETKEY123456" not in text
    assert {s["service"]: s for s in authed.get("/api/service-keys").json()}["etherscan"]["stored"]
    assert authed.put("/api/service-keys/nope", json={"key": "x"}).status_code == 404
    assert authed.delete("/api/service-keys/etherscan").status_code == 204


def test_fetch_settings_validated(authed):
    assert authed.patch("/api/settings", json={"fetch.time": "4:00"}).status_code == 400
    assert authed.patch("/api/settings", json={"fetch.time": "05:15"}).status_code == 200


def test_failed_automatic_fetch_is_retried_on_passing_errors_only(authed, db):
    from datetime import timedelta

    by = _setup_sources(authed)
    eth, bitget = by["ethereum"], by["bitget"]
    t0 = AFTER_SLOT
    for sid, msg in ((eth, "ChainUnavailable: TimeoutError"), (bitget, "sources.key_rejected")):
        db.add(
            Job(
                kind="fetch",
                source_id=sid,
                trigger="schedule",
                status="failed",
                message=msg,
                progress={},
                result={},
                finished_at=t0,
            )
        )
    db.commit()
    assert schedule.retry_once(t0 + timedelta(minutes=10)) == 0  # not yet
    assert schedule.retry_once(t0 + timedelta(minutes=16)) == 1  # the timeout only
    again = db.scalars(select(Job).where(Job.trigger == "retry-1")).one()
    assert again.source_id == eth and again.status == "queued"
    assert schedule.retry_once(t0 + timedelta(minutes=20)) == 0  # a newer job exists
    # the third retry failing too is the end
    again.status, again.finished_at, again.trigger = "failed", t0, "retry-3"
    again.message = "TimeoutError"
    db.commit()
    assert schedule.retry_once(t0 + timedelta(minutes=40)) == 0
