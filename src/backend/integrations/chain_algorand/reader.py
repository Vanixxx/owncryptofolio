"""Algorand through the AlgoNode indexer (2026-10-23).

* `/accounts/{a}/transactions` pages with `next` until a page is empty. Amounts in
  microAlgos (10^-6) or in the asset's own decimals (`/assets/{id}`, cached).
* `pay` moves ALGO, `axfer` an asset (ASA). Both can **close** the account: the rest
  (`close-amount`) goes to `close-remainder-to` / `close-to` — a second movement.
* The sender pays `fee`. An opt-in (0 of an asset to oneself) is just that fee.
* App calls carry `inner-txns`: payments made by the app to or from me are read the same
  way, without a fee of their own.
* **Rewards:** `sender-rewards`, `receiver-rewards`, `close-rewards` (the participation
  rewards until 2022) arrive with a transaction: staking income.
* NFTs (0 decimals, total 1) are skipped.
* Checked against a public account (122 transactions, 71 with rewards).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime
from decimal import Decimal

from app.modules.plugins import chain
from app.modules.plugins.contract import IncomeKind, Kind, Movement

API = "https://mainnet-idx.algonode.cloud/v2"
NATIVE, DECIMALS = "ALGO", 6
PAGE = 1000


def transactions(address: str) -> list[dict]:
    rows: list[dict] = []
    token = None
    while True:
        body = chain.http_json(
            f"{API}/accounts/{address}/transactions?limit={PAGE}"
            + (f"&next={token}" if token else "")
        )
        page = (body or {}).get("transactions")
        if not isinstance(page, list):
            raise chain.ChainUnavailable("invalid answer")
        rows += page
        token = body.get("next-token")
        if not page or not token:
            return rows


class Assets:
    """ASA id → (unit name, decimals), None for an NFT."""

    def __init__(self) -> None:
        self.known: dict[int, tuple[str, int] | None] = {}

    def __call__(self, asset_id: int) -> tuple[str, int] | None:
        if asset_id not in self.known:
            params = (chain.http_json(f"{API}/assets/{asset_id}").get("asset") or {}).get(
                "params"
            ) or {}
            decimals = int(params.get("decimals") or 0)
            name = (params.get("unit-name") or params.get("name") or f"ASA{asset_id}").strip()
            nft = decimals == 0 and int(params.get("total") or 0) == 1
            self.known[asset_id] = None if nft else (name, decimals)
        return self.known[asset_id]


def convert(
    address: str, records: list[dict], assets: Callable[[int], tuple[str, int] | None]
) -> list[Movement]:
    out: list[Movement] = []

    def walk(t: dict, ref: str, outer: bool) -> None:
        when = chain.seconds(t.get("round-time") or 0)
        sender = t.get("sender")
        sent = sender == address
        fee = chain.units(t.get("fee") or 0, DECIMALS) if sent and outer else Decimal(0)
        base = {"timestamp": when, "raw": t if outer else {"inner": t}}
        moves: list[tuple[str, Decimal, str | None]] = []  # asset, amount, receiver
        kind = t.get("tx-type")
        if kind == "pay":
            p = t.get("payment-transaction") or {}
            moves.append((NATIVE, chain.units(p.get("amount") or 0, DECIMALS), p.get("receiver")))
            if p.get("close-remainder-to"):
                moves.append(
                    (
                        NATIVE,
                        chain.units(
                            p.get("close-amount") or t.get("closing-amount") or 0, DECIMALS
                        ),
                        p["close-remainder-to"],
                    )
                )
        elif kind == "axfer":
            x = t.get("asset-transfer-transaction") or {}
            info = assets(int(x.get("asset-id") or 0))
            if info:
                sender = x.get("sender") or sender  # a clawback names the account it takes from
                sent = sender == address
                moves.append(
                    (info[0], chain.units(x.get("amount") or 0, info[1]), x.get("receiver"))
                )
                if x.get("close-to"):
                    moves.append(
                        (info[0], chain.units(x.get("close-amount") or 0, info[1]), x["close-to"])
                    )
        n = 0
        paid = False
        for asset, amount, receiver in moves:
            n += 1
            if not amount or not (sent or receiver == address):
                continue
            out.append(
                chain.transfer(
                    sent=sent,
                    received=receiver == address,
                    asset=asset,
                    amount=amount,
                    sender=sender,
                    receiver=receiver,
                    fee=None if paid else (fee or None),
                    fee_asset=NATIVE,
                    external_id=f"{ref}:{n}",
                    **base,
                )
            )
            paid = paid or (sent and bool(fee))
        if fee and not paid:
            out.append(
                Movement(
                    kind=Kind.FEE,
                    fee_asset=NATIVE,
                    fee_amount=fee,
                    comment=kind,
                    external_id=f"{ref}:fee",
                    **base,
                )
            )
        for field, who in (
            ("sender-rewards", t.get("sender")),
            ("receiver-rewards", (t.get("payment-transaction") or {}).get("receiver")),
            ("close-rewards", (t.get("payment-transaction") or {}).get("close-remainder-to")),
        ):
            reward = int(t.get(field) or 0)
            if reward and who == address and outer:
                out.append(
                    Movement(
                        kind=Kind.INCOME,
                        income_kind=IncomeKind.STAKING,
                        incoming_asset=NATIVE,
                        incoming_amount=chain.units(reward, DECIMALS),
                        external_id=f"{ref}:{field}",
                        comment="participation rewards",
                        **base,
                    )
                )
        for i, inner in enumerate(t.get("inner-txns") or []):
            walk(inner, f"{ref}:i{i}", False)

    for t in records:
        walk(t, t.get("id") or "", True)
    out.sort(key=lambda m: m.timestamp)
    return out


def fetch(
    address: str,
    since: datetime | None,
    progress: Callable[[dict], None] | None = None,
    key: str | None = None,
) -> Iterator[Movement]:
    records = transactions(address)
    if progress:
        progress({"step": "transactions", "done": 1, "total": 1, "rows": len(records)})
    yield from chain.since_only(convert(address, records, Assets()), since)


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    try:
        account = chain.http_json(f"{API}/accounts/{address}").get("account") or {}
    except chain.ChainUnavailable as exc:
        if str(exc) == "HTTP 404":
            return [("spot", NATIVE, Decimal(0))]
        raise
    out = [("spot", NATIVE, chain.units(account.get("amount") or 0, DECIMALS))]
    assets = Assets()
    for a in account.get("assets") or []:
        info = assets(int(a.get("asset-id") or 0))
        if info and int(a.get("amount") or 0):
            out.append(("spot", info[0], chain.units(a["amount"], info[1])))
    return out
