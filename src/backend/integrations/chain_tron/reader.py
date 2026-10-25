"""Tron through TronGrid (2026-10-23).

* `/v1/accounts/{a}/transactions` (TRX, TRC-10, contract calls, internal transactions)
  and `/v1/accounts/{a}/transactions/trc20` (tokens with symbol and decimals), both paged
  with `meta.fingerprint`, oldest first. Amounts in sun (10^-6).
* **Addresses inside a transaction are hex** (`41…`): turned into the `T…` form
  (base58check), the one users know.
* **Fee** is `ret[0].fee`: TRX burned for bandwidth and energy, paid by the sender
  (`owner_address`), also when the contract call failed. A token transfer's fee sits on
  its contract call, which is booked as a fee of its own.
* **Staked TRX stays yours:** freezing, unfreezing and delegating resources move no coin;
  the balance counts liquid + frozen + unfreezing + delegated, so the check still meets.
* **Voting rewards** (`WithdrawBalanceContract`) name no amount in the transaction; it comes
  from `gettransactioninfobyid` (`withdraw_amount`): staking income.
* TRC-10 tokens are named by id: `/v1/assets/{id}` gives abbreviation and precision.
* Spam tokens (fake USDT, "visit …") arrive like any other; the spam rules hide them.
* A free key (TronGrid) only raises the limits; without one, short pauses between pages.
* Checked against a public address (70 transactions, TRC-20 transfers).
"""

from __future__ import annotations

import contextlib
import hashlib
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from decimal import Decimal

from app.modules.plugins import chain
from app.modules.plugins.contract import IncomeKind, Kind, Movement

API = "https://api.trongrid.io"
NATIVE, DECIMALS = "TRX", 6
PAGE = 200
PAUSE = 0.4  # without a key TronGrid answers 429 to a quick series
ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def base58(hex_address: str | None) -> str | None:
    """`41…` (or `0x…`) → `T…`."""
    if not hex_address:
        return None
    h = hex_address.lower().removeprefix("0x")
    if h.startswith("t"):
        return hex_address  # already base58
    raw = bytes.fromhex(("41" + h[-40:]) if len(h) == 40 else h)
    data = raw + hashlib.sha256(hashlib.sha256(raw).digest()).digest()[:4]
    n, out = int.from_bytes(data, "big"), ""
    while n:
        n, r = divmod(n, 58)
        out = ALPHABET[r] + out
    return "1" * (len(data) - len(data.lstrip(b"\0"))) + out


class Grid:
    def __init__(self, key: str | None) -> None:
        self.headers = {"TRON-PRO-API-KEY": key} if key else None
        self.assets: dict[str, tuple[str, int]] = {}

    def get(self, path: str, body: dict | None = None):
        if not self.headers:
            time.sleep(PAUSE)
        return chain.http_json(f"{API}/{path}", body, headers=self.headers)

    def pages(self, path: str) -> list[dict]:
        rows: list[dict] = []
        fingerprint = None
        while True:
            sep = "&" if "?" in path else "?"
            body = self.get(
                f"{path}{sep}limit={PAGE}&order_by=block_timestamp,asc"
                + (f"&fingerprint={fingerprint}" if fingerprint else "")
            )
            page = (body or {}).get("data")
            if not isinstance(page, list):
                raise chain.ChainUnavailable("invalid answer")
            rows += page
            fingerprint = (body.get("meta") or {}).get("fingerprint")
            if not fingerprint or not page:
                return rows

    def asset(self, asset_id: str) -> tuple[str, int]:
        if asset_id not in self.assets:
            data = (self.get(f"v1/assets/{asset_id}") or {}).get("data") or [{}]
            a = data[0] if data else {}
            self.assets[asset_id] = (
                (a.get("abbr") or a.get("name") or f"TRC10-{asset_id}").strip(),
                int(a.get("precision") or 0),
            )
        return self.assets[asset_id]

    def withdrawn(self, tx_id: str) -> Decimal:
        info = self.get("wallet/gettransactioninfobyid", {"value": tx_id}) or {}
        return chain.units(info.get("withdraw_amount") or 0, DECIMALS)


def _when(ms) -> datetime:
    return datetime.fromtimestamp(int(ms) / 1000, tz=UTC)


