"""Source of funds (ADR 0046)."""

from decimal import Decimal

from app.modules.plugins.contract import IncomeKind, Kind, Market, Movement
from tests import test_tax
from tests.test_tax import at, buy, run, sell

setup = test_tax.setup  # the fixture

D = Decimal


def deposit(when, eur):
    return Movement(
        timestamp=when, kind=Kind.FIAT_DEPOSIT, incoming_asset="EUR", incoming_amount=D(eur)
    )


def test_the_tax_is_the_same_with_and_without_the_trace(setup, db):
    a, _, load = setup
    load(a, deposit(at(0), 30000), buy(at(0, 1), 1, 30000), sell(at(10), "0.5", 20000))
    plain, traced = run(db), run(db, trace=True)
    assert [d.gain for d in plain.disposals] == [d.gain for d in traced.disposals]
    assert plain.trace is None and traced.trace is not None


def test_a_sale_splits_into_own_money_and_gain_through_a_transfer(setup, authed, db):
    a, b, load = setup
    load(a, deposit(at(0), 30000), buy(at(0, 1), 1, 30000))
    load(
        a,
        Movement(
            timestamp=at(5),
            kind=Kind.SEND,
            outgoing_asset="BTC",
            outgoing_amount=D(1),
            external_id="tx9",
        ),
    )
    load(
        b,
        Movement(
            timestamp=at(5, 5),
            kind=Kind.RECEIVE,
            incoming_asset="BTC",
            incoming_amount=D(1),
            external_id="tx9",
        ),
        sell(at(10), 1, 40000),
    )
    rows = authed.get("/api/tax/origin").json()
    sale = next(r for r in rows if r["kind"] == "sale")
    transfer = next(r for r in rows if r["kind"] == "transfer")
    e = authed.get(f"/api/tax/origin/{sale['row']}").json()
    mix = {m["kind"]: m["value"] for m in e["mix"]}
    assert mix == {"bank": "30000.00", "gain": "10000.00"}
    # the chain: sale ← transfer (with its id) ← buy ← deposit
    kinds = []
    n = e["tree"]
    while n.get("children"):
        n = n["children"][0]
        kinds.append(n["kind"])
    assert kinds == ["transfer", "buy", "bank"]
    assert e["tree"]["children"][0]["tx"] == "tx9"
    # the transfer itself, between own wallets: worth 40,000 then, 10,000 of it price gain
    t = authed.get(f"/api/tax/origin/{transfer['row']}").json()
    assert t["target"]["amount"] == "40000.00"
    assert {m["kind"]: m["value"] for m in t["mix"]} == {"bank": "30000.00", "gain": "10000.00"}
    for kind, magic in (("pdf", b"%PDF"), ("xlsx", b"PK")):
        f = authed.get(f"/api/tax/origin/{sale['row']}/file?kind={kind}")
        assert f.status_code == 200 and f.content[: len(magic)] == magic


def test_income_card_and_unknown_origins(setup, authed, db):
    a, _, load = setup
    load(
        a,
        Movement(
            timestamp=at(0),
            kind=Kind.INCOME,
            income_kind=IncomeKind.STAKING,
            incoming_asset="ETH",
            incoming_amount=D(1),
        ),
        Movement(timestamp=at(1), kind=Kind.RECEIVE, incoming_asset="ETH", incoming_amount=D(1)),
        sell(at(2), 2, 4000, asset="ETH"),
    )
    sale = next(r for r in authed.get("/api/tax/origin").json() if r["kind"] == "sale")
    mix = {
        m["kind"]: m["value"] for m in authed.get(f"/api/tax/origin/{sale['row']}").json()["mix"]
    }
    assert mix == {"income": "2000.00", "unknown": "2000.00"}
    assert authed.get("/api/tax/origin/999999").status_code == 404


