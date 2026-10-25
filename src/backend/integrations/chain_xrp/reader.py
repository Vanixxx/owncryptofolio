"""XRP Ledger through Ripple's public JSON-RPC servers (2026-10-23).

* `account_tx` pages with `marker`; xrplcluster.com rationed us after a few calls
  ("units quota"), s1/s2.ripple.com answered freely — two servers, the second as fallback.
* The answer has two forms: API v1 `tx` with `hash` and `date` inside, v2 `tx_json` with
  `hash` beside it. Both are read.
* **Time counts from 2000-01-01** (Ripple epoch), not from 1970.
* **What arrived is `meta.delivered_amount`**, not `Amount`: a partial payment delivers
  less than it names. XRP comes as a string of drops (10^-6), an issued currency as
  {currency, issuer, value} with a decimal value; a 40-character currency is hex ASCII.
* The fee (drops) is paid by `Account`, also for a transaction that failed (`tec…`).
* Not a payment and sent by me (trust line, offer, settings): its fee is booked, the rest
  is "not read". Offers trade on the ledger's DEX: such an account shows in the balance check.
* An address that never received its reserve is `actNotFound`: no history, not an error.
* Written from the docs and a public account (9 payments): the user has no XRP account.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from decimal import Decimal

from app.modules.plugins import chain
from app.modules.plugins.contract import Kind, Movement

SERVERS = ("https://s2.ripple.com:51234/", "https://s1.ripple.com:51234/")
NATIVE, DECIMALS = "XRP", 6
RIPPLE_EPOCH = 946684800
PAGE = 200


class NoAccount(Exception):
    pass


def rpc(method: str, params: dict) -> dict:
    last: Exception | None = None
    for url in SERVERS:
        try:
            body = chain.http_json(url, {"method": method, "params": [params]})
        except chain.ChainUnavailable as exc:
            last = exc
            continue
        result = (body or {}).get("result") or {}
        if result.get("error") == "actNotFound":
            raise NoAccount
        if result.get("status") == "success":
            return result
        last = chain.ChainUnavailable(str(result.get("error") or "invalid answer"))
    raise last or chain.ChainUnavailable("no answer")


def transactions(account: str) -> list[dict]:
    rows: list[dict] = []
    marker = None
    while True:
        params = {
            "account": account,
            "limit": PAGE,
            "forward": True,
            "ledger_index_min": -1,
            "ledger_index_max": -1,
        }
        if marker:
            params["marker"] = marker
        try:
            result = rpc("account_tx", params)
        except NoAccount:
            return []
        rows += result.get("transactions") or []
        marker = result.get("marker")
        if not marker:
            return rows


def currency(code: str) -> str:
    if len(code) == 40:  # hex: an ASCII name padded with zeros
        try:
            text = bytes.fromhex(code).rstrip(b"\x00").decode()
            if text.isprintable() and text:
                return text
        except ValueError:
            pass
    return code


def amount(value) -> tuple[str, Decimal] | None:
    if isinstance(value, str):
        return NATIVE, chain.units(value, DECIMALS)
    if isinstance(value, dict) and value.get("currency"):
        return currency(value["currency"]), Decimal(str(value.get("value") or "0"))
    return None


def convert(account: str, records: list[dict]) -> list[Movement]:
    out: list[Movement] = []
    for rec in records:
        tx = rec.get("tx_json") or rec.get("tx") or {}
        meta = rec.get("meta") or {}
        tx_hash = rec.get("hash") or tx.get("hash")
        if not tx.get("date") and tx.get("date") != 0:
            continue
        timestamp = datetime.fromtimestamp(int(tx["date"]) + RIPPLE_EPOCH, tz=UTC)
        mine = tx.get("Account") == account
        fee = chain.units(tx.get("Fee") or 0, DECIMALS) if mine else None
        base = {"timestamp": timestamp, "external_id": tx_hash, "raw": rec}
        ok = meta.get("TransactionResult") == "tesSUCCESS"
        kind = tx.get("TransactionType")
        if ok and kind == "Payment":
            got = amount(
                meta.get("delivered_amount") or meta.get("DeliveredAmount") or tx.get("Amount")
            )
            if got:
                out.append(
                    chain.transfer(
                        sent=mine,
                        received=tx.get("Destination") == account,
                        asset=got[0],
                        amount=got[1],
                        sender=tx.get("Account"),
                        receiver=tx.get("Destination"),
                        fee=fee or None,
                        fee_asset=NATIVE,
                        comment=f"tag {tx['DestinationTag']}" if "DestinationTag" in tx else None,
                        **base,
                    )
                )
                continue
        if mine and fee:
            # failed, or not a payment: the fee left the account all the same
            out.append(
                Movement(kind=Kind.FEE, fee_asset=NATIVE, fee_amount=fee, comment=kind, **base)
            )
        elif not mine:
            out.append(Movement(kind=Kind.OTHER, comment=kind, **base))
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
    yield from chain.since_only(convert(address, records), since)


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    try:
        info = rpc("account_info", {"account": address, "ledger_index": "validated"})
    except NoAccount:
        return [("spot", NATIVE, Decimal(0))]
    out = [("spot", NATIVE, chain.units(info["account_data"]["Balance"], DECIMALS))]
    lines = rpc("account_lines", {"account": address, "ledger_index": "validated"})
    for line in lines.get("lines") or []:
        value = Decimal(str(line.get("balance") or "0"))
        if value > 0:
            out.append(("spot", currency(line.get("currency") or ""), value))
    return out
