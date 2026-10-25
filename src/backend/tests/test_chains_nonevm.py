"""The networks added on 2026-10-23, on made-up answers in the form each API gives."""

from decimal import Decimal

from app.modules.plugins.contract import IncomeKind, Kind

ME, OTHER = "rMe", "rOther"


def test_xrp_delivered_amount_ripple_epoch_hex_currency_and_failed_fee():
    from integrations.chain_xrp import reader

    records = [
        {  # API v1 form; a partial payment delivers less than Amount
            "tx": {
                "TransactionType": "Payment",
                "Account": OTHER,
                "Destination": ME,
                "Amount": "5000000",
                "Fee": "12",
                "date": 0,
                "hash": "H1",
            },
            "meta": {"TransactionResult": "tesSUCCESS", "delivered_amount": "4000000"},
        },
        {  # API v2 form, an issued currency with a hex name, sent by me
            "hash": "H2",
            "tx_json": {
                "TransactionType": "Payment",
                "Account": ME,
                "Destination": OTHER,
                "Fee": "10",
                "date": 60,
            },
            "meta": {
                "TransactionResult": "tesSUCCESS",
                "delivered_amount": {
                    "currency": "534F4C4F00000000000000000000000000000000",
                    "issuer": "rX",
                    "value": "1.5",
                },
            },
        },
        {  # failed: the fee is gone all the same
            "tx": {
                "TransactionType": "Payment",
                "Account": ME,
                "Destination": OTHER,
                "Amount": "1",
                "Fee": "15",
                "date": 120,
                "hash": "H3",
            },
            "meta": {"TransactionResult": "tecUNFUNDED_PAYMENT"},
        },
    ]
    got = reader.convert(ME, records)
    assert got[0].kind == Kind.RECEIVE and got[0].incoming_amount == Decimal("4")
    assert got[0].timestamp.year == 2000  # Ripple epoch, not 1970
    assert (got[1].kind, got[1].outgoing_asset, got[1].fee_amount) == (
        Kind.SEND,
        "SOLO",
        Decimal("0.00001"),
    )
    assert (got[2].kind, got[2].fee_amount) == (Kind.FEE, Decimal("0.000015"))


def test_tezos_fees_only_when_applied_payouts_as_income_and_nfts_skipped():
    from integrations.chain_tezos import reader

    op = {"type": "transaction", "timestamp": "2025-01-01T00:00:00Z", "hash": "o1", "id": 1}
    ops = [
        {
            **op,
            "status": "applied",
            "sender": {"address": "tzMe"},
            "target": {"address": "tzX"},
            "amount": 1_000_000,
            "bakerFee": 500,
            "storageFee": 100,
            "allocationFee": 64_250,
        },
        {
            **op,
            "id": 2,
            "status": "failed",
            "sender": {"address": "tzMe"},
            "target": {"address": "tzX"},
            "amount": 1_000_000,
            "bakerFee": 500,
            "storageFee": 100,
            "allocationFee": 64_250,
        },
        {
            **op,
            "id": 3,
            "status": "applied",
            "sender": {"address": "tzBaker", "alias": "Baker"},
            "target": {"address": "tzMe"},
            "amount": 2_000,
        },
    ]
    tokens = [
        {
            "id": 9,
            "timestamp": "2025-01-02T00:00:00Z",
            "transactionId": 5,
            "amount": "1500000",
            "from": {"address": "tzX"},
            "to": {"address": "tzMe"},
            "token": {"metadata": {"symbol": "USDt", "decimals": "6"}},
        },
        {
            "id": 10,
            "timestamp": "2025-01-02T00:00:00Z",
            "transactionId": 6,
            "amount": "1",
            "from": {"address": "tzX"},
            "to": {"address": "tzMe"},
            "token": {"metadata": {"decimals": "0", "artifactUri": "ipfs://x"}},
        },
    ]
    got = reader.convert("tzMe", ops, tokens, delegate="tzBaker")
    assert got[0].fee_amount == Decimal("0.06485")  # baker + storage + allocation
    assert (got[1].kind, got[1].fee_amount) == (
        Kind.FEE,
        Decimal("0.0005"),
    )  # failed: baker fee only
    assert got[2].kind == Kind.INCOME and got[2].income_kind == IncomeKind.STAKING
    assert [(m.incoming_asset, m.incoming_amount) for m in got[3:]] == [("USDT", Decimal("1.5"))]