def test_euro_paid_straight_from_the_bank_is_own_money(setup, authed, db):
    """MEXC sells USDT for SEPA or a bank card without a deposit row (Vanixxx, 2026-10-17)."""
    a, _, load = setup
    load(
        a,
        buy(at(0), 1000, 1000, asset="USDT", comment="Payment ID: 1 Bank card"),
        buy(at(1), 500, 500, asset="USDT", comment="SEPA"),
        sell(at(2), 1500, 1500, asset="USDT"),
    )
    sale = next(r for r in authed.get("/api/tax/origin").json() if r["kind"] == "sale")
    mix = {
        m["kind"]: m["value"] for m in authed.get(f"/api/tax/origin/{sale['row']}").json()["mix"]
    }
    assert mix == {"card": "1000.00", "bank": "500.00"}


def test_a_rebooking_booked_arrival_first_keeps_the_real_origin(setup, authed, db):
    """Bitget books the futures arrival before the spot departure; what the futures account
    sells in between came from the real lots, not from an unknown inflow."""
    a, _, load = setup
    load(
        a,
        deposit(at(0), 30000),
        buy(at(0, 1), 1, 30000),
        Movement(
            timestamp=at(5),
            kind=Kind.INTERNAL_TRANSFER,
            market=Market.FUTURES,
            incoming_asset="BTC",
            incoming_amount=D(1),
        ),
        sell(at(5, 1), 1, 40000, market=Market.FUTURES),
        Movement(
            timestamp=at(5, 2),
            kind=Kind.INTERNAL_TRANSFER,
            outgoing_asset="BTC",
            outgoing_amount=D(1),
        ),
    )
    sale = next(r for r in authed.get("/api/tax/origin").json() if r["kind"] == "sale")
    mix = {
        m["kind"]: m["value"] for m in authed.get(f"/api/tax/origin/{sale['row']}").json()["mix"]
    }
    assert mix == {"bank": "30000.00", "gain": "10000.00"}


def test_todays_holdings_with_an_unrealized_gain(setup, authed, db):
    """1 BTC bought for 30,000 € of own money, worth 40,000 € today: 10,000 € price gain not
    yet sold; 500 € still on the exchange as euro."""
    from datetime import date

    from app.modules.prices.models import PriceDaily

    a, _, load = setup
    load(a, deposit(at(0), 30500), buy(at(0, 1), 1, 30000))
    db.merge(PriceDaily(asset="BTC", day=date.today(), quote="EUR", close=D(40000), source="t"))
    db.commit()
    h = authed.get("/api/tax/origin/holdings").json()
    assert {m["kind"]: m["value"] for m in h["mix"]} == {"bank": "30500.00", "gain": "10000.00"}
    assert {c["asset"]: c["value"] for c in h["coins"]} == {"BTC": "40000.00", "EUR": "500.00"}
    one = authed.get("/api/tax/origin/holdings?asset=BTC").json()
    assert one["target"]["amount"] == "40000.00"
    assert any(k.get("detail") == "unrealized" for k in one["tree"]["children"])
    assert authed.get("/api/tax/origin/holdings?asset=XYZ").status_code == 404
    f = authed.get("/api/tax/origin/holdings/file?kind=pdf")
    assert f.status_code == 200 and f.content[:4] == b"%PDF"


def test_a_planned_step_takes_the_lots_in_tax_order_without_booking(setup, authed, db):
    from datetime import date

    from app.modules.prices.models import PriceDaily

    a, _, load = setup
    load(a, deposit(at(0), 30000), buy(at(0, 1), 1, 30000))
    db.merge(PriceDaily(asset="BTC", day=date.today(), quote="EUR", close=D(40000), source="t"))
    db.commit()
    opts = authed.get("/api/tax/origin/planned/options").json()
    assert {(o["asset"], o["qty"]) for o in opts if o["source"] == a.id} == {("BTC", "1")}
    q = f"/api/tax/origin/planned?source={a.id}&asset=BTC&qty=0.5&day=2026-12-01"
    p = authed.get(q).json()
    assert (p["target"]["kind"], p["target"]["amount"], p["target"]["at"]) == (
        "planned",
        "20000.00",
        "2026-12-01",
    )
    assert {m["kind"]: m["value"] for m in p["mix"]} == {"bank": "15000.00", "gain": "5000.00"}
    # nothing booked: the whole BTC is still there
    assert authed.get("/api/tax/origin/planned/options").json() == opts
    too = authed.get(f"/api/tax/origin/planned?source={a.id}&asset=BTC&qty=2")
    assert too.status_code == 400 and too.json()["error"]["code"] == "origin.planned_too_much"
    f = authed.get(q.replace("planned?", "planned/file?kind=pdf&"))
    assert f.status_code == 200 and f.content[:4] == b"%PDF"


