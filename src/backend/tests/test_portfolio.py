"""Portfolio pass (ADR 0040) on small, hand-checkable histories."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app.modules.plugins.contract import IncomeKind, Kind, Market, Movement

T = datetime(2025, 1, 10, 12, tzinfo=UTC)
D = Decimal


@pytest.fixture
def setup(authed, db):
    from app.modules.prices.models import PriceDaily, PriceLatest
    from app.modules.raw import service as raw
    from app.modules.sources.models import Source

    authed.post("/api/sources", json={"provider": "manual", "label": "Exchange"})
    authed.post("/api/sources", json={"provider": "manual", "label": "Wallet"})
    a, b = db.query(Source).order_by(Source.id).all()
    # BTC 30,000 € on day 0, 40,000 € from day 1; SOL 100 €
    for i in range(30):
        day = date(2025, 1, 10) + timedelta(days=i)
        db.add(
            PriceDaily(
                asset="BTC", day=day, quote="EUR", close=D(30000 if i == 0 else 40000), source="t"
            )
        )
        db.add(PriceDaily(asset="SOL", day=day, quote="EUR", close=D(100), source="t"))
    for asset, price in (("BTC", 40000), ("SOL", 100)):
        db.add(
            PriceLatest(asset=asset, quote="EUR", price=D(price), source="t", at=datetime.now(UTC))
        )
    db.commit()

    def load(source, *moves):
        raw.import_movements(db, source, "file", "t", list(moves))

    return a, b, load


def _get(authed):
    body = authed.get("/api/portfolio").json()
    return body["summary"], {i["asset"]: i for i in body["items"]}


def test_buy_sell_with_fee_in_the_bought_coin(setup, authed):
    a, _, load = setup
    load(
        a,
        Movement(
            timestamp=T, kind=Kind.FIAT_DEPOSIT, incoming_asset="EUR", incoming_amount=D(30000)
        ),
        # Bitget style: the fee is paid in the coin just bought
        Movement(
            timestamp=T + timedelta(minutes=1),
            kind=Kind.TRADE,
            incoming_asset="BTC",
            incoming_amount=D("1.01"),
            outgoing_asset="EUR",
            outgoing_amount=D(30000),
            fee_asset="BTC",
            fee_amount=D("0.01"),
        ),
        Movement(
            timestamp=T + timedelta(days=1),
            kind=Kind.TRADE,
            incoming_asset="EUR",
            incoming_amount=D(20000),
            outgoing_asset="BTC",
            outgoing_amount=D("0.5"),
        ),
    )
    s, items = _get(authed)
    btc = items["BTC"]
    assert btc["qty"] == "0.5" and btc["cost"] == "15000.00"
    assert btc["realized"] == "5000.00" and btc["realized_pct"] == "33.33"
    assert s["net_deposited"] == "30000.00" and s["cash"] == "20000.00"
    assert s["unrealized"] == "5000.00"  # 0.5 × 40,000 − 15,000


def test_a_fee_in_the_money_received_lowers_the_gain(setup, authed):
    """Like the tax report: selling for euros with the fee in euros (review 2026-10-24)."""
    a, _, load = setup
    load(
        a,
        Movement(
            timestamp=T, kind=Kind.FIAT_DEPOSIT, incoming_asset="EUR", incoming_amount=D(30000)
        ),
        Movement(
            timestamp=T + timedelta(minutes=1),
            kind=Kind.TRADE,
            incoming_asset="BTC",
            incoming_amount=D(1),
            outgoing_asset="EUR",
            outgoing_amount=D(30000),
        ),
        Movement(
            timestamp=T + timedelta(days=1),
            kind=Kind.TRADE,
            incoming_asset="EUR",
            incoming_amount=D(20000),
            outgoing_asset="BTC",
            outgoing_amount=D("0.5"),
            fee_asset="EUR",
            fee_amount=D(100),
        ),
    )
    s, items = _get(authed)
    assert items["BTC"]["realized"] == "4900.00"  # 20,000 − 100 − 15,000
    assert s["cash"] == "19900.00"


def test_transfer_keeps_cost_and_the_network_fee_raises_it(setup, authed):
    a, b, load = setup
    load(
        a,
        Movement(
            timestamp=T,
            kind=Kind.TRADE,
            incoming_asset="BTC",
            incoming_amount=D(1),
            outgoing_asset="EUR",
            outgoing_amount=D(30000),
        ),
        Movement(
            timestamp=T + timedelta(hours=1),
            kind=Kind.SEND,
            outgoing_asset="BTC",
            outgoing_amount=D(1),
            external_id="tx1",
        ),
    )
    load(
        b,
        Movement(
            timestamp=T + timedelta(hours=1, minutes=5),
            kind=Kind.RECEIVE,
            incoming_asset="BTC",
            incoming_amount=D("0.999"),
            external_id="tx1",
        ),
    )
    s, items = _get(authed)
    btc = items["BTC"]
    assert btc["qty"] == "0.999" and btc["cost"] == "30000.00" and btc["realized"] == "0.00"
    assert s["card_deposits"] == "30000.00"  # EUR spent that never arrived: from the bank
    places = {(p["source_id"], p["qty"]) for p in btc["places"]}
    assert places == {(b.id, "0.999")}


def test_selling_what_was_never_there_is_unclear_not_gain(setup, authed):
    a, _, load = setup
    load(
        a,
        Movement(
            timestamp=T + timedelta(days=1),
            kind=Kind.TRADE,
            incoming_asset="EUR",
            incoming_amount=D(40000),
            outgoing_asset="BTC",
            outgoing_amount=D(1),
        ),
    )
    s, items = _get(authed)
    assert items["BTC"]["realized"] == "0.00" and items["BTC"]["unclear_qty"] == "1"
    assert s["unclear"] == "40000.00"
    gaps = authed.get("/api/portfolio/gaps").json()
    assert gaps[0]["asset"] == "BTC" and gaps[0]["from"].startswith("2025-01-11")
    # the transactions list shows it right at the line: BTC −1 after it (Vanixxx, 2026-10-08)
    body = authed.get("/api/merged", params={"show": "short"}).json()
    row = body["items"][0]["row"]
    assert row["short"] == ["BTC"] and row["after"]["BTC"] == "-1" and body["summary"]["short"] == 1


def test_income_costs_its_market_value_and_open_send_leaves(setup, authed):
    a, _, load = setup
    load(
        a,
        Movement(
            timestamp=T,
            kind=Kind.INCOME,
            income_kind=IncomeKind.STAKING,
            incoming_asset="SOL",
            incoming_amount=D(2),
        ),
        Movement(
            timestamp=T + timedelta(days=2),
            kind=Kind.SEND,
            outgoing_asset="SOL",
            outgoing_amount=D(1),
        ),
    )
    s, items = _get(authed)
    sol = items["SOL"]
    assert sol["income"] == "200.00" and sol["cost"] == "100.00" and sol["open_qty"] == "1"
    assert s["open"] == "100.00" and s["realized"] == "0.00"


def test_marked_sends(setup, authed):
    a, _, load = setup
    load(
        a,
        Movement(
            timestamp=T,
            kind=Kind.TRADE,
            incoming_asset="SOL",
            incoming_amount=D(10),
            outgoing_asset="EUR",
            outgoing_amount=D(500),
        ),
        Movement(
            timestamp=T + timedelta(days=1),
            kind=Kind.SEND,
            outgoing_asset="SOL",
            outgoing_amount=D(2),
        ),
        Movement(
            timestamp=T + timedelta(days=2),
            kind=Kind.SEND,
            outgoing_asset="SOL",
            outgoing_amount=D(3),
        ),
    )
    sends = [r for r in authed.get("/api/raw", params={"kind": "send"}).json()["rows"]]
    by_time = sorted(sends, key=lambda r: r["timestamp"])
    authed.post("/api/merged/open-mark", json={"send_id": by_time[0]["id"], "mark": "external"})
    authed.post(
        "/api/merged/open-mark", json={"send_id": by_time[1]["id"], "mark": "own_untracked"}
    )
    s, items = _get(authed)
    sol = items["SOL"]
    # paid away 2 SOL worth 200 € that cost 100 €; 3 SOL stay, outside the known sources
    assert sol["realized"] == "100.00" and sol["qty"] == "8"
    assert any(p["outside"] and p["qty"] == "3" for p in sol["places"])


def test_history_high_and_futures_positions(setup, authed):
    a, _, load = setup
    load(
        a,
        Movement(
            timestamp=T,
            kind=Kind.TRADE,
            incoming_asset="BTC",
            incoming_amount=D(1),
            outgoing_asset="EUR",
            outgoing_amount=D(30000),
        ),
        Movement(
            timestamp=T,
            kind=Kind.FUTURES_POSITION,
            market=Market.FUTURES,
            instrument="BTCUSDT",
            raw={
                "Direction": "Long",
                "Open Time": "2025-01-10 10:00:00",
                "Close Time": "2025-01-10 13:00:00",
                "Avg Entry Price": "100",
                "Avg Close Price": "110",
            },
        ),
        Movement(
            timestamp=T - timedelta(minutes=30),
            kind=Kind.REALIZED_PNL,
            market=Market.FUTURES,
            instrument="BTCUSDT",
            incoming_asset="EUR",
            incoming_amount=D(10),
            fee_asset="EUR",
            fee_amount=D(1),
        ),
        Movement(
            timestamp=T + timedelta(days=5),
            kind=Kind.FUNDING,
            market=Market.FUTURES,
            instrument="ETHUSDT",
            outgoing_asset="EUR",
            outgoing_amount=D(2),
        ),
    )
    hist = authed.get("/api/portfolio/history").json()
    # the 9 € futures result stay in the futures account: the spot buy came by card
    assert hist[0]["day"] == "2025-01-10" and hist[0]["value"] == "30009.00"
    assert hist[1]["value"] == "40009.00"
    s, _ = _get(authed)
    assert s["futures"]["result"] == "7.00" and D(s["high"]["value"]) >= 40000
    pos = authed.get("/api/portfolio/futures").json()
    known = next(p for p in pos if p["known"])
    assert known["side"] == "long" and known["result"] == "9" and known["entry"] == "100"
    assert next(p for p in pos if not p["known"])["funding"] == "-2"


def test_deposits_in_usd_convert_at_their_own_day(setup, authed, db):
    from app.modules.prices.models import FxDaily

    a, _, load = setup
    for i in range(30):
        day = date(2025, 1, 10) + timedelta(days=i)
        # the dollar moves every day; the deposit must not
        db.add(
            FxDaily(day=day, base="USD", quote="EUR", rate=D("0.9") + D(i) / 100, source_day=day)
        )
    db.add(
        FxDaily(
            day=datetime.now(UTC).date(),
            base="USD",
            quote="EUR",
            rate=D("0.5"),
            source_day=datetime.now(UTC).date(),
        )
    )
    db.commit()
    authed.patch("/api/settings", json={"general.currency": "USD"})
    load(
        a,
        Movement(timestamp=T, kind=Kind.FIAT_DEPOSIT, incoming_asset="EUR", incoming_amount=D(900)),
    )
    hist = authed.get("/api/portfolio/history").json()
    assert {h["deposited"] for h in hist} == {"1000.00"}  # 900 € / 0.9 on the day it came
    s, _ = _get(authed)
    assert s["net_deposited"] == "1000.00"


def test_closed_positions_are_one_line_in_transactions(setup, authed):
    a, _, load = setup
    load(
        a,
        Movement(
            timestamp=T,
            kind=Kind.FUTURES_POSITION,
            market=Market.FUTURES,
            instrument="BTCUSDT",
            raw={
                "Direction": "Short",
                "Open Time": "2025-01-10 10:00:00",
                "Close Time": "2025-01-10 13:00:00",
            },
        ),
        Movement(
            timestamp=T - timedelta(minutes=30),
            kind=Kind.REALIZED_PNL,
            market=Market.FUTURES,
            instrument="BTCUSDT",
            incoming_asset="EUR",
            incoming_amount=D(10),
        ),
        Movement(
            timestamp=T - timedelta(hours=1),
            kind=Kind.FUNDING,
            market=Market.FUTURES,
            instrument="BTCUSDT",
            outgoing_asset="EUR",
            outgoing_amount=D(1),
        ),
    )
    items = authed.get("/api/merged").json()["items"]
    pos = [i for i in items if i["type"] == "position"]
    assert len(pos) == 1 and pos[0]["side"] == "short" and pos[0]["result"] == "9"
    assert {r["kind"] for r in pos[0]["rows"]} == {"futures_position", "realized_pnl", "funding"}
    assert not any(i["type"] == "row" and i["row"]["market"] == "futures" for i in items)
    only = authed.get("/api/merged", params={"kind": "funding"}).json()["items"]
    assert [i["type"] for i in only] == ["position"]


def test_fiat_in_or_out_without_counter_side_is_a_deposit_whatever_the_kind(setup, authed):
    a, _, load = setup
    load(
        a,
        # Bitget delivers a euro deposit with an empty type: read as "other"
        Movement(timestamp=T, kind=Kind.OTHER, incoming_asset="EUR", incoming_amount=D(10)),
        Movement(
            timestamp=T + timedelta(hours=1),
            kind=Kind.OTHER,
            incoming_asset="EUR",
            incoming_amount=D(10),
        ),
        Movement(
            timestamp=T + timedelta(hours=2),
            kind=Kind.OTHER,
            outgoing_asset="EUR",
            outgoing_amount=D(5),
        ),
    )
    s, _ = _get(authed)
    assert s["net_deposited"] == "15.00" and s["external_in"] == "0.00" and s["open"] == "0.00"


def test_each_trade_shows_what_it_came_to(setup, authed):
    a, _, load = setup
    load(
        a,
        # bought 1 BTC for 30,000 € (+ 10 € fee) on day 0; today 40,000 €
        Movement(
            timestamp=T,
            kind=Kind.TRADE,
            incoming_asset="BTC",
            incoming_amount=D(1),
            outgoing_asset="EUR",
            outgoing_amount=D(30000),
            fee_asset="EUR",
            fee_amount=D(10),
        ),
        # sold 1 SOL for 120 € (price 100 that day by the table, the fiat side counts); today 100 €
        Movement(
            timestamp=T + timedelta(days=2),
            kind=Kind.TRADE,
            incoming_asset="EUR",
            incoming_amount=D(120),
            outgoing_asset="SOL",
            outgoing_amount=D(1),
        ),
    )
    rows = {
        i["row"]["incoming"][0]: i
        for i in authed.get("/api/merged").json()["items"]
        if i["type"] == "row"
    }
    buy, sell = rows["BTC"]["result"], rows["EUR"]["result"]
    assert buy["side"] == "buy" and buy["then"] == "30010.00" and buy["now"] == "40000.00"
    assert buy["result"] == "9990.00" and buy["pct"] == "33.3"
    assert (
        sell["side"] == "sell"
        and sell["then"] == "120.00"
        and sell["now"] == "100.00"
        and sell["result"] == "20.00"
    )


def test_five_minute_values_are_recorded_once_per_slot_and_thinned(setup, authed, db):
    from app.modules.portfolio import service
    from app.modules.portfolio.models import PortfolioTick

    a, _, load = setup
    load(
        a,
        Movement(
            timestamp=T,
            kind=Kind.TRADE,
            incoming_asset="BTC",
            incoming_amount=D(1),
            outgoing_asset="EUR",
            outgoing_amount=D(30000),
        ),
    )
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    now -= timedelta(minutes=now.minute % 5)  # start of a slot: +1 minute stays in it
    assert service.record_tick(db, now) and not service.record_tick(db, now + timedelta(minutes=1))
    # old fine points: within one hour only the first stays; beyond 90 days none
    old = now - timedelta(days=10)
    old = old.replace(minute=0)
    for m in (0, 5, 10):
        db.add(PortfolioTick(at=old + timedelta(minutes=m), value=D(1)))
    db.add(PortfolioTick(at=now - timedelta(days=100), value=D(1)))
    db.commit()
    service.record_tick(db, now + timedelta(minutes=5))
    kept = [t.at for t in db.query(PortfolioTick).order_by(PortfolioTick.at)]
    assert old in kept and old + timedelta(minutes=5) not in kept and len(kept) == 3
    points = authed.get("/api/portfolio/ticks", params={"hours": 24}).json()
    assert points[0]["value"] == "40000.00" and len(points) == 3  # two ticks + live


def test_the_dca_moves_with_every_buy(setup, authed):
    """The average buying price as a line through time (Vanixxx, 2026-10-08): a second buy at
    a higher price lifts it, a sale leaves it, selling all ends it."""
    a, _, load = setup

    def buy(days, qty, eur):
        return Movement(
            timestamp=T + timedelta(days=days),
            kind=Kind.TRADE,
            incoming_asset="SOL",
            incoming_amount=D(qty),
            outgoing_asset="EUR",
            outgoing_amount=D(eur),
        )

    load(
        a,
        Movement(
            timestamp=T, kind=Kind.FIAT_DEPOSIT, incoming_asset="EUR", incoming_amount=D(5000)
        ),
        buy(0, 10, 1000),  # 100 each
        buy(2, 10, 2000),  # 200 each: average 150
        Movement(
            timestamp=T + timedelta(days=3),
            kind=Kind.TRADE,
            incoming_asset="EUR",
            incoming_amount=D(1000),
            outgoing_asset="SOL",
            outgoing_amount=D(5),
        ),  # a sale keeps the average
        Movement(
            timestamp=T + timedelta(days=5),
            kind=Kind.TRADE,
            incoming_asset="EUR",
            incoming_amount=D(2000),
            outgoing_asset="SOL",
            outgoing_amount=D(15),
        ),
    )
    steps = authed.get("/api/portfolio/dca/sol").json()
    assert [(s["day"], s["value"] and float(s["value"])) for s in steps] == [
        ("2025-01-10", 100.0),
        ("2025-01-12", 150.0),
        ("2025-01-15", None),
    ]


def test_a_card_purchase_is_money_paid_in(setup, authed):
    """Bitget delivers "Buy with card" as USDT arriving, no euro side: it is a deposit by
    card, not a coin from outside that the chart would count as gain (2026-10-08)."""
    a, _, load = setup
    load(
        a,
        Movement(
            timestamp=T,
            kind=Kind.OTHER,
            incoming_asset="SOL",
            incoming_amount=D(5),
            comment="Buy with card",
        ),
    )
    s, items = _get(authed)
    assert s["card_deposits"] == "500.00" and s["net_deposited"] == "500.00"
    assert s["external_in"] == "0.00" and items["SOL"]["cost"] == "500.00"


def test_a_worthless_coin_shows_its_loss(setup, authed):
    """Entangle is dead: valued at 0 from a day on, the cost stays and the loss shows,
    instead of "no price" (Vanixxx, 2026-10-08)."""
    a, _, load = setup
    load(
        a,
        Movement(timestamp=T, kind=Kind.FIAT_DEPOSIT, incoming_asset="EUR", incoming_amount=D(300)),
        Movement(
            timestamp=T + timedelta(minutes=1),
            kind=Kind.TRADE,
            incoming_asset="NTGL",
            incoming_amount=D(1000),
            outgoing_asset="EUR",
            outgoing_amount=D(300),
        ),
    )
    assert _get(authed)[0]["unvalued"] == ["NTGL"]
    bad = authed.post("/api/prices/assets/NTGL/worthless", json={"since": "2025-01-20"})
    assert bad.json()["error"]["code"] == "prices.reason_required"
    assert (
        authed.post(
            "/api/prices/assets/NTGL/worthless",
            json={"since": "2025-01-20", "reason": "Projekt eingestellt"},
        ).status_code
        == 204
    )
    s, items = _get(authed)
    assert s["unvalued"] == [] and items["NTGL"]["value"] == "0.00"
    assert items["NTGL"]["unrealized"] == "-300.00" and items["NTGL"]["cost"] == "300.00"
    authed.post("/api/prices/assets/NTGL/worthless", json={"since": None})
    assert _get(authed)[0]["unvalued"] == ["NTGL"]


def test_euro_spent_where_there_was_none_came_by_card(setup, authed, db):
    """MEXC card buy: 200 € paid, 214.40 USDT bought, 6.3892 USDT fee. No euro at MEXC — the
    euro lying at the other exchange stay there, the 200 € are a card deposit and MEXC's
    euro never run below zero (Vanixxx, 2026-10-09)."""
    a, b, load = setup
    load(
        a,
        Movement(timestamp=T, kind=Kind.FIAT_DEPOSIT, incoming_asset="EUR", incoming_amount=D(500)),
    )
    load(
        b,
        Movement(
            timestamp=T + timedelta(hours=1),
            kind=Kind.TRADE,
            incoming_asset="SOL",
            incoming_amount=D("2.1"),
            outgoing_asset="EUR",
            outgoing_amount=D(200),
            fee_asset="SOL",
            fee_amount=D("0.1"),
        ),
    )
    s, items = _get(authed)
    assert s["card_deposits"] == "200.00" and s["net_deposited"] == "700.00"
    assert s["cash"] == "500.00"  # the other exchange's euro untouched
    assert items["SOL"]["qty"] == "2" and items["SOL"]["cost"] == "200.00"
    body = authed.get("/api/merged", params={"show": "short"}).json()
    assert body["items"] == []  # nothing below zero
    # the line says so: 200 EUR assumed paid in by card (Vanixxx, 2026-10-09)
    auto = authed.get("/api/merged", params={"show": "auto"}).json()
    assert [i["row"]["auto_deposit"] for i in auto["items"]] == [["EUR", "200"]]
    assert auto["summary"]["auto"] == 1
    # the balance check counts the card money too: the euros there are 0, not -200
    from app.modules.balances.service import reconcile

    eur = [
        i
        for e in reconcile(db)
        if e["source_id"] == b.id
        for i in e["items"]
        if i["asset"] == "EUR"
    ]
    assert eur == [] or eur[0]["computed"] in ("0", None)


def test_a_card_buy_is_paid_wholly_by_card(setup, authed):
    """50 € lie there, a 200 € buy: all 200 € came by card, the 50 € stay. And a buy marked
    "paid by card" counts so even when enough lay there (Vanixxx, 2026-10-10)."""
    a, _, load = setup
    load(
        a,
        Movement(timestamp=T, kind=Kind.FIAT_DEPOSIT, incoming_asset="EUR", incoming_amount=D(50)),
    )
    load(
        a,
        Movement(
            timestamp=T + timedelta(hours=1),
            kind=Kind.TRADE,
            incoming_asset="SOL",
            incoming_amount=D(2),
            outgoing_asset="EUR",
            outgoing_amount=D(200),
        ),
    )
    s, _ = _get(authed)
    assert (
        s["card_deposits"] == "200.00" and s["net_deposited"] == "250.00" and s["cash"] == "50.00"
    )
    sid = authed.get("/api/sources").json()[0]["id"]
    assert (
        authed.post(
            f"/api/sources/{sid}/manual",
            json={
                "kind": "trade",
                "time": "2025-01-12T10:00:00",
                "incoming_asset": "SOL",
                "incoming_amount": "0.4",
                "outgoing_asset": "EUR",
                "outgoing_amount": "40",
                "paid_by_card": True,
            },
        ).status_code
        == 201
    )
    s, _ = _get(authed)
    assert s["card_deposits"] == "240.00" and s["cash"] == "50.00"  # the 50 € still there


def test_a_trade_a_reader_marks_paid_by_paypal_is_money_paid_in(setup, authed):
    a, _, load = setup
    load(
        a,
        Movement(timestamp=T, kind=Kind.FIAT_DEPOSIT, incoming_asset="EUR", incoming_amount=D(500)),
    )
    load(
        a,
        Movement(
            timestamp=T + timedelta(hours=1),
            kind=Kind.TRADE,
            incoming_asset="SOL",
            incoming_amount=D(1),
            outgoing_asset="EUR",
            outgoing_amount=D("48.01"),
            fee_asset="EUR",
            fee_amount=D("1.99"),
            comment="Paid by PayPal",
        ),
    )
    s, _ = _get(authed)
    # 48.01 and the 1.99 fee by PayPal: 50 € paid in, the 500 € there untouched
    assert s["card_deposits"] == "50.00" and s["cash"] == "500.00"


def test_a_send_marked_lost_is_a_total_loss(setup, authed):
    """Sent to a provider that went bust (Trastra, Vanixxx 2026-10-11): the cost is lost."""
    a, _, load = setup
    load(
        a,
        Movement(
            timestamp=T,
            kind=Kind.TRADE,
            incoming_asset="SOL",
            incoming_amount=D(10),
            outgoing_asset="EUR",
            outgoing_amount=D(500),
        ),
        Movement(
            timestamp=T + timedelta(days=1),
            kind=Kind.SEND,
            outgoing_asset="SOL",
            outgoing_amount=D(4),
        ),
    )
    send = authed.get("/api/raw", params={"kind": "send"}).json()["rows"][0]
    r = authed.post("/api/merged/open-mark", json={"send_id": send["id"], "mark": "lost"})
    assert r.status_code == 204
    s, items = _get(authed)
    sol = items["SOL"]
    assert sol["realized"] == "-200.00" and sol["qty"] == "6" and not sol.get("open_qty")


def test_marked_receives(setup, authed):
    """A receive without counterpart can be marked (Vanixxx, 2026-10-11): income (Coinbase
    rewards for tasks), bought outside (BNB by card for fees), back from an own wallet."""
    a, _, load = setup
    load(
        a,
        Movement(
            timestamp=T,
            kind=Kind.TRADE,
            incoming_asset="SOL",
            incoming_amount=D(10),
            outgoing_asset="EUR",
            outgoing_amount=D(500),
        ),
        Movement(
            timestamp=T + timedelta(days=1),
            kind=Kind.SEND,
            outgoing_asset="SOL",
            outgoing_amount=D(2),
        ),
        Movement(
            timestamp=T + timedelta(days=2),
            kind=Kind.RECEIVE,
            incoming_asset="SOL",
            incoming_amount=D(2),
        ),
        Movement(
            timestamp=T + timedelta(days=3),
            kind=Kind.RECEIVE,
            incoming_asset="SOL",
            incoming_amount=D(1),
        ),
        Movement(
            timestamp=T + timedelta(days=4),
            kind=Kind.RECEIVE,
            incoming_asset="SOL",
            incoming_amount=D(3),
        ),
    )
    rows = sorted(authed.get("/api/raw").json()["rows"], key=lambda r: r["timestamp"])
    send, back, reward, bought = rows[1], rows[2], rows[3], rows[4]
    open_now = authed.get("/api/merged", params={"show": "open"}).json()
    assert open_now["summary"]["open"] >= 3  # receives without counterpart count now
    for row, mark in (
        (send, "own_untracked"),
        (back, "own_untracked"),
        (reward, "income"),
        (bought, "bought"),
    ):
        r = authed.post("/api/merged/open-mark", json={"send_id": row["id"], "mark": mark})
        assert r.status_code == 204, (mark, r.json())
    bad = authed.post("/api/merged/open-mark", json={"send_id": reward["id"], "mark": "lost"})
    assert bad.status_code == 400  # "lost" is for sends
    s, items = _get(authed)
    sol = items["SOL"]
    assert sol["qty"] == "14" and sol["income"] == "100.00"  # 1 SOL at 100 €
    # 500 € for the first buy came by card too (no euro lay there), plus the 300 € bought
    assert s["card_deposits"] == "800.00" and s["external_in"] == "0.00"
    assert not any(p["outside"] for p in sol["places"])  # the 2 SOL came back


def test_balance_at_a_moment_for_the_entry_form(setup, authed):
    """The form shows what lay there at the chosen time (Vanixxx, 2026-10-11)."""
    a, _, load = setup
    load(
        a,
        Movement(
            timestamp=T, kind=Kind.FIAT_DEPOSIT, incoming_asset="USD", incoming_amount=D(1000)
        ),
        Movement(
            timestamp=T + timedelta(days=2),
            kind=Kind.FIAT_WITHDRAWAL,
            outgoing_asset="USD",
            outgoing_amount=D(300),
        ),
    )
    q = {"source_id": a.id, "asset": "usd"}
    at = lambda d: authed.get(  # noqa: E731
        "/api/portfolio/balance-at", params={**q, "at": (T + timedelta(days=d)).isoformat()}
    ).json()["amount"]
    assert (at(-1), at(1), at(3)) == ("0", "1000", "700")
    out = next(r for r in authed.get("/api/raw", params={"kind": "fiat_withdrawal"}).json()["rows"])
    skipped = authed.get(
        "/api/portfolio/balance-at",
        params={**q, "at": (T + timedelta(days=3)).isoformat(), "skip": out["id"]},
    ).json()
    assert skipped["amount"] == "1000"  # editing the withdrawal: what lay there before it


def test_fiat_marked_lost_is_no_withdrawal(setup, authed):
    """Dollars left on a scam exchange (Cryptex, Vanixxx 2026-10-11): not paid out, lost."""
    a, _, load = setup
    load(
        a,
        Movement(timestamp=T, kind=Kind.FIAT_DEPOSIT, incoming_asset="EUR", incoming_amount=D(500)),
        Movement(
            timestamp=T + timedelta(days=1),
            kind=Kind.SEND,
            outgoing_asset="EUR",
            outgoing_amount=D(200),
        ),
    )
    s, _ = _get(authed)
    assert s["net_deposited"] == "300.00"  # unmarked: a withdrawal
    send = authed.get("/api/raw", params={"kind": "send"}).json()["rows"][0]
    authed.post("/api/merged/open-mark", json={"send_id": send["id"], "mark": "lost"})
    s, _ = _get(authed)
    assert s["net_deposited"] == "500.00" and s["cash"] == "300.00"


def test_the_day_price_is_the_utc_day_whatever_the_server_time_zone(setup, authed, db):
    """23:30 UTC on 10 Jan is 00:30 on 11 Jan in Berlin: valued with 10 Jan (30,000 €), the
    day prices are stored for (review 2026-10-24; the test server runs Europe/Berlin)."""
    a, _, load = setup
    load(
        a,
        Movement(
            timestamp=datetime(2025, 1, 10, 23, 30, tzinfo=UTC),
            kind=Kind.RECEIVE,
            incoming_asset="BTC",
            incoming_amount=D(1),
        ),
    )
    _, items = _get(authed)
    assert items["BTC"]["cost"] == "30000.00"
