from decimal import Decimal

from integrations.chain_ethereum.reader import amount, convert

ME = "0xAbCdEf0000000000000000000000000000000001"
OTHER = "0x9999999999999999999999999999999999999999"


def tx(**kw):
    return {
        "timeStamp": "1709290800",
        "hash": kw.pop("hash", "0xh"),
        "isError": "0",
        "gasUsed": "21000",
        "gasPrice": "1000000000",
        **kw,
    }


def test_amount_is_exact():
    assert amount("1234567890123456789", 18) == Decimal("1.234567890123456789")


def test_send_carries_fee_receive_does_not():
    ms = convert(
        ME,
        [
            tx(
                **{
                    "from": ME.lower(),
                    "to": OTHER,
                    "value": "10**18".replace("10**18", "1000000000000000000"),
                }
            ),
            tx(hash="0xi", **{"from": OTHER, "to": ME, "value": "500000000000000000"}),
        ],
        [],
        [],
    )
    send, receive = ms
    assert send.kind.value == "send" and send.fee_amount == Decimal("0.000021")
    assert receive.kind.value == "receive" and receive.fee_amount is None


def test_token_transfer_never_carries_the_fee():
    token = tx(
        **{
            "from": OTHER,
            "to": ME.lower(),
            "value": "2500000",
            "tokenSymbol": "USDC",
            "tokenDecimal": "6",
            "tokenName": "USD Coin",
        }
    )
    (m,) = convert(ME, [], [token], [])
    assert (m.kind.value, m.incoming_asset, m.incoming_amount) == (
        "receive",
        "USDC",
        Decimal("2.5"),
    )
    assert m.fee_amount is None


def test_contract_call_is_a_fee_and_failed_tx_too():
    ms = convert(
        ME,
        [
            tx(**{"from": ME, "to": OTHER, "value": "0"}),
            tx(hash="0xf", isError="1", **{"from": ME, "to": OTHER, "value": "5"}),
        ],
        [],
        [],
    )
    assert [m.kind.value for m in ms] == ["fee", "fee"]
    assert ms[1].comment == "failed transaction"


def test_foreign_failed_attempt_is_ignored():
    assert convert(ME, [tx(isError="1", **{"from": OTHER, "to": ME, "value": "5"})], [], []) == []


def test_internal_eth_transfer_received():
    (m,) = convert(
        ME,
        [],
        [],
        [
            {
                "timeStamp": "1709290800",
                "hash": "0xc",
                "from": OTHER,
                "to": ME.lower(),
                "value": "3000000000000000000",
                "isError": "0",
            }
        ],
    )
    assert (m.kind.value, m.incoming_amount) == ("receive", Decimal(3))
