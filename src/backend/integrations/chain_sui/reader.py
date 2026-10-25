"""Sui through GraphQL (research 2026-08-27, measured 2026-10-03).

* JSON-RPC on public full nodes is deprecated; GraphQL answers without a key. The
  field is `transactions` (filter `affectedAddress`), not the older
  `transactionBlocks`, which fails with HTTP 200 and an `errors` block — errors are
  checked, an empty answer is not trusted.
* Amounts exist **only** as balance changes per owner and coin type.
* **The gas is inside the sender's SUI change**: net gas = computation + storage −
  rebate. It is taken out and booked as the fee: sent + fee == what left.
* Coin types are full paths (`0x…2::sui::SUI`): symbol = last part; decimals of
  other coins come from `coinMetadata`, never assumed.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Iterator
from datetime import datetime

from app.modules.plugins import chain
from app.modules.plugins.contract import Kind, Movement

API = "https://graphql.mainnet.sui.io/graphql"
NATIVE, DECIMALS = "SUI", 9
SUI_TYPE = "0x0000000000000000000000000000000000000000000000000000000000000002::sui::SUI"

QUERY = """query($a: SuiAddress!, $after: String) {
  transactions(first: 50, after: $after, filter: {affectedAddress: $a}) {
    pageInfo { hasNextPage endCursor }
    nodes { digest sender { address } effects { timestamp status
      gasEffects { gasSummary { computationCost storageCost storageRebate } }
      balanceChanges(first: 50) { nodes { amount owner { address } coinType { repr } } } } } } }"""
METADATA = "query($t: String!) { coinMetadata(coinType: $t) { symbol decimals } }"


def _graphql(query: str, variables: dict) -> dict:
    body = chain.http_json(API, {"query": query, "variables": variables})
    if body.get("errors"):
        raise chain.ChainUnavailable(str(body["errors"][0].get("message"))[:120])
    return body.get("data") or {}


def transactions(address: str) -> list[dict]:
    rows: list[dict] = []
    after = None
    while True:
        page = _graphql(QUERY, {"a": address, "after": after}).get("transactions") or {}
        rows += page.get("nodes") or []
        info = page.get("pageInfo") or {}
        if not info.get("hasNextPage"):
            return rows
        after = info.get("endCursor")


def coin(coin_type: str, cache: dict) -> tuple[str, int]:
    if coin_type == SUI_TYPE or coin_type.endswith("::sui::SUI"):
        return NATIVE, DECIMALS
    if coin_type not in cache:
        meta = _graphql(METADATA, {"t": coin_type}).get("coinMetadata") or {}
        if meta.get("decimals") is None:
            raise chain.ChainUnavailable(f"no metadata for {coin_type[-30:]}")
        cache[coin_type] = (
            (meta.get("symbol") or coin_type.split("::")[-1]).upper(),
            int(meta["decimals"]),
        )
    return cache[coin_type]


def convert(
    address: str, txs: list[dict], metadata: Callable[[str], tuple[str, int]]
) -> list[Movement]:
    me = address.lower()
    out: list[Movement] = []
    for t in txs:
        effects = t.get("effects") or {}
        timestamp = datetime.fromisoformat(effects["timestamp"].replace("Z", "+00:00"))
        changes = (effects.get("balanceChanges") or {}).get("nodes") or []
        mine = [c for c in changes if ((c.get("owner") or {}).get("address") or "").lower() == me]
        is_sender = ((t.get("sender") or {}).get("address") or "").lower() == me
        g = (effects.get("gasEffects") or {}).get("gasSummary") or {}
        gas = (
            int(g.get("computationCost") or 0)
            + int(g.get("storageCost") or 0)
            - int(g.get("storageRebate") or 0)
        )
        fee = chain.units(gas, DECIMALS) if is_sender and gas > 0 else None
        if effects.get("status") not in (None, "SUCCESS"):
            if fee:
                out.append(
                    Movement(
                        kind=Kind.FEE,
                        fee_asset=NATIVE,
                        fee_amount=fee,
                        timestamp=timestamp,
                        external_id=t.get("digest"),
                        comment="failed transaction",
                        raw=t,
                    )
                )
            continue
        fee_left = fee is not None
        for c in mine:
            coin_type = (c.get("coinType") or {}).get("repr") or ""
            symbol, decimals = metadata(coin_type)
            amount = int(c["amount"])
            if symbol == NATIVE and is_sender and gas > 0:
                amount += gas  # take the gas out of the sender's change
            if amount == 0:
                continue
            others = [
                (o.get("owner") or {}).get("address")
                for o in changes
                if o is not c
                and (o.get("coinType") or {}).get("repr") == coin_type
                and (int(o["amount"]) < 0) != (amount < 0)
            ]
            pays = fee_left and symbol == NATIVE
            fee_left = fee_left and not pays
            out.append(
                chain.transfer(
                    sent=amount < 0,
                    received=amount > 0,
                    asset=symbol,
                    amount=chain.units(abs(amount), decimals),
                    timestamp=timestamp,
                    external_id=f"{t.get('digest')}:{symbol}",
                    sender=others[0] if others else None,
                    receiver=others[0] if others else None,
                    fee=fee if pays else None,
                    fee_asset=NATIVE,
                    raw=t,
                )
            )
        if fee_left:  # paid gas, but no SUI moved apart from it
            out.append(
                Movement(
                    kind=Kind.FEE,
                    fee_asset=NATIVE,
                    fee_amount=fee,
                    timestamp=timestamp,
                    external_id=t.get("digest"),
                    raw=t,
                )
            )
    return out


def fetch(
    address: str,
    since: datetime | None,
    progress: Callable[[dict], None] | None = None,
    key: str | None = None,
) -> Iterator[Movement]:
    txs = transactions(address)
    if progress:
        progress({"step": "transactions", "done": 1, "total": 1, "rows": len(txs)})
    cache: dict = {}
    yield from chain.since_only(convert(address, txs, lambda c: coin(c, cache)), since)


BALANCES = (
    "query($a: SuiAddress!) { address(address: $a) "
    "{ balances { nodes { coinType { repr } totalBalance } } } }"
)


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    data = _graphql(BALANCES, {"a": address})
    nodes = (((data.get("address") or {}).get("balances")) or {}).get("nodes") or []
    cache: dict = {}
    out = []
    for n in nodes:
        with contextlib.suppress(chain.ChainUnavailable):
            symbol, decimals = coin((n.get("coinType") or {}).get("repr") or "", cache)
            out.append(("spot", symbol, chain.units(int(n.get("totalBalance") or 0), decimals)))
    return out
