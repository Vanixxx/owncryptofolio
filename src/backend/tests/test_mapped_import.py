"""Own files with a column mapping (ADR 0048, M13 B)."""

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from openpyxl import Workbook

from app.modules.imports import mapped
from app.modules.plugins.contract import Kind

LEDGER = """txid,refid,time,type,asset,amount,fee
L1,R1,2024-03-01 10:00:00,deposit,EUR,1000.00,0
L2,R2,2024-03-02 11:00:00,trade,EUR,-500.00,1.00
L3,R2,2024-03-02 11:00:00,trade,BTC,0.0100000,0
L4,R3,2024-03-05 12:00:00,staking,DOT,0.5,0
L5,R4,2024-03-06 13:00:00,withdrawal,BTC,-0.0050000,0.0001
L6,R5,2024-03-07 13:00:00,transfer,BTC,0.1,0
L7,R6,2024-03-08 13:00:00,deposit,ETH,1.5,0
"""

TRADES = """Export Mein Konto 2024
Datum;Paar;Seite;Menge;Preis;Gebühr
02.03.2024 11:00;BTC/EUR;Kauf;0,01;50.000,00;0,5 EUR
03.03.2024 09:30;ETH-EUR;Verkauf;1,5;3.000,00;1,2 EUR
04.03.2024 09:30;SOLUSDT;Kauf;2;100;
"""


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_movement_form_is_recognised_and_read(tmp_path):
    path = _write(tmp_path, "ledger.csv", LEDGER)
    info = mapped.inspect(path, timezone="UTC")
    m = mapped.Mapping.model_validate(info["mapping"])
    assert m.form == "movement" and m.header_row == 0 and m.delimiter == ","
    assert m.columns["date"] == "time" and m.columns["type"] == "type"
    assert m.columns["asset"] == "asset" and m.columns["amount"] == "amount"
    assert m.columns["fee_amount"] == "fee"
    # words of the type column, as far as they are known
    assert m.values == {
        "deposit": "deposit",
        "trade": "trade",
        "staking": "income",
        "withdrawal": "withdrawal",
        "transfer": "internal",  # between own accounts at the exchange
    }
    assert info["distinct"]["type"] == ["deposit", "staking", "trade", "transfer", "withdrawal"]
    # a word not mapped is a problem with its row number, never guessed
    del m.values["transfer"]
    out = mapped.read(path, m)
    assert [p["row"] for p in out["problems"]] == [7]
    assert out["problems"][0]["message"] == "unmapped:transfer"
    m.values["transfer"] = "ignore"
    out = mapped.read(path, m)
    assert out["problems"] == [] and out["skipped"] == 1
    rows = [mv for _, mv in out["movements"]]
    kinds = [r.kind for r in rows]
    assert kinds == [Kind.FIAT_DEPOSIT, Kind.TRADE, Kind.INCOME, Kind.SEND, Kind.RECEIVE]
    trade = rows[1]  # two rows with the same id: minus out, plus in, fee kept
    assert (trade.outgoing_asset, trade.outgoing_amount) == ("EUR", Decimal("500.00"))
    assert (trade.incoming_asset, trade.incoming_amount) == ("BTC", Decimal("0.0100000"))
    assert (trade.fee_asset, trade.fee_amount) == ("EUR", Decimal("1.00"))
    send = rows[3]
    assert send.outgoing_amount == Decimal("0.0050000") and send.fee_amount == Decimal("0.0001")
    assert rows[0].timestamp == datetime(2024, 3, 1, 10, tzinfo=UTC)
    for r in rows:
        r.check()


def test_trade_form_with_comma_decimals_and_a_title_line(tmp_path):
    path = _write(tmp_path, "trades.csv", TRADES)
    info = mapped.inspect(path, timezone="Europe/Berlin")
    m = mapped.Mapping.model_validate(info["mapping"])
    assert m.form == "trade" and m.header_row == 1 and m.delimiter == ";" and m.decimal == ","
    assert m.values == {"Kauf": "buy", "Verkauf": "sell"}
    assert m.columns["pair"] == "Paar" and m.columns["price"] == "Preis"
    out = mapped.read(path, m)
    assert out["problems"] == [] and out["date_format"] == "%d.%m.%Y %H:%M"
    buy, sell, sol = (mv for _, mv in out["movements"])
    # local time of the setting: 11:00 in Berlin is 10:00 UTC
    assert buy.timestamp == datetime(2024, 3, 2, 10, tzinfo=UTC)
    assert (buy.incoming_asset, buy.incoming_amount) == ("BTC", Decimal("0.01"))
    assert (buy.outgoing_asset, buy.outgoing_amount) == ("EUR", Decimal("500.0000"))
    assert (buy.fee_asset, buy.fee_amount) == ("EUR", Decimal("0.5"))
    assert (sell.incoming_asset, sell.incoming_amount) == ("EUR", Decimal("4500.0000"))
    assert (sol.incoming_asset, sol.outgoing_asset) == ("SOL", "USDT")
    assert sol.fee_amount is None