def test_algorand_close_to_rewards_and_opt_in():
    from integrations.chain_algorand import reader

    def assets(asset_id):
        return {7: ("USDC", 6)}.get(asset_id)

    records = [
        {
            "id": "T1",
            "tx-type": "pay",
            "round-time": 1,
            "sender": "ME",
            "fee": 1000,
            "sender-rewards": 500,
            "payment-transaction": {
                "amount": 2_000_000,
                "receiver": "X",
                "close-remainder-to": "Y",
                "close-amount": 300_000,
            },
        },
        {
            "id": "T2",
            "tx-type": "axfer",
            "round-time": 2,
            "sender": "ME",
            "fee": 1000,
            "asset-transfer-transaction": {"amount": 0, "asset-id": 7, "receiver": "ME"},
        },
        {
            "id": "T3",
            "tx-type": "axfer",
            "round-time": 3,
            "sender": "X",
            "fee": 1000,
            "asset-transfer-transaction": {"amount": 2_500_000, "asset-id": 7, "receiver": "ME"},
        },
    ]
    got = reader.convert("ME", records, assets)
    sends = [m for m in got if m.kind == Kind.SEND]
    assert [m.outgoing_amount for m in sends] == [Decimal("2"), Decimal("0.3")]
    assert sum(m.fee_amount or 0 for m in sends) == Decimal("0.001")  # the fee once
    assert any(m.kind == Kind.INCOME and m.incoming_amount == Decimal("0.0005") for m in got)
    assert any(m.kind == Kind.FEE and m.comment == "axfer" for m in got)  # opt-in
    assert any(m.kind == Kind.RECEIVE and m.incoming_asset == "USDC" for m in got)


def test_tron_hex_addresses_fees_trc20_and_staked_balance(monkeypatch):
    from integrations.chain_tron import reader

    me = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    assert reader.base58("41a614f803b6fd780986a42c78ec9c7f77e6ded13c") == me
    send = {
        "txID": "a1",
        "block_timestamp": 1_700_000_000_000,
        "ret": [{"contractRet": "SUCCESS", "fee": 1_100_000}],
        "raw_data": {
            "contract": [
                {
                    "type": "TransferContract",
                    "parameter": {
                        "value": {
                            "amount": 5_000_000,
                            "owner_address": "41a614f803b6fd780986a42c78ec9c7f77e6ded13c",
                            "to_address": "41" + "11" * 20,
                        }
                    },
                }
            ]
        },
    }
    call = {
        **send,
        "txID": "a2",
        "ret": [{"contractRet": "SUCCESS", "fee": 300_000}],
        "raw_data": {
            "contract": [
                {
                    "type": "TriggerSmartContract",
                    "parameter": {
                        "value": {"owner_address": "41a614f803b6fd780986a42c78ec9c7f77e6ded13c"}
                    },
                }
            ]
        },
    }
    trc20 = [
        {
            "transaction_id": "a2",
            "block_timestamp": 1_700_000_000_000,
            "from": me,
            "to": "TX",
            "type": "Transfer",
            "value": "2500000",
            "token_info": {"symbol": "USDT", "decimals": 6, "address": "TC"},
        }
    ]
    got = reader.convert(me, [send, call], trc20, reader.Grid(None))
    assert (got[0].kind, got[0].outgoing_amount, got[0].fee_amount) == (
        Kind.SEND,
        Decimal("5"),
        Decimal("1.1"),
    )
    assert (got[1].kind, got[1].fee_amount) == (Kind.FEE, Decimal("0.3"))
    assert (got[2].outgoing_asset, got[2].outgoing_amount) == ("USDT", Decimal("2.5"))
    account = {
        "data": [
            {
                "balance": 1_000_000,
                "frozenV2": [{"amount": 2_000_000}],
                "unfrozenV2": [{"unfreeze_amount": 500_000}],
                "account_resource": {"delegated_frozenV2_balance_for_energy": 3_000_000},
            }
        ]
    }
    monkeypatch.setattr(reader.Grid, "get", lambda self, path, body=None: account)
    assert reader.balance(me)[0] == ("spot", "TRX", Decimal("6.5"))  # staked TRX stays yours


