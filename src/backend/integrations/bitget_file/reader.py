"""Bitget — file import (ZIP export).

Facts from the real exports (research 2026-08-23/24, re-checked 2026-10-03):

* **The time zone is nowhere.** Bitget writes local time of the download moment
  and does not say which offset. It follows from the download date (in the
  file names) and the user's time zone, DST included.
* `Spot-Transaktionen` lists each trade as two rows; together with
  `Order-Details` every trade would count twice. Only non-trade types are read.
* Withdrawals: `Quantity = |Amount| + |Fee|` links the deposit/withdrawal file
  (gross, txid, address) with the transaction file (net, fee) — by arithmetic,
  not by time, which differs by minutes.
* `Gains`/`Consumption` (instant swap) and `Increase`/`Reduce exchange rate`
  (token migration, MATIC -> POL 1:1) are row pairs in the same second.
* **Futures ledger** (`…Futures-Transaktionen`) carries a running wallet
  balance. `adjust_margin_ifm` and `adjust_down_leverage` move margin without
  cash flow: including them overstates the balance by exactly their sum
  (512.80 USDT, measured). The reader re-adds the ledger and rejects the file if
  the result does not match the reported balance.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from collections import defaultdict
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from app.modules.plugins import archive
from app.modules.plugins.contract import Kind, Market, Movement

DOWNLOAD = re.compile(r"(\d{4}-\d{2}-\d{2})[ _]\d{2}[:_]\d{2}[:_]\d{2}")

SPOT_OTHER = {
    "Transfer out": Kind.INTERNAL_TRANSFER,
    "Transfer in": Kind.INTERNAL_TRANSFER,
    "Buy with card": Kind.OTHER,
}
PAIRS = {
    ("Gains", "Consumption"): Kind.TRADE,
    ("Increase exchange rate", "Reduce exchange rate"): Kind.MIGRATION,
}
PAIRED = {t for pair in PAIRS for t in pair}
FROM_DEPOSIT_FILE = {"Ordinary Withdrawal", "Deposit"}
SKIP_SPOT = {"Buy", "Sell"} | FROM_DEPOSIT_FILE

FUTURES_TRANSFER = {"trans_to_exchange", "trans_from_exchange"}
FUTURES_NO_CASH = {"adjust_margin_ifm", "adjust_down_leverage"}
BALANCE_TOLERANCE = Decimal("0.000001")


def _num(value: str | None) -> Decimal | None:
    text = (value or "").strip().replace("\t", "")
    if not text or text in ("-", "NULL"):
        return None
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"not a number: {value!r}") from exc


def _offset(names: list[str], tz: str) -> timezone:
    for name in names:
        if m := DOWNLOAD.search(name):
            day = datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=ZoneInfo(tz))
            return timezone(day.utcoffset() or timedelta(0))
    raise ValueError(
        "no download date in the file names; Bitget states no time zone, "
        "so the real time cannot be determined"
    )


def _time(value: str, offset: timezone) -> datetime:
    try:
        return datetime.strptime((value or "").strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=offset)
    except ValueError as exc:
        raise ValueError(f"unreadable timestamp {value!r}") from exc


def _role(name: str) -> str | None:
    n = name.lower()
    if "futures" in n:
        if "transaktionen" in n or "transactions" in n:
            return "futures_ledger"
        if "positionsverlauf" in n or "position history" in n:
            return "futures_positions"
        return None
    if "margin" in n or "earn" in n or "einheitlichen" in n or "unified" in n:
        return None
    if "order-details" in n or "order details" in n:
        return "trades"
    if "spot-transaktionen" in n or "spot transactions" in n:
        return "transactions"
    if "einzahlungs" in n or "deposit" in n:
        return "deposits"
    return None


def _load(path: Path) -> tuple[dict[str, list[dict]], dict[str, int], list[str]]:
    if not zipfile.is_zipfile(path):
        raise ValueError("expected the Bitget export ZIP")
    archive.check(path)
    files: dict[str, list[dict]] = defaultdict(list)
    skipped: dict[str, int] = {}
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        for name in names:
            text = z.read(name).decode("utf-8-sig", errors="replace")
            rows = [
                r
                for r in csv.DictReader(io.StringIO(text))
                if any((v or "").strip() for v in r.values())
            ]
            role = _role(name)
            if role:
                files[role].extend(rows)
            elif rows:
                skipped[name] = len(rows)
    return files, skipped, [path.name, *names]


def skipped(path: Path, options: dict | None = None) -> dict[str, int]:
    """Non-empty files the reader deliberately does not read (ADR 0020)."""
    return _load(path)[1]


def read(path: Path, options: dict | None = None) -> Iterator[Movement]:
    files, _, names = _load(path)
    offset = _offset(names, (options or {}).get("timezone", "Europe/Berlin"))
    tx = files.get("transactions", [])
    yield from _trades(files.get("trades", []), offset)
    yield from _deposits(files.get("deposits", []), tx, offset)
    yield from _pairs(tx, offset)
    yield from _spot_other(tx, offset)
    yield from _futures_ledger(files.get("futures_ledger", []), offset)
    yield from _positions(files.get("futures_positions", []), offset)


def _clean(row: dict) -> dict:
    # Rows with more cells than the header put the surplus under the key None;
    # keep it (raw means raw, ADR 0001) under a name.
    return {("_extra" if k is None else k): v for k, v in row.items() if v not in (None, "", [])}


def _trades(rows: list[dict], offset: timezone) -> Iterator[Movement]:
    for r in rows:
        base, quote = (r.get("Base Asset") or "").strip(), (r.get("Quote Asset") or "").strip()
        amount, total, fee = _num(r.get("Amount")), _num(r.get("Total")), _num(r.get("Fee"))
        buy = (r.get("Direction") or "").strip().lower() == "buy"
        yield Movement(
            timestamp=_time(r.get("Date", ""), offset),
            kind=Kind.TRADE,
            incoming_asset=base if buy else quote,
            incoming_amount=amount if buy else total,
            outgoing_asset=quote if buy else base,
            outgoing_amount=total if buy else amount,
            fee_asset=(r.get("Fee Coin") or "").strip() or None if fee else None,
            fee_amount=abs(fee) if fee else None,
            comment=f"{r.get('Trading pair')} {r.get('Direction')}",
            raw=_clean(r),
        )


def _net_and_fee(tx: list[dict], coin: str, gross: Decimal | None):
    if gross is None:
        return None, None
    for r in tx:
        if (r.get("Coin") or "").strip().upper() != coin:
            continue
        net, fee = _num(r.get("Amount")), _num(r.get("Fee"))
        if net is not None and abs(net) + abs(fee or 0) == gross:
            return abs(net), (abs(fee) if fee else None)
    return None, None


def _deposits(rows: list[dict], tx: list[dict], offset: timezone) -> Iterator[Movement]:
    for r in rows:
        if (r.get("Status") or "").strip().lower() not in ("successful", "success", ""):
            continue
        coin = (r.get("Coin") or "").strip().upper()
        qty = _num(r.get("Quantity"))
        out = (r.get("Type") or "").strip().lower().startswith("withdraw")
        net, fee = _net_and_fee(tx, coin, qty) if out else (None, None)
        amount = net if net is not None else qty
        side = (
            {"outgoing_asset": coin, "outgoing_amount": amount}
            if out
            else {"incoming_asset": coin, "incoming_amount": amount}
        )
        yield Movement(
            timestamp=_time(r.get("Date", ""), offset),
            kind=Kind.SEND if out else Kind.RECEIVE,
            fee_asset=coin if fee else None,
            fee_amount=fee,
            external_id=(r.get("TxID") or "").strip() or None,
            counterparty=(r.get("Address") or "").strip() or None,
            raw=_clean(r),
            **side,
        )


def _signed(coin: str, amount: Decimal | None) -> dict:
    if amount is None or amount == 0:
        return {}
    if amount < 0:
        return {"outgoing_asset": coin, "outgoing_amount": -amount}
    return {"incoming_asset": coin, "incoming_amount": amount}


def _pairs(tx: list[dict], offset: timezone) -> Iterator[Movement]:
    by_time: dict[str, list[dict]] = defaultdict(list)
    for r in tx:
        if (r.get("Type") or "").strip() in PAIRED:
            by_time[(r.get("Date") or "").strip()].append(r)
    for ts, group in by_time.items():
        for (in_type, out_type), kind in PAIRS.items():
            ins = [r for r in group if r.get("Type", "").strip() == in_type]
            outs = [r for r in group if r.get("Type", "").strip() == out_type]
            if len(ins) == 1 and len(outs) == 1:
                i, o = ins[0], outs[0]
                yield Movement(
                    timestamp=_time(ts, offset),
                    kind=kind,
                    incoming_asset=i.get("Coin"),
                    incoming_amount=abs(_num(i.get("Amount")) or 0),
                    outgoing_asset=o.get("Coin"),
                    outgoing_amount=abs(_num(o.get("Amount")) or 0),
                    external_id=(i.get("order") or "").strip() or None,
                    comment=f"{in_type} / {out_type}",
                    raw={"in": _clean(i), "out": _clean(o)},
                )
            else:
                # No clean pair: shown one by one as 'other' instead of guessed.
                for r in ins + outs:
                    yield Movement(
                        timestamp=_time(ts, offset),
                        kind=Kind.OTHER,
                        comment=f"{r.get('Type')} without counterpart",
                        raw=_clean(r),
                        **_signed((r.get("Coin") or "").strip(), _num(r.get("Amount"))),
                    )


def _spot_other(tx: list[dict], offset: timezone) -> Iterator[Movement]:
    for r in tx:
        typ = (r.get("Type") or "").strip()
        if typ in SKIP_SPOT or typ in PAIRED:
            continue
        coin = (r.get("Coin") or "").strip()
        fee = _num(r.get("Fee"))
        yield Movement(
            timestamp=_time(r.get("Date", ""), offset),
            kind=SPOT_OTHER.get(typ, Kind.OTHER),
            fee_asset=coin if fee else None,
            fee_amount=abs(fee) if fee else None,
            external_id=(r.get("order") or "").strip() or None,
            comment=typ,
            raw=_clean(r),
            **_signed(coin, _num(r.get("Amount"))),
        )


def futures_kind(typ: str, amount: Decimal) -> Kind:
    """Shared with the API plugin: the tax endpoint uses the same type names."""
    t = typ.lower()
    if t in FUTURES_TRANSFER:
        return Kind.INTERNAL_TRANSFER
    if "settle_fee" in t or "funding" in t:
        return Kind.FUNDING
    if t.startswith(("open_", "burst_open")) and amount == 0:
        return Kind.FEE
    if "close" in t or "burst" in t or "liquidat" in t or "delivery" in t:
        return Kind.REALIZED_PNL
    return Kind.OTHER


def _futures_ledger(rows: list[dict], offset: timezone) -> Iterator[Movement]:
    expected: dict[str, Decimal] = {}
    summed: dict[str, Decimal] = defaultdict(Decimal)
    # The export lists newest first; reversing keeps the order of rows that share
    # a second, which sorting by the timestamp text would not.
    for r in reversed(rows):
        typ = (r.get("Type") or "").strip()
        coin = (r.get("Coin") or "").strip()
        amount, fee = _num(r.get("Amount")) or Decimal(0), _num(r.get("Fee")) or Decimal(0)
        balance = _num(r.get("Wallet balance"))
        if coin not in expected and balance is not None:
            # Opening balance = balance after the first row minus its own effect.
            effect = Decimal(0) if typ in FUTURES_NO_CASH else amount + fee
            expected[coin] = balance - effect
        if balance is not None:
            expected[coin + ":last"] = balance
        if typ in FUTURES_NO_CASH:
            continue
        summed[coin] += amount + fee
        instrument = (r.get("Futures") or "").strip()
        yield Movement(
            timestamp=_time(r.get("Date", ""), offset),
            kind=futures_kind(typ, amount),
            market=Market.FUTURES,
            instrument=None if instrument in ("", "NULL") else instrument,
            fee_asset=coin if fee else None,
            fee_amount=abs(fee) if fee else None,
            external_id=(r.get("Order") or "").strip() or None,
            comment=typ,
            raw=_clean(r),
            **_signed(coin, amount),
        )
    for coin, total in summed.items():
        opening, last = expected.get(coin), expected.get(coin + ":last")
        if (
            opening is not None
            and last is not None
            and abs(opening + total - last) > BALANCE_TOLERANCE
        ):
            raise ValueError(
                f"futures ledger {coin} does not add up: opening {opening} + "
                f"movements {total} != wallet balance {last}"
            )


def _positions(rows: list[dict], offset: timezone) -> Iterator[Movement]:
    for r in rows:
        contract, _, mode = (r.get("Futures") or "").partition(" ")
        yield Movement(
            timestamp=_time(r.get("Closed time", ""), offset),
            kind=Kind.FUTURES_POSITION,
            market=Market.FUTURES,
            instrument=contract.strip(),
            comment=mode.strip() or None,
            raw=_clean(r),
        )