def test_xlsx_with_real_dates(tmp_path):
    wb = Workbook()
    wb.active.append(["Date", "Type", "Coin", "Amount"])
    wb.active.append([datetime(2024, 5, 1, 8, 30), "Reward", "ADA", 12.5])
    path = tmp_path / "f.xlsx"
    wb.save(path)
    info = mapped.inspect(path, timezone="UTC")
    m = mapped.Mapping.model_validate(info["mapping"])
    assert m.values == {"Reward": "income"}
    ((n, mv),) = mapped.read(path, m)["movements"]
    assert n == 2 and mv.timestamp == datetime(2024, 5, 1, 8, 30, tzinfo=UTC)
    assert (mv.incoming_asset, mv.incoming_amount) == ("ADA", Decimal("12.5"))


@pytest.mark.parametrize(
    ("text", "decimal", "value"),
    [
        ("1.234,56", ",", "1234.56"),
        ("1,234.56", ".", "1234.56"),
        ("-0,5", ",", "-0.5"),
        ("0.001 BNB", ".", "0.001"),
        ("1e-5", ".", "0.00001"),
    ],
)
def test_numbers(text, decimal, value):
    assert mapped.number(text, decimal)[0] == Decimal(value)


def test_unit_next_to_the_number():
    assert mapped.number("0.001 BNB", ".") == (Decimal("0.001"), "BNB")
    assert mapped.number("$0.01", ".") == (Decimal("0.01"), "USD")


def test_dates_in_utc_and_epoch():
    assert mapped.when("2024-01-01 10:00:00 UTC", None, None, "Europe/Berlin").hour == 10
    assert mapped.when("1704103200000", None, None, "UTC") == datetime(2024, 1, 1, 10, tzinfo=UTC)
    assert mapped.detect_format(["13/01/2024 10:00", "01/02/2024 10:00"]) == "%d/%m/%Y %H:%M"


def _src(authed) -> int:
    authed.post("/api/sources", json={"provider": "manual", "label": "Bitpanda"})
    return authed.get("/api/sources").json()[0]["id"]


def _post(authed, url, sid, path, **data):
    with path.open("rb") as fh:
        return authed.post(
            url, data={"source_id": str(sid), **data}, files={"file": (path.name, fh)}
        )


def test_api_inspect_preview_import_and_keep_the_mapping(authed, tmp_path, env):
    sid = _src(authed)
    path = _write(tmp_path, "ledger.csv", LEDGER)
    info = _post(authed, "/api/imports/mapped/inspect", sid, path).json()
    assert info["saved"] is False and info["rows"] == 7
    m = info["mapping"] | {"timezone": "UTC"}
    m["values"]["transfer"] = "ignore"
    m["columns"]["id"] = "refid"
    pre = _post(authed, "/api/imports/mapped/preview", sid, path, mapping=json.dumps(m)).json()
    assert (pre["new"], pre["skipped"], pre["rejected"]) == (5, 1, 0)
    assert pre["rows"][1]["kind"] == "trade" and pre["rows"][1]["incoming"] == ["BTC", "0.0100000"]
    run = _post(authed, "/api/imports/mapped", sid, path, mapping=json.dumps(m)).json()
    assert run["added"] == 5
    (folder,) = (env / "data" / "originals" / str(sid)).iterdir()
    assert (
        json.loads((folder / "mapping@owncryptofolio.json").read_text())["columns"]["id"] == "refid"
    )
    # the next file of this source starts from the kept mapping
    again = _post(authed, "/api/imports/mapped/inspect", sid, path).json()
    assert again["saved"] is True and again["mapping"]["values"]["transfer"] == "ignore"
    pre = _post(authed, "/api/imports/mapped/preview", sid, path, mapping=json.dumps(m)).json()
    assert pre["duplicates"] == 5 and pre["new"] == 0


def test_api_refuses_wallets_and_broken_mappings(authed, tmp_path):
    sid = _src(authed)
    path = _write(tmp_path, "ledger.csv", LEDGER)
    r = _post(authed, "/api/imports/mapped/preview", sid, path, mapping='{"form": "nope"}')
    assert r.status_code == 400 and r.json()["error"]["code"] == "imports.mapping_invalid"
    r = _post(
        authed,
        "/api/imports/mapped/preview",
        sid,
        path,
        mapping=json.dumps({"columns": {"date": "missing"}}),
    )
    assert r.json()["error"]["code"] == "imports.mapped_unreadable"


