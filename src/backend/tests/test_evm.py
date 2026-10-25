"""EVM networks beyond Ethereum: shared reader, Cronos form, BNB through NodeReal."""

from decimal import Decimal

import pytest

from app.modules.plugins import evm
from app.modules.plugins.registry import discover

ME = "0xAbCdEf0000000000000000000000000000000001"
OTHER = "0x9999999999999999999999999999999999999999"


def test_all_evm_networks_are_plugins_with_their_service():
    reg = discover()
    chains = {
        p.manifest.source.provider: p.manifest.chain
        for p in reg.plugins.values()
        if p.manifest.chain
    }
    assert {"ethereum", "polygon", "avalanche", "sonic", "cronos", "bnb"} <= set(chains)
    assert {
        k: chains[k].native_asset for k in ("polygon", "avalanche", "sonic", "cronos", "bnb")
    } == {
        "polygon": "POL",
        "avalanche": "AVAX",
        "sonic": "S",
        "cronos": "CRO",
        "bnb": "BNB",
    }
    assert {k: chains[k].service for k in chains if chains[k].family == "evm"} == {
        "ethereum": "",
        "polygon": "etherscan",  # Blockscout behind Cloudflare since 2026-10
        "avalanche": "",
        "sonic": "etherscan",
        "cronos": "cronos",
        "bnb": "nodereal",
        "ronin": "",
        # added 2026-10-20 (beta): the free Etherscan key or a Blockscout without key
        "arbitrum": "etherscan",
        "linea": "etherscan",
        "mantle": "etherscan",
        "blast": "etherscan",
        "optimism": "",
        "zksync": "",
        "celo": "",
    }
    assert {k: chains[k].native_asset for k in ("mantle", "celo", "zksync")} == {
        "mantle": "MNT",
        "celo": "CELO",
        "zksync": "ETH",
    }


def test_explorer_sends_chainid_and_key_and_treats_status_0_as_error(monkeypatch):
    seen = []

    def answer(url, body=None):
        seen.append(url)
        return {"status": "0", "message": "NOTOK", "result": "Invalid API Key"}

    monkeypatch.setattr(evm, "http_json", answer)
    with pytest.raises(evm.ChainUnavailable, match="Invalid API Key"):
        evm.Explorer("https://x/api", {"chainid": 146}, key="k").get({"action": "txlist"})
    assert "chainid=146" in seen[0] and "apikey=k" in seen[0]


def test_no_transactions_found_is_an_empty_list(monkeypatch):
    monkeypatch.setattr(
        evm,
        "http_json",
        lambda url, body=None: {"status": "0", "message": "No transactions found", "result": []},
    )
    assert evm.Explorer("https://x/api").all("tokentx", ME) == []


def test_cronos_record_with_address_objects_is_received():
    from integrations.chain_cronos.reader import as_etherscan

    r = {
        "timestamp": 1781724486,
        "transactionHash": "0xh",
        "status": 1,
        "from": {"address": OTHER, "isContract": False},
        "to": {"address": ME.lower(), "isContract": False},
        "value": "1765677054500000000000",
        "cumulativeGasUsed": 25000,
        "gasPrice": "10378750000000",
    }
    (m,) = evm.convert(ME, [as_etherscan(r)], [], [], native="CRO")
    assert m.kind.value == "receive" and m.incoming_amount == Decimal("1765.6770545")
    assert m.incoming_asset == "CRO" and m.fee_amount is None and m.external_id == "0xh"


def test_cronos_failed_send_is_a_fee():
    from integrations.chain_cronos.reader import as_etherscan

    r = {
        "timestamp": 1,
        "transactionHash": "0xf",
        "status": 0,
        "from": {"address": ME},
        "to": {"address": OTHER},
        "value": "5",
        "cumulativeGasUsed": 21000,
        "gasPrice": "1000000000",
    }
    (m,) = evm.convert(ME, [as_etherscan(r)], [], [], native="CRO")
    assert m.kind.value == "fee" and m.fee_amount == Decimal("0.000021") and m.fee_asset == "CRO"


