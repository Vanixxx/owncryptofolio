"""Statistics page (ADR 0043) on a small history."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.modules.plugins.contract import IncomeKind, Kind, Movement

D = Decimal
T = datetime(2025, 1, 10, 12, tzinfo=UTC)


def test_fees_income_activity_and_btc_benchmark(authed, db):
    from app.modules.prices.models import PriceDaily
    from app.modules.raw import service as raw
    from app.modules.sources.models import Source

    authed.post("/api/sources", json={"provider": "manual", "label": "Exchange"})
    src = db.query(Source).one()
    for i in range(10):
        day = date(2025, 1, 10) + timedelta(days=i)
        db.add(
            PriceDaily(
                asset="BTC", day=day, quote="EUR", close=D(50000 if i < 5 else 100000), source="t"
            )
        )
    db.commit()
    raw.import_movements(
        db,
        src,
        "file",
        "t",
        [
            Movement(
                timestamp=T, kind=Kind.FIAT_DEPOSIT, incoming_asset="EUR", incoming_amount=D(1000)
            ),
            Movement(
                timestamp=T + timedelta(hours=1),
                kind=Kind.TRADE,
                incoming_asset="BTC",
                incoming_amount=D("0.01"),
                outgoing_asset="EUR",
                outgoing_amount=D(500),
                fee_asset="EUR",
                fee_amount=D(2),
            ),
            Movement(
                timestamp=T + timedelta(days=2),
                kind=Kind.INCOME,
                income_kind=IncomeKind.STAKING,
                incoming_asset="BTC",
                incoming_amount=D("0.0001"),
            ),
        ],
    )
    body = authed.get("/api/stats").json()
    assert body["fees"] == [{"year": 2025, "place": "Exchange", "value": "2.00"}]
    assert body["incomes"] == [{"month": "2025-01", "kind": "staking", "value": "5.00"}]
    (month,) = body["activity"]
    assert (month["trades"], month["deposits"]) == (1, "1000.00")
    # 1,000 € into BTC at 50,000 → 0.02 BTC, worth 2,000 € once BTC doubled
    assert body["benchmark"][-1]["value"] == "2000.00"
    # spot: the one sale-free history has no sales yet; health lists every kind
    assert body["spot"]["sales"] == 0
    assert {h["key"] for h in body["health"]} == {
        "gaps",
        "balances",
        "open",
        "short",
        "other",
        "unvalued",
        "card",
        "changed",
        "fetch",
    }
    # the coins without a price are named, so the page can link to each
    (unvalued,) = [h for h in body["health"] if h["key"] == "unvalued"]
    assert unvalued["assets"] == [] and unvalued["count"] == 0
