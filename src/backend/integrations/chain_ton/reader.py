"""TON through toncenter API v3 (2026-10-23).

* `/transactions?account=` lists the wallet's own transactions, oldest first, paged by
  `offset`. Amounts in nanotons (10^-9). Addresses in the answers are raw (`0:HEX`); the
  user enters the friendly form (`UQ…`/`EQ…`), which is turned into raw to compare.
* **One wallet transaction = one incoming message + its outgoing ones.** A message from
  outside (no source) is the owner's order: each outgoing message is a send. A message from
  another account brings value: a receive.
* **What it costs:** `total_fees` of the transaction plus the forward fee of each outgoing
  message — measured: in - out - total_fees - forward fees equals the balance to the nanoton.
  Receiving costs a little storage/compute fee too; it is booked on the receive.
* A message that bounces comes back as an incoming one and is read as such.
* Jettons (tokens) from `/jetton/transfers?owner_address=`: owners as source and
  destination; symbol and decimals of the jetton master (`/jetton/masters`, default 9).
* Without a key toncenter allows one call per second; with one (free) more.
* Checked against two public wallets (12 and 27 transactions, 16 jetton transfers).
"""

from __future__ import annotations

import base64
import time
from collections.abc import Callable, Iterator
from datetime import datetime
from decimal import Decimal

from app.modules.plugins import chain
from app.modules.plugins.contract import Kind, Movement

API = "https://toncenter.com/api/v3"
NATIVE, DECIMALS = "TON", 9
PAGE = 256
PAUSE = 1.1


def raw_address(address: str) -> str:
    """`UQ…`/`EQ…` (base64url, 36 bytes) or `0:hex` → `0:HEX`."""
    if ":" in address:
        wc, h = address.split(":", 1)
        return f"{int(wc)}:{h.upper()}"
    data = base64.urlsafe_b64decode(address + "=" * (-len(address) % 4))
    wc = int.from_bytes(data[1:2], "big", signed=True)
    return f"{wc}:{data[2:34].hex().upper()}"


class Center:
    def __init__(self, key: str | None) -> None:
        self.headers = {"X-API-Key": key} if key else None
        self.masters: dict[str, tuple[str, int]] = {}
        self.names: dict[str, str] = {}

    def get(self, path: str):
        if not self.headers:
            time.sleep(PAUSE)
        body = chain.http_json(f"{API}/{path}", headers=self.headers)
        for raw, entry in ((body or {}).get("address_book") or {}).items():
            if (entry or {}).get("user_friendly"):
                self.names[raw] = entry["user_friendly"]
        return body

    def pages(self, path: str, field: str) -> list[dict]:
        rows: list[dict] = []
        while True:
            page = (self.get(f"{path}&limit={PAGE}&offset={len(rows)}&sort=asc") or {}).get(field)
            if not isinstance(page, list):
                raise chain.ChainUnavailable("invalid answer")
            rows += page
            if len(page) < PAGE:
                return rows

    def master(self, address: str) -> tuple[str, int]:
        if address not in self.masters:
            body = self.get(f"jetton/masters?address={address}&limit=1") or {}
            found = body.get("jetton_masters") or [{}]
            content = (found[0] if found else {}).get("jetton_content") or {}
            # an off-chain content (USDT: only a uri) names itself in `metadata`
            listed = ((body.get("metadata") or {}).get(address) or {}).get("token_info") or []
            info = next((i for i in listed if i.get("type") == "jetton_masters"), {})
            symbol = content.get("symbol") or info.get("symbol") or content.get("name")
            decimals = content.get("decimals") or (info.get("extra") or {}).get("decimals") or 9
            # Tether writes USD₮
            self.masters[address] = (
                (symbol or address[:8]).strip().replace("₮", "T"),
                int(decimals),
            )
        return self.masters[address]

    def name(self, raw: str | None) -> str | None:
        return self.names.get(raw or "", raw)


def convert(me: str, txs: list[dict], jettons: list[dict], center: Center) -> list[Movement]:
    out: list[Movement] = []
    for t in txs:
        when = chain.seconds(t.get("now") or 0)
        msg = t.get("in_msg") or {}
        outs = t.get("out_msgs") or []
        fee = chain.units(
            int(t.get("total_fees") or 0) + sum(int(o.get("fwd_fee") or 0) for o in outs), DECIMALS
        )
        value = chain.units(msg.get("value") or 0, DECIMALS)
        ref = t.get("hash")
        paid = False
        if msg.get("source") and value:
            receive_fee = fee if not outs else Decimal(0)
            out.append(
                Movement(
                    kind=Kind.RECEIVE,
                    incoming_asset=NATIVE,
                    incoming_amount=value,
                    counterparty=center.name(msg.get("source")),
                    fee_asset=NATIVE if receive_fee else None,
                    fee_amount=receive_fee or None,
                    timestamp=when,
                    external_id=f"{ref}:in",
                    raw=t,
                )
            )
            paid = bool(receive_fee)
        for i, o in enumerate(outs):
            amount = chain.units(o.get("value") or 0, DECIMALS)
            if not amount:
                continue
            target = o.get("destination")
            out.append(
                chain.transfer(
                    sent=True,
                    received=target == me,
                    asset=NATIVE,
                    amount=amount,
                    receiver=center.name(target),
                    fee=None if paid else (fee or None),
                    fee_asset=NATIVE,
                    timestamp=when,
                    external_id=f"{ref}:out{i}",
                    raw=t,
                )
            )
            paid = paid or bool(fee)
        if fee and not paid:
            out.append(
                Movement(
                    kind=Kind.FEE,
                    fee_asset=NATIVE,
                    fee_amount=fee,
                    timestamp=when,
                    external_id=f"{ref}:fee",
                    raw=t,
                )
            )
    for j in jettons:
        if j.get("transaction_aborted"):
            continue
        symbol, decimals = center.master(j.get("jetton_master") or "")
        source, target = j.get("source"), j.get("destination")
        out.append(
            chain.transfer(
                sent=source == me,
                received=target == me,
                asset=symbol,
                amount=chain.units(j.get("amount") or 0, decimals),
                sender=center.name(source),
                receiver=center.name(target),
                timestamp=chain.seconds(j.get("transaction_now") or 0),
                external_id=f"{j.get('transaction_hash')}:jetton",
                raw=j,
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
    center = Center(key)
    txs = center.pages(f"transactions?account={address}", "transactions")
    if progress:
        progress({"step": "transactions", "done": 1, "total": 2, "rows": len(txs)})
    jettons = center.pages(
        f"jetton/transfers?owner_address={address}&direction=both", "jetton_transfers"
    )
    if progress:
        progress({"step": "jettons", "done": 2, "total": 2, "rows": len(txs) + len(jettons)})
    yield from chain.since_only(convert(raw_address(address), txs, jettons, center), since)


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    center = Center(key)
    wallets = (center.get(f"walletStates?address={address}") or {}).get("wallets") or [{}]
    out = [
        ("spot", NATIVE, chain.units((wallets[0] if wallets else {}).get("balance") or 0, DECIMALS))
    ]
    for w in (center.get(f"jetton/wallets?owner_address={address}&limit=100") or {}).get(
        "jetton_wallets"
    ) or []:
        if int(w.get("balance") or 0):
            symbol, decimals = center.master(w.get("jetton") or "")
            out.append(("spot", symbol, chain.units(w["balance"], decimals)))
    return out
