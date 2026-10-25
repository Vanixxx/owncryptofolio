"""Networks with their own answer form: Polkadot, VeChain, Hedera, Kaspa, ..."""

from decimal import Decimal

ME_DOT = "1MeDot"
OTHER = "1Other"


def test_polkadot_reads_ms_time_skips_foreign_assets_and_tags_the_chain():
    from integrations.chain_polkadot.reader import convert

    rows = [
        {
            "indexer": {"blockTime": 1737579552000, "blockHash": "0xb", "eventIndex": 3},
            "from": OTHER,
            "to": ME_DOT,
            "balance": "1520423527300",
            "isNativeAsset": True,
        },
        {
            "indexer": {"blockTime": 1737579552000, "blockHash": "0xb", "eventIndex": 4},
            "from": OTHER,
            "to": ME_DOT,
            "balance": "5000000",
            "isNativeAsset": False,
        },
        {
            "indexer": {"blockTime": 1737579600000, "blockHash": "0xc", "eventIndex": 1},
            "from": ME_DOT,
            "to": OTHER,
            "balance": "10000000000",
            "isNativeAsset": True,
        },
    ]
    received, sent = convert(ME_DOT, rows, "relay")
    assert received.kind.value == "receive" and received.incoming_amount == Decimal("152.04235273")
    assert received.timestamp.year == 2025 and received.external_id == "relay:0xb:3"
    assert (
        sent.kind.value == "send" and sent.outgoing_amount == Decimal(1) and sent.fee_amount is None
    )


ME_VET = "0x11ef000000000000000000000000000000003767"
OTHER_VET = "0x1ab4000000000000000000000000000000000001"


def test_vechain_vet_and_vtho_with_fee_in_vtho_once_per_transaction():
    from integrations.chain_vechain.reader import convert

    meta = {"blockTimestamp": 1737584000, "txID": "0xt", "clauseIndex": 0}
    rows = [
        {"sender": OTHER_VET, "recipient": ME_VET, "amount": "0x16345785d8a0000", "meta": meta},
        {
            "topics": ["0xddf2", "0x" + "0" * 24 + OTHER_VET[2:], "0x" + "0" * 24 + ME_VET[2:]],
            "data": "0xde0b6b3a7640000",
            "meta": {**meta, "txID": "0xv"},
        },
        {
            "sender": ME_VET,
            "recipient": OTHER_VET,
            "amount": "0xde0b6b3a7640000",
            "meta": {**meta, "txID": "0xs", "clauseIndex": 0},
        },
        {
            "sender": ME_VET,
            "recipient": OTHER_VET,
            "amount": "0xde0b6b3a7640000",
            "meta": {**meta, "txID": "0xs", "clauseIndex": 1},
        },
    ]
    vet, vtho, send1, send2 = convert(ME_VET, rows, lambda tx: Decimal("0.21"))
    assert (vet.kind.value, vet.incoming_asset, vet.incoming_amount) == (
        "receive",
        "VET",
        Decimal("0.1"),
    )
    assert (vtho.incoming_asset, vtho.incoming_amount, vtho.external_id) == (
        "VTHO",
        Decimal(1),
        "vtho:0xv:0",
    )
    assert send1.fee_asset == "VTHO" and send1.fee_amount == Decimal("0.21")
    assert send2.fee_amount is None  # one fee per transaction


ACC = "0.0.1234567"


def htx(transfers, payer="0.0.1", fee=0, rewards=(), result="SUCCESS"):
    return {
        "consensus_timestamp": "1737584000.123456789",
        "transaction_id": f"{payer}-1737584000-1",
        "charged_tx_fee": fee,
        "result": result,
        "name": "CRYPTOTRANSFER",
        "transfers": [{"account": a, "amount": v} for a, v in transfers],
        "staking_reward_transfers": [{"account": a, "amount": v} for a, v in rewards],
    }


