from decimal import Decimal

import pytest

from integrations.coinbase_api.reader import _secret, convert
from integrations.coinbase_file.reader import read

HEADER = (
    "ID,Timestamp,Transaction Type,Asset,Quantity Transacted,Price Currency,"
    "Price at Transaction,Subtotal,Total (inclusive of fees and/or spread),"
    "Fees and/or Spread,Notes"
)


def csv_file(tmp_path, rows, name="cb_2024.csv"):
    p = tmp_path / name
    p.write_text("Transactions\nUser,x,y\n" + HEADER + "\n" + "\n".join(rows) + "\n")
    return p


def test_trade_uses_counter_currency_from_note(tmp_path):
    p = csv_file(
        tmp_path,
        [
            "a1,2024-01-02 10:00:00 UTC,Buy,SOL,1.5,USD,$135.84,$203.76,$205.69,$1.93,"
            '"Bought 1.5 SOL for 180.00 EUR on SOL-EUR"'
        ],
    )
    (m,) = read(p)
    assert (m.incoming_asset, m.incoming_amount) == ("SOL", Decimal("1.5"))
    assert (m.outgoing_asset, m.outgoing_amount) == ("EUR", Decimal("180.00"))
    # the note's 180.00 EUR include the fee; the fee column is USD: no fee on top
    assert m.fee_asset is None and m.fee_amount is None


def test_convert_counted_once_and_staking_spread_is_no_fee(tmp_path):
    note = '"Converted 292.322503 USDT to 292.918841 USDC"'
    p = csv_file(
        tmp_path,
        [
            f"c1,2024-01-03 10:00:00 UTC,Convert,USDT,-292.322503,USD,$1,$292,$292,$0,{note}",
            f"c2,2024-01-03 10:00:00 UTC,Convert,USDC,292.918841,USD,$1,$292,$292,$0,{note}",
            "s1,2024-01-04 10:00:00 UTC,Staking Income,ETH,0.001,USD,$2000,$2,$2,$0.05,",
        ],
    )
    trade, income = list(read(p))
    assert (trade.outgoing_asset, trade.incoming_asset) == ("USDT", "USDC")
    assert income.kind.value == "income" and income.fee_amount is None


def test_german_and_damaged_exports_are_rejected(tmp_path):
    p = csv_file(tmp_path, ["x,2024-01-02 10:00:00 UTC,Receive,BTC,57.145.796,USD,,,,,"])
    with pytest.raises(ValueError, match="decimal point"):
        list(read(p))
    g = tmp_path / "de.csv"
    g.write_text("Transaktionen\nID;Zeitstempel\n")
    with pytest.raises(ValueError, match="German"):
        list(read(g))


def test_several_yearly_files_as_folder(tmp_path):
    csv_file(tmp_path, ["r1,2023-05-01 10:00:00 UTC,Receive,BTC,0.1,USD,,,,,"], "cb_2023.csv")
    csv_file(tmp_path, ["r2,2024-05-01 10:00:00 UTC,Send,BTC,-0.05,USD,,,,,"], "cb_2024.csv")
    kinds = [m.kind.value for m in read(tmp_path)]
    assert kinds == ["receive", "send"]


def entry(eid, currency, amount, typ, ts=1704189600000, **info):
    return {
        "id": eid,
        "currency": currency,
        "amount": amount,
        "timestamp": ts,
        "direction": "in" if float(amount) > 0 else "out",
        "info": {"type": typ, **info},
    }


def test_ledger_buy_from_both_wallets_counts_once_in_eur():
    block = {
        "id": "B1",
        "total": {"amount": "180.00", "currency": "EUR"},
        "subtotal": {"amount": "177.01", "currency": "EUR"},
        "fee": {"amount": "2.99", "currency": "EUR"},
    }
    ms = list(
        convert(
            [
                entry("1", "SOL", "1.5", "buy", buy=block),
                entry("2", "EUR", "-182.99", "buy", buy=block),
            ]
        )
    )
    assert len(ms) == 1
    m = ms[0]
    # subtotal + fee = the 180.00 paid: the fee is not on top (2026-10-10)
    assert (m.incoming_asset, m.outgoing_asset, m.outgoing_amount) == (
        "SOL",
        "EUR",
        Decimal("177.01"),
    )
    assert (m.fee_asset, m.fee_amount) == ("EUR", Decimal("2.99"))


def test_ledger_sell_takes_the_subtotal_the_fee_comes_off_once():
    block = {
        "id": "S1",
        "total": {"amount": "52.01", "currency": "EUR"},
        "subtotal": {"amount": "55.00", "currency": "EUR"},
        "fee": {"amount": "2.99", "currency": "EUR"},
    }
    (m,) = convert(
        [
            entry("1", "SOL", "-0.534083261", "sell", sell=block),
            entry("2", "EUR", "52.01", "sell", sell=block),
        ]
    )
    # 55.00 − 2.99 = the 52.01 that arrived
    assert (m.incoming_asset, m.incoming_amount, m.fee_amount) == (
        "EUR",
        Decimal("55.00"),
        Decimal("2.99"),
    )


