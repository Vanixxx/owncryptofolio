"""The merged view (ADR 0005, 0039): one line per transfer, spam out, open sends visible.

Computed on every request from the valid raw rows plus Vanixxx's stored decisions. Valid
means: not retracted (ADR 0036/0037) and not superseded by the API of the same exchange
(ADR 0033/0035). Symbols are read as the coin they stand for (ADR 0038).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.manual import service as manual
from app.modules.merged import detect
from app.modules.merged.models import (
    NotDustMark,
    OpenSendMark,
    SpamMark,
    TransferDecision,
    TransferExtra,
    TxNote,
)
from app.modules.prices.models import AssetAlias, PriceAsset
from app.modules.raw.models import RawRetraction, RawTransaction, current
from app.modules.raw.service import Overlap

DUST_SHARE = Decimal("0.0001")
"""A receive below 0.01 % of everything this source received of the coin is suggested as
dust (Hedera: 116 receives of 1 tinybar or 0.0001 HBAR next to 7,302 HBAR). Only receives:
staking rewards are as small as a dusting attack, but they are taxable income."""
OPEN_MARKS = ("external", "own_untracked", "lost")
# a receive without counterpart (Vanixxx, 2026-10-11): from an own wallet that is not set up
# here, bought outside (card), or income (rewards for tasks, gifts)
RECEIVE_MARKS = ("own_untracked", "bought", "income")


def _plain(v: Decimal | None) -> str | None:
    return None if v is None else format(v.normalize(), "f")


@dataclass
class View:
    rows: dict[int, RawTransaction]
    alias: dict[str, str]
    pairs: list[detect.Pair]
    ambiguous: set[str]
    forbidden: set[tuple[str, str]]
    taken: set[str]
    spam_assets: set[str]
    spam_tx: set[str]
    dust: set[str]
    marks: dict[str, OpenSendMark]
    replacing: set[int] = field(default_factory=set)
    extras: dict[str, str] = field(default_factory=dict)
    """A booking attached to a transfer → the send it belongs to (TransferExtra)."""
    by_fp: dict[str, RawTransaction] = field(default_factory=dict)
    decided_at: dict[str, datetime] = field(default_factory=dict)
    """When a person linked a pair (by send) or attached an extra (by extra): for the history."""
    notes: dict[str, str] = field(default_factory=dict)
    """Vanixxx's own notes, by fingerprint (on a transfer: its send)."""

    def asset(self, a: str | None) -> str | None:
        return None if a is None else self.alias.get(a, a)

    def is_spam(self, r: RawTransaction) -> str | None:
        if r.fingerprint in self.spam_tx:
            return "tx"
        assets = {self.asset(a) for a in (r.incoming_asset, r.outgoing_asset) if a}
        return "asset" if assets and assets <= self.spam_assets else None


def valid_rows(session: Session) -> list[RawTransaction]:
    overlap = Overlap(session)
    rows = session.scalars(
        select(RawTransaction).where(current()).order_by(RawTransaction.timestamp)
    ).all()
    return [
        r
        for r in rows
        if not overlap.covered(
            r.source_id,
            r.market,
            r.channel,
            r.timestamp,
            [(r.incoming_asset, r.incoming_amount), (r.outgoing_asset, r.outgoing_amount)],
        )
    ]