def test_hedera_receive_send_and_staking_reward_split_out():
    from integrations.chain_hedera.reader import convert

    (rec,) = convert(ACC, [htx([("0.0.4735544", -100_000_000), (ACC, 100_000_000)])])
    assert (
        rec.kind.value == "receive"
        and rec.incoming_amount == Decimal(1)
        and rec.counterparty == "0.0.4735544"
    )
    # I pay: 2 HBAR sent, fee 0.005 inside my negative amount
    (snd,) = convert(
        ACC,
        [
            htx(
                [(ACC, -200_500_000), ("0.0.2", 200_000_000), ("0.0.98", 500_000)],
                payer=ACC,
                fee=500_000,
            )
        ],
    )
    assert (
        snd.kind.value == "send"
        and snd.outgoing_amount == Decimal(2)
        and snd.fee_amount == Decimal("0.005")
    )
    # a reward of 0.2 paid along with a receipt of 1
    rew, rec2 = convert(
        ACC,
        [
            htx(
                [("0.0.800", -20_000_000), ("0.0.4735544", -100_000_000), (ACC, 120_000_000)],
                rewards=[(ACC, 20_000_000)],
            )
        ],
    )
    assert (rew.kind.value, rew.income_kind.value, rew.incoming_amount) == (
        "income",
        "staking",
        Decimal("0.2"),
    )
    assert rec2.incoming_amount == Decimal(1)


def test_hedera_spam_names_the_spammer_and_shows_its_memo():
    """A spammer's 1000 tinybar to many accounts, in a transaction that also paid someone
    else's staking reward: 0.0.800 is no counterparty, and the memo is the comment."""
    import base64

    from integrations.chain_hedera.reader import convert

    t = htx(
        [
            ("0.0.800", -2_024_952),
            ("0.0.2963125", -62_716),
            (ACC, 1000),
            ("0.0.7901430", 2_031_103),
            ("0.0.98", 41_208),
        ],
        payer="0.0.2963125",
        rewards=[("0.0.7901430", 2_030_103)],
    )
    t["memo_base64"] = base64.b64encode(b"Claim HBAR prize at hederairdrop.org").decode()
    (rec,) = convert(ACC, [t])
    assert (
        rec.counterparty == "0.0.2963125" and rec.comment == "Claim HBAR prize at hederairdrop.org"
    )
    assert rec.incoming_amount == Decimal("0.00001")


def test_hedera_failed_transaction_i_paid_is_a_fee_only():
    from integrations.chain_hedera.reader import convert

    (m,) = convert(
        ACC,
        [
            htx(
                [(ACC, -500_000), ("0.0.98", 500_000)],
                payer=ACC,
                fee=500_000,
                result="INSUFFICIENT_PAYER_BALANCE",
            )
        ],
    )
    assert m.kind.value == "fee" and m.fee_amount == Decimal("0.005")


def test_hedera_follows_links_next_from_account_creation(monkeypatch):
    from integrations.chain_hedera import reader

    pages = {
        f"/api/v1/accounts/{ACC}?transactions=false": {"created_timestamp": "100.0"},
        f"/api/v1/transactions?account.id={ACC}&limit=100&order=asc&timestamp=gte:100.0": {
            "transactions": [],
            "links": {"next": "/p2"},
        },  # an empty 60-day window is not the end
        "/p2": {"transactions": [htx([(ACC, 1)])], "links": {"next": None}},
    }
    monkeypatch.setattr(
        reader.chain, "http_json", lambda url, body=None: pages[url.removeprefix(reader.API)]
    )
    assert len(reader.transactions(ACC)) == 1


def test_kaspa_ms_time_fee_only_when_all_inputs_resolved():
    from integrations.chain_kaspa.reader import convert

    me, other = "kaspa:me", "kaspa:other"
    t = {
        "transaction_id": "k1",
        "block_time": 1737582184000,
        "is_accepted": True,
        "inputs": [{"previous_outpoint_address": me, "previous_outpoint_amount": 1_000_000_000}],
        "outputs": [
            {"script_public_key_address": other, "amount": 600_000_000},
            {"script_public_key_address": me, "amount": 399_990_000},
        ],
    }
    (m,) = convert(me, [t])
    assert (
        m.kind.value == "send"
        and m.outgoing_amount == Decimal(6)
        and m.fee_amount == Decimal("0.0001")
    )
    assert m.timestamp.year == 2025
    assert convert(me, [{**t, "is_accepted": False}]) == []


