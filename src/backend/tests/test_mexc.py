from datetime import UTC
from decimal import Decimal

import pytest
from openpyxl import Workbook

from integrations.mexc_api.reader import trade, transfer
from integrations.mexc_file.reader import read, skipped


def xlsx(path, rows):
    wb = Workbook()
    for r in rows:
        wb.active.append(r)
    wb.save(path)
    return path


RANGE = "2024-10-01-2026-08-24"


@pytest.fixture
def export(tmp_path):
    xlsx(
        tmp_path / f"Spot-Spot Trade History-{RANGE}.xlsx",
        [
            [
                "UID",
                "Pairs",
                "Time",
                "Side",
                "Filled Price",
                "Executed Amount",
                "Total",
                "Fee",
                "Role",
            ],
            [
                "1",
                "FET_USDT",
                "2025-02-03 21:13:10",
                "Buy",
                "0.839",
                "96.81",
                "81.22",
                "0.08USDT",
                "Taker",
            ],
        ],
    )
    xlsx(
        tmp_path / f"Funding History-Withdrawal History-{RANGE}.xlsx",
        [
            [
                "UID",
                "Status",
                "Time",
                "Crypto",
                "Network",
                "Request Amount",
                "Withdrawal Address",
                "memo",
                "TxID",
                "Trading Fee",
                "Settlement Amount",
            ],
            [
                "1",
                "Withdrawal Successful",
                "2025-01-08 22:44:44",
                "USDT",
                "BSC",
                "110",
                "0xabc",
                "",
                "0xtx",
                "1",
                "109",
            ],
        ],
    )
    # this one carries the time-zone label the unlabelled siblings inherit
    xlsx(
        tmp_path / f"Futures-Futures Capital Flow-{RANGE}.xlsx",
        [
            [
                "UID",
                "Time(UTC+02:00)",
                "Futures Trading Pair",
                "Crypto",
                "Fund Type",
                "Fund Flow Type",
                "Amount",
            ],
            ["1", "2025-07-09 22:08:17", "BTCUSDT", "USDT", "CLOSE_POSITION", "Inflow", "0.08"],
            ["1", "2025-07-09 22:00:00", "BTCUSDT", "USDT", "FEE", "Outflow", "-0.01"],
            ["1", "2025-07-09 21:00:00", "BTCUSDT", "USDT", "BONUS_DEDUCT", "Outflow", "-5"],
        ],
    )
    xlsx(
        tmp_path / f"Spot-Spot Statement-{RANGE}.xlsx",
        [["UID", "Transaction Type"], ["1", "Spot Trading"]],
    )
    return tmp_path


def test_reads_spot_and_futures_with_sibling_time_zone(export):
    ms = {
        m.kind.value + ":" + m.market.value: m for m in read(export, {"timezone": "Europe/Berlin"})
    }
    assert ms["trade:spot"].timestamp.hour == 19  # 21:13 at UTC+2
    assert ms["trade:spot"].fee_asset == "USDT"
    send = ms["send:spot"]
    assert (send.outgoing_amount, send.fee_amount, send.timestamp.hour) == (
        Decimal(109),
        Decimal(1),
        20,
    )
    assert ms["fee:futures"].fee_amount == Decimal("0.01")
    assert ms["realized_pnl:futures"].incoming_amount == Decimal("0.08")
    assert all("BONUS" not in (m.comment or "") for m in ms.values())
    for m in ms.values():
        m.check()


def test_german_export_with_time_zone_from_download_stamp(tmp_path):
    # Downloaded 2025-01-14 (winter, UTC+1): 21:44:44 local is 20:44:44 UTC.
    xlsx(
        tmp_path / "Auszahlungsverlauf-20230723-20250114_1736892468027.xlsx",
        [
            [
                "Status",
                "Zeit",
                "Krypto",
                "Netzwerk",
                "Angeforderter Betrag",
                "Auszahlungsadresse",
                "TxID",
                "Handelsgebühr",
                "Abrechnungsbetrag",
            ],
            [
                "Auszahlung erfolgreich",
                "2025-01-08 21:44:44",
                "USDT",
                "BSC",
                "110",
                "0xabc",
                "0xtx",
                "0",
                "110",
            ],
        ],
    )
    xlsx(
        tmp_path / "SPOT_Handelsverlauf exportieren-2025-01-14 23_09_48.xlsx",
        [
            [
                "Paare",
                "Zeit",
                "Seite",
                "Realisierter Preis",
                "Ausgeführter Betrag",
                "Gesamt",
                "Gebühr",
                "Rolle",
            ],
            [
                "ZEPH_USDT",
                "2024-04-01 13:02:45",
                "Kaufen",
                "14.43",
                "0.36",
                "5.19",
                "0.0052",
                "Maker",
            ],
        ],
    )
    send, buy = sorted(read(tmp_path, {"timezone": "Europe/Berlin"}), key=lambda m: m.kind.value)
    assert (send.kind.value, send.timestamp.hour, send.timestamp.tzinfo.utcoffset(None)) == (
        "send",
        20,
        UTC.utcoffset(None),
    )
    assert (buy.incoming_asset, buy.fee_asset) == ("ZEPH", "USDT")  # fee without unit: quote


