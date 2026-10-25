from decimal import Decimal

from integrations.bitget_api.reader import convert_futures, convert_spot, windows

TS = "1709290800000"  # 2024-03-01 11:00 UTC


def rec(**kw):
    return {"id": kw.pop("id", "1"), "ts": TS, "fee": "0", **kw}


def test_trade_pair_becomes_one_movement():
    ms = list(
        convert_spot(
            [
                rec(
                    id="1",
                    bizOrderId="A",
                    coin="BTC",
                    amount="0.01",
                    spotTaxType="Buy",
                    fee="-0.00001",
                ),
                rec(id="2", bizOrderId="A", coin="USDT", amount="-600", spotTaxType="Buy"),
            ]
        )
    )
    assert len(ms) == 1
    m = ms[0]
    assert (m.kind.value, m.incoming_asset, m.outgoing_asset) == ("trade", "BTC", "USDT")
    assert m.outgoing_amount == Decimal(600) and m.fee_amount == Decimal("0.00001")
    assert m.timestamp.hour == 11


def test_migration_pair():
    ms = list(
        convert_spot(
            [
                rec(
                    id="1",
                    bizOrderId="M",
                    coin="POL",
                    amount="10",
                    spotTaxType="Increase exchange rate",
                ),
                rec(
                    id="2",
                    bizOrderId="M",
                    coin="MATIC",
                    amount="-10",
                    spotTaxType="Reduce exchange rate",
                ),
            ]
        )
    )
    assert [m.kind.value for m in ms] == ["migration"]


def test_ambiguous_pair_is_not_guessed():
    ms = list(
        convert_spot(
            [
                rec(id="1", bizOrderId="X", coin="A", amount="1", spotTaxType="Buy"),
                rec(id="2", bizOrderId="X", coin="B", amount="2", spotTaxType="Buy"),
            ]
        )
    )
    assert [m.kind.value for m in ms] == ["other", "other"]


def test_singles():
    ms = {
        m.kind.value: m
        for m in convert_spot(
            [
                rec(id="1", coin="USDT", amount="100", spotTaxType="Deposit"),
                rec(id="2", coin="EUR", amount="50", spotTaxType="fiat_recharge_in"),
                rec(id="3", coin="USDT", amount="-20", spotTaxType="Withdrawal", fee="-1"),
            ]
        )
    }
    assert ms["receive"].incoming_amount == Decimal(100)
    assert ms["fiat_deposit"].incoming_asset == "EUR"
    assert ms["send"].outgoing_amount == Decimal(20) and ms["send"].fee_amount == Decimal(1)


def test_futures_records():
    ms = list(
        convert_futures(
            [
                {
                    "id": "1",
                    "ts": TS,
                    "symbol": "BTCUSDT",
                    "marginCoin": "USDT",
                    "futureTaxType": "close_long",
                    "amount": "12.5",
                    "fee": "-0.3",
                },
                {
                    "id": "2",
                    "ts": TS,
                    "symbol": "BTCUSDT",
                    "marginCoin": "USDT",
                    "futureTaxType": "contract_margin_settle_fee",
                    "amount": "-0.02",
                    "fee": "0",
                },
                {
                    "id": "3",
                    "ts": TS,
                    "symbol": "BTCUSDT",
                    "marginCoin": "USDT",
                    "futureTaxType": "adjust_margin_ifm",
                    "amount": "100",
                    "fee": "0",
                },
            ]
        )
    )
    assert [(m.kind.value, m.market.value) for m in ms] == [
        ("realized_pnl", "futures"),
        ("funding", "futures"),
    ]
    assert ms[1].outgoing_amount == Decimal("0.02")
    for m in ms:
        m.check()


def test_windows_cover_the_range_in_30_day_steps():
    from datetime import UTC, datetime

    a, b = datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 3, 15, tzinfo=UTC)
    spans = list(windows(a, b))
    assert spans[0][0] == a and spans[-1][1] == b and len(spans) == 3
    assert all((e - s).days <= 30 for s, e in spans)


def test_rate_limit_is_retried_and_spaced(monkeypatch):
    from integrations.bitget_api import reader

    pauses = []
    monkeypatch.setattr(reader, "_sleep", pauses.append)
    calls = {"n": 0}

    def flaky(params):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise RuntimeError('bitget {"code":"429","msg":"Too Many Requests"}')
        return {"data": [{"id": "1"}]}

    assert reader._paged(flaky, {}) == [{"id": "1"}]
    assert calls["n"] == 3
    assert 2 in pauses and 5 in pauses  # growing pauses after each 429


def test_other_errors_are_not_retried(monkeypatch):
    import pytest

    from integrations.bitget_api import reader

    monkeypatch.setattr(reader, "_sleep", lambda s: None)

    def broken(params):
        raise RuntimeError("40012 apikey/password is incorrect")

    with pytest.raises(RuntimeError, match="40012"):
        reader._paged(broken, {})
