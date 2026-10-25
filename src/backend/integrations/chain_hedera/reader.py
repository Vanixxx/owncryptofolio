"""Hedera through the public mirror node (research 2026-08-27/28, measured 2026-10-03).

* **The mirror node searches a window of about 60 days per call.** An empty page is
  not the end: `links.next` points to the next window. Reading starts at the
  account's `created_timestamp` (ascending) and follows `links.next` until it is
  null — 11 calls for the user's account, instead of stepping back from today.
* One transaction lists **all** accounts with signed amounts (receiver +, payer −,
  fee accounts +). Only my own entries matter; the sign says debit or credit.
* The payer is in `transaction_id` before the first dash; `charged_tx_fee` is his
  and is already inside his negative amount: sent = −amount − fee.
* **Staking rewards are paid along with any transfer** and listed separately in
  `staking_reward_transfers`, but also summed into my entry. They are split out as
  income (staking); the rest is the transfer.
* Dusting: 117 of 122 receipts are 1 tinybar or 0.0001 HBAR from strangers. Kept in
  the raw layer like everything else; hiding is the merged layer's job.
"""

from __future__ import annotations

import base64
from collections.abc import Callable, Iterator
from datetime import UTC, datetime

from app.modules.plugins import chain
from app.modules.plugins.contract import IncomeKind, Kind, Movement

API = "https://mainnet-public.mirrornode.hedera.com"
NATIVE, DECIMALS = "HBAR", 8
MAX_CALLS = 2000  # ~330 years of 60-day windows: a guard, never reached


def transactions(account: str) -> list[dict]:
    created = chain.http_json(f"{API}/api/v1/accounts/{account}?transactions=false").get(
        "created_timestamp"
    )
    if not created:
        raise chain.ChainUnavailable("account unknown")
    url = f"/api/v1/transactions?account.id={account}&limit=100&order=asc&timestamp=gte:{created}"
    rows: list[dict] = []
    seen: set[tuple] = set()
    for _ in range(MAX_CALLS):
        body = chain.http_json(API + url)
        for t in body.get("transactions") or []:
            ident = (t.get("consensus_timestamp"), t.get("transaction_id"))
            if ident not in seen:
                seen.add(ident)
                rows.append(t)
        url = (body.get("links") or {}).get("next")
        if not url:
            return rows
    raise chain.ChainUnavailable("too many pages")


def _time(t: dict) -> datetime:
    # nanoseconds after the dot: seconds are enough here
    return datetime.fromtimestamp(float(t["consensus_timestamp"]), tz=UTC)


def convert(account: str, txs: list[dict]) -> list[Movement]:
    out: list[Movement] = []
    for t in txs:
        mine = sum(
            int(x["amount"]) for x in t.get("transfers") or [] if x.get("account") == account
        )
        reward = sum(
            int(x["amount"])
            for x in t.get("staking_reward_transfers") or []
            if x.get("account") == account
        )
        payer = str(t.get("transaction_id") or "").split("-")[0] == account
        fee = int(t.get("charged_tx_fee") or 0) if payer else 0
        ok = t.get("result") in (None, "SUCCESS")
        base = {"timestamp": _time(t), "raw": t}
        tx_id = t.get("transaction_id")
        if reward and ok:
            out.append(
                Movement(
                    kind=Kind.INCOME,
                    income_kind=IncomeKind.STAKING,
                    incoming_asset=NATIVE,
                    incoming_amount=chain.units(reward, DECIMALS),
                    external_id=f"{tx_id}:reward",
                    comment="staking reward",
                    **base,
                )
            )
        rest = mine - reward + fee  # what moved besides reward and fee
        if not ok or (rest == 0 and fee):
            if fee:
                out.append(
                    Movement(
                        kind=Kind.FEE,
                        fee_asset=NATIVE,
                        fee_amount=chain.units(fee, DECIMALS),
                        external_id=tx_id,
                        comment=t.get("name"),
                        **base,
                    )
                )
            continue
        if rest == 0:
            continue
        # system accounts (fees, node, staking 0.0.800) are no counterparty: a spammer's
        # send in a transaction that also paid someone's reward named 0.0.800 (2026-10-09)
        others = [
            x
            for x in t.get("transfers") or []
            if x.get("account") != account
            and not _system(x.get("account"))
            and (int(x["amount"]) < 0) == (rest > 0)
        ]
        counterparty = (
            max(others, key=lambda x: abs(int(x["amount"])))["account"] if others else None
        )
        out.append(
            chain.transfer(
                sent=rest < 0,
                received=rest > 0,
                asset=NATIVE,
                amount=chain.units(abs(rest), DECIMALS),
                timestamp=base["timestamp"],
                external_id=tx_id,
                sender=counterparty,
                receiver=counterparty,
                fee=chain.units(fee, DECIMALS) if fee else None,
                comment=_memo(t) or t.get("name"),
                raw=t,
            )
        )
    return out


def _system(account: str | None) -> bool:
    """0.0.1 – 0.0.999: nodes, fee and staking accounts of the network itself."""
    try:
        return int(str(account).rsplit(".", 1)[-1]) < 1000
    except ValueError:
        return False


def _memo(t: dict) -> str | None:
    """The transfer's note: on tiny incoming amounts mostly phishing ("Claim HBAR prize at
    …"), worth showing so it can be recognised and found."""
    try:
        text = base64.b64decode(t.get("memo_base64") or "").decode("utf-8", "replace").strip()
    except (ValueError, TypeError):
        return None
    return text[:300] or None


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
    body = chain.http_json(f"{API}/api/v1/balances?account.id={address}")
    rows = body.get("balances") or []
    tinybar = int(rows[0].get("balance") or 0) if rows else 0
    return [("spot", NATIVE, chain.units(tinybar, DECIMALS))]
