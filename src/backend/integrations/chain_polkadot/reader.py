"""Polkadot through Statescan, on two chains (research 2026-08-27).

**The DOT history lies on two chains.** On 2025-11-04 balances moved from the Relay
Chain to the Asset Hub (block #28492512); everything before is only on the Relay
Chain. Both are read with the same address, as one network for the user.

* `indexer.blockTime` is in **milliseconds**.
* `isNativeAsset` is checked: the Asset Hub also carries USDT/USDC with other
  decimals; reading them with DOT's ten would give plausible wrong amounts.
* The transfer list carries no fee. For a transfer I sent, the fee comes from the
  extrinsic's events (`/extrinsics/<height>-<index>/events`, `TransactionFeePaid`:
  `actual_fee` + `tip`, only if `who` is me), once per extrinsic. No transaction
  hash in the list: block hash + event index identify the transfer.
* Subscan's free tier is gone; Statescan's hosts are not in any doc, they come from
  `REACT_APP_PUBLIC_API_END_POINT` in the explorer's bundle.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from decimal import Decimal

from app.modules.plugins import chain
from app.modules.plugins.contract import Movement

CHAINS = {"relay": "https://polkadot-api.statescan.io", "assethub": "https://ahp-api.statescan.io"}
NATIVE, DECIMALS = "DOT", 10
PAGE = 100


def transfers(api: str, address: str) -> list[dict]:
    rows: list[dict] = []
    page = 0
    while True:
        body = chain.http_json(f"{api}/accounts/{address}/transfers?page={page}&page_size={PAGE}")
        items = body.get("items") if isinstance(body, dict) else None
        if not isinstance(items, list):
            raise chain.ChainUnavailable("invalid answer")
        rows.extend(items)
        if len(rows) >= int(body.get("total") or 0) or not items:
            return rows
        page += 1


def extrinsic_fee(api: str, address: str, height: int, index: int) -> Decimal | None:
    body = chain.http_json(f"{api}/extrinsics/{height}-{index}/events?page=0&page_size=100")
    events = body.get("items") if isinstance(body, dict) else body  # paged answer
    for e in events if isinstance(events, list) else []:
        if e.get("method") != "TransactionFeePaid":
            continue
        args = {a.get("name"): a.get("value") for a in e.get("args") or []}
        if args.get("who") != address:
            return None
        return chain.units(int(args.get("actual_fee") or 0) + int(args.get("tip") or 0), DECIMALS)
    return None


def convert(
    address: str,
    records: list[dict],
    network: str,
    fee_of: Callable[[int, int], Decimal | None] = lambda _h, _i: None,
) -> list[Movement]:
    out = []
    charged: set[tuple] = set()
    for r in records:
        if not r.get("isNativeAsset", True):
            continue
        ix = r.get("indexer") or {}
        sent = r.get("from") == address
        extrinsic = (ix.get("blockHeight"), ix.get("extrinsicIndex"))
        fee = None
        if sent and None not in extrinsic and extrinsic not in charged:
            charged.add(extrinsic)
            fee = fee_of(*extrinsic)
        out.append(
            chain.transfer(
                sent=sent,
                received=r.get("to") == address,
                asset=NATIVE,
                amount=chain.units(r["balance"], DECIMALS),
                timestamp=datetime.fromtimestamp(int(ix["blockTime"]) / 1000, tz=UTC),
                external_id=f"{network}:{ix.get('blockHash')}:{ix.get('eventIndex')}",
                sender=r.get("from"),
                receiver=r.get("to"),
                fee=fee,
                comment=f"Polkadot {network}",
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
    movements: list[Movement] = []
    for i, (network, api) in enumerate(CHAINS.items(), 1):
        movements += convert(
            address,
            transfers(api, address),
            network,
            lambda height, index, api=api: extrinsic_fee(api, address, height, index),
        )
        if progress:
            progress({"step": network, "done": i, "total": len(CHAINS), "rows": len(movements)})
    yield from chain.since_only(movements, since)


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    """Relay Chain and Asset Hub together; a chain that does not know the account
    (HTTP 404, e.g. the relay after the move to the Asset Hub) holds nothing."""
    total = 0
    for api in CHAINS.values():
        try:
            body = chain.http_json(f"{api}/accounts/{address}")
        except chain.ChainUnavailable as exc:
            if str(exc) == "HTTP 404":
                continue
            raise
        total += int(((body or {}).get("data") or {}).get("total") or 0)
    return [("spot", NATIVE, chain.units(total, DECIMALS))]
