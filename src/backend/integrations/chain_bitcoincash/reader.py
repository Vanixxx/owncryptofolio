"""Bitcoin Cash through Haskoin (bitcoin.com's indexer, 2026-10-23).

* Blockchair blocked the IP after a few free calls, Trezor's Blockbook answers 403;
  `api.haskoin.com/bch` answers freely.
* `/address/{a}/transactions/full?limit=&offset=` (newest first) with inputs and outputs
  (`address`, `value` in satoshi) and `fee`. **Addresses are CashAddr with the prefix**
  (`bitcoincash:q…`): an address entered without it gets it, to compare.
* Netted per transaction like Bitcoin (`mempool.netted`). A transaction still in the
  mempool has no block height: skipped until confirmed.
* Checked against a public address (24 transactions): the sum equals the balance.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime

from app.modules.plugins import chain, mempool
from app.modules.plugins.contract import Movement

API = "https://api.haskoin.com/bch"
NATIVE, DECIMALS = "BCH", 8
PAGE = 100
PREFIX = "bitcoincash:"


def cashaddr(address: str) -> str:
    a = address.strip().lower()
    return a if a.startswith(PREFIX) else PREFIX + a


def transactions(address: str) -> list[dict]:
    rows: list[dict] = []
    while True:
        page = chain.http_json(
            f"{API}/address/{address}/transactions/full?limit={PAGE}&offset={len(rows)}"
        )
        if not isinstance(page, list):
            raise chain.ChainUnavailable("invalid answer")
        rows += page
        if len(page) < PAGE:
            return rows


def convert(address: str, txs: list[dict]) -> list[Movement]:
    me = cashaddr(address)
    out: list[Movement] = []
    for t in txs:
        block = t.get("block") or {}
        if t.get("deleted") or "height" not in block or not t.get("time"):
            continue
        m = mempool.netted(
            me,
            [(i.get("address"), i.get("value")) for i in t.get("inputs") or []],
            [(o.get("address"), o.get("value")) for o in t.get("outputs") or []],
            fee=int(t.get("fee") or 0),
            timestamp=chain.seconds(t["time"]),
            external_id=t.get("txid"),
            raw=t,
            native=NATIVE,
            decimals=DECIMALS,
        )
        if m:
            out.append(m)
    out.sort(key=lambda m: m.timestamp)
    return out


def fetch(
    address: str,
    since: datetime | None,
    progress: Callable[[dict], None] | None = None,
    key: str | None = None,
) -> Iterator[Movement]:
    txs = transactions(cashaddr(address))
    if progress:
        progress({"step": "transactions", "done": 1, "total": 1, "rows": len(txs)})
    yield from chain.since_only(convert(address, txs), since)


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    body = chain.http_json(f"{API}/address/{cashaddr(address)}/balance")
    return [("spot", NATIVE, chain.units(body.get("confirmed") or 0, DECIMALS))]