def build(session: Session) -> View:
    rows = valid_rows(session)
    alias = dict(session.execute(select(AssetAlias.alias, AssetAlias.asset)).all())
    spam_assets = set(session.scalars(select(PriceAsset.asset).where(PriceAsset.ignored.is_(True))))
    spam_tx = set(session.scalars(select(SpamMark.fingerprint)))
    decisions = list(session.scalars(select(TransferDecision)))
    forbidden = {(d.send_fp, d.receive_fp) for d in decisions if d.decision == "split"}
    manual = [d for d in decisions if d.decision == "linked"]
    by_fp = {r.fingerprint: r for r in rows}
    view = View(
        rows={r.id: r for r in rows},
        alias=alias,
        pairs=[],
        ambiguous=set(),
        forbidden=forbidden,
        taken=set(),
        spam_assets=spam_assets,
        spam_tx=spam_tx,
        dust=set(),
        marks={m.send_fp: m for m in session.scalars(select(OpenSendMark))},
        replacing=set(
            session.scalars(
                select(RawRetraction.replaced_by_id).where(
                    RawRetraction.replaced_by_id.is_not(None)
                )
            )
        ),
        by_fp=by_fp,
    )
    view.notes = {n.fingerprint: n.text for n in session.scalars(select(TxNote))}
    for e in session.scalars(select(TransferExtra)):
        if e.extra_fp in by_fp and e.send_fp in by_fp:
            view.extras[e.extra_fp] = e.send_fp
            view.decided_at[e.extra_fp] = e.created_at
    for d in manual:
        # a half already in a pair takes no second one (review 2026-10-24: after edits and a
        # restore one row could stand in two transfers)
        if (
            d.send_fp in by_fp
            and d.receive_fp in by_fp
            and not {d.send_fp, d.receive_fp} & view.taken
        ):
            view.pairs.append(detect.Pair(d.send_fp, d.receive_fp, "manual"))
            view.decided_at[d.send_fp] = d.created_at
            view.taken |= {d.send_fp, d.receive_fp}
    sends, receives = halves(view)
    # both halves of a pair split by hand stay single: what Vanixxx changed is not undone by
    # the next run, only by his own link (Vanixxx, 2026-10-23)
    alone = {fp for pair in forbidden for fp in pair}
    pairs, ambiguous = detect.find_pairs(sends, receives, forbidden, view.taken | alone)
    view.pairs += pairs
    view.ambiguous = set(ambiguous)
    view.taken |= {p.send for p in pairs} | {p.receive for p in pairs}
    # an attached booking whose send is in no transfer any more (split, linked elsewhere) is
    # an ordinary line again, not hidden (review 2026-10-24)
    paired = {p.send for p in view.pairs}
    view.extras = {x: send for x, send in view.extras.items() if send in paired}
    view.dust = _dust(view) - set(session.scalars(select(NotDustMark.fingerprint)))
    return view


def halves(view: View) -> tuple[list[detect.Half], list[detect.Half]]:
    sends, receives = [], []
    for r in view.rows.values():
        if view.is_spam(r) or r.fingerprint in view.extras:
            continue
        if r.kind == "send" and r.outgoing_amount:
            sends.append(
                detect.Half(
                    r.fingerprint,
                    r.timestamp,
                    view.asset(r.outgoing_asset),
                    r.outgoing_amount,
                    r.external_id,
                    r.source_id,
                )
            )
        elif r.kind == "receive" and r.incoming_amount:
            receives.append(
                detect.Half(
                    r.fingerprint,
                    r.timestamp,
                    view.asset(r.incoming_asset),
                    r.incoming_amount,
                    r.external_id,
                    r.source_id,
                )
            )
    return sends, receives


def _dust(view: View) -> set[str]:
    totals: dict[tuple[int, str], Decimal] = {}
    for r in view.rows.values():
        if r.kind == "receive" and r.incoming_amount:
            key = (r.source_id, view.asset(r.incoming_asset))
            totals[key] = totals.get(key, Decimal(0)) + r.incoming_amount
    return {
        r.fingerprint
        for r in view.rows.values()
        if r.kind == "receive"
        and r.incoming_amount
        and r.fingerprint not in view.taken
        and not view.is_spam(r)
        and r.incoming_amount < totals[(r.source_id, view.asset(r.incoming_asset))] * DUST_SHARE
    }


# --- serialising -------------------------------------------------------------------------


