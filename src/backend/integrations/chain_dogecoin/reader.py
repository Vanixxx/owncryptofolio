"""Dogecoin through BlockCypher (2026-10-23).

* Blockchair blocked the IP after a handful of free calls ("temporarily blacklisted",
  keys only on request), Trezor's Blockbook answers 403: BlockCypher's free tier (about
  100 calls an hour) carries a wallet — one call brings 50 transactions with their inputs.
* `/addrs/{a}/full?limit=50&txlimit=1000` pages backwards with `before=<height>` while
  `hasMore`. Each transaction names input addresses with `output_value`, outputs with
  `value`, and `fees` (satoshi-like units, 10^-8).
* Netted per transaction like Bitcoin (`mempool.netted`): sent + fee = what left the
  address, foreign inputs → "other". Unconfirmed transactions are skipped.
* Checked against a public address (4 transactions): the sum equals the balance.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime

from app.modules.plugins import chain, mempool
from app.modules.plugins.contract import Movement

API = "https://api.blockcypher.com/v1/doge/main"
NATIVE, DECIMALS = "DOGE", 8


def transactions(address: str) -> list[dict]:
    rows: list[dict] = []
    hashes: set[str] = set()
    before = None
    while True:
        body = chain.http_json(
            f"{API}/addrs/{address}/full?limit=50&txlimit=1000"
            + (f"&before={before}" if before else "")
        )
        page = (body or {}).get("txs")
        if not isinstance(page, list):
            raise chain.ChainUnavailable("invalid answer")
        new = [t for t in page if t.get("hash") not in hashes]
        rows += new
        hashes.update(t.get("hash") for t in new)
        heights = [t.get("block_height") for t in page if (t.get("block_height") or 0) > 0]
        if not body.get("hasMore") or not heights or not new:
            return rows
        # `before` is strictly below: one above the lowest block, so a block that the page
        # edge cut through is read again in full (review 2026-10-24); repeats are dropped
        before = min(heights) + 1


def convert(address: str, txs: list[dict]) -> list[Movement]:
    out: list[Movement] = []
    seen: set[str] = set()
    for t in txs:
        if not t.get("confirmed") or (t.get("block_height") or 0) <= 0 or t.get("hash") in seen:
            continue
        seen.add(t["hash"])
        if t.get("next_inputs") or t.get("next_outputs"):
            ins: list = [(None, None)]  # not all listed: no guess about who paid
        else:
            ins = [
                ((i.get("addresses") or [None])[0], i.get("output_value"))
                for i in t.get("inputs") or []
            ]
        m = mempool.netted(
            address,
            ins,
            [((o.get("addresses") or [None])[0], o.get("value")) for o in t.get("outputs") or []],
            fee=int(t.get("fees") or 0),
            timestamp=datetime.fromisoformat(t["confirmed"].replace("Z", "+00:00")),
            external_id=t.get("hash"),
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
    txs = transactions(address)
    if progress:
        progress({"step": "transactions", "done": 1, "total": 1, "rows": len(txs)})
    yield from chain.since_only(convert(address, txs), since)


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    body = chain.http_json(f"{API}/addrs/{address}/balance")
    return [("spot", NATIVE, chain.units(body.get("balance") or 0, DECIMALS))]
