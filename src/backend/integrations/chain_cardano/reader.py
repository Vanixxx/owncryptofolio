"""Cardano through Koios (research 2026-08-27/28, measured 2026-10-03).

UTXO like Bitcoin, netted with `mempool.netted`.

* Koios takes **POST** with the address in the body; as GET it answers 400 with a
  leaked Postgres message that reads like an unknown address.
* `address_txs` gives hashes only; `tx_info` with `_inputs: true` now carries inputs,
  outputs, fee and time in one call (2026-08 it still needed `tx_utxos` as well).
  Without inputs, change could not be told from a receipt: such a record aborts.
* Amounts are strings in lovelace, the address is `payment_addr.bech32`.
* **Reward withdrawals** spend from the stake account, not from a UTXO: they are
  booked as staking income and count as my input, otherwise a send that also
  withdraws would look smaller by exactly the reward.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime

from app.modules.plugins import chain, mempool
from app.modules.plugins.contract import IncomeKind, Kind, Movement

API = "https://api.koios.rest/api/v1"
NATIVE, DECIMALS = "ADA", 6
PAGE, BATCH = 1000, 50


def transactions(address: str) -> list[dict]:
    hashes: list[str] = []
    while True:
        batch = chain.http_json(
            f"{API}/address_txs?offset={len(hashes)}&limit={PAGE}", {"_addresses": [address]}
        )
        if not isinstance(batch, list):
            raise chain.ChainUnavailable("invalid answer")
        hashes += [b["tx_hash"] for b in batch if b.get("tx_hash")]
        if len(batch) < PAGE:
            break
    rows: list[dict] = []
    for i in range(0, len(hashes), BATCH):
        info = chain.http_json(
            f"{API}/tx_info", {"_tx_hashes": hashes[i : i + BATCH], "_inputs": True}
        )
        if not isinstance(info, list):
            raise chain.ChainUnavailable("invalid answer")
        rows += info
    return rows


def _addr(entry: dict) -> str | None:
    return (entry.get("payment_addr") or {}).get("bech32")


def convert(address: str, txs: list[dict]) -> list[Movement]:
    out: list[Movement] = []
    for t in txs:
        inputs, outputs = t.get("inputs") or [], t.get("outputs") or []
        if not inputs:
            raise chain.ChainUnavailable("Cardano transaction without inputs")
        stake = {e.get("stake_addr") for e in inputs + outputs if _addr(e) == address} - {None}
        withdrawn = sum(
            int(w.get("amount") or 0)
            for w in t.get("withdrawals") or []
            if w.get("stake_addr") in stake
        )
        timestamp = chain.seconds(t["tx_timestamp"])
        if withdrawn:
            out.append(
                Movement(
                    kind=Kind.INCOME,
                    income_kind=IncomeKind.STAKING,
                    incoming_asset=NATIVE,
                    incoming_amount=chain.units(withdrawn, DECIMALS),
                    timestamp=timestamp,
                    external_id=f"{t.get('tx_hash')}:withdrawal",
                    comment="reward withdrawal",
                    raw={"withdrawals": t.get("withdrawals")},
                )
            )
        m = mempool.netted(
            address,
            [(_addr(i), i.get("value")) for i in inputs]
            + ([(address, withdrawn)] if withdrawn else []),
            [(_addr(o), o.get("value")) for o in outputs],
            fee=int(t.get("fee") or 0),
            timestamp=timestamp,
            external_id=t.get("tx_hash"),
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
    info = chain.http_json(f"{API}/address_info", {"_addresses": [address]})
    lovelace = int((info[0] if isinstance(info, list) and info else {}).get("balance") or 0)
    return [("spot", NATIVE, chain.units(lovelace, DECIMALS))]
