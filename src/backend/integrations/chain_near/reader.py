"""NEAR through FastNEAR (2026-10-23).

NearBlocks without a key answered 429/525 and lists amounts as floats; FastNEAR's transaction
API gives the account's transactions with every receipt and outcome, free, exact.

* `POST tx.main.fastnear.com/v0/account` lists the account's transactions (pages by
  `resume_token`), `POST /v0/transactions` returns up to **20** of them in full.
* **Native balance, exact to the yoctoNEAR** (checked on a public account with 392
  transactions): + deposits that reach the account in a successful receipt from anyone but
  `system`; − deposits attached to the account's own transactions; − `tokens_burnt` of the
  whole transaction (its outcome and every receipt) — the signer pays the gas. **Receipts from
  `system` are refunds** of unused gas and are left out: counting them would count prepaid gas
  twice. A failed call gets its attached deposit back: then it is not an outflow.
* 1 yoctoNEAR deposits (every `ft_transfer`) are folded into the fee, not shown as sends.
* **Tokens (NEP-141)** from `EVENT_JSON` logs (`ft_transfer`, `ft_mint`, `ft_burn`), the token is
  the log's executor; symbol and decimals from `ft_metadata` over the public RPC. A token that
  logs nothing cannot be read: the balance check shows the gap.
* **Staking:** a deposit to a pool is an ordinary outflow, a withdrawal an inflow: staked NEAR
  leaves the balance (and the rewards come back with the withdrawal, not shown separately).
* Checked against a public account (392 transactions, 3 tokens).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import datetime
from decimal import Decimal

from app.modules.plugins import chain
from app.modules.plugins.contract import Kind, Movement

TX = "https://tx.main.fastnear.com"
ACCOUNT_API = "https://api.fastnear.com/v1/account"
TRANSIENT = {
    "TOO_MANY_REQUESTS",
    "TIMEOUT_ERROR",
    "INTERNAL_ERROR",
    "UNAVAILABLE_SHARD",
    "NOT_SYNCED_YET",
    "UNKNOWN_BLOCK",
    "GARBAGE_COLLECTED_BLOCK",
}
RPCS = ("https://rpc.mainnet.near.org", "https://free.rpc.fastnear.com")
NATIVE, DECIMALS = "NEAR", 24
PAGE = 500
BATCH = 20  # FastNEAR's limit per call
DUST = 10**12  # below this a deposit is a ticket (1 yocto), part of the fee
STAKING = (
    "deposit_and_stake",
    "stake",
    "stake_all",
    "unstake",
    "unstake_all",
    "withdraw",
    "withdraw_all",
)


def listing(address: str, since_ms: int | None) -> list[str]:
    """Hashes of the account's transactions, newest first; stops at a page older than `since`."""
    hashes: dict[str, None] = {}
    token = None
    while True:
        body: dict = {"account_id": address, "limit": PAGE}
        if token:
            body["resume_token"] = token
        page = chain.http_json(f"{TX}/v0/account", body)
        rows = (page or {}).get("account_txs")
        if not isinstance(rows, list):
            raise chain.ChainUnavailable("invalid answer")
        for r in rows:
            if since_ms is None or int(r.get("tx_block_timestamp") or 0) // 10**6 >= since_ms:
                hashes[r["transaction_hash"]] = None
        token = page.get("resume_token")
        if not token or not rows:
            return list(hashes)
        if since_ms is not None and all(
            int(r.get("tx_block_timestamp") or 0) // 10**6 < since_ms for r in rows
        ):
            return list(hashes)


def transactions(hashes: list[str], progress: Callable[[dict], None] | None = None) -> list[dict]:
    out: list[dict] = []
    for i in range(0, len(hashes), BATCH):
        out += (
            chain.http_json(f"{TX}/v0/transactions", {"tx_hashes": hashes[i : i + BATCH]}) or {}
        ).get("transactions") or []
        if progress:
            progress(
                {
                    "step": "transactions",
                    "done": min(i + BATCH, len(hashes)),
                    "total": len(hashes),
                    "rows": len(out),
                }
            )
    return out