COINBASE = """Transactions
User,x,y

ID,Timestamp,Transaction Type,Asset,Quantity Transacted,Price Currency,Price at Transaction,Subtotal,Total (inclusive of fees and/or spread),Fees and/or Spread,Notes
a1,2024-01-02 10:00:00 UTC,Buy,BTC,0.01,EUR,€40000.00,€400.00,€405.00,€5.00,Bought
a2,2024-01-03 10:00:00 UTC,Retail Staking Transfer,ETH,1,EUR,€2000,€2000,€2000,€0.00,
a3,2024-01-04 10:00:00 UTC,Sell,BTC,0.005,EUR,€42000.00,€210.00,€208.00,€2.00,Sold
a4,2024-01-05 10:00:00 UTC,Convert,ETH,-0.1,EUR,€2000,€200,€200,€0,Converted 0.1 ETH to 0.003 BTC
a5,2024-01-05 10:00:00 UTC,Convert,BTC,0.003,EUR,€2000,€200,€200,€0,Converted 0.1 ETH to 0.003 BTC
"""


def test_whole_trades_in_one_row(tmp_path):
    """Coinbase: buy and sell with their counter value in one row, transfers left open."""
    path = _write(tmp_path, "cb.csv", COINBASE)
    m = mapped.Mapping.model_validate(mapped.inspect(path, timezone="UTC")["mapping"])
    assert m.header_row == 3
    assert (
        m.columns["counter_asset"] == "Price Currency" and m.columns["counter_amount"] == "Subtotal"
    )
    # an own-account move is no income; a "Convert" is read from its note
    assert m.values == {
        "Buy": "buy",
        "Sell": "sell",
        "Retail Staking Transfer": "internal",
        "Convert": "convert",
    }
    out = mapped.read(path, m)
    assert out["problems"] == []
    buy, staking, sell, convert = (mv for _, mv in out["movements"])
    assert staking.kind is Kind.INTERNAL_TRANSFER and staking.incoming_amount == Decimal("1")
    assert (convert.outgoing_asset, convert.outgoing_amount) == ("ETH", Decimal("0.1"))
    assert (convert.incoming_asset, convert.incoming_amount) == ("BTC", Decimal("0.003"))
    assert (buy.incoming_asset, buy.incoming_amount) == ("BTC", Decimal("0.01"))
    assert (buy.outgoing_asset, buy.outgoing_amount) == ("EUR", Decimal("400.00"))
    assert (buy.fee_asset, buy.fee_amount) == ("EUR", Decimal("5.00"))
    assert (sell.incoming_asset, sell.incoming_amount) == ("EUR", Decimal("210.00"))


def test_a_list_of_one_kind_without_type_column(tmp_path):
    path = _write(tmp_path, "dep.csv", "Time,Crypto,Deposit Amount\n2024-01-01 10:00,ETH,1.5\n")
    m = mapped.Mapping.model_validate(mapped.inspect(path, timezone="UTC")["mapping"])
    with pytest.raises(mapped.Problem, match="roles:type"):
        mapped.read(path, m)
    m.kind = "deposit"
    ((_, mv),) = mapped.read(path, m)["movements"]
    assert mv.kind is Kind.RECEIVE and (mv.incoming_asset, mv.incoming_amount) == (
        "ETH",
        Decimal("1.5"),
    )


KRAKEN = """txid,refid,time,type,asset,amount,fee
L1,R1,2024-03-02 11:00:00,spend,EUR,-100.00,1.00
L2,R1,2024-03-02 11:00:00,receive,BTC,0.002,0
L3,R2,2024-03-03 11:00:00,receive,ETH,1,0
L4,R3,2024-03-04 11:00:00,spend,EUR,-50.00,0.5
L5,R3,2024-03-04 11:00:00,receive,SOL,0.5,0
L6,R4,2024-03-05 11:00:00,receive,DOT,2,0
L7,R5,2024-03-06 11:00:00,receive,ADA,9,0
"""


def test_halves_of_a_trade_found_by_their_shared_id(tmp_path):
    """Kraken's instant buy: "spend" and "receive" share a refid with opposite signs."""
    path = _write(tmp_path, "k.csv", KRAKEN)
    m = mapped.Mapping.model_validate(mapped.inspect(path, timezone="UTC")["mapping"])
    assert m.values["spend"] == "trade"
    # "receive" pairs only in 2 of 5 rows: a deposit word, not guessed as a trade half
    assert m.values["receive"] == "deposit"
