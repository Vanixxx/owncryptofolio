"""Balance check (ADR 0039): reported against computed per source and market."""

from datetime import UTC, datetime
from decimal import Decimal

from app.modules.balances import service
from app.modules.plugins.contract import Kind, Movement

T = datetime(2025, 1, 22, 12, tzinfo=UTC)


def setup_source(authed, db):
    from app.modules.raw import service as raw
    from app.modules.sources.models import Source

    authed.post("/api/sources", json={"provider": "manual", "label": "Gate.io"})
    source = db.query(Source).one()
    raw.import_movements(
        db,
        source,
        "manual",
        "m",
        [
            Movement(
                timestamp=T,
                kind=Kind.TRADE,
                incoming_asset="ETH",
                incoming_amount=Decimal("2"),
                outgoing_asset="USDT",
                outgoing_amount=Decimal("5000"),
                fee_asset="ETH",
                fee_amount=Decimal("0.01"),
            ),
            Movement(
                timestamp=T,
                kind=Kind.RECEIVE,
                incoming_asset="USDT",
                incoming_amount=Decimal("5000"),
            ),
        ],
    )
    return source


def by_asset(authed, sid):
    entry = next(e for e in authed.get("/api/balances").json() if e["source_id"] == sid)
    return entry, {i["asset"]: i for i in entry["items"]}


def test_unchecked_until_a_balance_is_known_then_ok_or_diff(authed, db):
    source = setup_source(authed, db)
    entry, items = by_asset(authed, source.id)
    assert (
        entry["status"] == "none"
        and items["ETH"]["computed"] == "1.99"
        and items["ETH"]["ok"] is None
    )
    assert "USDT" not in items  # computes to zero on both sides: nothing to show
    assert (
        authed.post(
            f"/api/balances/{source.id}", json={"asset": "eth", "amount": "1,99"}
        ).status_code
        == 204
    )
    entry, items = by_asset(authed, source.id)
    assert entry["status"] == "ok" and items["ETH"]["actual"] == "1.99"
    authed.post(
        f"/api/balances/{source.id}", json={"asset": "ETH", "amount": "2.5"}
    )  # the latest one counts
    entry, items = by_asset(authed, source.id)
    assert (
        entry["status"] == "diff" and entry["differences"] == 1 and items["ETH"]["diff"] == "-0.51"
    )
    bad = authed.post(f"/api/balances/{source.id}", json={"asset": "ETH", "amount": "abc"})
    assert bad.json()["error"]["code"] == "balances.invalid_amount"


def test_reported_asset_without_history_is_a_difference_spam_is_not(authed, db):
    from app.modules.prices.models import PriceAsset

    source = setup_source(authed, db)
    service.store(
        db,
        source,
        [
            ("spot", "ETH", Decimal("1.99")),
            ("spot", "ZEPH", Decimal("34.91")),
            ("spot", "SHIBSPAM", Decimal("1")),
        ],
        "api",
    )
    db.add(PriceAsset(asset="SHIBSPAM", ignored=True))
    db.commit()
    entry, items = by_asset(authed, source.id)
    assert items["ZEPH"]["ok"] is False and items["ZEPH"]["computed"] is None
    assert items["SHIBSPAM"]["spam"] is True
    assert entry["differences"] == 1  # ZEPH only; spam does not count


def test_a_failing_balance_never_fails_the_fetch(authed, db):
    source = setup_source(authed, db)

    class Broken:
        @staticmethod
        def balance(credentials):
            raise RuntimeError("exchange down")

    class Without:
        pass

    assert service.after_fetch(db, source, Broken, secrets={"k": "v"}) == {
        "balance_error": "exchange down"
    }
    assert service.after_fetch(db, source, Without, secrets={"k": "v"}) == {}

    class Good:
        @staticmethod
        def balance(credentials):
            return [("spot", "ETH", Decimal("1.99"))]

    assert service.after_fetch(db, source, Good, secrets={"k": "v"}) == {"balance_assets": 1}


def test_evm_balance_reads_native_and_known_tokens(monkeypatch):
    from app.modules.plugins import evm

    calls = []

    def rpc(url, method, params):
        calls.append(method)
        return "0xde0b6b3a7640000" if method == "eth_getBalance" else "0x" + "0" * 63 + "5"

    monkeypatch.setattr(evm, "rpc", rpc)
    out = evm.balances("https://x", "0x" + "a" * 40, "ETH", 18, {"LINK": ("0xc", 0)})
    assert out == [("spot", "ETH", Decimal(1)), ("spot", "LINK", Decimal(5))] and calls == [
        "eth_getBalance",
        "eth_call",
    ]


def test_long_spam_names_are_cut_like_the_raw_layer(authed, db):
    source = setup_source(authed, db)
    name = "Swap your voucher on bio.link/xyz and claim the reward now"
    service.store(db, source, [("spot", name, Decimal(1))], "chain")
    _, items = by_asset(authed, source.id)
    assert name.upper()[:40] in items