def test_a_coin_for_coin_trade_is_one_swap_with_both_sides(setup, authed, db):
    """USDT → LTC: the chain shows the swap, not a bare "sold USDT" (Vanixxx, 2026-10-18)."""
    a, _, load = setup
    load(
        a,
        deposit(at(0), 1000),
        buy(at(0, 1), 1000, 1000, asset="USDT"),
        Movement(
            timestamp=at(1),
            kind=Kind.TRADE,
            incoming_asset="ETH",
            incoming_amount=D("0.5"),
            outgoing_asset="USDT",
            outgoing_amount=D(1000),
        ),
        sell(at(2), "0.5", 1000, asset="ETH"),
    )
    rows = authed.get("/api/tax/origin").json()
    swap = next(r for r in rows if r["kind"] == "swap")
    assert (swap["asset"], swap["into_asset"], swap["into_qty"]) == ("USDT", "ETH", "0.5")
    sale = next(r for r in rows if r["kind"] == "sale")
    first = authed.get(f"/api/tax/origin/{sale['row']}").json()["tree"]["children"][0]
    assert (first["kind"], first["into_asset"]) == ("swap", "ETH")


def test_a_loss_shows_as_a_negative_share_with_overview_and_deposits(setup, authed, db):
    """As Blockpit shows it: 30,000 € own money, −10,000 € loss = 20,000 € (Vanixxx, 2026-10-18)."""
    a, _, load = setup
    load(a, deposit(at(0), 30000), buy(at(0, 1), 1, 30000), sell(at(10), 1, 20000))
    sale = next(r for r in authed.get("/api/tax/origin").json() if r["kind"] == "sale")
    e = authed.get(f"/api/tax/origin/{sale['row']}").json()
    assert {m["kind"]: m["value"] for m in e["mix"]} == {"bank": "30000.00", "loss": "-10000.00"}
    assert e["overview"]["transactions"] == 3 and len(e["overview"]["sources"]) == 1
    assert e["overview"]["channels"] == {"file": 3}
    (dep,) = e["deposits"]
    assert (dep["kind"], dep["value"], dep["share"], dep["channel"]) == (
        "bank",
        "30000.00",
        "30000.00",
        "file",
    )
    for kind, magic in (("pdf", b"%PDF"), ("xlsx", b"PK")):
        f = authed.get(f"/api/tax/origin/{sale['row']}/file?kind={kind}")
        assert f.status_code == 200 and f.content[: len(magic)] == magic


def test_flow_columns_put_origins_before_and_losses_after_their_step():
    from app.modules.tax.origin_flow_pdf import columns

    nodes = [
        {"id": "leaf:bank", "kind": "bank"},
        {"id": "g1", "kind": "stay"},
        {"id": "g2", "kind": "stay"},
        {"id": "leaf:gain", "kind": "gain"},
        {"id": "root", "kind": "root"},
        {"id": "leaf:loss", "kind": "loss"},
    ]
    links = [
        {"source": "leaf:bank", "target": "g1", "value": "100", "loss": False},
        {"source": "g1", "target": "g2", "value": "100", "loss": False},
        {"source": "leaf:gain", "target": "g2", "value": "20", "loss": False},
        {"source": "g2", "target": "root", "value": "120", "loss": False},
        {"source": "g2", "target": "leaf:loss", "value": "10", "loss": True},
    ]
    col = columns(nodes, links)
    # the gain sits right before g2, not in the first column; the loss right after g2
    assert col["leaf:bank"] == 0 and col["g1"] == 1 and col["g2"] == 2
    assert col["leaf:gain"] == 1 and col["leaf:loss"] == 3 and col["root"] == 3
