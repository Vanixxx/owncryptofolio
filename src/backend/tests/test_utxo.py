"""Bitcoin/Litecoin: netting per transaction (change, fee, foreign inputs, paging)."""

from decimal import Decimal

from app.modules.plugins import mempool

ME, SHOP, PAYER = "ltc1qme", "ltc1qshop", "ltc1qpayer"


def tx(vin, vout, fee=0, txid="t", confirmed=True):
    return {
        "txid": txid,
        "fee": fee,
        "status": {"confirmed": confirmed, "block_time": 1700000000 if confirmed else None},
        "vin": [{"prevout": {"scriptpubkey_address": a, "value": v}} for a, v in vin],
        "vout": [{"scriptpubkey_address": a, "value": v} for a, v in vout],
    }


def convert(*txs):
    return mempool.convert(ME, list(txs), native="LTC")


def test_receive_has_no_fee():
    (m,) = convert(
        tx([(PAYER, 300_000_000)], [(ME, 158_231_510), (PAYER, 141_000_000)], fee=768_490)
    )
    assert (m.kind.value, m.incoming_amount, m.fee_amount) == (
        "receive",
        Decimal("1.58231510"),
        None,
    )
    assert m.counterparty == PAYER


def test_send_with_change_is_netted_and_fee_not_counted_twice():
    # spend 5 LTC, send 1 to the shop, 0.001 fee, 3.999 back as change
    (m,) = convert(tx([(ME, 500_000_000)], [(SHOP, 100_000_000), (ME, 399_900_000)], fee=100_000))
    assert m.kind.value == "send" and m.counterparty == SHOP
    assert m.outgoing_amount == Decimal(1) and m.fee_amount == Decimal("0.001")
    assert m.outgoing_amount + m.fee_amount == Decimal("5") - Decimal("3.999")


def test_consolidation_is_only_a_fee():
    (m,) = convert(tx([(ME, 100), (ME, 200)], [(ME, 290)], fee=10))
    assert m.kind.value == "fee" and m.fee_amount == Decimal("1E-7")


def test_foreign_inputs_are_not_guessed():
    (m,) = convert(tx([(ME, 100), (PAYER, 100)], [(SHOP, 150), (ME, 40)], fee=10))
    assert m.kind.value == "other" and m.comment == "inputs from other addresses"


def test_unconfirmed_and_unrelated_are_skipped():
    assert (
        convert(tx([(PAYER, 5)], [(ME, 5)], confirmed=False), tx([(PAYER, 5)], [(SHOP, 5)])) == []
    )


def test_paging_follows_the_last_confirmed_txid(monkeypatch):
    calls = []
    pages = {
        "https://x/address/a/txs": [
            tx([(PAYER, 1)], [("a", 1)], txid=f"p1-{i}") for i in range(25)
        ],
        "https://x/address/a/txs/chain/p1-24": [tx([(PAYER, 1)], [("a", 1)], txid="p2-0")],
    }

    def answer(url, body=None):
        calls.append(url)
        return pages[url]

    monkeypatch.setattr(mempool, "http_json", answer)
    assert len(mempool.transactions("https://x", "a")) == 26 and len(calls) == 2