def row_dict(view: View, r: RawTransaction) -> dict:
    return {
        "id": r.id,
        "source_id": r.source_id,
        "channel": r.channel,
        "timestamp": r.timestamp.isoformat(),
        "kind": r.kind,
        "income_kind": r.income_kind,
        "market": r.market,
        "instrument": r.instrument,
        "incoming": [view.asset(r.incoming_asset), _plain(r.incoming_amount)],
        "outgoing": [view.asset(r.outgoing_asset), _plain(r.outgoing_amount)],
        "fee": [view.asset(r.fee_asset), _plain(r.fee_amount)],
        "external_id": r.external_id,
        "comment": r.comment,
        "note": view.notes.get(r.fingerprint),
        "paid_by_card": r.channel == "manual"
        and bool(((r.raw or {}).get("manual") or {}).get("paid_by_card")),
        "counterparty": r.counterparty,
        "raw_symbols": [a for a in (r.incoming_asset, r.outgoing_asset) if a and view.alias.get(a)],
        # same shape as /api/raw, so the row actions (edit, hide, history) work unchanged
        "state": "current",
        "covered_by_api": False,
        "corrects": (r.raw or {}).get("corrects") if r.channel == "manual" else None,
        # changed by hand: shown with the "edited" mark; after a reset it is gone again
        "modified": r.channel == "manual" and bool({"replaces", "corrects"} & (r.raw or {}).keys()),
        # has versions: the history is worth a look
        "edited": r.id in view.replacing
        or (r.channel == "manual" and bool({"replaces", "corrects"} & (r.raw or {}).keys())),
    }


def _at(view: View, fp: str) -> str | None:
    at = view.decided_at.get(fp)
    return at.isoformat() if at else None


def items(view: View) -> list[dict]:
    """Newest first: a transfer is ONE item (send + receive), everything else one row."""
    out: list[dict] = []
    in_pair: set[str] = set()
    for p in view.pairs:
        s, r = view.by_fp[p.send], view.by_fp[p.receive]
        in_pair |= {p.send, p.receive}
        network = (
            s.outgoing_amount - r.incoming_amount
            if s.outgoing_amount and r.incoming_amount
            else None
        )
        out.append(
            {
                "type": "transfer",
                "at": s.timestamp.isoformat(),
                "reason": p.reason,
                "send": row_dict(view, s),
                "receive": row_dict(view, r),
                # sent minus arrived is the network fee (ADR 0039), on top of the send's own fee
                "network_fee": [view.asset(s.outgoing_asset), _plain(network)]
                if network and network > 0
                else None,
                "extras": [
                    {**row_dict(view, view.by_fp[fp]), "attached_at": _at(view, fp)}
                    for fp, to in view.extras.items()
                    if to == p.send
                ],
                "linked_at": _at(view, p.send) if p.reason == "manual" else None,
            }
        )
    for r in view.rows.values():
        if r.fingerprint in in_pair or r.fingerprint in view.extras:
            continue
        mark = view.marks.get(r.fingerprint)
        out.append(
            {
                "type": "row",
                "at": r.timestamp.isoformat(),
                "row": row_dict(view, r),
                "spam": view.is_spam(r),
                "dust": r.fingerprint in view.dust,
                # a receive counts too (2026-10-11), unless it is dust or spam
                "open": r.kind in ("send", "receive")
                and not view.is_spam(r)
                and r.fingerprint not in view.dust
                and mark is None,
                "ambiguous": r.fingerprint in view.ambiguous,
                "open_mark": mark.mark if mark else None,
            }
        )
    out.sort(key=lambda i: i["at"], reverse=True)
    return out


def item_values(session: Session, view: View, its: list[dict]) -> dict[int, Decimal]:
    """EUR worth of each item (keyed by `id(item)`): a transfer by what was sent, a row by
    its bigger side, a futures position by its result (signed: a loss stays a loss). Unvalued
    items are left out and sort last."""
    from app.modules.prices.service import Valuer

    valuer = Valuer(session)
    out: dict[int, Decimal] = {}
    for i in its:
        if i["type"] == "position":
            # in EUR, not the display currency: the caller converts (review 2026-10-24: the
            # export converted a USD value a second time)
            if i.get("result_eur") is not None:
                out[id(i)] = Decimal(i["result_eur"])
            continue
        r = view.rows[i["send"]["id"]] if i["type"] == "transfer" else view.rows[i["row"]["id"]]
        best = None
        for asset, amount in (
            (r.incoming_asset, r.incoming_amount),
            (r.outgoing_asset, r.outgoing_amount),
        ):
            if asset and amount:
                p = valuer.eur(view.asset(asset), r.timestamp.date())
                if p is not None and (best is None or p * amount > best):
                    best = p * amount
        if best is not None:
            out[id(i)] = best
    return out