def test_same_withdrawal_in_two_exports_gets_same_utc_time(tmp_path):
    xlsx(
        tmp_path / "Auszahlungsverlauf-20230723-20250114_1736892468027.xlsx",
        [
            [
                "Status",
                "Zeit",
                "Krypto",
                "Netzwerk",
                "Angeforderter Betrag",
                "Auszahlungsadresse",
                "TxID",
                "Handelsgebühr",
                "Abrechnungsbetrag",
            ],
            [
                "Auszahlung erfolgreich",
                "2025-01-08 21:44:44",
                "USDT",
                "BSC",
                "110",
                "0xabc",
                "0xtx",
                "0",
                "110",
            ],
        ],
    )
    xlsx(
        tmp_path / "Withdrawal History-20240131-20250724_1753390352026.xlsx",
        [
            [
                "Status",
                "Time",
                "Crypto",
                "Network",
                "Request Amount",
                "Withdrawal Address",
                "TxID",
                "Trading Fee",
                "Settlement Amount",
            ],
            [
                "Withdrawal Successful",
                "2025-01-08 22:44:44",
                "USDT",
                "BSC",
                "110",
                "0xabc",
                "0xtx",
                "0",
                "110",
            ],
        ],
    )
    a, b = list(read(tmp_path, {"timezone": "Europe/Berlin"}))
    assert a.timestamp == b.timestamp  # -> same fingerprint, recognised as duplicate


def test_withdrawal_that_does_not_add_up_is_rejected(tmp_path):
    xlsx(
        tmp_path / f"Funding History-Withdrawal History-{RANGE}.xlsx",
        [
            [
                "Status",
                "Time(UTC+02:00)",
                "Crypto",
                "Request Amount",
                "Trading Fee",
                "Settlement Amount",
            ],
            ["Withdrawal Successful", "2025-01-08 22:44:44", "USDT", "110", "1", "100"],
        ],
    )
    with pytest.raises(ValueError, match="does not add up"):
        list(read(tmp_path, {}))


def test_unknown_files_are_named(export):
    assert any("Statement" in n for n in skipped(export))


def test_api_conversion():
    t = trade(
        {
            "symbol": "FET/USDT",
            "side": "sell",
            "amount": 10,
            "cost": 8.5,
            "id": "1",
            "timestamp": 1738613590000,
            "fee": {"currency": "USDT", "cost": 0.0085},
        }
    )
    assert (t.outgoing_asset, t.incoming_asset, t.incoming_amount) == (
        "FET",
        "USDT",
        Decimal("8.5"),
    )
    d = transfer(
        {
            "currency": "USDT",
            "amount": 50,
            "timestamp": 1738613590000,
            "txid": "0x1",
            "fee": {"currency": "USDT", "cost": 1},
        },
        incoming=True,
    )
    assert d.kind.value == "receive" and d.fee_amount is None


def test_every_api_query_spans_at_most_seven_days(monkeypatch):
    """MEXC rejects any trade, deposit or withdrawal query over 7 days (code 33333)."""
    from integrations.mexc_api import reader

    spans: list[tuple[str, int]] = []

    class FakeMexc:
        markets = {"BTC/USDT": {}}

        def load_markets(self):
            pass

        def fetch_balance(self):
            return {"total": {"BTC": 1}}

        def _query(self, name, since, params):
            spans.append((name, params["endTime"] - since))
            return []

        def fetch_my_trades(self, pair, since, limit, params):
            return self._query("trades", since, params)

        def fetch_deposits(self, since, params):
            return self._query("deposits", since, params)

        def fetch_withdrawals(self, since, params):
            return self._query("withdrawals", since, params)

    monkeypatch.setattr(reader, "_client", lambda _c: FakeMexc())
    assert list(reader.fetch({}, None)) == []
    assert {n for n, _ in spans} == {"trades", "deposits", "withdrawals"}
    assert max(ms for _, ms in spans) <= 7 * 24 * 3600 * 1000


