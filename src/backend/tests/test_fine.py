"""Fine prices and fine portfolio values (ADR 0044)."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.modules.plugins.contract import Kind, Movement

D = Decimal


def test_grid_is_hourly_then_five_minutes():
    from app.modules.portfolio.fine import grid

    now = datetime(2026, 10, 15, 12, 3, tzinfo=UTC)
    g = grid(now, now - timedelta(days=200))
    steps = [s for _, s in g]
    assert steps.count("5m") == 31 * 24 * 12 + 1 and steps[0] == "1h"
    assert g[-1][0] == datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
    assert all(g[i][0] < g[i + 1][0] for i in range(len(g) - 1))


def test_values_are_holding_times_fine_price_from_the_buy_on(authed, db, monkeypatch):
    from app.modules.portfolio import fine as pfine
    from app.modules.portfolio.models import PortfolioTick
    from app.modules.prices.models import PriceDaily, PriceFine, PriceSource
    from app.modules.raw import service as raw
    from app.modules.sources.models import Source

    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    bought = now - timedelta(hours=10)
    authed.post("/api/sources", json={"provider": "manual", "label": "Exchange"})
    src = db.query(Source).one()
    db.add(PriceSource(asset="BTC", rank=1, source="binance", ticker="BTCUSDT", quote="EUR"))
    for i in range(3):
        db.add(
            PriceDaily(
                asset="BTC",
                day=date.today() - timedelta(days=i),
                quote="EUR",
                close=D(50000),
                source="t",
            )
        )
    for h in range(24):
        at = now - timedelta(hours=h)
        db.add(
            PriceFine(asset="BTC", step="5m", at=at, close=D(60000 + h), quote="EUR", source="t")
        )
    db.commit()
    raw.import_movements(
        db,
        src,
        "file",
        "t",
        [
            Movement(
                timestamp=bought - timedelta(minutes=1),
                kind=Kind.FIAT_DEPOSIT,
                incoming_asset="EUR",
                incoming_amount=D(500),
            ),
            Movement(
                timestamp=bought,
                kind=Kind.TRADE,
                incoming_asset="BTC",
                incoming_amount=D("0.01"),
                outgoing_asset="EUR",
                outgoing_amount=D(500),
            ),
        ],
    )
    assert pfine.rebuild(db, now) > 0
    ticks = {t.at: t.value for t in db.query(PortfolioTick)}
    # an hour after the buy: 0.01 BTC at the fine price of that slot (60000 + 9)
    assert ticks[now - timedelta(hours=9)] == D("600.09")
    # nothing before the first movement
    assert min(ticks) >= bought - timedelta(minutes=5)


def test_missing_fills_before_the_oldest_when_the_window_grew(db):
    from app.modules.prices.fine import _missing
    from app.modules.prices.models import PriceFine

    now = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
    begin = now - timedelta(days=31)
    assert _missing(db, "BTC", "5m", begin, now) == [(begin, now)]
    for at in (now - timedelta(days=7), now - timedelta(minutes=5)):
        db.add(PriceFine(asset="BTC", step="5m", at=at, close=D(1), quote="EUR", source="t"))
    db.add(PriceFine(asset="BTC", step="5m", at=begin, close=D(1), quote="EUR", source="live"))
    db.commit()
    # live values do not count; the 7 days already there are not fetched again
    assert _missing(db, "BTC", "5m", begin, now) == [(begin, now - timedelta(days=7))]


def test_sparks_follow_the_span(authed, db):
    from app.modules.prices.models import PriceDaily, PriceFine

    now = datetime.now(UTC)
    for i in range(10):
        day = date.today() - timedelta(days=i)
        db.add(PriceDaily(asset="BTC", day=day, quote="EUR", close=D(100 + i), source="t"))
    for h in range(48):
        at = now - timedelta(hours=h)
        db.add(PriceFine(asset="BTC", step="5m", at=at, close=D(200 + h), quote="EUR", source="t"))
        db.add(PriceFine(asset="BTC", step="1h", at=at, close=D(300 + h), quote="EUR", source="t"))
    db.commit()
    h24 = authed.get("/api/prices/sparks?span=h24").json()["BTC"]
    # the last 24 hours of 5-minute prices (here one per hour), then today's price
    assert len(h24) == 25 and h24[0] == "223"
    d7 = authed.get("/api/prices/sparks?span=d7").json()["BTC"]
    assert d7[0].startswith("3")
    d90 = authed.get("/api/prices/sparks?span=d90").json()["BTC"]
    assert d90[0] == "109"
    assert authed.get("/api/prices/sparks?span=x").status_code == 422


def test_prices_end_on_a_day_and_are_no_longer_fetched(authed, db):
    from app.modules.prices import fine
    from app.modules.prices.models import PriceAsset, PriceDaily, PriceFine, PriceLatest
    from app.modules.prices.service import ended

    until = date.today() - timedelta(days=5)
    db.add(PriceAsset(asset="AGIX", confirmed=True, ignored=False))
    for i in range(10):
        day = date.today() - timedelta(days=i)
        db.add(PriceDaily(asset="AGIX", day=day, quote="USD", close=D("0.07"), source="t"))
    now = datetime.now(UTC)
    db.add(PriceFine(asset="AGIX", step="1h", at=now, close=D("0.59"), quote="USD", source="t"))
    db.add(PriceLatest(asset="AGIX", quote="USD", price=D("0.59"), source="t", at=now))
    db.commit()
    body = {"until": until.isoformat()}
    assert authed.post("/api/prices/assets/AGIX/until", json=body).status_code == 400
    body["reason"] = "merged into FET"
    assert authed.post("/api/prices/assets/AGIX/until", json=body).status_code == 204
    db.expire_all()
    assert max(d for (d,) in db.query(PriceDaily.day).filter_by(asset="AGIX")) == until
    assert db.query(PriceFine).filter_by(asset="AGIX").count() == 0
    assert db.query(PriceLatest).filter_by(asset="AGIX").count() == 0
    assert "AGIX" not in fine._assets(db) and "AGIX" in ended(db, date.today())
    row = next(a for a in authed.get("/api/prices/assets").json() if a["asset"] == "AGIX")
    assert row["prices_until"] == until.isoformat() and row["price"] is None
    # undone: fetched again from the next run on
    assert authed.post("/api/prices/assets/AGIX/until", json={"until": None}).status_code == 204
    db.expire_all()
    assert db.get(PriceAsset, "AGIX").prices_until is None
