from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select, update

from app.modules.plugins.contract import Kind, Movement
from app.modules.raw import guard
from app.modules.raw import service as raw
from app.modules.raw.guard import RawLayerProtected, raw_unlocked
from app.modules.raw.models import ImportRun, RawTransaction
from tests.conftest import make_source

T = datetime(2024, 3, 1, tzinfo=UTC)


def moves(n=3, start=0):
    return [
        Movement(
            timestamp=T + timedelta(hours=i),
            kind=Kind.RECEIVE,
            incoming_asset="BTC",
            incoming_amount=Decimal(i + 1),
        )
        for i in range(start, start + n)
    ]


def count(db):
    return db.scalar(select(func.count()).select_from(RawTransaction))


def test_import_then_reimport_adds_nothing(db):
    s = make_source(db)
    first = raw.import_movements(db, s, "file", "a.zip", moves())
    assert (first.read, first.added, first.duplicates) == (3, 3, 0)
    second = raw.import_movements(db, s, "file", "a.zip", moves())
    assert (second.added, second.duplicates) == (0, 3)
    assert count(db) == 3
    assert (first.data_from, first.data_to) == (T, T + timedelta(hours=2))


def test_same_movement_through_another_channel_is_a_separate_row(db):
    s = make_source(db)
    raw.import_movements(db, s, "file", "a", moves(1))
    raw.import_movements(db, s, "api", "API", moves(1))
    assert count(db) == 2


def test_invalid_rows_are_rejected_and_reported(db):
    s = make_source(db)
    bad = Movement(timestamp=T, kind=Kind.TRADE, incoming_asset="BTC", incoming_amount=Decimal(1))
    run = raw.import_movements(db, s, "file", "a", [*moves(1), bad])
    assert (run.added, run.rejected) == (1, 1)
    assert "both sides" in run.problems[0]


def test_failing_reader_leaves_no_run(db):
    s = make_source(db)

    def broken():
        yield from moves(1)
        raise ValueError("unreadable")

    with pytest.raises(ValueError):
        raw.import_movements(db, s, "file", "a", broken())
    assert db.scalar(select(func.count()).select_from(ImportRun)) == 0
    assert count(db) == 0


def test_revert_only_latest_run(db):
    s = make_source(db)
    r1 = raw.import_movements(db, s, "file", "a", moves(2))
    r2 = raw.import_movements(db, s, "file", "b", moves(2, start=5))
    other = raw.import_movements(db, s, "api", "API", moves(1))
    with pytest.raises(Exception) as exc:
        raw.revert(db, r1.id)
    assert exc.value.code == "imports.not_latest_run"
    assert raw.revert(db, r2.id) == {"rows": 2}
    assert count(db) == 3  # run 1 and the api row stay
    assert raw.revert(db, r1.id) == {"rows": 2}
    assert db.get(ImportRun, other.id) is not None


@pytest.fixture
def production(monkeypatch):
    """Make the guard believe it runs against a production database."""
    monkeypatch.setattr(guard, "is_test_database", lambda session: False)


def test_guard_refuses_delete_update_and_bulk(db, production):
    s = make_source(db)
    raw.import_movements(db, s, "file", "a", moves(1))
    row = db.scalars(select(RawTransaction)).one()
    db.delete(row)
    with pytest.raises(RawLayerProtected):
        db.flush()
    db.rollback()
    row = db.scalars(select(RawTransaction)).one()
    row.comment = "changed"
    with pytest.raises(RawLayerProtected):
        db.flush()
    db.rollback()
    with pytest.raises(RawLayerProtected):
        db.execute(delete(RawTransaction))
    db.rollback()
    with pytest.raises(RawLayerProtected):
        db.execute(update(RawTransaction).values(comment="x"))
    db.rollback()
    assert count(db) == 1


def test_guard_allows_revert_and_unlocked_maintenance(db, production):
    s = make_source(db)
    run = raw.import_movements(db, s, "file", "a", moves(2))
    assert raw.revert(db, run.id) == {"rows": 2}
    raw.import_movements(db, s, "file", "a", moves(1))
    with raw_unlocked("test maintenance"):
        db.execute(delete(RawTransaction))
    db.commit()
    assert count(db) == 0


def test_unlock_needs_a_reason():
    with pytest.raises(ValueError), raw_unlocked(" "):
        pass


def test_coverage_comes_from_delivered_api_data_per_market(db):
    s = make_source(db)
    raw.import_movements(db, s, "api", "API", moves(1, start=5))  # spot API from T+5h
    cov = raw.api_coverage(db)
    start = T + timedelta(hours=5)
    assert cov == {(s.id, "spot"): start}
    assert raw.covered_by_api(cov, s.id, "spot", "file", start)
    assert not raw.covered_by_api(cov, s.id, "spot", "file", start - timedelta(seconds=1))
    assert not raw.covered_by_api(cov, s.id, "spot", "api", start)
    # The API delivered no futures: file futures rows always count.
    assert not raw.covered_by_api(cov, s.id, "futures", "file", start + timedelta(days=1))


def test_coverage_boundary_ignores_milliseconds(db):
    s = make_source(db)
    api_start = T + timedelta(milliseconds=150)
    raw.import_movements(
        db,
        s,
        "api",
        "API",
        [
            Movement(
                timestamp=api_start,
                kind=Kind.RECEIVE,
                incoming_asset="BNB",
                incoming_amount=Decimal(1),
            )
        ],
    )
    cov = raw.api_coverage(db)
    # The same event from a file has whole seconds only.
    assert raw.covered_by_api(cov, s.id, "spot", "file", T)


def test_event_overlap_matches_by_second_asset_amount(db, monkeypatch):
    """Coinbase mode: only file rows the API also knows are superseded."""
    s = make_source(db)
    monkeypatch.setattr(raw.Overlap, "__init__", lambda self, session, ids=None: None)
    o = raw.Overlap(db)
    o.mode = {s.id: "event"}
    o.period = {}
    o.events = {s.id: raw.event_keys(T, [("SOL", Decimal("1.5")), ("EUR", Decimal("180"))])}
    # same second, crypto side matches although the fiat side differs (USD in the file)
    assert o.covered(
        s.id, "spot", "file", T, [("SOL", Decimal("1.50")), ("USD", Decimal("203.76"))]
    )
    # a file-only staking reward stays
    assert not o.covered(s.id, "spot", "file", T, [("ETH", Decimal("0.01"))])
    assert not o.covered(s.id, "spot", "file", T + timedelta(seconds=1), [("SOL", Decimal("1.5"))])