def test_ledger_conversion_staking_transfer_and_income():
    ms = list(
        convert(
            [
                entry("1", "USDT", "-292.322503", "trade", trade={"id": "T1"}),
                entry("2", "USDC", "292.918841", "trade", trade={"id": "T1"}),
                entry("3", "SOL", "-0.5", "staking_transfer"),
                entry("4", "ETH", "0.001", "interest"),
            ]
        )
    )
    kinds = sorted(m.kind.value for m in ms)
    assert kinds == ["income", "trade"]  # the one-legged staking transfer is not emitted


def test_advanced_trade_fill_counter_amount():
    (m,) = convert(
        [
            entry(
                "1",
                "USDC",
                "316.16",
                "advanced_trade_fill",
                advanced_trade_fill={
                    "product_id": "USDC-EUR",
                    "fill_price": "0.9645",
                    "commission": "0.5",
                    "order_side": "buy",
                },
            )
        ]
    )
    assert m.outgoing_amount == Decimal("316.16") * Decimal("0.9645")
    assert (m.outgoing_asset, m.fee_asset) == ("EUR", "EUR")


def test_pem_secret_with_escaped_newlines():
    assert (
        _secret("-----BEGIN EC-----\\nabc\\n-----END EC-----")
        == "-----BEGIN EC-----\nabc\n-----END EC-----\n"
    )


def test_key_file_or_key_pair():
    from integrations.coinbase_api.reader import key_pair

    pem = "-----BEGIN EC PRIVATE KEY-----\\nabc\\n-----END EC PRIVATE KEY-----\\n"
    key_file = '{"name": "organizations/o/apiKeys/k", "privateKey": "' + pem + '"}'
    name, private = key_pair({"key_file": key_file})
    assert (
        name == "organizations/o/apiKeys/k" and private.startswith("-----BEGIN") and "\n" in private
    )
    assert key_pair({"key_file": '{"id": "abc", "privateKey": "xyz"}'})[0] == "abc"
    assert key_pair({"api_key": " k ", "api_secret": "s"})[0] == "k"
    with pytest.raises(ValueError, match="JSON"):
        key_pair({"key_file": "not json"})


def test_ed25519_key_file_signs_with_eddsa():
    """A CDP key file holds an Ed25519 key as one base64 line of 88 characters. ccxt
    detects it by that shape; a trailing line break made it sign with the wrong method."""
    import base64
    import json

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from integrations.coinbase_api.reader import _client

    k = Ed25519PrivateKey.generate()
    raw = serialization.Encoding.Raw
    seed = k.private_bytes(raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    private = base64.b64encode(
        seed + k.public_key().public_bytes(raw, serialization.PublicFormat.Raw)
    )
    key_file = json.dumps({"name": "0a1b2c3d-key", "privateKey": private.decode()})
    signed = _client({"key_file": key_file}).sign("accounts", ["v2", "private"], "GET", {})
    token = signed["headers"]["Authorization"].removeprefix("Bearer ")
    header = json.loads(base64.urlsafe_b64decode(token.split(".")[0] + "=="))
    assert header["alg"] == "EdDSA" and header["kid"] == "0a1b2c3d-key"


def test_coinbase_credentials_accept_either_way(authed):
    authed.post("/api/sources", json={"provider": "coinbase", "label": "Coinbase"})
    sid = authed.get("/api/sources").json()[0]["id"]
    put = lambda body: authed.put(f"/api/sources/{sid}/credentials", json=body)  # noqa: E731
    assert put({"key_file": '{"name":"n","privateKey":"p"}'}).status_code == 204
    assert authed.get("/api/sources").json()[0]["credentials"] == ["key_file"]
    assert put({"api_key": "k", "api_secret": "s"}).status_code == 204
    assert authed.get("/api/sources").json()[0]["credentials"] == ["api_key", "api_secret"]
    assert put({"api_key": "k"}).json()["error"]["code"] == "sources.credentials_incomplete"


def test_a_buy_paid_by_paypal_says_so():
    """The money came from outside: the trade carries it, the app counts it as paid in."""
    block = {
        "id": "P1",
        "total": {"amount": "50.00", "currency": "EUR"},
        "subtotal": {"amount": "48.01", "currency": "EUR"},
        "fee": {"amount": "1.99", "currency": "EUR"},
        "payment_method_name": "PayPal - x@y",
    }
    (m,) = convert([entry("1", "BTC", "0.0015", "buy", buy=block)])
    assert m.comment == "Paid by PayPal"
    block2 = {**block, "id": "P2", "payment_method_name": "Euro Wallet"}
    (m2,) = convert([entry("2", "BTC", "0.0015", "buy", buy=block2)])
    assert m2.comment is None


def test_a_send_carries_the_chain_hash_and_the_address():
    """Details showed no address, and a send to an own wallet stayed open (2026-10-11)."""
    (send,) = convert(
        [
            entry(
                "cb1",
                "ETH",
                "-0.00189371",
                "send",
                to={"address": "0xOwnWallet", "resource": "address"},
                network={"hash": "0xchainhash", "network_name": "ethereum"},
            )
        ]
    )
    assert (send.kind.value, send.external_id, send.counterparty) == (
        "send",
        "0xchainhash",
        "0xOwnWallet",
    )
    (no_hash,) = convert([entry("cb2", "BTC", "-0.1", "send")])
    assert no_hash.external_id == "cb2" and no_hash.counterparty is None
