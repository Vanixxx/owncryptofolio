"""Stellar through Horizon (research 2026-08-27).

* **An account exists only after its minimum deposit.** Before that Horizon answers
  HTTP 404 for an address that is fine: read as "no history yet", not as an error.
* `/payments` covers create_account, payment and path payments; `join=transactions`
  adds `fee_charged` (stroops) and `fee_account` — the fee is the payer's.
* **Amounts come as decimals** ("1.5000000"), the one exception among all networks:
  no `units()` here, applying seven decimals again would be off by 10^7.
* Paging: `order=asc` with `cursor` = the last `paging_token`.
* Written from the docs and a public account: the user's account is still empty.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime
from decimal import Decimal

from app.modules.plugins import chain
from app.modules.plugins.contract import Kind, Movement

API = "https://horizon.stellar.org"
NATIVE, DECIMALS = "XLM", 7
PAGE = 200


def payments(account: str) -> list[dict]:
    rows: list[dict] = []
    cursor = ""
    while True:
        try:
            body = chain.http_json(
                f"{API}/accounts/{account}/payments?limit={PAGE}&order=asc&join=transactions"
                + (f"&cursor={cursor}" if cursor else "")
            )
        except chain.ChainUnavailable as exc:
            if str(exc) == "HTTP 404" and not rows:
                return []  # account not created yet: it appears with the first deposit
            raise
        records = (body.get("_embedded") or {}).get("records")
        if not isinstance(records, list):
            raise chain.ChainUnavailable("invalid answer")
        rows += records
        if len(records) < PAGE:
            return rows
        cursor = records[-1]["paging_token"]


def _asset(code: str | None, kind: str | None) -> str:
    return NATIVE if kind == "native" or not code else code


def convert(account: str, records: list[dict]) -> list[Movement]:
    out: list[Movement] = []
    charged: set[str] = set()
    for r in records:
        tx = r.get("transaction") or {}
        timestamp = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
        tx_hash = r.get("transaction_hash")
        fee = None
        if tx.get("fee_account") == account and tx_hash not in charged:
            charged.add(tx_hash)
            fee = Decimal(int(tx.get("fee_charged") or 0)).scaleb(-DECIMALS) or None
        if r.get("transaction_successful") is False:
            if fee:
                out.append(
                    Movement(
                        kind=Kind.FEE,
                        fee_asset=NATIVE,
                        fee_amount=fee,
                        timestamp=timestamp,
                        external_id=f"{tx_hash}:{r.get('id')}",
                        raw=r,
                    )
                )
            continue
        kind = r.get("type")
        if kind == "create_account":
            sender, receiver = r.get("funder"), r.get("account")
            asset, amount = NATIVE, Decimal(r.get("starting_balance") or "0")
        elif kind in ("payment", "path_payment_strict_send", "path_payment_strict_receive"):
            sender, receiver = r.get("from"), r.get("to")
            asset, amount = (
                _asset(r.get("asset_code"), r.get("asset_type")),
                Decimal(r.get("amount") or "0"),
            )
            if kind != "payment" and sender == account and receiver != account:
                asset = _asset(r.get("source_asset_code"), r.get("source_asset_type"))
                amount = Decimal(r.get("source_amount") or "0")
        else:
            out.append(
                Movement(
                    kind=Kind.OTHER,
                    comment=kind,
                    timestamp=timestamp,
                    external_id=f"{tx_hash}:{r.get('id')}",
                    raw=r,
                )
            )
            continue
        out.append(
            chain.transfer(
                sent=sender == account,
                received=receiver == account,
                asset=asset,
                amount=amount,
                timestamp=timestamp,
                external_id=f"{tx_hash}:{r.get('id')}",
                sender=sender,
                receiver=receiver,
                fee=fee,
                fee_asset=NATIVE,
                raw=r,
            )
        )
    return out


def fetch(
    address: str,
    since: datetime | None,
    progress: Callable[[dict], None] | None = None,
    key: str | None = None,
) -> Iterator[Movement]:
    records = payments(address)
    if progress:
        progress({"step": "payments", "done": 1, "total": 1, "rows": len(records)})
    yield from chain.since_only(convert(address, records), since)


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    try:
        body = chain.http_json(f"{API}/accounts/{address}")
    except chain.ChainUnavailable as exc:
        if str(exc) == "HTTP 404":
            return [("spot", NATIVE, Decimal(0))]  # no account before the first deposit
        raise
    out = []
    for b in body.get("balances") or []:
        asset = NATIVE if b.get("asset_type") == "native" else b.get("asset_code")
        if asset:
            out.append(("spot", asset, Decimal(str(b.get("balance") or "0"))))
    return out