def convert(address: str, txs: list[dict], trc20: list[dict], grid: Grid) -> list[Movement]:
    out: list[Movement] = []
    for t in txs:
        if "internal_tx_id" in t:  # TRX a contract sent to me, or I sent through one
            value = int(((t.get("data") or {}).get("call_value") or {}).get("_") or 0)
            sender, receiver = base58(t.get("from_address")), base58(t.get("to_address"))
            if (
                value
                and address in (sender, receiver)
                and not (t.get("data") or {}).get("rejected")
            ):
                out.append(
                    chain.transfer(
                        sent=sender == address,
                        received=receiver == address,
                        asset=NATIVE,
                        amount=chain.units(value, DECIMALS),
                        sender=sender,
                        receiver=receiver,
                        timestamp=_when(t.get("block_timestamp") or 0),
                        external_id=f"{t.get('tx_id')}:{t.get('internal_tx_id')}",
                        raw=t,
                    )
                )
            continue
        contract = ((t.get("raw_data") or {}).get("contract") or [{}])[0]
        kind = contract.get("type")
        value = (contract.get("parameter") or {}).get("value") or {}
        owner = base58(value.get("owner_address"))
        ret = (t.get("ret") or [{}])[0]
        ok = ret.get("contractRet") in (None, "SUCCESS")
        fee = chain.units(ret.get("fee") or 0, DECIMALS) if owner == address else Decimal(0)
        base = {
            "timestamp": _when(t.get("block_timestamp") or 0),
            "external_id": t.get("txID"),
            "raw": t,
        }
        if ok and kind in ("TransferContract", "TransferAssetContract"):
            receiver = base58(value.get("to_address"))
            if kind == "TransferContract":
                asset, amount = NATIVE, chain.units(value.get("amount") or 0, DECIMALS)
            else:
                name = value.get("asset_name") or ""
                if name and not name.isdigit():
                    with contextlib.suppress(ValueError):
                        name = bytes.fromhex(name).decode()
                asset, decimals = grid.asset(name)
                amount = chain.units(value.get("amount") or 0, decimals)
            out.append(
                chain.transfer(
                    sent=owner == address,
                    received=receiver == address,
                    asset=asset,
                    amount=amount,
                    sender=owner,
                    receiver=receiver,
                    fee=fee or None,
                    fee_asset=NATIVE,
                    **base,
                )
            )
            continue
        if ok and kind == "WithdrawBalanceContract" and owner == address:
            reward = grid.withdrawn(t.get("txID"))
            if reward:
                out.append(
                    Movement(
                        kind=Kind.INCOME,
                        income_kind=IncomeKind.STAKING,
                        incoming_asset=NATIVE,
                        incoming_amount=reward,
                        comment="voting rewards",
                        fee_asset=NATIVE if fee else None,
                        fee_amount=fee or None,
                        **base,
                    )
                )
                continue
        if fee:
            out.append(
                Movement(kind=Kind.FEE, fee_asset=NATIVE, fee_amount=fee, comment=kind, **base)
            )
    seen: dict[str, int] = {}
    for t in trc20:
        info = t.get("token_info") or {}
        if t.get("type") not in (None, "Transfer") or not info.get("symbol"):
            continue
        tx = t.get("transaction_id") or ""
        seen[tx] = seen.get(tx, 0) + 1
        sender, receiver = t.get("from"), t.get("to")
        out.append(
            chain.transfer(
                sent=sender == address,
                received=receiver == address,
                asset=str(info["symbol"]).strip(),
                amount=chain.units(t.get("value") or 0, int(info.get("decimals") or 0)),
                sender=sender,
                receiver=receiver,
                timestamp=_when(t.get("block_timestamp") or 0),
                external_id=f"{tx}:trc20:{seen[tx]}",
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
    grid = Grid(key)
    txs = grid.pages(f"v1/accounts/{address}/transactions")
    if progress:
        progress({"step": "transactions", "done": 1, "total": 2, "rows": len(txs)})
    trc20 = grid.pages(f"v1/accounts/{address}/transactions/trc20")
    if progress:
        progress({"step": "trc20", "done": 2, "total": 2, "rows": len(txs) + len(trc20)})
    yield from chain.since_only(convert(address, txs, trc20, grid), since)


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    grid = Grid(key)
    data = (grid.get(f"v1/accounts/{address}") or {}).get("data") or []
    if not data:
        return [("spot", NATIVE, Decimal(0))]  # an address becomes an account with its first TRX
    a = data[0]
    resource = a.get("account_resource") or {}
    sun = (
        int(a.get("balance") or 0)
        + sum(int(f.get("amount") or 0) for f in a.get("frozenV2") or [])
        + sum(int(u.get("unfreeze_amount") or 0) for u in a.get("unfrozenV2") or [])
        + int(a.get("delegated_frozenV2_balance_for_bandwidth") or 0)
        + int(resource.get("delegated_frozenV2_balance_for_energy") or 0)
    )
    out = [("spot", NATIVE, chain.units(sun, DECIMALS))]
    for item in a.get("assetV2") or []:
        if int(item.get("value") or 0):
            asset, decimals = grid.asset(str(item.get("key")))
            out.append(("spot", asset, chain.units(item["value"], decimals)))
    by_contract = {c: (s, d) for s, (c, d) in (tokens or {}).items()}
    for entry in a.get("trc20") or []:
        for contract, value in entry.items():
            if contract in by_contract and int(value or 0):
                symbol, decimals = by_contract[contract]
                out.append(("spot", symbol, chain.units(value, decimals)))
    return out