def test_german_futures_flow_and_bonus_as_income(tmp_path):
    """Old German exports (Vanixxx, 2026-10-11): the capital flow and the position history
    are read; a bonus is income, its deduction is skipped, an unused bonus leaves again."""
    xlsx(
        tmp_path / "MEXC - Futures-Mittelfluss-20240115-20250114_1736892812028.xlsx",
        [
            [
                "Zeit(UTC+01:00)",
                "Futures-Handelspaar",
                "Krypto",
                "Mittelart",
                "Art des Mittelflusses",
                "Betrag",
            ],
            ["2024-11-03 03:52:07", "", "USDT", "BONUS_DEDUCT", "Outflow", "-29.6"],
            ["2024-11-03 03:52:07", "POL_USDT", "USDT", "LIQUIDATION", "Outflow", "-29.5"],
            ["2024-10-27 08:51:35", "", "USDT", "BONUS", "Inflow", "30"],
            ["2024-09-10 11:33:10", "", "USDT", "TRANSFER", "Inflow", "53.53"],
            ["2024-06-25 17:21:15", "", "USDT", "BONUS", "Outflow", "-20"],
        ],
    )
    xlsx(
        tmp_path / "FUTURE_Positionsverlauf-20240115-20250114_1736892768028.xlsx",
        [
            [
                "Handelspaar",
                "Öffnungszeiten(UTC+01:00)",
                "Schließzeiten",
                "Margin-Modus",
                "Durchschn. Einstiegspreis",
                "Durchschn. Schlusskurs",
                "Richtung",
                "Schließmenge (Kontr.)",
                "Gebühr",
                "Realisierte PNL",
                "Status",
            ],
            [
                "POL_USDT",
                "2024-10-30 19:35:30",
                "2024-11-03 03:52:07",
                "Isoliert",
                "0.33",
                "0.30",
                "Long",
                "89",
                "0.11USDT",
                "-30USDT",
                "Alle geschlossen",
            ],
        ],
    )
    ms = list(read(tmp_path, {"timezone": "Europe/Berlin"}))
    by = {(m.kind.value, m.comment): m for m in ms}
    assert (
        ("other", "BONUS_DEDUCT") not in by and ("fee", "BONUS_DEDUCT") not in by and len(ms) == 5
    )
    bonus = by[("income", "BONUS")]
    assert bonus.incoming_amount == Decimal(30) and bonus.income_kind.value == "reward"
    assert by[("fee", "BONUS")].fee_amount == Decimal(20)  # ran out unused: a futures cost
    liq = by[("realized_pnl", "LIQUIDATION")]
    assert liq.instrument == "POLUSDT" and liq.timestamp.hour == 2  # 03:52 at UTC+1
    assert by[("internal_transfer", "TRANSFER")].incoming_amount == Decimal("53.53")
    pos = next(m for m in ms if m.kind.value == "futures_position")
    assert pos.instrument == "POL_USDT" and pos.comment == "Long Isolated"
    for m in ms:
        m.check()


def test_trades_are_paged_within_a_window_and_pairs_come_from_transfers_too(monkeypatch):
    """A full page asks again from its newest millisecond; a coin only deposited and sold
    again in the period is still asked for (review 2026-10-24)."""
    from integrations.mexc_api import reader

    monkeypatch.setattr(reader, "TRADE_LIMIT", 2)
    asked: list[str] = []

    def row(i):
        return {
            "id": str(i),
            "timestamp": 1_700_000_000_000 + i,
            "symbol": "SOL/USDT",
            "side": "buy",
            "amount": 1,
            "price": 1,
            "cost": 1,
            "fee": None,
        }

    class FakeMexc:
        markets = {"SOL/USDT": {}}

        def load_markets(self):
            pass

        def fetch_balance(self):
            return {"total": {}}

        def fetch_my_trades(self, pair, since, limit, params):
            asked.append(pair)
            start = self.start = getattr(self, "start", since)  # five trades in the window
            rows = [row(i) | {"timestamp": start + i} for i in range(5)]
            return [r for r in rows if r["timestamp"] >= since][:limit]

        def fetch_deposits(self, since, params):
            return [{"currency": "SOL", "status": "ok"}] if not asked else []

        def fetch_withdrawals(self, since, params):
            return []

    monkeypatch.setattr(reader, "_client", lambda _c: FakeMexc())
    monkeypatch.setattr(reader, "transfer", lambda t, incoming: t)
    monkeypatch.setattr(reader, "trade", lambda t: t["id"])
    monkeypatch.setattr(reader, "HISTORY_DAYS", 1)
    out = list(reader.fetch({}, None))
    assert set(asked) == {"SOL/USDT"}
    assert sorted(x for x in out if isinstance(x, str)) == ["0", "1", "2", "3", "4"]