FIAT = frozenset({"EUR", "USD"})


def _money(v: Decimal | None) -> str | None:
    return None if v is None else format(v.quantize(Decimal("0.01")), "f")


def row_values(valuer, view: View, r: dict, currency: str) -> dict:
    """Each side of a row dict at its day's price, in the display currency; None if unpriced."""
    day = datetime.fromisoformat(r["timestamp"]).date()
    out = {}
    for side in ("incoming", "outgoing", "fee"):
        asset, amount = r[side]
        price = valuer.eur(asset, day) if asset and amount else None
        value = (
            valuer.in_currency(price * Decimal(amount), day, currency)
            if price is not None
            else None
        )
        out[side] = _money(value)
    return out


def trade_result(valuer, view: View, r: RawTransaction, currency: str) -> dict | None:
    """What this one trade came to, apart from average cost and tax (Vanixxx, 2026-10-05):
    a buy against today's value of what was bought, a sale against today's value of what
    was sold. Values of the day in EUR, shown in the display currency."""
    ia, oa, fa = view.asset(r.incoming_asset), view.asset(r.outgoing_asset), view.asset(r.fee_asset)
    iq, oq, fq = (
        r.incoming_amount or Decimal(0),
        r.outgoing_amount or Decimal(0),
        r.fee_amount or Decimal(0),
    )
    if r.kind != "trade" or not ia or not oa or not iq or not oq:
        return None
    day, today = r.timestamp.date(), datetime.now(UTC).date()

    def then(asset: str, qty: Decimal) -> Decimal | None:
        p = valuer.eur(asset, day)
        return None if p is None else p * qty

    # what the trade was worth: the fiat side exactly, else what can be valued
    worth = (
        then(oa, oq)
        if oa in FIAT
        else then(ia, iq)
        if ia in FIAT
        else (then(oa, oq) or then(ia, iq))
    )
    if worth is None:
        return None
    fee = then(fa, fq) if fa and fq else Decimal(0)
    if ia not in FIAT:  # a buy
        qty = iq - fq if fa == ia else iq
        price_now = valuer.latest_eur(ia, today)
        cost = worth + (fee if fa != ia else Decimal(0)) if fee is not None else worth
        if price_now is None:
            return None
        now = qty * price_now
        side, asset, base, result = "buy", ia, cost, now - cost
        price_then = worth / iq
    else:  # a sale: the money received against what the coins would be worth now
        price_now = valuer.latest_eur(oa, today)
        if price_now is None:
            return None
        proceeds = worth - (fee or Decimal(0))
        now = oq * price_now
        side, asset, qty, base, result = "sell", oa, oq, now, proceeds - now
        cost = proceeds
        price_then = worth / oq
    conv = lambda v, d: valuer.in_currency(v, d, currency)  # noqa: E731
    return {
        "side": side,
        "asset": asset,
        "qty": format(qty.normalize(), "f"),
        "then": _money(conv(cost, day)),
        "now": _money(conv(now, today)),
        "result": _money(conv(result, today)),
        "pct": format((result / base * 100).quantize(Decimal("0.1")), "f") if base else None,
        "price_then": format(conv(price_then, day).normalize(), "f")
        if conv(price_then, day)
        else None,
        "price_now": format(conv(price_now, today).normalize(), "f")
        if conv(price_now, today)
        else None,
        "currency": currency,
    }


def lines_rows(i: dict) -> list[dict]:
    """Every row of a list line: a transfer's halves and extras, a position's bookings."""
    if i["type"] == "transfer":
        return [i["send"], i["receive"], *i["extras"]]
    return i["rows"] if i["type"] == "position" else [i["row"]]


def summary(view: View, its: list[dict]) -> dict:
    rows = [i for i in its if i["type"] == "row"]
    return {
        "edited": sum(1 for i in its if any(r["modified"] for r in lines_rows(i))),
        "noted": sum(1 for i in its if any(r["note"] for r in lines_rows(i))),
        "marked": sum(1 for i in rows if i["open_mark"]),
        "transfers": sum(1 for i in its if i["type"] == "transfer"),
        "open": sum(1 for i in rows if i["open"]),
        "ambiguous": sum(1 for i in rows if i["ambiguous"]),
        "dust": sum(1 for i in rows if i["dust"]),
        "spam": sum(1 for i in rows if i["spam"]),
        "rows": len(view.rows),
    }


