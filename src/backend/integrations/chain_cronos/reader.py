"""Cronos EVM through the Cronos Explorer API (research 2026-08-27, measured 2026-10-03).

Not in Etherscan V2, no Blockscout instance, Routescan says "chain not supported".
`cronoscan.com` answers every path with HTTP 200 and HTML — a dead end that looks alive.

The answer has its own form, mapped onto the Etherscan form for the shared reader:

* `getTxsByAddress`, `startBlock`/`endBlock` are mandatory (HTTP 400 otherwise).
* `from`/`to` are objects with `.address`; compared as strings they never match.
* The hash is `transactionHash`, gas used is `cumulativeGasUsed`, `status` is 1 on
  success (a number now, a string in 2026-08).
* Only native CRO: token and internal transfer endpoints were not found (404/400).
"""

from __future__ import annotations

import urllib.parse
from collections.abc import Callable, Iterator
from datetime import datetime

from app.modules.plugins import evm
from app.modules.plugins.contract import Movement

API = "https://explorer-api.cronos.org/mainnet/api/v1"
NATIVE, DECIMALS = "CRO", 18
PAGE = 100


def _address(value) -> str:
    return (value.get("address") if isinstance(value, dict) else value) or ""


def as_etherscan(r: dict) -> dict:
    return {
        "timeStamp": r["timestamp"],
        "hash": r.get("transactionHash"),
        "from": _address(r.get("from")),
        "to": _address(r.get("to")),
        "value": r.get("value") or 0,
        "isError": "0" if str(r.get("status")) == "1" else "1",
        "gasUsed": r.get("cumulativeGasUsed") or r.get("gas"),
        "gasPrice": r.get("gasPrice"),
    }


def _transactions(address: str, key: str) -> list[dict]:
    rows: list[dict] = []
    page = 1
    while True:
        query = {
            "address": address,
            "startBlock": 0,
            "endBlock": 999_999_999,
            "page": page,
            "limit": PAGE,
            "apikey": key,
        }
        body = evm.http_json(f"{API}/account/getTxsByAddress?{urllib.parse.urlencode(query)}")
        result = body.get("result")
        if not isinstance(result, list):
            raise evm.ChainUnavailable(str(body.get("message") or "invalid answer")[:120])
        rows.extend(result)
        total = (body.get("pagination") or {}).get("totalPage") or 1
        if page >= total or not result:
            return rows
        page += 1


def fetch(
    address: str,
    since: datetime | None,
    progress: Callable[[dict], None] | None = None,
    key: str | None = None,
) -> Iterator[Movement]:
    if not key:
        raise evm.ChainUnavailable("Cronos Explorer key missing")
    txs = [as_etherscan(r) for r in _transactions(address, key)]
    if progress:
        progress({"step": "txlist", "done": 1, "total": 1, "rows": len(txs)})
    movements = evm.convert(address, txs, [], [], native=NATIVE, decimals=DECIMALS)
    yield from evm.since_only(movements, since)


BALANCE_RPC = "https://evm.cronos.org"


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    return evm.balances(BALANCE_RPC, address, NATIVE, DECIMALS, tokens)