class Tokens:
    """Contract → (symbol, decimals) by `ft_metadata`, asked once.

    A contract that answers "no such method" is no token and is skipped. A node that does not
    answer is **not** a reason to skip: a token silently left out would be missing for good, so
    the next server is tried and, when none answers, the fetch fails and is repeated later."""

    def __init__(self) -> None:
        self.known: dict[str, tuple[str, int] | None] = {}

    def __call__(self, contract: str) -> tuple[str, int] | None:
        if contract not in self.known:
            self.known[contract] = self._ask(contract)
        return self.known[contract]

    def _ask(self, contract: str) -> tuple[str, int] | None:
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "query",
            "params": {
                "request_type": "call_function",
                "finality": "final",
                "account_id": contract,
                "method_name": "ft_metadata",
                "args_base64": "",
            },
        }
        last: Exception | None = None
        for server in RPCS:
            try:
                answer = chain.http_json(server, body)
            except chain.ChainUnavailable as exc:
                last = exc
                continue
            error = answer.get("error")
            if error:
                cause = (
                    (error.get("cause") or {}).get("name") if isinstance(error, dict) else None
                ) or ""
                if cause in TRANSIENT or (
                    isinstance(error, dict) and error.get("name") in TRANSIENT
                ):
                    last = chain.ChainUnavailable(cause or "node error")  # the node's own trouble
                    continue
                return None  # no such account, no contract code, no method: not a token
            try:
                meta = json.loads(bytes(answer["result"]["result"]).decode())
                return str(meta["symbol"]).strip(), int(meta["decimals"])
            except (KeyError, TypeError, ValueError):
                return None  # answered, but not a fungible token
        raise last or chain.ChainUnavailable("no answer")


def _deposit(action) -> int:
    if not isinstance(action, dict):
        return 0
    for k in ("Transfer", "FunctionCall"):
        if k in action:
            return int(action[k].get("deposit") or 0)
    return 0


def _failed(outcome: dict) -> bool:
    return "Failure" in (outcome.get("status") or {})