# --- decisions -----------------------------------------------------------------------------


def _row(session: Session, raw_id: int, kind: str) -> RawTransaction:
    r = session.get(RawTransaction, raw_id)
    if r is None or r.kind != kind:
        raise AppError("merged.wrong_row", 400, kind=kind)
    return r


def link(session: Session, send_id: int, receive_id: int) -> None:
    s, r = _row(session, send_id, "send"), _row(session, receive_id, "receive")
    view = build(session)
    sent, got = view.asset(s.outgoing_asset), view.asset(r.incoming_asset)
    if sent != got:
        # a transfer moves one coin; BCH out and USD in is a transfer plus a trade
        # (Cryptex, Vanixxx 2026-10-11): the books put 1,015 "BCH" where USD arrived
        raise AppError("merged.asset_mismatch", 400, sent=sent or "", got=got or "")
    for p in view.pairs:
        if p.reason == "manual" and ({p.send, p.receive} & {s.fingerprint, r.fingerprint}):
            raise AppError("merged.already_linked", 409)
    session.execute(
        delete(TransferDecision).where(
            TransferDecision.send_fp == s.fingerprint, TransferDecision.receive_fp == r.fingerprint
        )
    )
    session.add(
        TransferDecision(send_fp=s.fingerprint, receive_fp=r.fingerprint, decision="linked")
    )
    session.execute(delete(OpenSendMark).where(OpenSendMark.send_fp == s.fingerprint))
    session.commit()


def split(session: Session, send_id: int, receive_id: int) -> None:
    """Separates a transfer. Both halves stay single until linked by hand (Vanixxx, 2026-10-23)."""
    s, r = _row(session, send_id, "send"), _row(session, receive_id, "receive")
    session.execute(
        delete(TransferDecision).where(
            TransferDecision.send_fp == s.fingerprint, TransferDecision.receive_fp == r.fingerprint
        )
    )
    session.add(TransferDecision(send_fp=s.fingerprint, receive_fp=r.fingerprint, decision="split"))
    session.commit()


def mark_open(session: Session, send_id: int, mark: str | None, note: str | None) -> None:
    """Marks a send or a receive that has no counterpart (the table keeps its old name)."""
    s = session.get(RawTransaction, send_id)
    if s is None or s.kind not in ("send", "receive"):
        raise AppError("merged.wrong_row", 400, kind="send")
    session.execute(delete(OpenSendMark).where(OpenSendMark.send_fp == s.fingerprint))
    if mark is not None:
        if mark not in (OPEN_MARKS if s.kind == "send" else RECEIVE_MARKS):
            raise AppError("merged.invalid_mark", 400)
        session.add(
            OpenSendMark(send_fp=s.fingerprint, mark=mark, note=(note or "").strip() or None)
        )
    session.commit()


def set_spam(session: Session, raw_ids: list[int], spam: bool) -> int:
    rows = [session.get(RawTransaction, i) for i in raw_ids]
    if any(r is None for r in rows):
        raise AppError("merged.wrong_row", 400, kind="any")
    fps = [r.fingerprint for r in rows]
    session.execute(delete(SpamMark).where(SpamMark.fingerprint.in_(fps)))
    if spam:
        session.add_all(SpamMark(fingerprint=fp) for fp in fps)
    session.commit()
    return len(fps)


