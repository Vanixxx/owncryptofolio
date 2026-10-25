"""Solana through the public RPC (research 2026-08-27/28).

* JSON-RPC over **POST**; a GET returns a web page.
* `getSignaturesForAddress` gives ids only (paged with `before`); every transaction
  is one more `getTransaction` call. The public RPC is rate limited: calls are paced.
* **SPL tokens live on their own token accounts.** A transfer to the token account
  does not list the wallet; asking only the wallet missed 214.04 RENDER in 2026-08.
  The token accounts (`getTokenAccountsByOwner`) are asked as well, signatures
  taken once.
* SOL: `pre`/`postBalances` at my index in `accountKeys` (linked by **index**). The
  fee is paid by `accountKeys[0]` and is inside its change: sent = −change − fee.
* Tokens: `pre`/`postTokenBalances` linked by `accountIndex` (lists may differ in
  length and order), filtered by `owner`. Symbol from a short verified mint list;
  an unknown mint stays under its address, so it shows instead of being guessed.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from datetime import datetime

from app.modules.plugins import chain
from app.modules.plugins.contract import Kind, Movement

API = "https://api.mainnet-beta.solana.com"
NATIVE, DECIMALS = "SOL", 9
TOKEN_PROGRAMS = (
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",  # Token-2022
)
MINTS = {"rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof": "RENDER"}
PAGE = 1000
PAUSE = 0.25


def _rpc(method: str, params: list):
    time.sleep(PAUSE)
    for attempt in range(4):
        try:
            body = chain.http_json(
                API, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
            )
        except chain.ChainUnavailable as exc:
            if str(exc) == "HTTP 429" and attempt < 3:
                time.sleep(2 * (attempt + 1))
                continue
            raise
        if "error" in body:
            raise chain.ChainUnavailable(str((body["error"] or {}).get("message"))[:120])
        return body.get("result")
    raise chain.ChainUnavailable("rate limited")


def _signatures(account: str) -> list[dict]:
    rows: list[dict] = []
    before = None
    while True:
        opts = {"limit": PAGE, **({"before": before} if before else {})}
        batch = _rpc("getSignaturesForAddress", [account, opts]) or []
        rows += batch
        if len(batch) < PAGE:
            return rows
        before = batch[-1]["signature"]


def transactions(address: str, progress: Callable[[dict], None] | None = None) -> list[dict]:
    accounts = [address]
    for program in TOKEN_PROGRAMS:
        found = _rpc(
            "getTokenAccountsByOwner", [address, {"programId": program}, {"encoding": "jsonParsed"}]
        )
        accounts += [a["pubkey"] for a in (found or {}).get("value") or [] if a.get("pubkey")]
    signatures: dict[str, dict] = {}
    for account in accounts:
        for s in _signatures(account):
            signatures.setdefault(s["signature"], s)
    rows = []
    missing = 0
    for i, sig in enumerate(signatures, 1):
        tx = _rpc(
            "getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]
        )
        if tx:
            rows.append({**tx, "signature": sig})
        else:
            missing += 1
        if progress and i % 10 == 0:
            progress(
                {"step": "transactions", "done": i, "total": len(signatures), "rows": len(rows)}
            )
    if missing:
        # the node did not hand them over (lag, pruned): an error, not a gap (review 2026-10-24)
        raise chain.ChainUnavailable(f"{missing} transactions not delivered by the node")
    return rows


def _key(k) -> str:
    return k.get("pubkey") if isinstance(k, dict) else k


def convert(address: str, txs: list[dict]) -> list[Movement]:
    out: list[Movement] = []
    for t in txs:
        meta = t.get("meta") or {}
        timestamp = chain.seconds(t["blockTime"])
        sig = t.get("signature")
        keys = [
            _key(k)
            for k in ((t.get("transaction") or {}).get("message") or {}).get("accountKeys") or []
        ]
        signer = bool(keys) and keys[0] == address
        fee = (
            chain.units(int(meta.get("fee") or 0), DECIMALS) if signer and meta.get("fee") else None
        )
        if meta.get("err") is not None:
            if fee:
                out.append(
                    Movement(
                        kind=Kind.FEE,
                        fee_asset=NATIVE,
                        fee_amount=fee,
                        timestamp=timestamp,
                        external_id=sig,
                        comment="failed transaction",
                        raw=t,
                    )
                )
            continue
        moved = _tokens(address, t, meta, timestamp, sig)
        pre, post = meta.get("preBalances") or [], meta.get("postBalances") or []
        sol = None
        if address in keys and len(pre) == len(keys) == len(post):
            i = keys.index(address)
            change = int(post[i]) - int(pre[i]) + (int(meta.get("fee") or 0) if signer else 0)
            if change:
                other = next((k for j, k in enumerate(keys) if j != i), None)
                sol = chain.transfer(
                    sent=change < 0,
                    received=change > 0,
                    asset=NATIVE,
                    amount=chain.units(abs(change), DECIMALS),
                    timestamp=timestamp,
                    external_id=f"{sig}:SOL",
                    sender=other,
                    receiver=other,
                    fee=fee,
                    raw=t,
                )
        if sol:
            out.append(sol)
        elif fee:  # a token transfer I signed: the SOL fee is the only SOL movement
            out.append(
                Movement(
                    kind=Kind.FEE,
                    fee_asset=NATIVE,
                    fee_amount=fee,
                    timestamp=timestamp,
                    external_id=f"{sig}:fee",
                    raw=t,
                )
            )
        out += moved
    return out


def _tokens(
    address: str, t: dict, meta: dict, timestamp: datetime, sig: str | None
) -> list[Movement]:
    def by_index(entries):
        return {e["accountIndex"]: e for e in entries or [] if "accountIndex" in e}

    def raw(entry):
        return int(((entry or {}).get("uiTokenAmount") or {}).get("amount") or 0)

    pre, post = by_index(meta.get("preTokenBalances")), by_index(meta.get("postTokenBalances"))
    out = []
    for index in sorted(set(pre) | set(post)):
        entry = post.get(index) or pre[index]
        if entry.get("owner") != address:
            continue
        change = raw(post.get(index)) - raw(pre.get(index))
        if not change:
            continue
        mint = entry.get("mint") or ""
        decimals = int((entry.get("uiTokenAmount") or {}).get("decimals") or 0)
        out.append(
            chain.transfer(
                sent=change < 0,
                received=change > 0,
                asset=MINTS.get(mint, mint),
                amount=chain.units(abs(change), decimals),
                timestamp=timestamp,
                external_id=f"{sig}:{mint}",
                raw=t,
                comment=None if mint in MINTS else f"unknown SPL mint {mint}",
            )
        )
    return out


def fetch(
    address: str,
    since: datetime | None,
    progress: Callable[[dict], None] | None = None,
    key: str | None = None,
) -> Iterator[Movement]:
    yield from chain.since_only(convert(address, transactions(address, progress)), since)


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    lamports = int((_rpc("getBalance", [address]) or {}).get("value") or 0)
    out = [("spot", NATIVE, chain.units(lamports, DECIMALS))]
    for program in TOKEN_PROGRAMS:
        found = _rpc(
            "getTokenAccountsByOwner", [address, {"programId": program}, {"encoding": "jsonParsed"}]
        )
        for acc in (found or {}).get("value") or []:
            info = (((acc.get("account") or {}).get("data") or {}).get("parsed") or {}).get(
                "info"
            ) or {}
            amount = info.get("tokenAmount") or {}
            mint = info.get("mint") or ""
            if amount.get("amount") is not None:
                out.append(
                    (
                        "spot",
                        MINTS.get(mint, mint),
                        chain.units(int(amount["amount"]), int(amount.get("decimals") or 0)),
                    )
                )
    return out
