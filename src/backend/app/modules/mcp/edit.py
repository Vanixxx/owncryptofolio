"""Stage 2 (ADR 0049): Claude changes data — always as a plan the user confirms as a whole.

A `plan_*` tool checks every item by doing it for real inside a transaction that is rolled
back: the same functions as the web pages, so the preview says exactly what will happen —
and, for entries and corrections, how the holdings move. It returns the complete list and
a plan id. Only `apply_plan` with that id changes anything; the list cannot change in
between. Items that failed in the preview are skipped. Raw data stays untouched as always:
corrections become manual rows, hiding is undoable, nothing is deleted.
"""

from __future__ import annotations

import logging
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_engine
from app.core.errors import AppError
from app.modules.mcp.models import McpChange

MAX_ITEMS = 50
PLAN_TTL = 30 * 60  # seconds a plan waits for the user's OK
MAX_PLANS = 50

log = logging.getLogger(__name__)


@dataclass
class Plan:
    id: str
    action: str
    items: list[dict]
    token: str
    created: float = field(default_factory=time.monotonic)
    ok: list[bool] = field(default_factory=list)


plans: dict[str, Plan] = {}


def _tz(db: Session) -> str:
    from app.modules.settings import service as settings_service

    return settings_service.all_settings(db)["general.timezone"]


# --- the actions: one function per kind of change, all from the existing services --------


def _entry(item: dict):
    from app.modules.manual.service import EntryIn

    return EntryIn.model_validate(item["entry"])


def _do(db: Session, action: str, item: dict) -> list[int]:
    """Carry out one item; returns the rows it touched (for the "changed by Claude" filter)."""
    from app.modules.manual import service as manual
    from app.modules.merged import service as merged

    if action == "link_transfers":
        merged.link(db, item["send_id"], item["receive_id"])
        return [item["send_id"], item["receive_id"]]
    if action == "split_transfers":
        merged.split(db, item["send_id"], item["receive_id"])
        return [item["send_id"], item["receive_id"]]
    if action == "notes":
        merged.set_note(db, item["row_id"], item.get("text"))
        return [item["row_id"]]
    if action == "open_marks":
        merged.mark_open(db, item["row_id"], item.get("mark"), item.get("note"))
        return [item["row_id"]]
    if action == "spam":
        merged.set_spam(db, [item["row_id"]], item["spam"])
        return [item["row_id"]]
    if action == "hide_rows":
        manual.remove(db, item["row_id"])
        return [item["row_id"]]
    if action == "restore_rows":
        manual.restore(db, item["row_id"])
        return [item["row_id"]]
    if action == "add_entries":
        new = manual.add(db, item["source_id"], _entry(item), _tz(db))
        return [new["id"]]
    if action == "correct_rows":
        new = manual.edit(db, item["row_id"], _entry(item), _tz(db))
        return [item["row_id"], new["id"]]
    raise AppError("mcp.unknown_action", 400)


MOVES = ("add_entries", "correct_rows", "hide_rows", "restore_rows")
"""Actions that change holdings: their preview shows the effect per coin."""


def _qty(db: Session) -> dict[str, Decimal]:
    from app.modules.portfolio import api as portfolio_api

    return {i["asset"]: Decimal(str(i["qty"] or 0)) for i in portfolio_api.holdings(db)["items"]}


def _row(db: Session, row_id: int | None) -> dict | None:
    from app.modules.raw.models import RawTransaction

    r = db.get(RawTransaction, row_id) if row_id else None
    if r is None:
        return None
    out = {"id": r.id, "at": r.timestamp.isoformat(), "kind": r.kind, "source_id": r.source_id}
    for side in ("incoming", "outgoing", "fee"):
        asset, amount = getattr(r, f"{side}_asset"), getattr(r, f"{side}_amount")
        if asset:
            out[side] = f"{amount.normalize():f} {asset}"
    return out