def test_ton_raw_address_and_fees_with_forward_fees():
    from integrations.chain_ton import reader

    raw = reader.raw_address("UQAE88HHlayJBeMXNDYrFJh1q5UirlODq3q7LhDaXai6gtwi")
    assert raw == "0:04F3C1C795AC8905E31734362B149875AB9522AE5383AB7ABB2E10DA5DA8BA82"
    center = reader.Center(None)
    txs = [
        {
            "hash": "h1",
            "now": 1,
            "total_fees": "50",
            "in_msg": {"source": "0:AA", "value": "1000000000"},
            "out_msgs": [],
        },
        {
            "hash": "h2",
            "now": 2,
            "total_fees": "500",
            "in_msg": {"source": None, "value": "0"},
            "out_msgs": [{"destination": "0:BB", "value": "400000000", "fwd_fee": "100"}],
        },
    ]
    got = reader.convert(raw, txs, [], center)
    assert (got[0].kind, got[0].fee_amount) == (
        Kind.RECEIVE,
        Decimal("5E-8"),
    )  # receiving costs a little
    assert (got[1].kind, got[1].outgoing_amount, got[1].fee_amount) == (
        Kind.SEND,
        Decimal("0.4"),
        Decimal("6E-7"),
    )


def test_dogecoin_and_bitcoin_cash_net_like_bitcoin():
    from integrations.chain_bitcoincash import reader as bch
    from integrations.chain_dogecoin import reader as doge

    tx = {
        "hash": "d1",
        "confirmed": "2025-01-01T00:00:00Z",
        "block_height": 5,
        "fees": 100_000_000,
        "inputs": [{"addresses": ["DMe"], "output_value": 1_000_000_000}],
        "outputs": [
            {"addresses": ["DX"], "value": 600_000_000},
            {"addresses": ["DMe"], "value": 300_000_000},
        ],
    }
    (m,) = doge.convert("DMe", [tx])
    assert (m.kind, m.outgoing_amount, m.fee_amount) == (Kind.SEND, Decimal("6"), Decimal("1"))
    assert doge.convert("DMe", [{**tx, "confirmed": None}]) == []  # unconfirmed: later

    me = "bitcoincash:q" + "q" * 41
    t = {
        "txid": "b1",
        "time": 1,
        "block": {"height": 9},
        "fee": 0,
        "inputs": [{"address": "bitcoincash:qother", "value": 5}],
        "outputs": [{"address": me, "value": 5}],
    }
    (m,) = bch.convert(me.removeprefix("bitcoincash:"), [t])  # entered without the prefix
    assert m.kind == Kind.RECEIVE and m.incoming_amount == Decimal("5E-8")
    assert bch.convert(me, [{**t, "block": {"mempool": 1}}]) == []


