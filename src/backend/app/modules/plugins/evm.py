"""Shared reader for EVM networks in the Etherscan answer form (research 2026-08-27).

Blockscout (Ethereum, Polygon), Routescan (Avalanche) and Etherscan V2 (Sonic) all
answer `module=account&action=txlist|tokentx|txlistinternal` the same way, so one
reader serves them. Networks with their own form (Cronos, BNB through NodeReal)
map their records into this form and reuse `convert`.

Three lists, not one: `txlist` (native coin, carries the fee), `tokentx` (tokens)
and `txlistinternal` (native coin sent by contracts, e.g. exchange withdrawals).

* The fee belongs to the native row only. `tokentx` repeats gasUsed/gasPrice of
  the same transaction; booking it there counts the fee twice or more.
* A failed transaction moves no value but the gas is gone: booked as `fee`.
* EVM addresses carry a checksum in their letter case: compare lower case.
* Amounts are integers in the smallest unit; `scaleb` shifts the point exactly,
  a float division would already be wrong at 18 decimals.
* Errors come back as HTTP 200 with status "0": a missing result is an error,
  "No transactions found" is an answer, not an empty wallet by accident.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.modules.plugins.contract import Kind, Movement, fingerprint

PAGE = 1000
WINDOW = 10_000  # rows one query can reach (page × offset)
TIMEOUT = 30
RETRY_PAUSES = (2, 5, 10)  # seconds before the 2nd, 3rd, 4th try
LISTS = ("txlist", "tokentx", "txlistinternal")


class ChainUnavailable(RuntimeError):
    pass


MAX_RESET_WAIT = 15 * 60


def reset_wait(headers) -> float:
    """Seconds until a throttled explorer lets us in again: Blockscout sends
    `x-ratelimit-reset` in milliseconds (Ronin: 10 calls, then ~9 minutes, measured
    2026-10-05). A background fetch may wait that long; longer waits are not worth it."""
    try:
        ms = float((headers or {}).get("x-ratelimit-reset") or 0)
    except (TypeError, ValueError):
        return 0.0
    return min(ms / 1000 + 1, MAX_RESET_WAIT) if ms > 0 else 0.0


def http_json(url: str, body: dict | None = None, headers: dict | None = None) -> Any:
    """GET (or POST with a JSON body). Messages never carry the URL: it may hold a key.
    `headers` for an API key sent as a header (TronGrid)."""
    data = None if body is None else json.dumps(body).encode()
    headers = {
        "User-Agent": "owncryptofolio",
        "Content-Type": "application/json",
        **(headers or {}),
    }
    for attempt in range(len(RETRY_PAUSES) + 1):
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            # Free explorers throttle (429) or are briefly overloaded (503): wait and
            # retry instead of failing the whole fetch (measured 2026-10-03, Blockscout).
            if exc.code in (429, 503) and attempt < len(RETRY_PAUSES):
                time.sleep(max(RETRY_PAUSES[attempt], reset_wait(exc.headers)))
                continue
            raise ChainUnavailable(f"HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            # a slow or briefly unreachable explorer: litecoinspace timed out at the 04:00
            # round three times (2026-10-10/12) and answered fine minutes later
            if attempt < len(RETRY_PAUSES):
                time.sleep(RETRY_PAUSES[attempt])
                continue
            raise ChainUnavailable(type(exc).__name__) from exc
        except ValueError as exc:
            raise ChainUnavailable(type(exc).__name__) from exc
    raise ChainUnavailable("no answer")


@dataclass
class Explorer:
    """An API in the Etherscan form. `params` carries e.g. `chainid` for Etherscan V2."""

    base: str
    params: dict = field(default_factory=dict)
    key: str | None = None
    pause: float = 0.0  # Etherscan's free tier allows a few calls per second

    def get(self, params: dict) -> list[dict]:
        query = {**self.params, **params, **({"apikey": self.key} if self.key else {})}
        if self.pause:
            time.sleep(self.pause)
        body = http_json(f"{self.base}?{urllib.parse.urlencode(query)}")
        result = body.get("result")
        if isinstance(result, list):
            return result
        message = str(result or body.get("message") or "")
        if "No transactions found" in message or "No internal transactions" in message:
            return []
        raise ChainUnavailable(message[:120] or "invalid answer")

    def all(self, action: str, address: str) -> list[dict]:
        """Every row of one list. The explorers give at most 10,000 rows per query
        (page × offset, "Result window is too large"): beyond that the query starts again at
        the last block read, whose rows are read again in full (review 2026-10-24)."""
        rows: list[dict] = []
        page, start = 1, 0
        while True:
            batch = self.get(
                {
                    "module": "account",
                    "action": action,
                    "address": address,
                    "startblock": start,
                    "page": page,
                    "offset": PAGE,
                    "sort": "asc",
                }
            )
            rows.extend(batch)
            if len(batch) < PAGE:
                return rows
            if page * PAGE < WINDOW:
                page += 1
                continue
            last = int(batch[-1].get("blockNumber") or 0)
            if last <= start:
                raise ChainUnavailable("more rows in one block than one query can hold")
            rows = [r for r in rows if int(r.get("blockNumber") or 0) < last]
            page, start = 1, last


def fetch(
    explorer: Explorer,
    address: str,
    since: datetime | None,
    progress: Callable[[dict], None] | None,
    native: str,
    decimals: int = 18,
) -> Iterator[Movement]:
    lists: dict[str, list[dict]] = {}
    for i, action in enumerate(LISTS, 1):
        lists[action] = explorer.all(action, address)
        if progress:
            rows = sum(len(v) for v in lists.values())
            progress({"step": action, "done": i, "total": len(LISTS), "rows": rows})
    movements = convert(address, *(lists[a] for a in LISTS), native=native, decimals=decimals)
    yield from since_only(movements, since)


def since_only(movements: list[Movement], since: datetime | None) -> Iterator[Movement]:
    # Full lists are cheap at wallet scale; `since` only trims what is handed on.
    return (m for m in movements if since is None or m.timestamp >= since)


def amount(raw: str | int, decimals: int) -> Decimal:
    return Decimal(int(raw)).scaleb(-decimals)


def _ts(value: str | int) -> datetime:
    return datetime.fromtimestamp(int(value), tz=UTC)


def convert(
    address: str,
    txlist: list[dict],
    tokentx: list[dict],
    internal: list[dict],
    *,
    native: str,
    decimals: int = 18,
) -> list[Movement]:
    """Pure conversion — no network, testable."""
    me = address.lower()
    out: list[Movement] = []
    for r in txlist:
        out.extend(_native(r, me, native, decimals))
    for r in tokentx:
        symbol = (r.get("tokenSymbol") or "").strip() or "UNKNOWN"
        out.append(_transfer(r, me, symbol, int(r.get("tokenDecimal") or 0), "token"))
    for r in internal:
        if r.get("isError") == "1":
            continue
        out.append(_transfer(r, me, native, decimals, "internal"))
    return _apart(out)


def _apart(rows: list[Movement]) -> list[Movement]:
    """Two equal transfers in one transaction (a payout contract sending 5 USDT twice) would
    share one fingerprint and the second would count as a duplicate (review 2026-10-24).
    From the second on they get `hash:2`, `hash:3`; the first keeps the plain hash, so rows
    read before stay recognised. The same log entry listed twice (`logIndex`, `traceId`)
    is still one row."""
    seen: dict[str, list[object]] = {}
    out = []
    for m in rows:
        key = fingerprint("", m)
        raw = m.raw or {}
        entry = raw["logIndex"] if raw.get("logIndex") is not None else raw.get("traceId")
        known = seen.setdefault(key, [])
        if known and (entry is None or entry in known):
            continue  # the very same record twice
        known.append(entry)
        if len(known) > 1:
            m = m.model_copy(update={"external_id": f"{m.external_id}:{len(known)}"})
        out.append(m)
    return out


def _fee(r: dict, native: str, decimals: int) -> dict:
    used, price = r.get("gasUsed"), r.get("gasPrice")
    if not used or not price:
        return {}
    return {"fee_asset": native, "fee_amount": amount(int(used) * int(price), decimals)}


def _native(r: dict, me: str, native: str, decimals: int) -> list[Movement]:
    sender, receiver = (r.get("from") or "").lower(), (r.get("to") or "").lower()
    value = amount(r.get("value") or 0, decimals)
    fee = _fee(r, native, decimals)
    base = {"timestamp": _ts(r["timeStamp"]), "external_id": r.get("hash"), "raw": r}
    if r.get("isError") == "1":
        if sender == me:
            return [Movement(kind=Kind.FEE, comment="failed transaction", **fee, **base)]
        return []  # someone else's failed attempt: nothing arrived, nothing paid
    if sender == me and value == 0:
        # A contract call (token transfer, approval, swap): the gas is the movement here,
        # the tokens come through tokentx.
        return [Movement(kind=Kind.FEE, comment="contract call", **fee, **base)]
    if sender == me and receiver == me:
        return [
            Movement(
                kind=Kind.INTERNAL_TRANSFER,
                incoming_asset=native,
                incoming_amount=value,
                outgoing_asset=native,
                outgoing_amount=value,
                **fee,
                **base,
            )
        ]
    if sender == me:
        return [
            Movement(
                kind=Kind.SEND,
                outgoing_asset=native,
                outgoing_amount=value,
                counterparty=r.get("to"),
                **fee,
                **base,
            )
        ]
    if receiver == me and value > 0:
        # The sender pays the gas on every chain: no fee on receipt.
        return [
            Movement(
                kind=Kind.RECEIVE,
                incoming_asset=native,
                incoming_amount=value,
                counterparty=r.get("from"),
                **base,
            )
        ]
    return []


def _transfer(r: dict, me: str, asset: str, decimals: int, source: str) -> Movement:
    sender, receiver = (r.get("from") or "").lower(), (r.get("to") or "").lower()
    value = amount(r.get("value") or 0, decimals)
    base = {
        "timestamp": _ts(r["timeStamp"]),
        "external_id": r.get("hash"),
        "comment": f"{source} {r.get('tokenName') or ''}".strip(),
        "raw": r,
    }
    if sender == me and receiver == me:
        return Movement(
            kind=Kind.INTERNAL_TRANSFER,
            incoming_asset=asset,
            incoming_amount=value,
            outgoing_asset=asset,
            outgoing_amount=value,
            **base,
        )
    if sender == me:
        return Movement(
            kind=Kind.SEND,
            outgoing_asset=asset,
            outgoing_amount=value,
            counterparty=r.get("to"),
            **base,
        )
    if receiver == me:
        return Movement(
            kind=Kind.RECEIVE,
            incoming_asset=asset,
            incoming_amount=value,
            counterparty=r.get("from"),
            **base,
        )
    # The address only took part (e.g. a contract event): shown, never dropped.
    return Movement(kind=Kind.OTHER, incoming_asset=asset, incoming_amount=value, **base)


# --- balances (ADR 0039) ---------------------------------------------------------------

BALANCE_OF = "0x70a08231"  # balanceOf(address)


def rpc(url: str, method: str, params: list):
    body = http_json(url, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    if not isinstance(body, dict) or "error" in body:
        message = (body.get("error") or {}).get("message") if isinstance(body, dict) else None
        raise ChainUnavailable(str(message or "invalid answer")[:120])
    return body.get("result")


def balances(
    url: str, address: str, native: str, decimals: int, tokens: dict[str, tuple[str, int]] | None
) -> list[tuple[str, str, Decimal]]:
    """Native coin by eth_getBalance and every token the address ever moved by balanceOf,
    over a public RPC node (no key). A token that does not answer is left out, not 0."""
    out = [
        ("spot", native, amount(int(rpc(url, "eth_getBalance", [address, "latest"]), 16), decimals))
    ]
    data = BALANCE_OF + "0" * 24 + address[2:].lower()
    for symbol, (contract, token_decimals) in (tokens or {}).items():
        try:
            value = rpc(url, "eth_call", [{"to": contract, "data": data}, "latest"])
        except ChainUnavailable:
            continue
        if isinstance(value, str) and value.startswith("0x") and len(value) > 2:
            out.append(("spot", symbol, amount(int(value, 16), token_decimals)))
    return out