def plan(action: str, items: list[dict], token: str) -> dict:
    """Try every item in a transaction that is rolled back; keep the plan; return the list."""
    if not items:
        raise AppError("mcp.plan_empty", 400)
    if len(items) > MAX_ITEMS:
        raise AppError("mcp.plan_too_big", 400, max=MAX_ITEMS)
    conn = get_engine().connect()
    outer = conn.begin()
    # the services commit; in this mode a commit only closes a savepoint of the outer
    # transaction, which is rolled back at the end: nothing of the preview stays
    db = Session(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
    lines: list[dict] = []
    oks: list[bool] = []
    try:
        before = _qty(db) if action in MOVES else None
        for n, item in enumerate(items, 1):
            line: dict[str, Any] = {"n": n, "item": item}
            target = item.get("row_id") or item.get("send_id")
            if target:
                line["now"] = _row(db, target)
            try:
                touched = _do(db, action, item)
                line["status"] = "ok"
                if action in ("add_entries", "correct_rows"):
                    line["after"] = _row(db, touched[-1])
                oks.append(True)
            except (AppError, ValueError, KeyError) as exc:
                db.rollback()
                code = exc.code if isinstance(exc, AppError) else type(exc).__name__
                line["status"] = "skipped"
                line["reason"] = f"{code} {getattr(exc, 'params', '') or str(exc)[:200]}".strip()
                oks.append(False)
            lines.append(line)
        effect = None
        if before is not None:
            after = _qty(db)
            effect = {
                a: f"{(after.get(a, Decimal(0)) - before.get(a, Decimal(0))).normalize():+f}"
                for a in sorted(set(before) | set(after))
                if after.get(a, Decimal(0)) != before.get(a, Decimal(0))
            }
    finally:
        db.close()
        outer.rollback()
        conn.close()
    _sweep()
    pid = secrets.token_hex(8)
    plans[pid] = Plan(pid, action, items, token, ok=oks)
    return {
        "plan_id": pid,
        "action": action,
        "will_apply": sum(oks),
        "skipped": len(oks) - sum(oks),
        "items": lines,
        "holdings_effect": effect,
        "next": "Show the user this complete list. Only after their explicit OK call "
        f"apply_plan with plan_id={pid}; if they want only some items, pass their numbers "
        "(n) as `only`. The plan expires in 30 minutes.",
    }


def _sweep() -> None:
    now = time.monotonic()
    for pid in [p for p, x in plans.items() if now - x.created > PLAN_TTL]:
        del plans[pid]
    while len(plans) >= MAX_PLANS:
        del plans[min(plans, key=lambda p: plans[p].created)]


def apply(
    plan_id: str, token: str, db_factory: Callable[[], Session], only: list[int] | None = None
) -> dict:
    """Carry out a previewed plan, item by item, each in its own commit; record every one.
    `only`: the numbers of the preview the user chose ("1-14, not 44") — a part of what
    was shown, never anything else (Vanixxx, 2026-10-19)."""
    _sweep()
    p = plans.get(plan_id)
    if p is None or p.token != token:
        # another token's plan is as unknown as none (review 2026-10-24)
        raise AppError("mcp.plan_unknown", 404)
    chosen = set(only or range(1, len(p.items) + 1))
    if not chosen <= set(range(1, len(p.items) + 1)):
        raise AppError("mcp.plan_items_unknown", 400, max=len(p.items))
    del plans[plan_id]
    results = []
    for n, (item, ok) in enumerate(zip(p.items, p.ok, strict=True), 1):
        if n not in chosen:
            results.append({"n": n, "status": "left out"})
            continue
        if not ok:
            results.append({"n": n, "status": "skipped"})
            continue
        with db_factory() as db:
            try:
                touched = _do(db, p.action, item)
                db.add(McpChange(token=token, plan_id=p.id, action=p.action, item=item,
                                 row_ids=touched, ok=True))  # fmt: skip
                db.commit()
                results.append({"n": n, "status": "done", "rows": touched})
            except Exception as exc:  # noqa: BLE001 — one item failing must not end the rest
                db.rollback()
                if not isinstance(exc, (AppError, ValueError, KeyError)):
                    log.exception("Plan %s item %d failed", p.id, n)
                msg = exc.code if isinstance(exc, AppError) else str(exc)[:200]
                db.add(McpChange(token=token, plan_id=p.id, action=p.action, item=item,
                                 row_ids=[], ok=False, message=msg))  # fmt: skip
                db.commit()
                results.append({"n": n, "status": "failed", "reason": msg})
    done = sum(r["status"] == "done" for r in results)
    return {"plan_id": p.id, "action": p.action, "done": done, "results": results}


def changed_rows(db: Session) -> set[int]:
    """Every row Claude touched: for the filter on the transactions page."""
    out: set[int] = set()
    for ids in db.scalars(select(McpChange.row_ids).where(McpChange.ok.is_(True))):
        out |= {int(i) for i in ids or []}
    return out