def test_near_native_balance_model_and_tokens_from_events():
    from integrations.chain_near import reader

    me = "me.near"

    def receipt(
        rid, pred, recv, deposit=None, ts=2, logs=(), status=None, burnt="0", executor=None
    ):
        action = {
            "signer_id": "x",
            "actions": [{"Transfer": {"deposit": str(deposit)}}] if deposit else [],
        }
        return {
            "receipt": {
                "receipt_id": rid,
                "predecessor_id": pred,
                "receiver_id": recv,
                "receipt": {"Action": action},
            },
            "execution_outcome": {
                "block_timestamp": ts * 10**9,
                "outcome": {
                    "logs": list(logs),
                    "tokens_burnt": burnt,
                    "executor_id": executor or recv,
                    "status": status or {"SuccessValue": ""},
                },
            },
        }

    ONE = 10**24
    incoming = {  # someone sends me 2 NEAR; the system refund of gas is not a deposit
        "transaction": {
            "signer_id": "a.near",
            "receiver_id": me,
            "actions": [{"Transfer": {"deposit": str(2 * ONE)}}],
        },
        "execution_outcome": {
            "id": "t1",
            "block_timestamp": 10**9,
            "outcome": {"tokens_burnt": "0", "receipt_ids": ["r1"]},
        },
        "receipts": [receipt("r1", "a.near", me, 2 * ONE), receipt("r2", "system", "a.near", 5)],
    }
    event = 'EVENT_JSON:{"standard":"nep141","event":"ft_transfer","data":[{"old_owner_id":"a.near","new_owner_id":"me.near","amount":"1500000"}]}'
    sent = {  # I send 0.5 NEAR and call a token with a 1 yocto ticket; gas 0.01 NEAR burnt in total
        "transaction": {
            "signer_id": me,
            "receiver_id": "b.near",
            "actions": [
                {"Transfer": {"deposit": str(ONE // 2)}},
                {"FunctionCall": {"method_name": "ft_transfer", "deposit": "1"}},
            ],
        },
        "execution_outcome": {
            "id": "t2",
            "block_timestamp": 3 * 10**9,
            "outcome": {"tokens_burnt": str(ONE // 400), "receipt_ids": ["r3"]},
        },
        "receipts": [
            receipt(
                "r3",
                me,
                "b.near",
                ONE // 2,
                ts=3,
                burnt=str(ONE // 400),
                logs=[event],
                executor="usdt.near",
            ),
            receipt("r4", "system", me, 777, ts=4),
        ],
    }
    got = reader.convert(me, [sent, incoming], lambda contract: ("USDT", 6))
    native = [m for m in got if m.incoming_asset == "NEAR" or m.outgoing_asset == "NEAR"]
    assert [(m.kind, m.incoming_amount or m.outgoing_amount) for m in native] == [
        (Kind.RECEIVE, Decimal(2)),
        (Kind.SEND, Decimal("0.5")),
    ]
    send = native[1]
    assert send.fee_amount == Decimal("0.005") + Decimal(1).scaleb(
        -24
    )  # gas of the call and its receipt + the ticket
    token = [m for m in got if m.incoming_asset == "USDT"]
    assert token and token[0].incoming_amount == Decimal("1.5")

    failed = {
        **sent,
        "receipts": [
            receipt("r3", me, "b.near", ONE // 2, ts=3, status={"Failure": {}}, burnt="5")
        ],
    }
    assert not [
        m for m in reader.convert(me, [failed], lambda c: None) if m.kind == Kind.SEND
    ]  # deposit came back


def test_cosmos_fee_rewards_sends_and_staking_that_is_no_movement():
    from app.modules.plugins import cosmos

    me, other = "cosmos1me", "cosmos1other"

    def event(kind, **attrs):
        return {"type": kind, "attributes": [{"key": k, "value": v} for k, v in attrs.items()]}

    def tx(hash_, messages, events, fee="1000uatom", ts="2026-10-01T00:00:00Z"):
        return {
            "response": {"txhash": hash_, "timestamp": ts, "code": 0, "events": events},
            "tx": {
                "body": {"messages": [{"@type": f"/cosmos.x.{m}"} for m in messages]},
                "auth_info": {
                    "fee": {"amount": [{"denom": "uatom", "amount": fee.removesuffix("uatom")}]}
                },
            },
        }

    items = [
        tx(
            "A",
            ["MsgSend"],
            [
                event(
                    "transfer", sender=me, recipient="cosmos1fees", amount="1000uatom"
                ),  # the fee, no msg_index
                event("transfer", sender=me, recipient=other, amount="2500000uatom", msg_index="0"),
            ],
        ),
        tx(
            "B",
            ["MsgDelegate"],
            [
                event("transfer", sender=me, recipient="cosmos1fees", amount="1000uatom"),
                event(
                    "transfer",
                    sender="cosmos1distribution",
                    recipient=me,
                    amount="400000uatom",
                    msg_index="0",
                ),
                event("delegate", validator="v", delegator=me, amount="400000uatom", msg_index="0"),
            ],
            ts="2026-10-02T00:00:00Z",
        ),
        tx(
            "C",
            ["MsgRecvPacket"],
            [
                event(
                    "transfer",
                    sender="cosmos1escrow",
                    recipient=me,
                    amount="7ibc/X,9uatom",
                    msg_index="0",
                ),
            ],
            ts="2026-10-03T00:00:00Z",
        ),
    ]
    client = cosmos.Client(cosmos.Chain("ATOM", "uatom", ()))
    client.traces["ibc/X"] = "uosmo"
    got = cosmos.convert(me, items, client)
    assert [(m.kind, m.outgoing_amount, m.fee_amount) for m in got[:1]] == [
        (Kind.SEND, Decimal("2.5"), Decimal("0.001"))
    ]
    # the delegation itself is no movement: only the reward and the fee of that transaction
    assert (got[1].kind, got[1].income_kind) == (Kind.INCOME, IncomeKind.STAKING)
    assert (got[2].kind, got[2].fee_amount) == (Kind.FEE, Decimal("0.001"))
    assert [(m.incoming_asset, m.incoming_amount) for m in got[3:]] == [
        ("OSMO", Decimal("0.000007")),
        ("ATOM", Decimal("0.000009")),
    ]


def test_near_token_lookup_skips_only_a_contract_that_is_no_token(monkeypatch):
    from integrations.chain_near import reader

    answers = iter(
        [
            reader.chain.ChainUnavailable("HTTP 429"),  # first node down: the next one is asked
            {"result": {"error": "MethodNotFound"}},  # answered: no token
            {
                "error": {"name": "HANDLER_ERROR", "cause": {"name": "TOO_MANY_REQUESTS"}}
            },  # not "no token"
            {"error": {"name": "HANDLER_ERROR", "cause": {"name": "TOO_MANY_REQUESTS"}}},
            {
                "error": {"name": "HANDLER_ERROR", "cause": {"name": "UNKNOWN_ACCOUNT"}}
            },  # deleted: no token
        ]
    )

    def fake(url, body=None, headers=None):
        a = next(answers)
        if isinstance(a, Exception):
            raise a
        return a

    monkeypatch.setattr(reader.chain, "http_json", fake)
    tokens = reader.Tokens()
    assert tokens("not-a-token.near") is None
    try:
        tokens("busy.near")
    except reader.chain.ChainUnavailable:
        pass
    else:
        raise AssertionError("a token must not be dropped when no node answers")
    assert tokens("deleted.near") is None


def test_cosmos_history_that_breaks_off_in_the_middle_is_an_error(monkeypatch):
    """Page 2 fails on the only server that had page 1: no silent gap (review 2026-10-24);
    another server that reads the side to the end makes it good."""
    from types import SimpleNamespace

    import pytest

    from app.modules.plugins import chain, cosmos

    monkeypatch.setattr(cosmos, "PAGE", 1)
    tx = {"txhash": "H", "timestamp": "2025-01-01T00:00:00Z"}

    def client(servers, good):
        def get(path, base=None):
            first = "pagination.offset=0" in path
            if base in good or first:
                if not first:
                    return {"tx_responses": [], "txs": []}
                return {"tx_responses": [tx], "txs": [{}]}
            raise chain.ChainUnavailable("HTTP 502")

        return SimpleNamespace(spec=SimpleNamespace(servers=servers), get=get)

    with pytest.raises(chain.ChainUnavailable):
        cosmos.search(client(("a",), set()), "cosmos1me", None)
    assert len(cosmos.search(client(("a", "b"), {"b"}), "cosmos1me", None)) == 1


def test_dogecoin_page_edge_inside_a_block_reads_the_block_again(monkeypatch):
    """`before` is strictly below: the next page starts one block higher (review 2026-10-24)."""
    from app.modules.plugins import chain
    from integrations.chain_dogecoin import reader

    txs = [{"hash": f"h{i}", "block_height": h} for i, h in enumerate([9, 8, 7, 7, 6])]
    asked = []

    def http_json(url):
        before = int(url.split("before=")[1]) if "before=" in url else 10**9
        asked.append(before)
        rows = [t for t in txs if t["block_height"] < before][:3]
        return {"txs": rows, "hasMore": rows != [] and rows[-1] is not txs[-1]}

    monkeypatch.setattr(chain, "http_json", http_json)
    assert [t["hash"] for t in reader.transactions("D")] == [f"h{i}" for i in range(5)]
    assert asked[1] == 8  # one above the lowest block of page one (7)


def test_solana_transaction_the_node_does_not_deliver_is_an_error(monkeypatch):
    import pytest

    from app.modules.plugins import chain
    from integrations.chain_solana import reader

    monkeypatch.setattr(reader, "TOKEN_PROGRAMS", ())
    monkeypatch.setattr(reader, "_signatures", lambda account: [{"signature": "S1"}])
    monkeypatch.setattr(reader, "_rpc", lambda method, params: None)
    with pytest.raises(chain.ChainUnavailable, match="not delivered"):
        reader.transactions("addr")
