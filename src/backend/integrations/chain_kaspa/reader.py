"""Kaspa through api.kaspa.org (research 2026-08-27/28).

UTXO like Bitcoin, netted the same way (`mempool.netted`), with its own field names:
`outputs[].script_public_key_address`/`amount`, `inputs[].previous_outpoint_address`/
`previous_outpoint_amount`.

* **Without `resolve_previous_outpoints=light` the inputs are empty**: every spend
  would look like a receipt of the change.
* `block_time` is in **milliseconds**.
* The answer names no fee: it is inputs minus outputs, but only if **all** inputs
  are resolved — a wrong fee is worse than none.
* Transactions not accepted by the DAG (`is_accepted` false) moved nothing.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime

from app.modules.plugins import chain, mempool
from app.modules.plugins.contract import Movement

API = "https://api.kaspa.org"
NATIVE, DECIMALS = "KAS", 8
PAGE = 50


def transactions(address: str) -> list[dict]:
    rows: list[dict] = []
    while True:
        batch = chain.http_json(
            f"{API}/addresses/{address}/full-transactions?limit={PAGE}&offset={len(rows)}"
            "&resolve_previous_outpoints=light"
        )
        if not isinstance(batch, list):
            raise chain.ChainUnavailable("invalid answer")
        rows.extend(batch)
        if len(batch) < PAGE:
            return rows


def convert(address: str, txs: list[dict]) -> list[Movement]:
    out = []
    for t in txs:
        if t.get("is_accepted") is False:
            continue
        inputs = t.get("inputs") or []
        outputs = t.get("outputs") or []
        mine = [i for i in inputs if i.get("previous_outpoint_address") == address]
        if any(i.get("previous_outpoint_amount") is None for i in mine):
            raise chain.ChainUnavailable("Kaspa input of this address without resolved amount")
        resolved = all(i.get("previous_outpoint_amount") is not None for i in inputs)
        fee = (
            sum(int(i["previous_outpoint_amount"]) for i in inputs)
            - sum(int(o.get("amount") or 0) for o in outputs)
            if resolved and inputs
            else None
        )
        m = mempool.netted(
            address,
            [
                (i.get("previous_outpoint_address"), i.get("previous_outpoint_amount"))
                for i in inputs
            ],
            [(o.get("script_public_key_address"), o.get("amount")) for o in outputs],
            fee=fee,
            timestamp=datetime.fromtimestamp(int(t["block_time"]) / 1000, tz=UTC),
            external_id=t.get("transaction_id"),
            raw=t,
            native=NATIVE,
            decimals=DECIMALS,
        )
        if m:
            out.append(m)
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
    yield from chain.since_only(convert(address, txs), since)


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    body = chain.http_json(f"{API}/addresses/{address}/balance")
    return [("spot", NATIVE, chain.units(int(body.get("balance") or 0), DECIMALS))]
