"""Correct, hide, restore any row with history (ADR 0037)."""

from datetime import UTC, datetime
from decimal import Decimal

from app.modules.plugins.contract import Kind, Movement

CARD = Movement(
    timestamp=datetime(2024, 2, 13, 19, 20, 51, tzinfo=UTC),
    kind=Kind.OTHER,
    incoming_asset="BNB",
    incoming_amount=Decimal("0.5142"),
    comment="Buy with card",
    raw={"replaces": 1, "Type": "Buy with card"},  # an exchange's own key, never a link
)
FIX = {
    "kind": "trade",
    "time": "2024-02-13T20:20:51",
    "incoming_asset": "BNB",
    "incoming_amount": "0.5142",
    "outgoing_asset": "EUR",
    "outgoing_amount": "150",
}


def bitget_with_file_row(authed, db):
    from app.modules.raw import service as raw
    from app.modules.sources.models import Source

    authed.post("/api/sources", json={"provider": "bitget", "label": "Bitget"})
    source = db.query(Source).filter_by(provider="bitget").one()
    run = raw.import_movements(db, source, "file", "export.zip", [CARD])
    rows = authed.get("/api/raw", params={"source_id": source.id}).json()["rows"]
    return source, run, rows[0]["id"]


def listed(authed, sid, **params):
    return authed.get("/api/raw", params={"source_id": sid, **params}).json()["rows"]


def test_correcting_a_file_row_keeps_the_original_and_shows_the_correction(authed, db):
    source, _, original = bitget_with_file_row(authed, db)
    fixed = authed.put(f"/api/raw/{original}", json=FIX).json()
    assert fixed["corrects"] == original and fixed["edited"]
    rows = listed(authed, source.id)
    assert [(r["id"], r["kind"], r["channel"]) for r in rows] == [(fixed["id"], "trade", "manual")]
    states = {r["id"]: r["state"] for r in listed(authed, source.id, show_hidden="true")}
    assert states == {fixed["id"]: "current"}  # a replaced version is no row of its own
    hist = authed.get(f"/api/raw/{fixed['id']}/history").json()
    assert [(h["id"], h["channel"], h["state"]) for h in hist] == [
        (original, "file", "replaced"),
        (fixed["id"], "manual", "current"),
    ]
    assert authed.get(f"/api/raw/{original}/history").json() == hist


def test_a_new_fetch_does_not_bring_the_original_back(authed, db):
    from app.modules.raw import service as raw

    source, _, original = bitget_with_file_row(authed, db)
    authed.put(f"/api/raw/{original}", json=FIX)
    again = raw.import_movements(db, source, "file", "export again.zip", [CARD])
    assert (again.added, again.duplicates) == (0, 1)
    assert len(listed(authed, source.id)) == 1


def test_revert_is_refused_while_a_row_is_corrected_and_restore_brings_the_original_back(
    authed, db
):
    source, run, original = bitget_with_file_row(authed, db)
    fixed = authed.put(f"/api/raw/{original}", json=FIX).json()
    r = authed.delete(f"/api/import-runs/{run.id}")
    assert r.status_code == 409 and r.json()["error"] == {
        "code": "imports.has_corrections",
        "params": {"count": 1},
    }
    assert authed.post(f"/api/raw/{original}/restore").status_code == 204
    assert [r["id"] for r in listed(authed, source.id)] == [original]
    states = {r["id"]: r["state"] for r in listed(authed, source.id, show_hidden="true")}
    assert states == {original: "current"}  # the discarded correction is no row of its own
    hist = {h["id"]: h["state"] for h in authed.get(f"/api/raw/{original}/history").json()}
    assert hist == {original: "current", fixed["id"]: "replaced"}
    assert listed(authed, source.id)[0]["edited"]  # the original now has a history
    assert authed.delete(f"/api/import-runs/{run.id}").status_code == 200
    assert [r["state"] for r in listed(authed, source.id, show_hidden="true")] == ["hidden"]


def test_hide_and_restore(authed, db):
    source, _, original = bitget_with_file_row(authed, db)
    assert authed.post(f"/api/raw/{original}/hide").status_code == 204
    assert listed(authed, source.id) == []
    assert listed(authed, source.id, show_hidden="true")[0]["state"] == "hidden"
    again = authed.post(f"/api/raw/{original}/hide")
    assert again.status_code == 409 and again.json()["error"]["code"] == "manual.already_changed"
    assert authed.post(f"/api/raw/{original}/restore").status_code == 204
    assert listed(authed, source.id)[0]["state"] == "current"
    r = authed.post(f"/api/raw/{original}/restore")
    assert r.status_code == 409 and r.json()["error"]["code"] == "manual.not_changed"


def test_editing_a_correction_keeps_the_link_and_restoring_a_middle_version(authed, db):
    source, _, original = bitget_with_file_row(authed, db)
    first = authed.put(f"/api/raw/{original}", json=FIX).json()
    second = authed.put(f"/api/raw/{first['id']}", json={**FIX, "outgoing_amount": "149.5"}).json()
    assert second["corrects"] == original
    hist = authed.get(f"/api/raw/{original}/history").json()
    assert [h["state"] for h in hist] == ["replaced", "replaced", "current"]
    authed.post(f"/api/raw/{first['id']}/restore")
    current = listed(authed, source.id)
    assert [r["id"] for r in current] == [first["id"]]  # never two valid versions
    hist = {h["id"]: h["state"] for h in authed.get(f"/api/raw/{original}/history").json()}
    assert hist == {original: "replaced", first["id"]: "current", second["id"]: "replaced"}


def test_last_fetch_per_source(authed, db):
    from app.modules.raw import service as raw

    source, _, _ = bitget_with_file_row(authed, db)
    entry = next(s for s in authed.get("/api/sources").json() if s["id"] == source.id)
    assert entry["last_fetch"] is None  # a file is no fetch
    raw.import_movements(db, source, "api", "API", [])
    entry = next(s for s in authed.get("/api/sources").json() if s["id"] == source.id)
    assert entry["last_fetch"] is not None
