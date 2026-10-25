"""Coinbase — yearly transaction CSV (research 2026-08-23, 2026-09-06).

* Two preamble lines before the header (`Transactions`, `User…`); `$` in money fields.
* **The German export rounds to nine decimals** and is rejected; so are damaged
  files where the decimal point got lost (`57.145.796` for `5.7145796`).
* `Convert` appears as TWO rows with the same note "Converted 292.32 USDT to
  292.91 USDC"; the other side is only in the note. The incoming row is used,
  the outgoing one skipped — otherwise every swap counts twice.
* The sign of `Quantity Transacted` is the direction.
* **Money is in the display currency (USD), not what was paid (EUR).** The note
  ("Bought 316.16 USDC for 304.94 EUR") names the real counter currency for
  trades, fee included (no separate fee then: the fee column is USD); `Price
  Currency` says USD for every row and must not be trusted. For
  income rows the fee column is a spread, not a fee: booked as nothing.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.modules.plugins.contract import IncomeKind, Kind, Movement

HEADER = "ID,"
CONVERT = re.compile(r"Converted\s+([\d.,]+)\s+([A-Z0-9]+)\s+to\s+([\d.,]+)\s+([A-Z0-9]+)", re.I)
TRADE_NOTE = re.compile(
    r"(Bought|Sold)\s+([\d.,]+)\s+([A-Z0-9]+)\s+for\s+([\d.,]+)\s+([A-Z]{2,5})", re.I
)

KINDS: dict[str, tuple[Kind, IncomeKind | None]] = {
    "buy": (Kind.TRADE, None),
    "sell": (Kind.TRADE, None),
    "convert": (Kind.TRADE, None),
    "advance trade buy": (Kind.TRADE, None),
    "advanced trade buy": (Kind.TRADE, None),
    "advance trade sell": (Kind.TRADE, None),
    "advanced trade sell": (Kind.TRADE, None),
    "send": (Kind.SEND, None),
    "receive": (Kind.RECEIVE, None),
    "deposit": (Kind.FIAT_DEPOSIT, None),
    "withdrawal": (Kind.FIAT_WITHDRAWAL, None),
    "staking income": (Kind.INCOME, IncomeKind.STAKING),
    "reward income": (Kind.INCOME, IncomeKind.REWARD),
    "learning reward": (Kind.INCOME, IncomeKind.REWARD),
    "interest": (Kind.INCOME, IncomeKind.INTEREST),
    "inflation reward": (Kind.INCOME, IncomeKind.REWARD),
    "retail staking transfer": (Kind.INTERNAL_TRANSFER, None),
    "retail unstaking transfer": (Kind.INTERNAL_TRANSFER, None),
}


def _num(raw: str | None, field: str) -> Decimal | None:
    value = (raw or "").replace("$", "").replace(" ", " ").strip()
    if not value or value == "-":
        return None
    if value.count(".") > 1:
        raise ValueError(
            f"{field}: {value!r} has several points — the decimal point got lost "
            "(e.g. after opening in a spreadsheet). Download the English CSV again."
        )
    if "," in value and "." not in value:
        raise ValueError(
            f"{field}: {value!r} uses a decimal comma — that is the German export, "
            "which rounds to nine decimals. Use the English export."
        )
    try:
        return Decimal(value.replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"{field}: {value!r} is not a number") from exc


def _time(raw: str) -> datetime:
    return datetime.strptime(raw.strip().removesuffix(" UTC").strip(), "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=UTC
    )


def _files(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(p for p in path.iterdir() if p.suffix.lower() == ".csv")
    return [path]


def skipped(path: Path, options: dict | None = None) -> dict[str, int]:
    if not path.is_dir():
        return {}
    return {p.name: 0 for p in sorted(path.iterdir()) if p.suffix.lower() != ".csv"}


def _rows(path: Path) -> Iterator[dict[str, str]]:
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(HEADER)), None)
    if start is None:
        if any(line.startswith("ID;") for line in lines[:12]):
            raise ValueError(
                "semicolon separated export detected — the German version, which "
                "rounds to nine decimals. Use the English export."
            )
        raise ValueError("no header line starting with 'ID,' found")
    yield from (r for r in csv.DictReader(io.StringIO("\n".join(lines[start:]))) if r.get("ID"))


def _trade_sides(row: dict[str, str], asset: str, qty: Decimal | None) -> dict:
    typ = row["Transaction Type"].strip().lower()
    note = (row.get("Notes") or "").strip()
    if typ == "convert":
        m = CONVERT.search(note)
        if not m:
            raise ValueError(f"Convert without readable note: {note!r}")
        out_qty, out_asset, in_qty, in_asset = m.groups()
        return {
            "outgoing_asset": out_asset,
            "outgoing_amount": _num(out_qty, "convert out"),
            "incoming_asset": in_asset,
            "incoming_amount": _num(in_qty, "convert in"),
        }
    m = TRADE_NOTE.search(note)
    if m:
        counter, currency = _num(m.group(4), "note amount"), m.group(5).upper()
    else:
        counter = _num(row.get("Subtotal"), "Subtotal")
        currency = (row.get("Price Currency") or "USD").strip().upper()
    amount = abs(qty) if qty is not None else None
    counter = abs(counter) if counter is not None else None
    if "sell" in typ:
        return {
            "outgoing_asset": asset,
            "outgoing_amount": amount,
            "incoming_asset": currency,
            "incoming_amount": counter,
        }
    return {
        "incoming_asset": asset,
        "incoming_amount": amount,
        "outgoing_asset": currency,
        "outgoing_amount": counter,
    }


def read(path: Path, options: dict | None = None) -> Iterator[Movement]:
    for file in _files(path):
        for row in _rows(file):
            typ = row["Transaction Type"].strip()
            kind, income = KINDS.get(typ.lower(), (Kind.OTHER, None))
            asset = (row.get("Asset") or "").strip().upper()
            qty = _num(row.get("Quantity Transacted"), "Quantity Transacted")
            if typ.lower() == "convert" and qty is not None and qty < 0:
                continue  # the other half of the same swap
            if kind is Kind.TRADE:
                sides = _trade_sides(row, asset, qty)
                fee = _num(row.get("Fees and/or Spread"), "Fees and/or Spread")
                counter = sides.get("outgoing_asset")
                fee_asset = counter if counter != asset else sides.get("incoming_asset")
                if TRADE_NOTE.search((row.get("Notes") or "").strip()):
                    # the note's amount is what was paid or received, fee included, and
                    # the fee column is in USD: booked again it came off twice (2026-10-10)
                    fee, fee_asset = None, None
            else:
                out = qty is not None and qty < 0
                amount = abs(qty) if qty is not None else None
                sides = (
                    {"outgoing_asset": asset, "outgoing_amount": amount}
                    if out
                    else {"incoming_asset": asset, "incoming_amount": amount}
                )
                fee, fee_asset = None, None  # a spread on rewards is no fee
            fee = abs(fee) if fee else None
            address = (row.get("Recipient Address") or row.get("Sender Address") or "").strip()
            yield Movement(
                timestamp=_time(row["Timestamp"]),
                kind=kind,
                income_kind=income,
                fee_asset=fee_asset if fee else None,
                fee_amount=fee,
                external_id=row["ID"].strip(),
                comment=(row.get("Notes") or "").strip() or None,
                counterparty=address or None,
                raw={k: v for k, v in row.items() if k and v},
                **sides,
            )