def candidates_for(session: Session, raw_id: int) -> list[dict]:
    """Possible partners for an open send — or, the other way round, for an open receive
    (Vanixxx, 2026-10-06: "Gegenstück suchen" was missing on receives)."""
    r = session.get(RawTransaction, raw_id)
    if r is None or r.kind not in ("send", "receive"):
        raise AppError("merged.wrong_row", 400, kind="send")
    view = build(session)
    sends, receives = halves(view)
    mine, others = (sends, receives) if r.kind == "send" else (receives, sends)
    half = next((h for h in mine if h.fp == r.fingerprint), None)
    if half is None:
        return []
    taken = view.taken - {half.fp}
    out = []
    # A pair split by hand is still offered (marked), so a split can be undone; the
    # automatic detection keeps respecting it.
    for c in detect.candidates(half, others, set(), taken):
        send_fp, recv_fp = (half.fp, c.receive) if r.kind == "send" else (c.receive, half.fp)
        partner = row_dict(view, view.by_fp[c.receive])
        out.append(
            {
                "partner": partner,
                "receive": partner,
                "send_id": view.by_fp[send_fp].id,
                "receive_id": view.by_fp[recv_fp].id,
                "minutes": c.minutes,
                "diff_pct": format(c.diff_pct.quantize(Decimal("0.01")), "f"),
                "sharp": c.sharp,
                "split_before": (send_fp, recv_fp) in view.forbidden,
            }
        )
    return out[:10]


EXTRA_WINDOW = 7200
"""Seconds around a transfer in which a separate fee booking is offered (2 hours)."""


def attachable(session: Session, send_id: int) -> list[dict]:
    """Bookings that could belong to this transfer as its fee: same source, close in time,
    only going out (a fee, an "other" deduction, a small send), not yet in any transfer."""
    s = _row(session, send_id, "send")
    view = build(session)
    in_pair = {p.send for p in view.pairs} | {p.receive for p in view.pairs}
    out = []
    for r in view.rows.values():
        if (
            r.source_id == s.source_id
            and r.fingerprint not in in_pair
            and r.fingerprint not in view.extras
            and r.id != s.id
            and can_attach(r)
            and abs((r.timestamp - s.timestamp).total_seconds()) <= EXTRA_WINDOW
        ):
            out.append(row_dict(view, r))
    return sorted(out, key=lambda x: x["timestamp"])


def can_attach(r: RawTransaction) -> bool:
    """Only going out: a fee, an "other" deduction, a small send."""
    return not r.incoming_amount and bool(r.outgoing_amount or r.fee_amount)


def transfers_for(session: Session, extra_id: int) -> list[dict]:
    """The other way round (Vanixxx, 2026-10-06): transfers a fee booking could belong to —
    sent from or arrived at its source, close in time."""
    extra = session.get(RawTransaction, extra_id)
    if extra is None or not can_attach(extra):
        raise AppError("merged.wrong_row", 400, kind="fee")
    view = build(session)
    out = []
    for p in view.pairs:
        s, r = view.by_fp[p.send], view.by_fp[p.receive]
        if (
            extra.fingerprint not in (p.send, p.receive)
            and extra.source_id in (s.source_id, r.source_id)
            and abs((s.timestamp - extra.timestamp).total_seconds()) <= EXTRA_WINDOW
        ):
            out.append({"send": row_dict(view, s), "receive": row_dict(view, r)})
    return sorted(out, key=lambda x: x["send"]["timestamp"])


def attach(session: Session, send_id: int, extra_id: int) -> None:
    """The rules of `attachable` and `transfers_for`, checked here too: only a booking going
    out, of one side of this transfer, close in time and not half of another transfer — else
    its incoming coins would vanish from holdings and tax (review 2026-10-24)."""
    s = _row(session, send_id, "send")
    extra = session.get(RawTransaction, extra_id)
    if extra is None or extra.id == s.id or not can_attach(extra):
        raise AppError("merged.wrong_row", 400, kind="fee")
    view = build(session)
    pair = next((p for p in view.pairs if p.send == s.fingerprint), None)
    in_pair = {p.send for p in view.pairs} | {p.receive for p in view.pairs}
    sides = {s.source_id} | ({view.by_fp[pair.receive].source_id} if pair else set())
    if (
        extra.fingerprint in in_pair
        or extra.source_id not in sides
        or abs((extra.timestamp - s.timestamp).total_seconds()) > EXTRA_WINDOW
    ):
        raise AppError("merged.wrong_row", 400, kind="fee")
    session.merge(TransferExtra(extra_fp=extra.fingerprint, send_fp=s.fingerprint))
    session.commit()


