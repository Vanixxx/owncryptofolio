"""The tax report of one year (ADR 0042): the pass of `engine` cut to the year, summed per
pot (§ 23, § 22, § 20), with the limits and everything that is not counted listed apart.

The pass always runs over the whole history: the lots of a sale in 2025 come from 2021.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.merged import service as merged
from app.modules.portfolio.service import _cached
from app.modules.prices.service import Valuer
from app.modules.settings import service as settings
from app.modules.sources.models import Source, Wallet
from app.modules.tax import carry
from app.modules.tax.engine import Engine, Params, Result
from app.modules.tax.lots import ZERO, Method, local_day, one_year_after
from app.modules.tax.models import TaxReport

LIMIT_22 = Decimal(256)
"""§ 22 Nr. 3 EStG: income below it stays untaxed — its own pot, never netted with § 23."""


def limit_23(year: int) -> Decimal:
    """§ 23 Abs. 3 EStG: 600 € up to 2023, 1,000 € from 2024. A limit, not an allowance: from
    it on the WHOLE gain is taxable."""
    return Decimal(1000 if year >= 2024 else 600)


def params(session: Session, method: str | None = None) -> Params:
    s = settings.all_settings(session)
    return Params(
        method=Method(method or s["tax.method"]), airdrop_taxable=s["tax.airdrop_taxable"]
    )


def compute(session: Session, p: Params) -> Result:
    def make():
        return Engine(merged.build(session), Valuer(session), p).run()

    return _cached(session, f"tax-{p.method}-{p.airdrop_taxable}", make)


def _n(v: Decimal | None) -> str | None:
    """Plain decimal string: JSON knows only floats."""
    if v is None:
        return None
    v = v.quantize(Decimal("0.00000001")) if abs(v) < 10**20 else v
    text = f"{v.normalize():f}"
    return "0" if text in ("-0", "") else text


def _eur(v: Decimal | None) -> str | None:
    # half a cent rounds up, as in German commercial practice (review 2026-10-24)
    return None if v is None else f"{v.quantize(Decimal('0.01'), ROUND_HALF_UP):f}"


def _t(at: datetime) -> str:
    return at.isoformat()


def place_names(session: Session) -> dict[int, str]:
    wallets = dict(session.execute(select(Wallet.id, Wallet.name)).all())
    out = {}
    for s in session.scalars(select(Source)):
        out[s.id] = f"{wallets[s.wallet_id]} · {s.label}" if s.wallet_id in wallets else s.label
    return out


def years(session: Session) -> list[int]:
    res = compute(session, params(session))
    seen = {local_day(d.sold).year for d in res.disposals}
    seen |= {local_day(i.at).year for i in res.incomes}
    seen |= {local_day(f.at).year for f in res.futures}
    seen |= {local_day(x.at).year for x in res.losses}
    # a year with only sales without a recorded purchase must show, to point at the fix
    seen |= {local_day(u.at).year for u in res.uncovered + res.open_sends}
    return sorted(seen, reverse=True)


FORM_LINES = {2024: {"so23": 54, "so22": 11, "kap19": 19, "kap21": 21, "kap24": 24}}
"""Lines of the official forms per year, as the 2024 forms number them. Other
years: the form is named, the line has to be looked up (they move between years)."""


def forms(year: int, s23: Decimal, s22: Decimal, kap_gains: Decimal, kap_losses: Decimal) -> list:
    """Where each sum goes in the tax return (Blockpit check 2024, Vanixxx 2026-10-13)."""
    n = FORM_LINES.get(year, {})
    return [
        {"form": "SO", "line": n.get("so23"), "key": "s23", "value": _eur(s23)},
        {"form": "SO", "line": n.get("so22"), "key": "s22", "value": _eur(s22)},
        {"form": "KAP", "line": n.get("kap19"), "key": "kap19", "value": _eur(kap_gains)},
        {"form": "KAP", "line": n.get("kap21"), "key": "kap21", "value": _eur(kap_gains)},
        {"form": "KAP", "line": n.get("kap24"), "key": "kap24", "value": _eur(kap_losses)},
    ]


def by_source(disposals, name) -> list[dict]:
    """Gains and losses per exchange or wallet, taxable and tax-free apart."""
    out: dict[int, list[Decimal]] = {}
    for d in disposals:
        e = out.setdefault(d.source, [ZERO] * 4)
        g = d.gain or ZERO
        e[(2 if d.tax_free else 0) + (0 if g >= 0 else 1)] += g
    return [
        {
            "place": name(src),
            "gains": _eur(e[0]),
            "losses": _eur(e[1]),
            "net": _eur(e[0] + e[1]),
            "free_gains": _eur(e[2]),
            "free_losses": _eur(e[3]),
            "free_net": _eur(e[2] + e[3]),
        }
        for src, e in sorted(out.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))
    ]


def _flows(session: Session) -> dict:
    """Every movement as (source, coin, year) → (in, out): the holding changes of a year.
    Spam stays out, closed futures positions move nothing. Money paid by card counts as
    paid in at its row (the portfolio's automatic card deposits): else euro at Bitget ran
    thousands below zero."""

    def make():
        from app.modules.portfolio.service import auto_deposits

        view = merged.build(session)
        card = auto_deposits(session)
        out: dict[tuple[int, str, int], list[Decimal]] = {}
        for r in view.rows.values():
            if view.is_spam(r) or r.kind == "futures_position":
                continue
            y = local_day(r.timestamp).year
            if r.id in card:
                fiat, qty = card[r.id]
                e = out.setdefault((r.source_id, fiat, y), [ZERO, ZERO])
                e[0] += qty
            for asset, qty, side in (
                (r.incoming_asset, r.incoming_amount, 0),
                (r.outgoing_asset, r.outgoing_amount, 1),
                (r.fee_asset, r.fee_amount, 1),
            ):
                if asset and qty:
                    e = out.setdefault((r.source_id, view.asset(asset), y), [ZERO, ZERO])
                    e[side] += qty
        return out

    return _cached(session, "tax-flows", make)


def holding_changes(session: Session, year: int, name) -> list[dict]:
    """Per exchange or wallet and coin: holding on 1 January, in, out, holding on 31 December
    and its value then — Blockpit's "Bestände und Bestandsveränderungen"."""
    flows = _flows(session)
    valuer = _cached(session, "tax-valuer", lambda: Valuer(session))
    end = date(year, 12, 31)
    acc: dict[tuple[int, str], list[Decimal]] = {}
    for (src, asset, y), (i, o) in flows.items():
        if y > year:
            continue
        e = acc.setdefault((src, asset), [ZERO, ZERO, ZERO])
        if y < year:
            e[0] += i - o
        else:
            e[1] += i
            e[2] += o
    out = []
    for (src, asset), (start, i, o) in sorted(
        acc.items(), key=lambda kv: (names_key(name, kv[0][0]), kv[0][1])
    ):
        stop = start + i - o
        if abs(start) < DUST_QTY and not i and not o:
            continue
        price = valuer.eur(asset, end)
        out.append(
            {
                "place": name(src),
                "asset": asset,
                "start": _n(start),
                "in": _n(i),
                "out": _n(o),
                "end": _n(stop),
                "value": None if price is None else _eur(stop * price),
            }
        )
    return out


DUST_QTY = Decimal("0.00000001")


def names_key(name, src: int) -> str:
    return name(src) or ""


def year_report(session: Session, year: int, method: str | None = None) -> dict:
    p = params(session, method)
    res = compute(session, p)
    names = place_names(session)

    def name(source: int) -> str | None:
        return names.get(source)  # 0 = outside: the UI names it

    def inside(at: datetime) -> bool:
        return local_day(at).year == year

    disposals = [d for d in res.disposals if inside(d.sold)]
    incomes = [i for i in res.incomes if inside(i.at)]
    futures = [f for f in res.futures if inside(f.at)]
    losses = [x for x in res.losses if inside(x.at)]
    uncovered = [u for u in res.uncovered if inside(u.at)]
    open_sends = [u for u in res.open_sends if inside(u.at)]

    taxed = [d for d in disposals if not d.tax_free]
    gains = sum((d.gain for d in taxed if d.gain is not None and d.gain > 0), ZERO)
    minus = sum((d.gain for d in taxed if d.gain is not None and d.gain < 0), ZERO)
    net = gains + minus
    lim23 = limit_23(year)
    income = sum((i.value or ZERO for i in incomes), ZERO)

    def flows(kind: str, sign: int) -> Decimal:
        return sum(
            (
                f.value
                for f in futures
                if f.kind == kind
                and f.value is not None
                and (f.value > 0 if sign > 0 else f.value < 0)
            ),
            ZERO,
        )

    s20 = {
        "gains": flows("pnl", 1),
        "losses": flows("pnl", -1),
        "funding_in": flows("funding", 1),
        "funding_out": flows("funding", -1),
        "fees": flows("fee", -1),
        "bonus": flows("bonus", 1) + flows("bonus", -1),
    }
    s20["net"] = sum(s20.values(), ZERO)
    # Anlage KAP keeps gains and losses of derivatives apart (lines 21 and 24): funding and
    # a used bonus side with the gains, paid funding and fees with the losses
    kap_gains = s20["gains"] + s20["funding_in"] + max(s20["bonus"], ZERO)
    kap_losses = -(s20["losses"] + s20["funding_out"] + s20["fees"] + min(s20["bonus"], ZERO))
    by_kind: dict[str, Decimal] = {}
    for i in incomes:
        by_kind[i.kind] = by_kind.get(i.kind, ZERO) + (i.value or ZERO)

    cfg = settings.all_settings(session)
    summary = {
        "year": year,
        "method": p.method.value,
        # who the report is for; kept reports keep the head they were made with
        "holder": {k: cfg[f"report.{k}"].strip() for k in ("name", "address", "tax_number")},
        "airdrop_taxable": p.airdrop_taxable,
        "s23": {
            "gains": _eur(gains),
            "losses": _eur(minus),
            "net": _eur(net),
            "limit": _eur(lim23),
            "taxable": net >= lim23,
            "share": _eur(max(net, ZERO) / lim23 * 100),
            "tax_free_gain": _eur(
                sum((d.gain for d in disposals if d.tax_free and d.gain is not None), ZERO)
            ),
            "count": len(disposals),
            "count_taxed": len(taxed),
            "estimated": sum(1 for d in taxed if d.estimated),
            "unvalued": sum(1 for d in disposals if d.gain is None),
        },
        "s22": {
            "total": _eur(income),
            "limit": _eur(LIMIT_22),
            "taxable": income >= LIMIT_22,
            "share": _eur(income / LIMIT_22 * 100),
            "count": len(incomes),
            "unvalued": sum(1 for i in incomes if i.value is None),
            "by_kind": {k: _eur(v) for k, v in sorted(by_kind.items())},
        },
        "s20": {k: _eur(v) for k, v in s20.items()}
        | {"count": len(futures), "kap_gains": _eur(kap_gains), "kap_losses": _eur(kap_losses)},
        "lost": {
            "cost": _eur(sum((x.cost or ZERO for x in losses), ZERO)),
            "count": len(losses),
            "unknown_cost": sum(1 for x in losses if x.cost is None),
        },
        "forms": forms(year, net, income if income >= LIMIT_22 else ZERO, kap_gains, kap_losses),
        "carry": carry_summary(session, res, year),
        "open": {
            "uncovered": len(uncovered),
            "open_sends": len(open_sends),
            "unvalued_assets": sorted(res.unvalued),
        },
    }
    lines = {
        "by_source": by_source(disposals, name),
        "holdings": holding_changes(session, year, name),
        "disposals": [_disposal(d, name) for d in disposals],
        "incomes": [_income(i, name) for i in incomes],
        "futures": [_flow(f, name) for f in futures],
        "losses": [_loss(x, name) for x in losses],
        "uncovered": [_uncovered(u, name) for u in uncovered + open_sends],
        "year_end": [
            _lot(lot, name(place[0]), place[1])
            for place, lot in sorted(
                res.year_end.get(year, []), key=lambda pl: (pl[1].asset, pl[1].acquired)
            )
        ],
    }
    digest = fingerprint(summary, lines)
    return {"summary": summary, "lines": lines, "digest": digest}


def carry_summary(session: Session, res: Result, year: int) -> dict:
    """The loss carry of § 23 for all years, and the row of this one (ADR 0045)."""
    rows = [
        {k: (_eur(v) if isinstance(v, Decimal) else v) for k, v in r.items()}
        for r in carry.rows(carry.nets(res.disposals), carry.assessed(session), limit_23)
    ]
    fixed = carry.assessed(session)
    first = rows[0]["year"] - 1 if rows else None
    opening = (
        {"year": first, "amount": _eur(fixed[first][0]), "note": fixed[first][1]}
        if first in fixed
        else None
    )
    return {
        "year": next((r for r in rows if r["year"] == year), None),
        "rows": rows,
        "opening": opening,
    }


def _disposal(d, name) -> dict:
    return {
        "asset": d.asset,
        "place": name(d.source),
        "sold": _t(d.sold),
        "acquired": _t(d.acquired),
        "days": d.days,
        "qty": _n(d.qty),
        "proceeds": _eur(d.proceeds),
        "cost": _eur(d.cost),
        "gain": _eur(d.gain),
        "tax_free": d.tax_free,
        "estimated": d.estimated,
        "how": d.how,
        "row": d.row,
        "origin": d.origin,
    }


def _income(i, name) -> dict:
    return {
        "asset": i.asset,
        "place": name(i.source),
        "at": _t(i.at),
        "qty": _n(i.qty),
        "value": _eur(i.value),
        "kind": i.kind,
        "row": i.row,
    }


def _flow(f, name) -> dict:
    return {
        "place": name(f.source),
        "at": _t(f.at),
        "kind": f.kind,
        "asset": f.asset,
        "amount": _n(f.amount),
        "value": _eur(f.value),
        "row": f.row,
    }


def _loss(x, name) -> dict:
    return {
        "asset": x.asset,
        "place": name(x.source),
        "at": _t(x.at),
        "acquired": _t(x.acquired) if x.acquired else None,
        "qty": _n(x.qty),
        "cost": _eur(x.cost),
        "row": x.row,
        "origin": x.origin,
    }


def _uncovered(u, name) -> dict:
    return {
        "asset": u.asset,
        "place": name(u.source),
        "at": _t(u.at),
        "qty": _n(u.qty),
        "proceeds": _eur(u.proceeds),
        "reason": u.reason,
        "row": u.row,
    }


def _lot(lot, place: str | None, market: str | None = None) -> dict:
    return {
        "asset": lot.asset,
        "place": place,
        "market": market,
        "qty": _n(lot.qty),
        "acquired": _t(lot.acquired),
        "cost": _eur(lot.cost),
        "free_from": one_year_after(local_day(lot.acquired)).isoformat(),
        "estimated": lot.estimated,
        "origin": lot.origin,
    }


def row_report(session: Session, ids: list[int]) -> dict:
    """What one transaction means for the tax (ADR 0042, Vanixxx 2026-10-13): what it sold
    and from which purchases, what it started and what became of that, what it carried.
    A transfer passes its send, receive and attached fees together."""
    p = params(session)
    res = compute(session, p)
    names = place_names(session)
    name = names.get
    want = set(ids)
    open_lots = [(pl, lot) for pl, lot in res.lots.open() if lot.origin in want]
    return {
        "method": p.method.value,
        "sold": [_disposal(d, name) for d in res.disposals if d.row in want],
        "incomes": [_income(i, name) for i in res.incomes if i.row in want],
        "futures": [_flow(f, name) for f in res.futures if f.row in want],
        "losses": [_loss(x, name) for x in res.losses if x.row in want],
        "uncovered": [_uncovered(u, name) for u in res.uncovered + res.open_sends if u.row in want],
        "created": [_lot(lot, None) for i in ids for lot in res.created.get(i, [])],
        "moved": [
            {
                "asset": m.asset,
                "qty": _n(m.qty),
                "acquired": _t(m.acquired),
                "cost": _eur(m.cost),
                "origin": m.origin,
                "free_from": one_year_after(local_day(m.acquired)).isoformat(),
            }
            for i in ids
            for m in res.moved.get(i, [])
        ],
        "later": {
            "sold": [_disposal(d, name) for d in res.disposals if d.origin in want],
            "losses": [_loss(x, name) for x in res.losses if x.origin in want],
            "open": [_lot(lot, name(pl[0]), pl[1]) for pl, lot in open_lots],
        },
    }


def frozen(session: Session, year: int) -> list[dict]:
    """Reports kept for the year, newest first, each checked against a fresh pass with ITS
    method — a correction in an earlier year changes the lots and shows here too."""
    out = []
    for r in session.scalars(
        select(TaxReport).where(TaxReport.year == year).order_by(TaxReport.created_at.desc())
    ):
        now = year_report(session, year, r.method)["digest"]
        out.append(
            {
                "id": r.id,
                "created_at": r.created_at.isoformat(),
                "method": r.method,
                "same": now == r.digest,
                "note": r.note,
                "summary": r.summary,
            }
        )
    return out


def freeze(session: Session, year: int, method: str | None = None, note: str | None = None) -> dict:
    rep = year_report(session, year, method)
    row = TaxReport(
        year=year,
        method=rep["summary"]["method"],
        digest=rep["digest"],
        summary=rep["summary"],
        lines=rep["lines"],
        note=(note or "").strip()[:200] or None,
    )
    session.add(row)
    session.flush()
    _files(row, rep)
    session.commit()
    return {"id": row.id}


def _files(row: TaxReport, rep: dict) -> None:
    from app.modules.tax import files

    made = row.created_at or datetime.now().astimezone()
    row.xlsx, row.pdf = files.xlsx(rep), files.pdf(rep, made)


def kept_note(session: Session, report_id: int, note: str | None) -> dict:
    """A comment on a kept version, changed later (Vanixxx, 2026-10-13)."""
    row = session.get(TaxReport, report_id)
    if row is None:
        raise AppError("tax.report_not_found", 404)
    row.note = (note or "").strip()[:200] or None
    session.commit()
    return {"id": row.id, "note": row.note}


def kept_delete(session: Session, report_id: int) -> None:
    """A kept version Vanixxx no longer wants (a test, a draft). Only the kept copy goes; the
    transactions are not touched."""
    row = session.get(TaxReport, report_id)
    if row is None:
        raise AppError("tax.report_not_found", 404)
    session.delete(row)
    session.commit()


def kept_file(session: Session, report_id: int, kind: str) -> tuple[bytes, str]:
    """A kept report's file as it was made. Reports kept before files were stored get
    theirs from their kept lines, once, dated with the day they were kept."""
    row = session.get(TaxReport, report_id)
    if row is None:
        raise AppError("tax.report_not_found", 404)
    if getattr(row, kind) is None:
        if row.lines is None:
            raise AppError("tax.no_lines", 409)
        _files(row, {"summary": row.summary, "lines": row.lines})
        session.commit()
    name = f"steuer-{row.year}-{row.method}-festgehalten-{row.created_at:%Y%m%d-%H%M%S}.{kind}"
    return getattr(row, kind), name


FIGURES = (
    ("s23", "gains"),
    ("s23", "losses"),
    ("s23", "net"),
    ("s23", "tax_free_gain"),
    ("s22", "total"),
    ("s20", "gains"),
    ("s20", "losses"),
    ("s20", "funding_in"),
    ("s20", "funding_out"),
    ("s20", "fees"),
    ("s20", "net"),
    ("lost", "cost"),
)
AMOUNT = {
    "disposals": "gain",
    "incomes": "value",
    "futures": "value",
    "losses": "cost",
    "uncovered": "proceeds",
    "year_end": "cost",
}


def _d(v) -> Decimal | None:
    return None if v is None else Decimal(v)


def _by_key(cat: str, lines: list[dict]) -> dict:
    """One entry per transaction (per coin for the year-end holding): a sale over three
    lots is one change, not three."""
    out: dict = {}
    for x in lines:
        key = x["asset"] if cat == "year_end" else x["row"]
        e = out.setdefault(
            key,
            {
                "asset": x["asset"],
                "at": x.get("sold") or x.get("at"),
                "row": x.get("row"),
                "qty": ZERO,
                "amount": ZERO,
            },
        )
        e["qty"] += _d(x.get("qty") or x.get("amount")) or ZERO
        a = _d(x.get(AMOUNT[cat]))
        e["amount"] = None if a is None or e["amount"] is None else e["amount"] + a
    return out


def fingerprint(summary: dict, lines: dict) -> str:
    """sha256 over what counts for the tax: the key figures and, per transaction, quantity
    and amount — exactly what `compare` shows. Not over the shape of the lines: a new field
    in a later version of the app must not mark every kept report as changed (two kept
    reports of 2026-10-13 did exactly that)."""
    body = {
        "method": summary["method"],
        "figures": [summary[pot][key] for pot, key in FIGURES],
        "lines": {
            cat: sorted(
                (str(k), _n(v["qty"]), _eur(v["amount"]))
                for k, v in _by_key(cat, lines[cat]).items()
            )
            for cat in AMOUNT
        },
    }
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def compare(session: Session, year: int, a: int, b: int | None) -> dict:
    """A kept report against now (b=None) or against another kept report: the key figures
    side by side and every transaction whose lines differ (Vanixxx, 2026-10-13)."""
    old = session.get(TaxReport, a)
    if old is None or old.year != year:
        raise AppError("tax.report_not_found", 404)
    if b is None:
        rep = year_report(session, year, old.method)
        new_summary, new_lines, label = rep["summary"], rep["lines"], None
    else:
        other = session.get(TaxReport, b)
        if other is None or other.year != year:
            raise AppError("tax.report_not_found", 404)
        new_summary, new_lines, label = other.summary, other.lines, other.created_at.isoformat()

    figures = []
    for pot, key in FIGURES:
        o, n = _d(old.summary[pot][key]), _d(new_summary[pot][key])
        figures.append(
            {
                "pot": pot,
                "key": key,
                "old": _eur(o),
                "new": _eur(n),
                "delta": _eur(None if o is None or n is None else n - o),
            }
        )
    changes = []
    if old.lines is not None and new_lines is not None:
        for cat in AMOUNT:
            before, after = _by_key(cat, old.lines[cat]), _by_key(cat, new_lines[cat])
            for key in sorted(set(before) | set(after), key=str):
                o, n = before.get(key), after.get(key)
                if o and n and (o["qty"], o["amount"]) == (n["qty"], n["amount"]):
                    continue
                ref = n or o
                changes.append(
                    {
                        "cat": cat,
                        "state": "added" if o is None else "removed" if n is None else "changed",
                        "asset": ref["asset"],
                        "at": ref["at"],
                        "row": ref["row"],
                        "old": None
                        if o is None
                        else {"qty": _n(o["qty"]), "amount": _eur(o["amount"])},
                        "new": None
                        if n is None
                        else {"qty": _n(n["qty"]), "amount": _eur(n["amount"])},
                    }
                )
    return {
        "old": {
            "id": old.id,
            "created_at": old.created_at.isoformat(),
            "method": old.method,
            "note": old.note,
        },
        "new": label,
        "figures": figures,
        "changes": changes,
        "lines_known": old.lines is not None and new_lines is not None,
    }


LIMIT_WARN = Decimal(80)
"""From this share of a limit on, the app says so (ADR 0044)."""


def limits(session: Session) -> dict:
    """How far this year's § 23 balance and § 22 income use their limits (ADR 0044)."""
    year = local_day(datetime.now().astimezone()).year
    s = year_report(session, year)["summary"]
    out = {"year": year}
    for pot, value in (("s23", s["s23"]["net"]), ("s22", s["s22"]["total"])):
        share = Decimal(s[pot]["share"])
        out[pot] = {
            "value": value,
            "limit": s[pot]["limit"],
            "share": s[pot]["share"],
            "level": "over" if s[pot]["taxable"] else "near" if share >= LIMIT_WARN else "ok",
        }
    return out


def upcoming(session: Session, days: int = 30) -> list[dict]:
    """What turns tax-free in the next `days` (ADR 0043): per coin and day the quantity, its
    value now and the gain that would then be free, in the display currency."""
    res = compute(session, params(session))
    currency = settings.all_settings(session)["general.currency"]
    valuer = _cached(session, "valuer", lambda: Valuer(session))
    today = local_day(datetime.now().astimezone())
    until = today + timedelta(days=days)
    acc: dict[tuple[str, date], list[Decimal]] = {}
    for _, lot in res.lots.open():
        free_on = one_year_after(local_day(lot.acquired)) + timedelta(days=1)
        if not today < free_on <= until:
            continue
        e = acc.setdefault((lot.asset, free_on), [ZERO, ZERO])
        e[0] += lot.qty
        e[1] += lot.cost
    out = []
    for (asset, free_on), (qty, cost) in sorted(acc.items(), key=lambda kv: kv[0][1]):
        price = valuer.latest_eur(asset, today)
        value = None if price is None else price * qty
        out.append(
            {
                "asset": asset,
                "free_on": free_on.isoformat(),
                "qty": _n(qty),
                "value": _eur(valuer.in_currency(value, today, currency)),
                "gain": _eur(
                    valuer.in_currency(None if value is None else value - cost, today, currency)
                ),
            }
        )
    return out


def holdings(session: Session) -> dict[str, dict]:
    """Per coin today: how much is past the holding period and when the next lot gets there
    (ADR 0042 point 8). Lots outside (own wallet not set up) count too: they are held."""
    res = compute(session, params(session))
    today = local_day(datetime.now().astimezone())
    out: dict[str, dict] = {}
    for _, lot in res.lots.open():
        e = out.setdefault(
            lot.asset, {"qty": ZERO, "free": ZERO, "oldest": None, "next_free": None}
        )
        e["qty"] += lot.qty
        ends = one_year_after(local_day(lot.acquired))
        if today > ends:
            e["free"] += lot.qty
        elif e["next_free"] is None or ends < e["next_free"]:
            e["next_free"] = ends
        if e["oldest"] is None or lot.acquired < e["oldest"]:
            e["oldest"] = lot.acquired
    return {
        a: {
            "qty": _n(e["qty"]),
            "free": _n(e["free"]),
            "days": (today - local_day(e["oldest"])).days,
            "next_free": (e["next_free"] + timedelta(days=1)).isoformat()
            if e["next_free"]
            else None,
        }
        for a, e in out.items()
    }


def free_coins(session: Session) -> dict:
    """Per coin today (Vanixxx 2026-10-16): how much is tax-free and how much not yet, both
    also as value and unrealized gain in the display currency, and when the next part turns
    free. Lots outside count as with `holdings`."""
    res = compute(session, params(session))
    currency = settings.all_settings(session)["general.currency"]
    valuer = _cached(session, "valuer", lambda: Valuer(session))
    today = local_day(datetime.now().astimezone())
    acc: dict[str, dict] = {}
    for _, lot in res.lots.open():
        e = acc.setdefault(
            lot.asset,
            {"free": [ZERO, ZERO], "taxed": [ZERO, ZERO], "next": None, "next_qty": ZERO},
        )
        free_on = one_year_after(local_day(lot.acquired)) + timedelta(days=1)
        part = e["free"] if today >= free_on else e["taxed"]
        part[0] += lot.qty
        part[1] += lot.cost
        if today < free_on:
            if e["next"] is None or free_on < e["next"]:
                e["next"], e["next_qty"] = free_on, ZERO
            if free_on == e["next"]:
                e["next_qty"] += lot.qty

    def money(price: Decimal | None, qty: Decimal, cost: Decimal) -> tuple:
        if price is None or not qty:
            return (None, None) if price is None else (ZERO, ZERO)
        value = price * qty
        return (
            valuer.in_currency(value, today, currency),
            valuer.in_currency(value - cost, today, currency),
        )

    coins = []
    for asset, e in acc.items():
        price = valuer.latest_eur(asset, today)
        vf, gf = money(price, *e["free"])
        vt, gt = money(price, *e["taxed"])
        coins.append(
            {
                "asset": asset,
                "free": _n(e["free"][0]),
                "taxed": _n(e["taxed"][0]),
                "value_free": _eur(vf),
                "value_taxed": _eur(vt),
                "gain_free": _eur(gf),
                "gain_taxed": _eur(gt),
                "next_free": e["next"].isoformat() if e["next"] else None,
                "next_qty": _n(e["next_qty"]) if e["next"] else None,
            }
        )

    def worth(c: dict) -> Decimal:
        return Decimal(c["value_free"] or 0) + Decimal(c["value_taxed"] or 0)

    coins.sort(key=lambda c: (-worth(c), c["asset"]))

    def total(key: str) -> str:
        return _eur(sum((Decimal(c[key]) for c in coins if c[key] is not None), ZERO))

    keys = ("value_free", "value_taxed", "gain_free", "gain_taxed")
    return {"currency": currency, "coins": coins, "total": {k: total(k) for k in keys}}