def test_cardano_reward_withdrawal_is_income_and_counts_as_input():
    from integrations.chain_cardano.reader import convert

    me, shop = "addr1me", "addr1shop"
    t = {
        "tx_hash": "c1",
        "tx_timestamp": 1737582632,
        "fee": "200000",
        "inputs": [{"value": "10000000", "payment_addr": {"bech32": me}, "stake_addr": "stake1me"}],
        "outputs": [
            {"value": "5000000", "payment_addr": {"bech32": shop}},
            {"value": "6800000", "payment_addr": {"bech32": me}, "stake_addr": "stake1me"},
        ],
        "withdrawals": [{"amount": "2000000", "stake_addr": "stake1me"}],
    }
    reward, send = convert(me, [t])
    assert (reward.kind.value, reward.income_kind.value, reward.incoming_amount) == (
        "income",
        "staking",
        Decimal(2),
    )
    # 10 + 2 (reward) in, 6.8 back, 0.2 fee: 5 sent
    assert (
        send.kind.value == "send"
        and send.outgoing_amount == Decimal(5)
        and send.fee_amount == Decimal("0.2")
    )


def test_cardano_without_inputs_is_refused():
    import pytest

    from app.modules.plugins.chain import ChainUnavailable
    from integrations.chain_cardano.reader import convert

    with pytest.raises(ChainUnavailable):
        convert("addr1me", [{"tx_hash": "x", "tx_timestamp": 1, "inputs": [], "outputs": []}])


def test_stellar_amounts_are_decimal_and_404_means_no_account_yet(monkeypatch):
    from app.modules.plugins.chain import ChainUnavailable
    from integrations.chain_stellar import reader

    me, other = "GME", "GOTHER"
    rows = [
        {
            "type": "create_account",
            "funder": other,
            "account": me,
            "starting_balance": "2.5000000",
            "created_at": "2025-01-01T00:00:00Z",
            "transaction_hash": "h1",
            "id": "1",
            "transaction_successful": True,
            "transaction": {"fee_account": other, "fee_charged": "100"},
        },
        {
            "type": "payment",
            "from": me,
            "to": other,
            "amount": "1.0000000",
            "asset_type": "native",
            "created_at": "2025-01-02T00:00:00Z",
            "transaction_hash": "h2",
            "id": "2",
            "transaction_successful": True,
            "transaction": {"fee_account": me, "fee_charged": "100"},
        },
    ]
    created, paid = reader.convert(me, rows)
    assert created.kind.value == "receive" and created.incoming_amount == Decimal("2.5")
    assert (
        paid.kind.value == "send"
        and paid.outgoing_amount == Decimal(1)
        and paid.fee_amount == Decimal("0.00001")
    )

    def not_found(url, body=None):
        raise ChainUnavailable("HTTP 404")

    monkeypatch.setattr(reader.chain, "http_json", not_found)
    assert reader.payments(me) == []


SUI_ME = "0x" + "a" * 64
SUI_OTHER = "0x" + "b" * 64
SUI = "0x" + "0" * 63 + "2::sui::SUI"


def sui_tx(changes, sender, gas=(1000, 2000, 500)):
    return {
        "digest": "d",
        "sender": {"address": sender},
        "effects": {
            "timestamp": "2025-04-26T09:34:56.057Z",
            "status": "SUCCESS",
            "gasEffects": {
                "gasSummary": dict(
                    zip(("computationCost", "storageCost", "storageRebate"), gas, strict=True)
                )
            },
            "balanceChanges": {
                "nodes": [
                    {"amount": str(a), "owner": {"address": o}, "coinType": {"repr": c}}
                    for o, a, c in changes
                ]
            },
        },
    }


