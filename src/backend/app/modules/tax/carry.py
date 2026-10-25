"""Loss carry of § 23 EStG (ADR 0045): a year's loss goes back one year, the rest forward
without end. Only years whose gain reaches the limit use it — a gain below the limit is
tax-free anyway and does not eat the carry. What the tax office fixed (Feststellungsbescheid)
wins over the computed carry.

This is a proposal to check with the tax adviser, not the office's decision."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.tax.lots import ZERO, local_day
from app.modules.tax.models import TaxLossAssessed


def assessed(session: Session) -> dict[int, tuple[Decimal, str | None]]:
    return {r.year: (r.amount, r.note) for r in session.scalars(select(TaxLossAssessed))}


def set_assessed(session: Session, year: int, amount: Decimal | None, note: str | None) -> None:
    """The office's figure for the end of `year`; None removes it."""
    if amount is not None and amount < 0:
        raise AppError("tax.carry_negative", 400)
    row = session.get(TaxLossAssessed, year)
    if amount is None:
        if row is not None:
            session.delete(row)
    elif row is None:
        session.add(TaxLossAssessed(year=year, amount=amount, note=(note or "").strip() or None))
    else:
        row.amount, row.note = amount, (note or "").strip() or None
    session.commit()


def nets(disposals) -> dict[int, Decimal]:
    """The § 23 balance per year: gains and losses within the holding period."""
    out: dict[int, Decimal] = {}
    for d in disposals:
        if d.tax_free or d.gain is None:
            continue
        y = local_day(d.sold).year
        out[y] = out.get(y, ZERO) + d.gain
    return out


def rows(
    net_by_year: dict[int, Decimal],
    fixed: dict[int, tuple[Decimal, str | None]],
    limit,
    until: int | None = None,
) -> list[dict]:
    """One row per year from the first one with data (or after the first fixed figure) to
    `until` (this year). Amounts are Decimals, losses and carries positive."""
    until = until or local_day(datetime.now(UTC)).year
    years = set(net_by_year) | {y + 1 for y in fixed}
    if not years:
        return []
    first = min(years)
    carry = fixed[first - 1][0] if first - 1 in fixed else ZERO
    out: list[dict] = []
    for y in range(first, until + 1):
        net = net_by_year.get(y, ZERO)
        lim = limit(y)
        taxable = net >= lim
        used = min(carry, net) if taxable else ZERO
        row = {
            "year": y,
            "net": net,
            "limit": lim,
            "taxable": taxable,
            "start": carry,
            "used": used,
            "back_in": ZERO,
            "back_out": ZERO,
            "loss": ZERO,
            "remaining": net - used if taxable else ZERO,
            "end": ZERO,
            "assessed": None,
            "note": None,
            "diff": None,
            "running": y == until,
        }
        carry -= used
        if net < 0:
            loss = -net
            prev = out[-1] if out else None
            # back one year, only into a gain that is taxed there
            if prev and prev["taxable"] and prev["remaining"] > 0:
                back = min(loss, prev["remaining"])
                prev["remaining"] -= back
                prev["back_in"] = back
                row["back_out"] = back
                loss -= back
            row["loss"] = loss
            carry += loss
        row["end"] = carry
        if y in fixed:
            amount, note = fixed[y]
            row["assessed"], row["note"], row["diff"] = amount, note, amount - carry
            carry = amount
        out.append(row)
    return out
