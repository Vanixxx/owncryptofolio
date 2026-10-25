"""BNB Smart Chain through NodeReal MegaNode, `nr_getAssetTransfers` (BSCTrace).

BscScan's API was retired into Etherscan V2, whose free tier excludes BNB ("Free API
access is not supported for this chain", measured 2026-08-27 and 2026-10-03); no
Blockscout instance, Routescan "chain not supported". NodeReal is the successor
BNB Chain itself points to, with a free tier (docs, 2026-10-03).

* JSON-RPC POST, the key is part of the URL — never put the URL into a message.
* One query per direction (`fromAddress`, `toAddress`); a transfer to myself shows
  up in both and is taken once (identity includes `logIndex`: two equal token
  transfers in one transaction stay two).
* **A query may span less than 2,000,000 blocks** ("range must be less than
  2000000"; `toBlock: "latest"` is refused as well). The chain is read in windows
  up to `eth_blockNumber`: about 63 calls, 25 s (measured 2026-10-03).
* An address that never sent (`eth_getTransactionCount` = 0) cannot be the sender
  of anything; the `fromAddress` pass is skipped then, halving the calls.
* Values and block numbers are hex; `blockTimeStamp` is seconds; `gasPrice`/
  `gasUsed`/`receiptsStatus` exist on external transfers only.
* Categories: external (BNB), internal (BNB from contracts), 20 (BEP-20).
* Measured at the user's address: two BNB receipts sum to the known balance
  0.04275846 BNB (2026-10-03).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime

from app.modules.plugins import evm
from app.modules.plugins.contract import Movement

API = "https://bsc-mainnet.nodereal.io/v1"
NATIVE, DECIMALS = "BNB", 18
CATEGORIES = ["external", "internal", "20"]
MAX = "0x3e8"  # 1000, the documented maximum
WINDOW = 2_000_000  # blocks per query, exclusive limit


def _rpc(key: str, method: str, params: list):
    body = evm.http_json(
        f"{API}/{key}", {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    )
    if "error" in body:
        raise evm.ChainUnavailable(str((body["error"] or {}).get("message") or "error")[:120])
    return body.get("result")


def windows(latest: int, size: int = WINDOW) -> list[tuple[int, int]]:
    return [(start, min(start + size - 1, latest)) for start in range(0, latest + 1, size)]


def _transfers(key: str, direction: str, address: str, start: int, end: int) -> list[dict]:
    rows: list[dict] = []
    page_key = None
    while True:
        params = {
            "category": CATEGORIES,
            "fromBlock": hex(start),
            "toBlock": hex(end),
            "order": "asc",
            "excludeZeroValue": False,
            "maxCount": MAX,
            direction: address,
        }
        if page_key:
            params["pageKey"] = page_key
        result = _rpc(key, "nr_getAssetTransfers", [params]) or {}
        rows.extend(result.get("transfers") or [])
        page_key = result.get("pageKey")
        if not page_key:
            return rows


def _int(value) -> int:
    if value in (None, ""):
        return 0
    return int(value, 16) if isinstance(value, str) and value.startswith("0x") else int(value)


def split(transfers: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """NodeReal records → the three Etherscan lists of the shared reader."""
    txlist, tokentx, internal = [], [], []
    seen = set()
    for t in transfers:
        ident = (
            t.get("category"),
            t.get("hash"),
            t.get("from"),
            t.get("to"),
            t.get("value"),
            t.get("contractAddress"),
            t.get("logIndex"),
        )
        if ident in seen:
            continue
        seen.add(ident)
        base = {
            "timeStamp": _int(t.get("blockTimeStamp")),
            "hash": t.get("hash"),
            "from": t.get("from") or "",
            "to": t.get("to") or "",
            "value": _int(t.get("value")),
        }
        category = t.get("category")
        if category == "external":
            status = t.get("receiptsStatus")
            txlist.append(
                {
                    **base,
                    "isError": "1" if status is not None and _int(status) != 1 else "0",
                    "gasUsed": _int(t.get("gasUsed")),
                    "gasPrice": _int(t.get("gasPrice")),
                }
            )
        elif category == "internal":
            internal.append({**base, "isError": "0"})
        elif category == "20":
            tokentx.append(
                {
                    **base,
                    "tokenSymbol": t.get("asset"),
                    "contractAddress": t.get("contractAddress"),
                    "tokenDecimal": t.get("decimal") or 0,
                    "tokenName": t.get("name"),
                }
            )
    return txlist, tokentx, internal


def fetch(
    address: str,
    since: datetime | None,
    progress: Callable[[dict], None] | None = None,
    key: str | None = None,
) -> Iterator[Movement]:
    if not key:
        raise evm.ChainUnavailable("NodeReal key missing")
    latest = int(_rpc(key, "eth_blockNumber", []), 16)
    sent = int(_rpc(key, "eth_getTransactionCount", [address, "latest"]), 16)
    directions = ("fromAddress", "toAddress") if sent else ("toAddress",)
    parts = [(d, w) for d in directions for w in windows(latest)]
    transfers: list[dict] = []
    for i, (direction, (start, end)) in enumerate(parts, 1):
        transfers += _transfers(key, direction, address, start, end)
        if progress:
            progress({"step": direction, "done": i, "total": len(parts), "rows": len(transfers)})
    txlist, tokentx, internal = split(transfers)
    movements = evm.convert(address, txlist, tokentx, internal, native=NATIVE, decimals=DECIMALS)
    yield from evm.since_only(movements, since)


BALANCE_RPC = "https://bsc-dataseed.binance.org"


# Rows read before the reader kept the contract (2026-10-04) cannot say which token they
# moved, and raw rows are never changed (ADR 0001). The two that matter, checked on the
# chain on 2026-10-23 (symbol, name, decimals): without them AXS/SLP stay "not checked".
KNOWN_TOKENS = {
    "AXS": ("0x715D400F88C167884bbCc41C5FeA407ed4D2f8A0", 18),
    "SLP": ("0x070a08BeEF8d36734dD67A491202fF35a6A16d97", 18),
}


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    tokens = tokens or {}
    out = evm.balances(BALANCE_RPC, address, NATIVE, DECIMALS, {**KNOWN_TOKENS, **tokens})
    # a known token this address never had stays out, as before
    return [x for x in out if x[1] in tokens or x[1] not in KNOWN_TOKENS or x[2] != 0]
