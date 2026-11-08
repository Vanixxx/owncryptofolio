"""Qubic through rpc.qubic.org (research 2026-11-06).

Two sources that overlap badly, so each serves one side of `EVENTS_FROM`:

* **Transfer events** (`getEventLogs`, type 0, beta) exist from epoch 207 on and hold every
  QU that moved, also the receipts no transaction of this identity shows: contract payouts,
  SendMany. A contract that sends money back gives a second event with the same hash, so
  an event is one movement.
* **Transactions** (`getTransactionsForIdentity`) reach back to epoch 104 (2024-04-10) but
  only name the signed transfer. Whatever a contract paid out before `EVENTS_FROM` cannot
  be read at all: the balance check shows that gap.

* QUBIC has no decimals and no network fee.
* At most 1000 rows a page and 10000 a query, `hits.total` stops at 10000: past that the
  next query starts at the lowest tick reached (rows sort by tick, descending).
* The Cloudflare in front answers 429 to quick series; 1.3 s apart held for hundreds of
  calls (measured 2026-11-06). The API documents no limit.
* `moneyFlew` means the money moved only for plain transfers: a contract call that failed
  still says true. Before `EVENTS_FROM` its refund is not visible.
* The counters in the balance answer are no lifetime totals: they start over once an
  identity was empty.
"""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Callable, Iterator
from datetime import UTC, datetime

from app.modules.plugins import chain
from app.modules.plugins.contract import Movement

API = "https://rpc.qubic.org"
NATIVE, DECIMALS = "QUBIC", 0
EVENTS_FROM = 48160000  # first tick of epoch 207 (2026-04-01): no transfer event before it
PAGE, LIMIT = 1000, 10000
PAUSE = 1.3


def _walk(path: str, field: str, body: dict, tick_range: dict) -> list[dict]:
    """Every row of a query, however many. Pages overlap at the tick they meet in."""
    rows: list[dict] = []
    ticks = dict(tick_range)
    while True:
        for offset in range(0, LIMIT, PAGE):
            if rows:
                time.sleep(PAUSE)
            answer = chain.http_json(
                f"{API}/query/v1/{path}",
                {
                    **body,
                    "ranges": {"tickNumber": ticks},
                    "pagination": {"offset": offset, "size": PAGE},
                },
            )
            page = (answer or {}).get(field)
            if not isinstance(page, list):
                raise chain.ChainUnavailable("invalid answer")
            rows += page
            if len(page) < PAGE:
                return rows
        lowest = str(min(int(r["tickNumber"]) for r in page))
        if lowest == ticks.get("lte"):
            raise chain.ChainUnavailable("more rows in one tick than a query returns")
        ticks = {**ticks, "lte": lowest}


def transactions(address: str) -> list[dict]:
    rows = _walk(
        "getTransactionsForIdentity",
        "transactions",
        {"identity": address},
        {"lte": str(EVENTS_FROM - 1)},
    )
    return list({r["hash"]: r for r in rows}.values())


def events(address: str) -> list[dict]:
    rows: list[dict] = []
    for side in ("source", "destination"):
        rows += _walk(
            "getEventLogs",
            "eventLogs",
            {"filters": {side: address, "logType": "0"}},
            {"gte": str(EVENTS_FROM)},
        )
        time.sleep(PAUSE)
    # to myself: found from both sides. logId starts over each epoch
    return list({(r["epoch"], r["logId"]): r for r in rows}.values())


def _when(ms) -> datetime:
    return datetime.fromtimestamp(int(ms) / 1000, tz=UTC)


def _movement(address: str, source, destination, amount, ms, external_id, raw) -> Movement:
    return chain.transfer(
        sent=source == address,
        received=destination == address,
        asset=NATIVE,
        amount=chain.units(amount, DECIMALS),
        sender=source,
        receiver=destination,
        timestamp=_when(ms),
        external_id=external_id,
        raw=raw,
    )


def convert(address: str, txs: list[dict], logs: list[dict]) -> list[Movement]:
    out = [
        _movement(address, t["source"], t["destination"], t["amount"], t["timestamp"], t["hash"], t)
        for t in txs
        if t.get("moneyFlew") and int(t["amount"]) and int(t["tickNumber"]) < EVENTS_FROM
    ]
    hashes = Counter(e.get("transactionHash") for e in logs)
    for e in logs:
        q = e.get("quTransfer") or {}
        if int(e["tickNumber"]) < EVENTS_FROM or not int(q.get("amount") or 0):
            continue
        tx = e.get("transactionHash")
        # the bare hash when it stands alone: transfer matching compares it with the exchange's
        external_id = tx if tx and hashes[tx] == 1 else f"{tx or f'epoch{e["epoch"]}'}:{e['logId']}"
        out.append(
            _movement(
                address,
                q.get("source"),
                q.get("destination"),
                q["amount"],
                e["timestamp"],
                external_id,
                e,
            )
        )
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
        progress({"step": "transactions", "done": 1, "total": 2, "rows": len(txs)})
    time.sleep(PAUSE)
    logs = events(address)
    if progress:
        progress({"step": "events", "done": 2, "total": 2, "rows": len(txs) + len(logs)})
    yield from chain.since_only(convert(address, txs, logs), since)


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    answer = chain.http_json(f"{API}/live/v1/balances/{address}")
    value = (answer or {}).get("balance")
    if not isinstance(value, dict):
        raise chain.ChainUnavailable("invalid answer")
    return [("spot", NATIVE, chain.units(value.get("balance") or 0, DECIMALS))]