def test_missing_coin_is_zero_on_an_exchange_but_unchecked_on_a_chain(authed, db):
    source = setup_source(authed, db)
    service.store(db, source, [("spot", "BTC", Decimal(0))], "chain")
    _, items = by_asset(authed, source.id)
    entry, items = by_asset(authed, source.id)
    assert items["ETH"]["ok"] is None and items["ETH"]["actual"] is None
    assert entry["status"] == "ok" and entry["unchecked"] == 1
    service.store(db, source, [("spot", "BTC", Decimal(0))], "api")
    _, items = by_asset(authed, source.id)
    assert items["ETH"]["ok"] is False and items["ETH"]["actual"] == "0"


def test_a_coin_gone_since_the_last_fetch_is_not_kept_from_an_older_fetch(authed, db):
    source = setup_source(authed, db)
    service.store(
        db, source, [("spot", "ETH", Decimal("1.99")), ("spot", "SLP", Decimal(5))], "api"
    )
    service.store(db, source, [("spot", "ETH", Decimal("1.99"))], "api")
    entry, items = by_asset(authed, source.id)
    assert "SLP" not in items and entry["status"] == "ok"


def test_vtho_grown_by_holding_vet_is_booked_as_income(db):
    """VTHO comes from holding VET, no transfer shows it: after a fetch, what the balance
    holds beyond the transactions is booked once as a reward (Vanixxx, 2026-10-09)."""
    from app.modules.plugins.contract import IncomeKind
    from app.modules.raw import service as raw
    from app.modules.raw.models import RawTransaction
    from app.modules.sources.models import Source

    D = Decimal

    s = Source(provider="vechain", kind="wallet", label="VeChain", address="0x1")
    db.add(s)
    db.commit()
    raw.import_movements(
        db,
        s,
        "chain",
        "Chain",
        [
            Movement(
                timestamp=T, kind=Kind.RECEIVE, incoming_asset="VTHO", incoming_amount=D("100")
            ),
            Movement(
                timestamp=T,
                kind=Kind.SEND,
                outgoing_asset="VET",
                outgoing_amount=D("1"),
                fee_asset="VTHO",
                fee_amount=D("2"),
            ),
        ],
    )
    service.store(db, s, [("spot", "VTHO", D("150"))], "chain")
    assert service.book_accrual(db, s, ["VTHO"]) == {"accrued": {"VTHO": "52"}}
    row = db.query(RawTransaction).filter_by(source_id=s.id, kind="income").one()
    assert row.income_kind == IncomeKind.REWARD.value and row.incoming_amount == D("52")
    # the next fetch without growth books nothing; less than the transactions never
    service.store(db, s, [("spot", "VTHO", D("150"))], "chain")
    assert service.book_accrual(db, s, ["VTHO"]) == {}
    service.store(db, s, [("spot", "VTHO", D("120"))], "chain")
    assert service.book_accrual(db, s, ["VTHO"]) == {}


def test_money_and_dollar_coins_may_be_a_few_cents_apart(authed, db):
    """Exchanges show cents: 0.039 EUR computed against 0.03 reported is right (Vanixxx,
    2026-10-10). A coin keeps the sharp check."""
    source = setup_source(authed, db)
    authed.post(f"/api/balances/{source.id}", json={"asset": "USDT", "amount": "0.04"})
    authed.post(f"/api/balances/{source.id}", json={"asset": "ETH", "amount": "1.98"})
    _, items = by_asset(authed, source.id)
    assert items["USDT"]["ok"] is True and items["ETH"]["ok"] is False


def test_mexc_balance_reads_spot_and_futures(monkeypatch):
    """MEXC's futures account has its own balance (Vanixxx, 2026-10-10: futures stayed unchecked)."""
    from integrations.mexc_api import reader

    class Client:
        def fetch_balance(self, params=None):
            swap = (params or {}).get("type") == "swap"
            return {"total": {"USDT": 87.98} if swap else {"ZEPH": 34.91, "BTC": 0}}

    monkeypatch.setattr(reader, "_client", lambda c: Client())
    assert reader.balance({}) == [
        ("spot", "ZEPH", Decimal("34.91")),
        ("futures", "USDT", Decimal("87.98")),
    ]


def test_a_manual_balance_and_a_fetch_for_the_same_coin_are_not_added_up(authed, db):
    """The newer of the two counts (review 2026-10-24: they were summed, 1.99 became 3.98)."""
    source = setup_source(authed, db)
    service.store(db, source, [("spot", "ETH", Decimal("1.99"))], "manual")
    service.store(db, source, [("spot", "ETH", Decimal("1.99"))], "chain")
    _, items = by_asset(authed, source.id)
    assert items["ETH"]["actual"] == "1.99" and items["ETH"]["ok"] is True
    service.store(db, source, [("spot", "ETH", Decimal(1))], "manual")
    _, items = by_asset(authed, source.id)
    assert items["ETH"]["actual"] == "1"


def test_a_failing_balance_never_shows_the_key(authed, db):
    """The error text of a failed balance call is scrubbed like the fetch (review 2026-10-24)."""
    from types import SimpleNamespace

    source = setup_source(authed, db)

    def boom(secrets):
        raise RuntimeError("GET https://x/api?AccessKeyId=SECRETKEY1234 failed")

    out = service.after_fetch(
        db, source, SimpleNamespace(balance=boom), secrets={"api_key": "SECRETKEY1234"}
    )
    assert "SECRETKEY1234" not in out["balance_error"] and "***" in out["balance_error"]