def test_sui_gas_is_taken_out_of_the_senders_change():
    from integrations.chain_sui.reader import convert

    meta = lambda c: ("SUI", 9) if c == SUI else ("USDC", 6)  # noqa: E731
    # I send 1 SUI, gas 0.0000025: my change is -(1 + 0.0000025)
    (send,) = convert(
        SUI_ME,
        [sui_tx([(SUI_ME, -1_000_002_500, SUI), (SUI_OTHER, 1_000_000_000, SUI)], SUI_ME)],
        meta,
    )
    assert (
        send.kind.value == "send"
        and send.outgoing_amount == Decimal(1)
        and send.fee_amount == Decimal("0.0000025")
    )
    (rec,) = convert(
        SUI_ME,
        [
            sui_tx(
                [
                    (SUI_OTHER, -2_000_000, "0x9::usdc::USDC"),
                    (SUI_ME, 2_000_000, "0x9::usdc::USDC"),
                ],
                SUI_OTHER,
            )
        ],
        meta,
    )
    assert (rec.kind.value, rec.incoming_asset, rec.incoming_amount, rec.fee_amount) == (
        "receive",
        "USDC",
        Decimal(2),
        None,
    )


def test_solana_sol_by_index_tokens_by_account_index_fee_out_of_signer_change():
    from integrations.chain_solana.reader import MINTS, convert

    me, other = "SoLMe", "SoLOther"
    render = next(iter(MINTS))
    receive_render = {
        "signature": "s1",
        "blockTime": 1738964292,
        "transaction": {"message": {"accountKeys": [{"pubkey": other}, {"pubkey": "ata"}]}},
        "meta": {
            "err": None,
            "fee": 5000,
            "preBalances": [10, 0],
            "postBalances": [5, 0],
            "preTokenBalances": [
                {
                    "accountIndex": 1,
                    "owner": me,
                    "mint": render,
                    "uiTokenAmount": {"amount": "0", "decimals": 8},
                }
            ],
            "postTokenBalances": [
                {
                    "accountIndex": 1,
                    "owner": me,
                    "mint": render,
                    "uiTokenAmount": {"amount": "2007000000", "decimals": 8},
                }
            ],
        },
    }
    (m,) = convert(me, [receive_render])
    assert (m.kind.value, m.incoming_asset, m.incoming_amount) == (
        "receive",
        "RENDER",
        Decimal("20.07"),
    )
    send_sol = {
        "signature": "s2",
        "blockTime": 1738964292,
        "transaction": {"message": {"accountKeys": [me, other]}},
        "meta": {
            "err": None,
            "fee": 5000,
            "preBalances": [2_000_005_000, 0],
            "postBalances": [1_000_000_000, 1_000_000_000],
        },
    }
    (s,) = convert(me, [send_sol])
    assert (
        s.kind.value == "send"
        and s.outgoing_amount == Decimal(1)
        and s.fee_amount == Decimal("0.000005")
    )


def test_polkadot_fee_from_extrinsic_events_once_and_only_if_i_paid(monkeypatch):
    from integrations.chain_polkadot import reader

    events = {
        "items": [
            {"method": "Withdraw", "args": []},
            {
                "method": "TransactionFeePaid",
                "args": [
                    {"name": "who", "value": ME_DOT},
                    {"name": "actual_fee", "value": 160276631},
                    {"name": "tip", "value": 1},
                ],
            },
        ]
    }
    monkeypatch.setattr(reader.chain, "http_json", lambda url, body=None: events)
    assert reader.extrinsic_fee("https://x", ME_DOT, 1, 2) == Decimal("0.0160276632")
    assert reader.extrinsic_fee("https://x", OTHER, 1, 2) is None

    ix = {"blockTime": 1, "blockHash": "0xb", "blockHeight": 7, "extrinsicIndex": 2}
    rows = [
        {"indexer": {**ix, "eventIndex": 3}, "from": ME_DOT, "to": OTHER, "balance": "10000000000"},
        {"indexer": {**ix, "eventIndex": 5}, "from": ME_DOT, "to": OTHER, "balance": "10000000000"},
    ]
    asked = []
    first, second = reader.convert(
        ME_DOT, rows, "relay", lambda h, i: asked.append((h, i)) or Decimal("0.01")
    )
    assert first.fee_amount == Decimal("0.01") and second.fee_amount is None and asked == [(7, 2)]