def test_bnb_transfers_split_into_three_lists_and_self_transfer_counts_once():
    from integrations.chain_bnb.reader import split

    me = ME.lower()
    external = {
        "category": "external",
        "blockTimeStamp": 1620089457,
        "hash": "0xa",
        "from": OTHER,
        "to": me,
        "value": "0xde0b6b3a7640000",
        "asset": "BNB",
        "gasPrice": 5000000000,
        "gasUsed": 21000,
        "receiptsStatus": 1,
    }
    token = {
        "category": "20",
        "blockTimeStamp": 1620089460,
        "hash": "0xb",
        "from": OTHER,
        "to": me,
        "value": "0x0000000000000000000000000000000000000000000000000564d702d38f5e0000",
        "asset": "CAKE",
        "decimal": 18,
        "contractAddress": "0xc",
    }
    self_send = {
        "category": "external",
        "blockTimeStamp": 1620089470,
        "hash": "0xs",
        "from": me,
        "to": me,
        "value": "0x1",
        "gasPrice": 1,
        "gasUsed": 1,
        "receiptsStatus": 1,
    }
    internal = {
        "category": "internal",
        "blockTimeStamp": 1620089480,
        "hash": "0xi",
        "from": OTHER,
        "to": me,
        "value": "0x2386f26fc10000",
    }
    # fromAddress and toAddress both return the transfer to myself
    txlist, tokentx, internals = split([external, token, self_send, self_send, internal])
    assert (len(txlist), len(tokentx), len(internals)) == (2, 1, 1)
    moves = evm.convert(ME, txlist, tokentx, internals, native="BNB")
    kinds = {(m.kind.value, m.incoming_asset, m.incoming_amount) for m in moves}
    assert ("receive", "BNB", Decimal(1)) in kinds
    assert ("receive", "CAKE", Decimal("99.5")) in kinds
    assert ("receive", "BNB", Decimal("0.01")) in kinds
    assert ("internal_transfer", "BNB", Decimal("1E-18")) in kinds


def test_bnb_failed_external_send_is_a_fee():
    from integrations.chain_bnb.reader import split

    t = {
        "category": "external",
        "blockTimeStamp": 1,
        "hash": "0xf",
        "from": ME.lower(),
        "to": OTHER,
        "value": "0x5",
        "gasPrice": 1000000000,
        "gasUsed": 21000,
        "receiptsStatus": 0,
    }
    (m,) = evm.convert(ME, *split([t]), native="BNB")
    assert m.kind.value == "fee" and m.fee_asset == "BNB"


def test_keyed_networks_refuse_to_run_without_key():
    from integrations.chain_bnb import reader as bnb
    from integrations.chain_cronos import reader as cronos

    for reader in (bnb, cronos):
        with pytest.raises(evm.ChainUnavailable, match="key missing"):
            list(reader.fetch(ME, None))


def test_bnb_windows_stay_below_two_million_blocks():
    from integrations.chain_bnb.reader import windows

    w = windows(125_535_367)
    assert w[0] == (0, 1_999_999) and w[-1][1] == 125_535_367
    assert all(e - s + 1 <= 2_000_000 for s, e in w) and len(w) == 63
    assert all(w[i][1] + 1 == w[i + 1][0] for i in range(len(w) - 1))


def test_bnb_address_that_never_sent_is_only_asked_as_receiver(monkeypatch):
    from integrations.chain_bnb import reader

    asked = []

    def rpc(key, method, params):
        if method == "eth_blockNumber":
            return hex(3_000_000)
        if method == "eth_getTransactionCount":
            return "0x0"
        p = params[0]
        asked.append(("fromAddress" in p, p["fromBlock"], p["toBlock"]))
        return {"transfers": []}

    monkeypatch.setattr(reader, "_rpc", rpc)
    assert list(reader.fetch(ME, None, key="k")) == []
    assert asked == [(False, "0x0", hex(1_999_999)), (False, hex(2_000_000), hex(3_000_000))]


def test_bnb_two_equal_token_transfers_in_one_tx_stay_two():
    from integrations.chain_bnb.reader import split

    t = {
        "category": "20",
        "blockTimeStamp": 1,
        "hash": "0xh",
        "from": OTHER,
        "to": ME.lower(),
        "value": "0x1",
        "asset": "X",
        "decimal": "18",
        "contractAddress": "0xc",
    }
    _, tokentx, _ = split([{**t, "logIndex": 1}, {**t, "logIndex": 2}, {**t, "logIndex": 2}])
    assert len(tokentx) == 2


