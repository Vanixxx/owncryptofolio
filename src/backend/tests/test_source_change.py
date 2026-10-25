"""A source delivers a row again with other values (Vanixxx, 2026-10-23): held back, decided."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select

from app.modules.plugins.contract import Kind, Movement
from app.modules.raw import service as raw
from app.modules.raw.models import RawTransaction, current
from tests.conftest import make_source

T = datetime(2025, 3, 1, 12, tzinfo=UTC)


def buy(qty: str, ext: str = "order-1", at: datetime = T) -> Movement:
    return Movement(
        timestamp=at,
        kind=Kind.TRADE,
        incoming_asset="BTC",
        incoming_amount=Decimal(qty),
        outgoing_asset="EUR",
        outgoing_amount=Decimal("100"),
        external_id=ext,
    )


def _current(db) -> list[RawTransaction]:
    return list(db.scalars(select(RawTransaction).where(current())))


def test_a_changed_row_is_held_back_not_doubled(client, db):
    s = make_source(db)
    raw.import_movements(db, s, "api", "API", [buy("0.002")])
    run = raw.import_movements(db, s, "api", "API", [buy("0.0021")])
    assert (run.added, run.changed) == (0, 1)
    assert [r.incoming_amount for r in _current(db)] == [Decimal("0.002")]
    (c,) = raw.changes(db)
    assert c["old"]["incoming"] == ["BTC", "0.002"] and c["new"]["incoming"] == ["BTC", "0.0021"]
    # the same change again: not a second notice
    again = raw.import_movements(db, s, "api", "API", [buy("0.0021")])
    assert again.changed == 0 and len(raw.changes(db)) == 1


def test_take_replaces_the_old_row_which_stays_stored(authed, db):
    s = make_source(db)
    raw.import_movements(db, s, "api", "API", [buy("0.002")])
    raw.import_movements(db, s, "api", "API", [buy("0.0021")])
    (c,) = authed.get("/api/raw/changes").json()
    assert authed.post(f"/api/raw/changes/{c['id']}/take").status_code == 204
    assert [r.incoming_amount for r in _current(db)] == [Decimal("0.0021")]
    assert db.scalar(select(func.count()).select_from(RawTransaction)) == 2  # raw first
    assert authed.get("/api/raw/changes").json() == []
    # the source keeps delivering the new values: a plain duplicate now
    assert raw.import_movements(db, s, "api", "API", [buy("0.0021")]).duplicates == 1


def test_keep_leaves_the_old_row_and_asks_no_more(authed, db):
    s = make_source(db)
    raw.import_movements(db, s, "api", "API", [buy("0.002")])
    raw.import_movements(db, s, "api", "API", [buy("0.0021")])
    (c,) = authed.get("/api/raw/changes").json()
    assert authed.post(f"/api/raw/changes/{c['id']}/keep").status_code == 204
    assert authed.post(f"/api/raw/changes/{c['id']}/keep").status_code == 409
    run = raw.import_movements(db, s, "api", "API", [buy("0.0021")])
    assert (run.added, run.changed) == (0, 0)
    assert [r.incoming_amount for r in _current(db)] == [Decimal("0.002")]


def test_partial_fills_and_rows_without_id_are_added_as_before(client, db):
    s = make_source(db)
    raw.import_movements(db, s, "api", "API", [buy("0.002")])
    # a second fill of the same order, old one delivered too: a new row
    run = raw.import_movements(db, s, "api", "API", [buy("0.002"), buy("0.001")])
    assert (run.added, run.changed) == (1, 0)
    # two new rows for the one key: no guess, both added
    t = make_source(db, label="Other")
    raw.import_movements(db, t, "api", "API", [buy("0.5")])
    run = raw.import_movements(db, t, "api", "API", [buy("0.4"), buy("0.3")])
    assert (run.added, run.changed) == (2, 0)
    # without an id nothing can be recognised
    u = make_source(db, label="Third")
    raw.import_movements(db, u, "file", "f", [buy("1", ext=None)])
    assert raw.import_movements(db, u, "file", "f", [buy("2", ext=None)]).added == 1


def test_revert_of_the_run_brings_the_old_row_back(authed, db):
    s = make_source(db)
    raw.import_movements(db, s, "api", "API", [buy("0.002")])
    run = raw.import_movements(db, s, "api", "API", [buy("0.0021")])
    (c,) = raw.changes(db)
    raw.decide_change(db, c["id"], take=True)
    raw.revert(db, run.id)
    assert [r.incoming_amount for r in _current(db)] == [Decimal("0.002")]
    assert raw.changes(db) == []
