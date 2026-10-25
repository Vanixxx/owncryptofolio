"""KuCoin — BillingHistory ZIP (research 2026-08-29).

* **The topic files are read, not the account history**: the history contains
  the moves between funding, trading and futures account; the same 50 USDC
  appear three times there. Exception: `KuCoin Event` exists only in the history
  (56.276201 VTHO on 2024-04-25, confirmed by the capital snapshot).
* The time zone is in every time column (`Time(UTC+02:00)`) and belongs to the
  profile, not to the download.
* Withdrawal `Amount` is what arrives; the fee comes on top.
* Cancelled fiat deposits look like deposits (2 × 180 EUR); only successful ones count.
* Futures: the realised PNL of a closed position (-19.69870666 USDT) already
  includes funding (-0.40) and trading fees (-0.64). Booked as one result plus
  the position.
* **Transfers to and from futures** are read from the account history (2026-10-11):
  there is no futures history in the ZIP. A move between the funding and the trading
  account shows in both their histories (same coin, amount, second); a `Transfer` with
  no such twin went to or came from the futures account (2024-03-21: 110.84 USDT out,
  2024-03-22: 91.14 USDT back = the money minus the -19.70 result). Before this the
  futures side ran to -19.70 and spot kept 19.70 too much.
* File names contain umlauts in varying encodings; they are matched by ASCII parts.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.modules.plugins.archive import check as zip_check
from app.modules.plugins.contract import IncomeKind, Kind, Market, Movement

TZ = re.compile(r"\(UTC([+-])(\d{1,2})(?::(\d{2}))?\)")
AMOUNT_ASSET = re.compile(r"^\s*([\d.,]+)\s+([A-Za-z0-9]+)\s*$")
FIAT = {"EUR", "USD", "GBP", "CHF", "CAD", "AUD", "JPY"}
COVERED = {"Transfer", "Convert Market", "Spot", "Deposit", "Withdraw"}
HISTORY_ONLY = {"KuCoin Event": IncomeKind.REWARD}
SUCCESS = {"SUCCESS", "DEAL", "PART_DEAL"}


def _num(raw, where: str) -> Decimal:
    if raw is None or str(raw).strip() == "":
        return Decimal(0)
    try:
        return Decimal(str(raw).strip().replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"{where}: {raw!r} is not a number") from exc


def _files(path: Path) -> dict[str, list[dict]]:
    archives = sorted(path.glob("*.zip")) if path.is_dir() else [path]
    out: dict[str, list[dict]] = {}
    for archive in archives:
        if not zipfile.is_zipfile(archive):
            raise ValueError("expected KuCoin's BillingHistory ZIP")
        zip_check(archive)
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                if not info.filename.lower().endswith(".csv"):
                    continue
                data = z.read(info)
                try:
                    text = data.decode("utf-8-sig")
                except UnicodeDecodeError:
                    text = data.decode("cp1252", errors="replace")
                rows = [r for r in csv.DictReader(io.StringIO(text)) if any(r.values())]
                out.setdefault(info.filename.rsplit("/", 1)[-1], []).extend(rows)
    return out


def _pick(files, starts: str = "", contains: str = "", without: str = "") -> list[dict]:
    rows: list[dict] = []
    for name, content in files.items():
        if starts and not name.startswith(starts):
            continue
        if contains and contains not in name:
            continue
        if without and without in name:
            continue
        rows += content
    return rows


def _tz_column(rows: list[dict], contains: str = "") -> tuple[str, timezone]:
    if not rows:
        return "", UTC
    hits = [c for c in rows[0] if c and TZ.search(c) and (not contains or contains in c)]
    if not hits:
        raise ValueError(f"no time column with time zone (looked for {contains or 'any'})")
    sign, hh, mm = TZ.search(hits[0]).groups()
    delta = timedelta(hours=int(hh), minutes=int(mm or 0))
    return hits[0], timezone(-delta if sign == "-" else delta)


def _time(raw: str, tz: timezone, where: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime((raw or "").strip(), fmt).replace(tzinfo=tz)
        except ValueError:
            continue
    raise ValueError(f"{where}: unreadable time {raw!r}")


def _raw(r: dict) -> dict:
    return {k: v for k, v in r.items() if k and v and k != "UID"}


def skipped(path: Path, options: dict | None = None) -> dict[str, int]:
    used = (
        "Einzahlungsverlauf",
        "Auszahlungsprotokoll",
        "Fiat-W",
        "Spot-Orders",
        "Konvertierte",
        "Kontoverlauf_Handelskonto",
        "Kontoverlauf_Finanzierungskonto",
        "Realisierte",
    )
    return {n: len(r) for n, r in _files(path).items() if r and not any(u in n for u in used)}


def read(path: Path, options: dict | None = None) -> Iterator[Movement]:
    files = _files(path)
    yield from _deposits(files)
    yield from _withdrawals(files)
    yield from _fiat(files)
    yield from _trades(files)
    yield from _converts(files)
    yield from _history_only(files)
    yield from _futures(files)
    yield from _futures_transfers(files)


def _deposits(files) -> Iterator[Movement]:
    rows = _pick(files, contains="Einzahlungsverlauf")
    col, tz = _tz_column(rows)
    for r in rows:
        if (r.get("Status") or "").strip().upper() not in SUCCESS:
            continue
        asset, fee = (r.get("Coin") or "").strip().upper(), _num(r.get("Fee"), "deposit")
        yield Movement(
            timestamp=_time(r.get(col, ""), tz, "deposit"),
            kind=Kind.FIAT_DEPOSIT if asset in FIAT else Kind.RECEIVE,
            incoming_asset=asset,
            incoming_amount=_num(r.get("Amount"), "deposit"),
            fee_asset=asset if fee else None,
            fee_amount=fee or None,
            comment=(r.get("Remarks") or "").strip() or None,
            raw=_raw(r),
        )


def _withdrawals(files) -> Iterator[Movement]:
    rows = _pick(files, contains="Auszahlungsprotokoll")
    col, tz = _tz_column(rows)
    for r in rows:
        if (r.get("Status") or "").strip().upper() not in SUCCESS:
            continue
        asset, fee = (r.get("Coin") or "").strip().upper(), _num(r.get("Fee"), "withdrawal")
        yield Movement(
            timestamp=_time(r.get(col, ""), tz, "withdrawal"),
            kind=Kind.FIAT_WITHDRAWAL if asset in FIAT else Kind.SEND,
            outgoing_asset=asset,
            outgoing_amount=_num(r.get("Amount"), "withdrawal"),
            fee_asset=asset if fee else None,
            fee_amount=fee or None,
            counterparty=(r.get("Withdrawal Address/Account") or "").strip() or None,
            raw=_raw(r),
        )


def _fiat(files) -> Iterator[Movement]:
    rows = _pick(files, starts="Fiat-W", without="auszahlungen")
    if not rows:
        return
    col, tz = _tz_column(rows)
    for r in rows:
        if (r.get("Status") or "").strip().upper() not in SUCCESS:
            continue  # CANCELLED never flowed
        asset, fee = (r.get("Currency (Fiat)") or "").strip().upper(), _num(r.get("Fee"), "fiat")
        yield Movement(
            timestamp=_time(r.get(col, ""), tz, "fiat"),
            kind=Kind.FIAT_DEPOSIT,
            incoming_asset=asset,
            incoming_amount=_num(r.get("Fiat Amount"), "fiat"),
            fee_asset=asset if fee else None,
            fee_amount=fee or None,
            external_id=(r.get("Order ID") or "").strip() or None,
            comment=(r.get("Deposit Method") or "").strip() or None,
            raw=_raw(r),
        )


def _trades(files) -> Iterator[Movement]:
    rows = _pick(files, starts="Spot-Orders", without="Splitting")
    col, tz = _tz_column(rows, contains="Filled")
    for r in rows:
        qty, volume = _num(r.get("Filled Amount"), "trade"), _num(r.get("Filled Volume"), "trade")
        if not qty:
            continue  # cancelled or unfilled
        pair = (r.get("Symbol") or "").strip().upper()
        if "-" not in pair:
            raise ValueError(f"pair {pair!r} without separator")
        base, quote = pair.split("-", 1)
        buy = (r.get("Side") or "").strip().upper() == "BUY"
        fee = _num(r.get("Fee"), "trade")
        yield Movement(
            timestamp=_time(r.get(col, ""), tz, "trade"),
            kind=Kind.TRADE,
            incoming_asset=base if buy else quote,
            incoming_amount=qty if buy else volume,
            outgoing_asset=quote if buy else base,
            outgoing_amount=volume if buy else qty,
            fee_asset=((r.get("Fee Currency") or "").strip().upper() or None) if fee else None,
            fee_amount=fee or None,
            external_id=(r.get("Order ID") or "").strip() or None,
            raw=_raw(r),
        )


def _converts(files) -> Iterator[Movement]:
    rows = _pick(files, starts="Konvertierte")
    if not rows:
        return
    col, tz = _tz_column(rows)
    for r in rows:
        if (r.get("Status") or "").strip().upper() not in SUCCESS:
            continue
        sell, buy = AMOUNT_ASSET.match(r.get("Sell") or ""), AMOUNT_ASSET.match(r.get("Buy") or "")
        if not sell or not buy:
            raise ValueError(f"conversion unreadable: {r.get('Sell')!r} / {r.get('Buy')!r}")
        yield Movement(
            timestamp=_time(r.get(col, ""), tz, "convert"),
            kind=Kind.TRADE,
            outgoing_asset=sell.group(2),
            outgoing_amount=_num(sell.group(1), "convert"),
            incoming_asset=buy.group(2),
            incoming_amount=_num(buy.group(1), "convert"),
            comment=(r.get("Price") or "").strip() or None,
            raw=_raw(r),
        )


def _history_only(files) -> Iterator[Movement]:
    rows = _pick(files, starts="Kontoverlauf")
    if not rows:
        return
    col, tz = _tz_column(rows)
    seen: set[tuple] = set()
    for r in rows:
        typ = (r.get("Type") or "").strip()
        if typ in COVERED:
            continue
        if typ not in HISTORY_ONLY:
            raise ValueError(f"unknown booking type in account history: {typ!r}")
        asset, amount = (r.get("Currency") or "").strip().upper(), _num(r.get("Amount"), typ)
        when = _time(r.get(col, ""), tz, typ)
        if (when, asset, amount, typ) in seen:
            continue  # the same event in two account histories
        seen.add((when, asset, amount, typ))
        if (r.get("Side") or "").strip().lower() != "deposit":
            raise ValueError(f"{typ} booked as outflow ({r.get('Side')!r}) - not seen before")
        yield Movement(
            timestamp=when,
            kind=Kind.INCOME,
            income_kind=HISTORY_ONLY[typ],
            incoming_asset=asset,
            incoming_amount=amount,
            comment=typ,
            raw=_raw(r),
        )


def _futures(files) -> Iterator[Movement]:
    rows = _pick(files, contains="Realisierte")
    for r in rows:
        closing = next((k for k in r if k and "Closing Time" in k), None)
        if closing is None:
            raise ValueError("futures result without closing time column")
        tz = _tz_column([r], contains="Closing")[1]
        when = _time(r.get(closing, ""), tz, "futures")
        pnl = _num(r.get("Realized PNL"), "futures")
        symbol = (r.get("Symbol") or "").strip()
        coin = (
            "USDT" if symbol.endswith("USDTM") else "USDC" if symbol.endswith("USDCM") else "USDT"
        )
        sides = (
            {"incoming_asset": coin, "incoming_amount": pnl}
            if pnl >= 0
            else {"outgoing_asset": coin, "outgoing_amount": -pnl}
        )
        # Realized PNL already contains funding and trading fees (see module doc).
        yield Movement(
            timestamp=when,
            kind=Kind.REALIZED_PNL,
            market=Market.FUTURES,
            instrument=symbol,
            comment=r.get("Close Type"),
            raw=_raw(r),
            **sides,
        )
        yield Movement(
            timestamp=when,
            kind=Kind.FUTURES_POSITION,
            market=Market.FUTURES,
            instrument=symbol,
            comment=r.get("Close Type"),
            raw=_raw(r),
        )


TWIN_SECONDS = 120
"""The two halves of a move between funding and trading account: the same second, seen
up to a minute apart when one side waits (2024-03-21: 19:55:35 both)."""


def _futures_transfers(files) -> Iterator[Movement]:
    rows = []
    for name, content in files.items():
        if not name.startswith("Kontoverlauf") or not content:
            continue
        col, tz = _tz_column(content)
        for r in content:
            if (r.get("Type") or "").strip() != "Transfer":
                continue
            rows.append(
                (
                    name,
                    _time(r.get(col, ""), tz, "transfer"),
                    (r.get("Currency") or "").strip().upper(),
                    _num(r.get("Amount"), "transfer"),
                    (r.get("Side") or "").strip().lower(),
                    r,
                )
            )
    for name, when, coin, amount, side, r in rows:
        if "Handelskonto" not in name and "Finanzierungskonto" not in name:
            continue  # margin accounts: their own moves, not booked here
        twin = any(
            n != name
            and c == coin
            and a == amount
            and sd != side
            and abs((w - when).total_seconds()) <= TWIN_SECONDS
            for n, w, c, a, sd, _ in rows
        )
        if twin:
            continue  # between funding and trading: both are spot here
        if "margin" in (r.get("Remark") or "").lower():
            raise ValueError(f"transfer to margin on {when} - margin is not supported yet")
        out = side == "withdrawal"
        comment = "SPOT -> FUTURES" if out else "FUTURES -> SPOT"
        for market, leaves in ((Market.SPOT, out), (Market.FUTURES, not out)):
            yield Movement(
                timestamp=when,
                kind=Kind.INTERNAL_TRANSFER,
                market=market,
                comment=comment,
                raw=_raw(r),
                **(
                    {"outgoing_asset": coin, "outgoing_amount": amount}
                    if leaves
                    else {"incoming_asset": coin, "incoming_amount": amount}
                ),
            )