def test_throttled_answer_is_retried(monkeypatch):
    import io
    import urllib.error

    calls = []

    def fake_urlopen(req, timeout):
        calls.append(1)
        if len(calls) < 3:
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, None)
        return io.BytesIO(b'{"status": "1", "result": []}')

    monkeypatch.setattr(evm.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(evm.time, "sleep", lambda s: None)
    assert evm.http_json("https://x/api") == {"status": "1", "result": []} and len(calls) == 3


def test_throttling_that_does_not_end_fails_named(monkeypatch):
    import urllib.error

    def always_429(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, None)

    monkeypatch.setattr(evm.urllib.request, "urlopen", always_429)
    monkeypatch.setattr(evm.time, "sleep", lambda s: None)
    with pytest.raises(evm.ChainUnavailable, match="HTTP 429"):
        evm.http_json("https://x/api")


def test_ronin_reads_ronin_prefixed_addresses_as_hex():
    from integrations.chain_ronin import reader

    assert reader.hex_address("ronin:" + "ab" * 20) == "0x" + "ab" * 20
    assert reader.hex_address("0x" + "cd" * 20) == "0x" + "cd" * 20


def test_throttled_explorer_waits_for_its_reset():
    from app.modules.plugins.evm import MAX_RESET_WAIT, reset_wait

    assert reset_wait({"x-ratelimit-reset": "546789"}) == pytest.approx(547.789)
    assert reset_wait({"x-ratelimit-reset": "99999999"}) == MAX_RESET_WAIT
    assert reset_wait({}) == 0 and reset_wait(None) == 0


def test_a_timeout_is_retried_then_named(monkeypatch):
    """litecoinspace timed out at the 04:00 round and answered minutes later (2026-10-12)."""
    import io

    calls = []

    def slow_then_fine(req, timeout):
        calls.append(1)
        if len(calls) < 2:
            raise TimeoutError
        return io.BytesIO(b"[]")

    monkeypatch.setattr(evm.urllib.request, "urlopen", slow_then_fine)
    monkeypatch.setattr(evm.time, "sleep", lambda s: None)
    assert evm.http_json("https://x/api") == [] and len(calls) == 2

    def always_slow(req, timeout):
        raise TimeoutError

    monkeypatch.setattr(evm.urllib.request, "urlopen", always_slow)
    with pytest.raises(evm.ChainUnavailable, match="TimeoutError"):
        evm.http_json("https://x/api")


def test_bnb_balance_knows_axs_and_slp_without_a_stored_contract(monkeypatch):
    # rows read before 2026-10-04 carry no contract; the two that matter are known
    from integrations.chain_bnb import reader

    asked = {}

    def fake(url, address, native, decimals, tokens):
        asked.update(tokens)
        return [
            ("spot", "BNB", Decimal("1")),
            ("spot", "AXS", Decimal("5")),
            ("spot", "SLP", Decimal("0")),
        ]

    monkeypatch.setattr(reader.evm, "balances", fake)
    out = reader.balance("0x" + "0" * 40, tokens={})
    assert {"AXS", "SLP"} <= asked.keys()
    assert [a for _, a, _ in out] == ["BNB", "AXS"]  # a known token never held stays out


def test_two_equal_token_transfers_in_one_transaction_stay_two():
    """A payout contract sends 5 USDT twice in one tx (review 2026-10-24): two rows, the
    first with the plain hash as before; the same log entry listed twice is still one."""
    from app.modules.plugins.contract import fingerprint
    from app.modules.plugins.evm import convert

    me = "0x" + "a" * 40
    row = {
        "timeStamp": "1700000000",
        "hash": "0xabc",
        "from": "0x" + "b" * 40,
        "to": me,
        "value": "5000000",
        "tokenSymbol": "USDT",
        "tokenDecimal": "6",
    }
    out = convert(me, [], [row | {"logIndex": "1"}, row | {"logIndex": "2"}], [], native="ETH")
    assert [m.external_id for m in out] == ["0xabc", "0xabc:2"]
    assert len({fingerprint("s", m) for m in out}) == 2
    again = convert(me, [], [row | {"logIndex": "1"}, row | {"logIndex": "1"}], [], native="ETH")
    assert [m.external_id for m in again] == ["0xabc"]


def test_more_than_ten_thousand_rows_continue_from_the_last_block(monkeypatch):
    """Explorers stop at page × offset = 10,000: the list goes on from the last block read,
    rows of that block are read again, none twice (review 2026-10-24)."""
    monkeypatch.setattr(evm, "PAGE", 2)
    monkeypatch.setattr(evm, "WINDOW", 4)
    chain_rows = [
        {"hash": f"h{i}", "blockNumber": str(b)} for i, b in enumerate([1, 2, 3, 3, 4, 5, 6])
    ]
    asked = []

    def get(self, params):
        asked.append((params["startblock"], params["page"]))
        rows = [r for r in chain_rows if int(r["blockNumber"]) >= params["startblock"]]
        if (params["page"]) * params["offset"] > 4:
            raise evm.ChainUnavailable("Result window is too large")
        i = (params["page"] - 1) * params["offset"]
        return rows[i : i + params["offset"]]

    monkeypatch.setattr(evm.Explorer, "get", get)
    explorer = evm.Explorer.__new__(evm.Explorer)
    got = explorer.all("txlist", "0x0")
    assert [r["hash"] for r in got] == [f"h{i}" for i in range(7)]
    assert asked[2][0] == 3  # started again at block 3