def detach(session: Session, extra_id: int) -> None:
    extra = session.get(RawTransaction, extra_id)
    if extra is not None:
        session.execute(delete(TransferExtra).where(TransferExtra.extra_fp == extra.fingerprint))
        session.commit()


def make_transfer(session: Session, send_id: int, target_id: int, tz: str) -> dict:
    """A send that went to an own wallet or exchange (Vanixxx, 2026-10-06: correcting an
    "Umbuchung" into a transfer). Links to the fitting receive the target already has —
    the chain usually delivers it — or, if none, enters that receive by hand there."""
    s = _row(session, send_id, "send")
    if target_id == s.source_id:
        raise AppError("merged.same_source", 400)
    view = build(session)
    asset = view.asset(s.outgoing_asset)
    taken = {p.send for p in view.pairs} | {p.receive for p in view.pairs}
    best = None
    for r in view.rows.values():
        if (
            r.source_id == target_id
            and r.kind == "receive"
            and r.fingerprint not in taken
            and view.asset(r.incoming_asset) == asset
            and r.incoming_amount
            and abs(r.timestamp - s.timestamp) <= detect.WIDE_WINDOW
            and abs(r.incoming_amount - s.outgoing_amount)
            <= s.outgoing_amount * detect.WIDE_TOLERANCE
        ):
            gap = abs(r.timestamp - s.timestamp)
            if best is None or gap < best[0]:
                best = (gap, r)
    if best is not None:
        link(session, s.id, best[1].id)
        return {"receive_id": best[1].id, "created": False}
    entry = manual.EntryIn(
        kind="receive",
        # with its offset: in the hour that exists twice a local time would be ambiguous
        time=s.timestamp.astimezone(UTC).isoformat(),
        incoming_asset=s.outgoing_asset,
        incoming_amount=format(s.outgoing_amount.normalize(), "f"),
        comment="transfer",
    )
    created = manual.add(session, target_id, entry, tz)
    link(session, s.id, created["id"])
    return {"receive_id": created["id"], "created": True}


def set_note(session: Session, raw_id: int, text: str | None) -> None:
    """Vanixxx's own note on a line; empty removes it. The raw row stays as it is."""
    r = session.get(RawTransaction, raw_id)
    if r is None:
        raise AppError("merged.wrong_row", 400, kind="any")
    text = (text or "").strip()[:2000]
    session.execute(delete(TxNote).where(TxNote.fingerprint == r.fingerprint))
    if text:
        session.add(TxNote(fingerprint=r.fingerprint, text=text))
    session.commit()


def search_text(view: View, r: RawTransaction, zone: ZoneInfo | None = None) -> str:
    """What the free search looks in: coins (also as the source wrote them), transaction
    ID, the source's comment, Vanixxx's note, the counterparty — and the date and time in the
    user's zone, as "04.10.2026" and "2026-10-04" (Vanixxx, 2026-10-06)."""
    local = r.timestamp.astimezone(zone or UTC)
    parts = [
        local.strftime("%d.%m.%Y %Y-%m-%d %H:%M:%S"),
        r.incoming_asset,
        r.outgoing_asset,
        r.fee_asset,
        view.asset(r.incoming_asset),
        view.asset(r.outgoing_asset),
        view.asset(r.fee_asset),
        r.external_id,
        r.comment,
        r.counterparty,
        r.instrument,
        view.notes.get(r.fingerprint),
    ]
    return " ".join(p for p in parts if p).lower()


def set_dust(session: Session, raw_ids: list[int], dust: bool) -> int:
    """Not dust: takes lines off the dust suggestion, one or many picked at once;
    `dust=True` undoes that."""
    rows = [session.get(RawTransaction, i) for i in raw_ids]
    if any(r is None for r in rows):
        raise AppError("merged.wrong_row", 400, kind="any")
    fps = [r.fingerprint for r in rows]
    session.execute(delete(NotDustMark).where(NotDustMark.fingerprint.in_(fps)))
    if not dust:
        session.add_all(NotDustMark(fingerprint=fp) for fp in fps)
    session.commit()
    return len(fps)
