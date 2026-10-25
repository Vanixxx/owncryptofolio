"""Tezos through TzKT (2026-10-23).

* `/accounts/{a}/operations` lists every operation the account sends, receives or starts;
  paged with `lastId`. Amounts and fees in mutez (10^-6).
* **What the sender pays:** `bakerFee` always, `storageFee` and `allocationFee` only when
  the operation was applied; a failed or backtracked one still costs the baker fee.
* A contract call (amount 0, e.g. a token transfer) is its fee; the tokens themselves come
  from `/tokens/transfers` (FA1.2 and FA2, symbol and decimals from the metadata). Tokens
  with an `artifactUri` are NFTs and skipped.
* **Baker payouts** are ordinary transactions: from the account's delegate, or from a
  sender TzKT names "…Payout…", they are staking income (Vanixxx, 2026-10-23).
* Reveal, delegation, origination, staking: their fee, the rest is not read.
* Checked against a public account (7 operations, 10 token transfers): the sum of the
  movements equals the balance TzKT reports.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime
from decimal import Decimal

from app.modules.plugins import chain
from app.modules.plugins.contract import IncomeKind, Kind, Movement

API = "https://api.tzkt.io/v1"
NATIVE, DECIMALS = "XTZ", 6
PAGE = 1000


def _get(path: str):
    return chain.http_json(f"{API}/{path}")


def operations(address: str) -> list[dict]:
    rows: list[dict] = []
    last = None
    while True:
        page = _get(
            f"accounts/{address}/operations?limit={PAGE}&sort=0"
            + (f"&lastId={last}" if last else "")
        )
        if not isinstance(page, list):
            raise chain.ChainUnavailable("invalid answer")
        rows += page
        if len(page) < PAGE:
            return rows
        last = page[-1]["id"]


def token_transfers(address: str) -> list[dict]:
    rows: list[dict] = []
    last = 0
    while True:
        page = _get(
            f"tokens/transfers?anyof.from.to={address}&sort.asc=id&id.gt={last}&limit={PAGE}"
        )
        if not isinstance(page, list):
            raise chain.ChainUnavailable("invalid answer")
        rows += page
        if len(page) < PAGE:
            return rows
        last = page[-1]["id"]


def _when(o: dict) -> datetime:
    return datetime.fromisoformat(o["timestamp"].replace("Z", "+00:00"))


def _who(x) -> str | None:
    return (x or {}).get("address")


def _fee(o: dict) -> Decimal:
    mutez = int(o.get("bakerFee") or 0)
    if o.get("status") == "applied":
        mutez += int(o.get("storageFee") or 0) + int(o.get("allocationFee") or 0)
    return chain.units(mutez, DECIMALS)


def token(t: dict) -> tuple[str, int] | None:
    meta = (t.get("token") or {}).get("metadata") or {}
    if "artifactUri" in meta or not meta.get("symbol") or meta.get("decimals") in (None, ""):
        return None  # an NFT, or a token without a name to price it by
    return str(meta["symbol"]).strip(), int(meta["decimals"])


def convert(
    address: str, ops: list[dict], tokens: list[dict], delegate: str | None
) -> list[Movement]:
    out: list[Movement] = []
    for o in ops:
        sent, received = _who(o.get("sender")) == address, _who(o.get("target")) == address
        fee = _fee(o) if sent else Decimal(0)
        base = {"timestamp": _when(o), "external_id": f"{o.get('hash')}:{o.get('id')}", "raw": o}
        amount = chain.units(o.get("amount") or 0, DECIMALS)
        if o.get("type") == "transaction" and o.get("status") == "applied" and amount:
            sender = o.get("sender") or {}
            payout = (
                received
                and not sent
                and (_who(sender) == delegate or "payout" in (sender.get("alias") or "").lower())
            )
            if payout:
                out.append(
                    Movement(
                        kind=Kind.INCOME,
                        income_kind=IncomeKind.STAKING,
                        incoming_asset=NATIVE,
                        incoming_amount=amount,
                        counterparty=_who(sender),
                        comment=sender.get("alias"),
                        **base,
                    )
                )
                continue
            out.append(
                chain.transfer(
                    sent=sent,
                    received=received,
                    asset=NATIVE,
                    amount=amount,
                    sender=_who(o.get("sender")),
                    receiver=_who(o.get("target")),
                    fee=fee or None,
                    fee_asset=NATIVE,
                    **base,
                )
            )
        elif sent and fee:
            what = (o.get("parameter") or {}).get("entrypoint") or o.get("type")
            out.append(
                Movement(kind=Kind.FEE, fee_asset=NATIVE, fee_amount=fee, comment=what, **base)
            )
    for t in tokens:
        info = token(t)
        if not info:
            continue
        asset, decimals = info
        ref = t.get("transactionId") or t.get("originationId") or t.get("migrationId")
        out.append(
            chain.transfer(
                sent=_who(t.get("from")) == address,
                received=_who(t.get("to")) == address,
                asset=asset,
                amount=chain.units(t.get("amount") or 0, decimals),
                sender=_who(t.get("from")),
                receiver=_who(t.get("to")),
                timestamp=_when(t),
                external_id=f"op{ref}:tok{t.get('id')}",
                raw=t,
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
    account = _get(f"accounts/{address}")
    ops = operations(address)
    if progress:
        progress({"step": "operations", "done": 1, "total": 2, "rows": len(ops)})
    tokens = token_transfers(address)
    if progress:
        progress({"step": "tokens", "done": 2, "total": 2, "rows": len(ops) + len(tokens)})
    delegate = _who((account or {}).get("delegate"))
    yield from chain.since_only(convert(address, ops, tokens, delegate), since)


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    account = _get(f"accounts/{address}")
    out = [("spot", NATIVE, chain.units(account.get("balance") or 0, DECIMALS))]
    for b in _get(f"tokens/balances?account={address}&balance.gt=0&limit={PAGE}") or []:
        info = token(b)
        if info:
            out.append(("spot", info[0], chain.units(b.get("balance") or 0, info[1])))
    return out