def _when(ns) -> datetime:
    return chain.seconds(int(ns) // 10**9)


def convert(
    me: str, txs: list[dict], tokens: Callable[[str], tuple[str, int] | None]
) -> list[Movement]:
    out: list[Movement] = []
    seen: set[str] = set()
    for t in sorted(txs, key=lambda x: x["execution_outcome"]["block_timestamp"]):
        tx = t["transaction"]
        first = t["execution_outcome"]
        when = _when(first["block_timestamp"])
        hash_ = tx.get("hash") or first["id"]
        receipts = t.get("receipts") or []
        signed = tx["signer_id"] == me
        fee = Decimal(0)
        extras: list[Movement] = []
        if signed:
            burnt = int(first["outcome"]["tokens_burnt"]) + sum(
                int(r["execution_outcome"]["outcome"]["tokens_burnt"]) for r in receipts
            )
            # the first receipt of the call: if it failed, the deposits come back
            head = next(
                (
                    r
                    for r in receipts
                    if r["receipt"]["receipt_id"] in first["outcome"]["receipt_ids"]
                ),
                None,
            )
            refunded = head is not None and _failed(head["execution_outcome"]["outcome"])
            dust = 0
            methods = [
                (
                    a["FunctionCall"]["method_name"]
                    if isinstance(a, dict) and "FunctionCall" in a
                    else None,
                    _deposit(a),
                )
                for a in tx["actions"]
            ]
            for n, (method, dep) in enumerate(methods):
                if not dep or refunded or tx["receiver_id"] == me:
                    continue
                if dep < DUST:
                    dust += dep
                    continue
                extras.append(
                    Movement(
                        kind=Kind.SEND,
                        outgoing_asset=NATIVE,
                        outgoing_amount=chain.units(dep, DECIMALS),
                        counterparty=tx["receiver_id"],
                        comment=method if method in STAKING else None,
                        timestamp=when,
                        external_id=f"{hash_}:out{n}",
                        raw=t,
                    )
                )
            fee = chain.units(burnt + dust, DECIMALS)
        paid = False
        for m in extras:
            if not paid and fee:
                m = m.model_copy(update={"fee_asset": NATIVE, "fee_amount": fee})
                paid = True
            out.append(m)
        if fee and not paid:
            method = next(
                (
                    a["FunctionCall"]["method_name"]
                    for a in tx["actions"]
                    if isinstance(a, dict) and "FunctionCall" in a
                ),
                None,
            )
            out.append(
                Movement(
                    kind=Kind.FEE,
                    fee_asset=NATIVE,
                    fee_amount=fee,
                    comment=method,
                    timestamp=when,
                    external_id=f"{hash_}:fee",
                    raw=t,
                )
            )
        for r in receipts:
            meta, outcome = r["receipt"], r["execution_outcome"]["outcome"]
            rid = meta["receipt_id"]
            when_r = _when(r["execution_outcome"]["block_timestamp"])
            action = (meta.get("receipt") or {}).get("Action")
            if (
                action
                and rid not in seen
                and meta["receiver_id"] == me
                and meta["predecessor_id"] not in (me, "system")
            ):
                seen.add(rid)
                dep = sum(_deposit(a) for a in action["actions"])
                if dep >= DUST and not _failed(outcome):
                    out.append(
                        Movement(
                            kind=Kind.RECEIVE,
                            incoming_asset=NATIVE,
                            incoming_amount=chain.units(dep, DECIMALS),
                            counterparty=meta["predecessor_id"],
                            timestamp=when_r,
                            external_id=f"{hash_}:in:{rid}",
                            raw=t,
                        )
                    )
            for i, log in enumerate(outcome.get("logs") or []):
                if not log.startswith("EVENT_JSON:") or f"{rid}:{i}" in seen:
                    continue
                try:
                    event = json.loads(log[len("EVENT_JSON:") :])
                except ValueError:
                    continue
                if event.get("standard") != "nep141" or me not in json.dumps(event):
                    continue
                seen.add(f"{rid}:{i}")
                info = tokens(outcome["executor_id"])
                if not info:
                    continue
                for n, d in enumerate(event.get("data") or []):
                    sender = (
                        d.get("old_owner_id")
                        if event["event"] == "ft_transfer"
                        else d.get("owner_id")
                        if event["event"] == "ft_burn"
                        else None
                    )
                    receiver = (
                        d.get("new_owner_id")
                        if event["event"] == "ft_transfer"
                        else d.get("owner_id")
                        if event["event"] == "ft_mint"
                        else None
                    )
                    if event["event"] not in ("ft_transfer", "ft_mint", "ft_burn"):
                        continue
                    out.append(
                        chain.transfer(
                            sent=sender == me,
                            received=receiver == me,
                            asset=info[0],
                            amount=chain.units(d.get("amount") or 0, info[1]),
                            sender=sender,
                            receiver=receiver,
                            timestamp=when_r,
                            external_id=f"{hash_}:{rid}:{i}.{n}",
                            raw=d,
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
    # a day of margin: a transaction's receipts arrive over a few blocks
    since_ms = int(since.timestamp() * 1000) - 86_400_000 if since else None
    hashes = listing(address, since_ms)
    txs = transactions(hashes, progress)
    yield from chain.since_only(convert(address, txs, Tokens()), since)


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    meta = Tokens()
    state = (chain.http_json(f"{ACCOUNT_API}/{address}/full") or {}).get("state") or {}
    out = [
        (
            "spot",
            NATIVE,
            chain.units(int(state.get("balance") or 0) + int(state.get("locked") or 0), DECIMALS),
        )
    ]
    for t in (chain.http_json(f"{ACCOUNT_API}/{address}/ft") or {}).get("tokens") or []:
        if int(t.get("balance") or 0):
            info = meta(t["contract_id"])
            if info:
                out.append(("spot", info[0], chain.units(t["balance"], info[1])))
    return out
