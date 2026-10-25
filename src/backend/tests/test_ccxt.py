"""The ccxt plugin for every other exchange (ADR 0048), against a stand-in exchange."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import ccxt
import pytest

from app.modules.plugins.contract import Kind
from app.modules.plugins.manifest import CcxtInfo, Channel, Manifest
from app.modules.plugins.registry import discover
from integrations.ccxt_api import reader


def test_one_plugin_per_exchange_own_plugins_win():
    reg = discover()
    assert "ccxt_api" not in reg.plugins and reg.errors == {}
    # Bitget, MEXC and Coinbase keep their own, tested API plugins
    for own in ("bitget", "mexc", "coinbase"):
        assert reg.find(own, Channel.API).key == f"{own}_api"
    kraken = reg.plugins["ccxt_api:kraken"]
    assert kraken.manifest.plugin.status == "beta"
    assert kraken.manifest.source.provider_name == "Kraken"
    # the file import of Kraken stays tested next to the beta API
    assert reg.plugins["kraken_file"].manifest.plugin.status == "tested"
    # each exchange asks for what it needs: KuCoin also a passphrase
    kucoin = reg.plugins["ccxt_api:kucoin"].manifest.credentials
    assert kucoin.fields == ["api_key", "api_secret", "api_passphrase"]
    assert kucoin.secret == ["api_secret", "api_passphrase"]
    # wallet-key exchanges and futures-only ones are left out
    assert "ccxt_api:hyperliquid" not in reg.plugins
    assert "ccxt_api:binanceusdm" not in reg.plugins
    assert len([k for k in reg.plugins if k.startswith("ccxt_api:")]) > 40


def test_tested_list_drops_the_badge():
    names = {eid: m.plugin.status for eid, m, _ in reader.expand(_manifest(tested=["kraken"]))}
    assert names["kraken"] == "tested" and names["binance"] == "beta"


def _manifest(**ccxt_info):
    m = Manifest.load(Path(reader.__file__).with_name("plugin.toml"))
    m.ccxt = CcxtInfo(**ccxt_info)
    return m


T0 = int(datetime(2024, 1, 1, tzinfo=UTC).timestamp() * 1000)


class Fake:
    """Answers like a ccxt exchange that only gives trades per pair and pages by time."""

    has = {"fetchDeposits": True, "fetchWithdrawals": True}
    markets = {"BTC/EUR": {"spot": True}, "ETH/USDT": {"spot": True}, "BTC/USDT:USDT": {}}

    def __init__(self):
        self.calls = []

    def load_markets(self):
        return self.markets

    def fetch_balance(self, params=None):
        return {"total": {"BTC": 0.5, "EUR": 0}}

    def _page(self, rows, since):
        rows = [r for r in rows if since is None or r["timestamp"] >= since]
        return rows[:2]  # two per page

    def fetch_deposits(self, code=None, since=None, limit=None):
        rows = [
            {"id": "d1", "timestamp": T0, "currency": "EUR", "amount": 100, "status": "ok"},
            {"id": "d2", "timestamp": T0 + 1, "currency": "ETH", "amount": 1, "status": "ok"},
            {"id": "d3", "timestamp": T0 + 2, "currency": "ETH", "amount": 9, "status": "failed"},
        ]
        return self._page(rows, since)

    def fetch_withdrawals(self, code=None, since=None, limit=None):
        rows = [
            {
                "id": "w1",
                "timestamp": T0 + 5,
                "currency": "ETH",
                "amount": 0.5,
                "fee": {"currency": "ETH", "cost": 0.01},
                "status": "ok",
            }
        ]
        return self._page(rows, since)

    def fetch_my_trades(self, symbol=None, since=None, limit=None):
        if symbol is None:
            raise ccxt.ArgumentsRequired("symbol required")
        self.calls.append(symbol)
        if symbol != "BTC/EUR":
            return []
        rows = [
            {
                "id": f"t{i}",
                "timestamp": T0 + 10 + i,
                "symbol": "BTC/EUR",
                "side": "buy",
                "amount": 0.1,
                "cost": 3000,
                "fee": {"currency": "EUR", "cost": 3},
            }
            for i in range(5)
        ]
        return self._page(rows, since)


@pytest.fixture
def fake(monkeypatch):
    ex = Fake()
    monkeypatch.setattr(reader, "_client", lambda eid, creds: ex)
    return ex


def test_fetch_pages_and_tries_the_pairs_of_moved_coins(fake):
    rows = list(reader.fetch("x", CcxtInfo(), {"api_key": "k"}, None))
    kinds = [r.kind for r in rows]
    assert kinds.count(Kind.RECEIVE) == 2  # the failed deposit is left out
    assert kinds.count(Kind.SEND) == 1
    assert kinds.count(Kind.TRADE) == 5  # three pages of trades
    # coins held (BTC) and moved (EUR, ETH) against the quotes that exist as spot markets
    # (each next page starts at the newest millisecond again, so rows of that millisecond
    # beyond the page edge are not skipped: one row overlaps per page)
    assert sorted(fake.calls) == sorted(["BTC/EUR"] * 5 + ["ETH/USDT"])
    send = next(r for r in rows if r.kind is Kind.SEND)
    assert send.outgoing_amount == Decimal("0.5") and send.fee_amount == Decimal("0.01")


def test_fee_inside_the_amount_per_exchange(fake):
    rows = list(reader.fetch("x", CcxtInfo(fee_in_amount=["x"]), {"api_key": "k"}, None))
    send = next(r for r in rows if r.kind is Kind.SEND)
    assert send.outgoing_amount == Decimal("0.49") and send.fee_amount == Decimal("0.01")


def test_a_refused_start_is_asked_again_without_one():
    calls = []

    def fn(code=None, since=None):
        calls.append(since)
        if since is not None:
            raise ccxt.BadRequest("time range too large")
        return [{"id": "a", "timestamp": 1}]

    assert reader._paged(fn, 5, None) == [{"id": "a", "timestamp": 1}]
    assert calls == [5, None]


def test_a_refused_key_is_not_hidden():
    def fn(code=None, since=None):
        raise ccxt.AuthenticationError("invalid key")

    with pytest.raises(ccxt.AuthenticationError):
        reader._paged(fn, 5, None)


def test_credentials_go_to_ccxt_by_their_names():
    client = reader._client("kucoin", {"api_key": "k", "api_secret": "s", "api_passphrase": "p"})
    assert (client.apiKey, client.secret, client.password) == ("k", "s", "p")
