"""Merged view (ADR 0005, 0039): transfers as one line, spam, open sends, decisions."""

from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.modules.merged import service
from app.modules.portfolio import service as portfolio
from app.modules.portfolio.engine import card_purchase
from app.modules.prices.models import PriceAsset
from app.modules.prices.service import Valuer
from app.modules.raw import filters
from app.modules.raw.models import RawTransaction
from app.modules.settings import service as settings_service
from app.modules.sources.models import Source, Wallet

router = APIRouter(prefix="/api/merged", tags=["merged"])


def _q(v):
    return format(v.normalize(), "f")


class PairIn(BaseModel):
    send_id: int
    receive_id: int


class MarkIn(BaseModel):
    send_id: int
    mark: str | None = None
    note: str | None = None


class SpamIn(BaseModel):
    raw_ids: list[int]
    spam: bool


@dataclass
class ListQuery:
    """What the list shows: the same filters and order for the page and for the export."""

    source_id: str | None = None
    """Several comma-separated, like wallet, kind and coin (Vanixxx, 2026-10-07)."""
    market: str | None = None
    wallet_id: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    tz: str = "UTC"
    kind: str | None = None
    asset: str | None = None
    origin: str | None = None
    """Where rows came from, several comma-separated: api, file, chain, manual (2026-10-09)."""
    q: str | None = None
    """Free search: every word must turn up in a coin, ID, comment, note or address."""
    show: str = Query(
        "normal",
        pattern="^(normal|clean|spam|open|ambiguous|dust|edited|noted|marked|short|auto|card|mcp)$",
    )
    """The "notice" filter: open (no counterpart), ambiguous, dust, spam, edited by hand,
    with a note, marked as external or own untracked (Vanixxx, 2026-10-06)."""
    sort: str = Query("time", pattern="^(time|value)$")
    desc: bool = True


def select_items(db: Session, q: ListQuery) -> tuple[service.View, dict, list[dict]]:
    """The chosen lines and the notice counts. The counts follow every other filter, so
    "open (12)" means 12 within the chosen wallet, coin, time … (Vanixxx, 2026-10-10)."""
    from dataclasses import replace

    view, _, its = prepare(db)
    noticed = choose(db, view, its, replace(q, show="all"))
    return view, counts(view, noticed), choose(db, view, its, q)


def counts(view: service.View, its: list[dict]) -> dict:
    summary = service.summary(view, its)
    summary["short"] = sum(1 for i in its if i["short"])
    summary["auto"] = sum(1 for i in its if any(r["auto_deposit"] for r in service.lines_rows(i)))
    summary["card"] = sum(1 for i in its if any(r.get("card") for r in service.lines_rows(i)))
    return summary


def prepare(db: Session) -> tuple[service.View, dict, list[dict]]:
    """Every line of the merged view with what the list needs, before any filter."""
    view = service.build(db)
    its = service.items(view)
    its = _with_positions(db, view, its)
    # where each row came from: a correction says where its original came from
    originals = {
        r.raw.get("corrects") for r in view.rows.values() if r.channel == "manual" and r.raw
    }
    origin = (
        dict(
            db.execute(
                select(RawTransaction.id, RawTransaction.channel).where(
                    RawTransaction.id.in_({int(x) for x in originals if x is not None})
                )
            ).all()
        )
        if originals - {None}
        else {}
    )
    # the balance after each row: where it ran below zero, something is missing before.
    # After grouping, so a futures position carries it for its bookings (2026-10-09)
    after = portfolio.balances_after(db)
    auto = portfolio.auto_deposits(db)
    for i in its:
        for r in service.lines_rows(i):
            bal = after.get(r["id"], {})
            r["after"] = {a: _q(v) for a, (v, _) in bal.items()}
            r["short"] = sorted(a for a, (_, neg) in bal.items() if neg)
            r["origin"] = origin.get(r.get("corrects"), r["channel"])
            # money assumed paid in by card here: more was spent than was there
            a = auto.get(r["id"])
            r["auto_deposit"] = [a[0], _q(a[1])] if a else None
            # bought by card, but only the coin is known (Bitget "Buy with card"): the euro
            # paid are missing, so the cost is the market value (Blockpit check 2024)
            raw = view.rows.get(r["id"])
            r["card"] = bool(raw is not None and card_purchase(raw) and not raw.outgoing_asset)
        i["short"] = any(r["short"] for r in service.lines_rows(i))
    return view, counts(view, its), its


def choose(db: Session, view: service.View, its: list[dict], q: ListQuery) -> list[dict]:
    """The lines a query keeps, in its order."""
    kinds = set(filters.values(q.kind)) or None
    origins = set(filters.values(q.origin)) or None
    # rows changed through MCP (ADR 0049)
    by_mcp: set[int] = set()
    if q.show == "mcp":
        from app.modules.mcp.edit import changed_rows

        by_mcp = changed_rows(db)
    # the kind is decided per line below: "transfer" and "futures_position" are line types
    f = filters.build(
        db,
        source_id=q.source_id,
        wallet_id=q.wallet_id,
        date_from=q.date_from,
        date_to=q.date_to,
        tz=q.tz,
        asset=q.asset,
    )
    words = (q.q or "").lower().split()
    zone = ZoneInfo(settings_service.all_settings(db)["general.timezone"])
    # a source's name is searched too: "bitget" finds everything there (Vanixxx, 2026-10-06)
    names: dict[int, str] = {}
    if words:
        wallets = dict(db.execute(select(Wallet.id, Wallet.name)).all())
        for sid, label, provider, wid in db.execute(
            select(Source.id, Source.label, Source.provider, Source.wallet_id)
        ):
            names[sid] = f"{label} {provider} {wallets.get(wid, '')}".lower()

    coin_names = (
        {a: n.lower() for a, n in db.execute(select(PriceAsset.asset, PriceAsset.name)) if n}
        if words
        else {}
    )

    def notices(i: dict) -> str:
        """The line's notices and type as keys ("dust", "edited", "futures" …): the page
        sends its own words for them as alternatives, e.g. "staub|dust"."""
        keys = [i["type"]]
        if i["type"] == "row":
            keys += [k for k in ("open", "ambiguous", "dust") if i[k]]
            keys += ["spam"] if i["spam"] else []
            keys += ["marked"] if i["open_mark"] else []
            keys += ["card"] if i["row"].get("card") else []
        rows = service.lines_rows(i)
        keys += ["edited"] if any(r["modified"] for r in rows) else []
        keys += ["noted"] if any(r["note"] for r in rows) else []
        return " ".join(keys)

    def found(i: dict, rows: list[dict]) -> bool:
        parts = [notices(i)]
        for r in rows:
            if r["id"] in view.rows:
                parts.append(service.search_text(view, view.rows[r["id"]], zone))
                parts.append(names.get(r["source_id"], ""))
                parts += [f"{r['kind']} {r['market']}"]
                parts += [coin_names.get(r[s][0], "") for s in ("incoming", "outgoing", "fee")]
        text = " ".join(parts)
        # a word may carry alternatives: "staub|dust" matches either
        return all(any(alt in text for alt in w.split("|") if alt) for w in words)

    def keep(i: dict) -> bool:
        rows = (
            [i["send"], i["receive"]]
            if i["type"] == "transfer"
            else i["rows"]
            if i["type"] == "position"
            else [i["row"]]
        )
        if kinds is not None:
            if i["type"] == "transfer":
                if "transfer" not in kinds:
                    return False
            elif i["type"] == "position":
                # a position stands for its rows: it matches its own kind and theirs
                if "futures_position" not in kinds and all(r["kind"] not in kinds for r in rows):
                    return False
            elif not filters.kind_matches(kinds, i["row"]["kind"], i["row"]["income_kind"]):
                return False
        # a line comes from where any of its rows came from (a transfer: API and chain)
        if origins is not None and not any(r.get("origin") in origins for r in rows):
            return False
        # a transfer counts for both of its sources
        if not any(f.matches(view.rows[r["id"]], kind=False) for r in rows if r["id"] in view.rows):
            return False
        if q.market is not None and all(r["market"] != q.market for r in rows):
            return False
        if words and not found(i, rows + i.get("extras", [])):
            return False
        if q.show == "all":  # inside only: for the notice counts
            return True
        if q.show == "spam":
            return i["type"] == "row" and bool(i["spam"])
        if q.show == "clean":  # everything but spam and dust (Vanixxx, 2026-10-07)
            return i["type"] != "row" or not (i["spam"] or i["dust"])
        if q.show == "open":
            return i["type"] == "row" and (i["open"] or i["ambiguous"])
        if q.show == "short":
            return bool(i.get("short"))
        if q.show == "auto":
            return any(r.get("auto_deposit") for r in rows)
        if q.show == "card":
            return any(r.get("card") for r in rows)
        if q.show == "ambiguous":
            return i["type"] == "row" and i["ambiguous"]
        if q.show == "marked":
            return i["type"] == "row" and bool(i["open_mark"])
        if q.show == "mcp":
            return any(r["id"] in by_mcp for r in service.lines_rows(i))
        if q.show == "edited":
            return any(r["modified"] for r in service.lines_rows(i))
        if q.show == "noted":
            return any(r["note"] for r in service.lines_rows(i))
        if q.show == "dust":
            return i["type"] == "row" and i["dust"]
        return i["type"] != "row" or not i["spam"]

    selected = [i for i in its if keep(i)]
    if q.sort == "value":
        # biggest first: what a line moved, in EUR at that day's price (fees aside)
        valued = service.item_values(db, view, selected)
        selected.sort(
            key=lambda i: -1 if id(i) not in valued else abs(valued[id(i)]), reverse=q.desc
        )
    elif not q.desc:
        selected.reverse()
    return selected


@router.get("/facets")
def facets(q: ListQuery = Depends(), db: Session = Depends(get_session)) -> dict:
    """Which coins, kinds and sources the other filters leave (Vanixxx, 2026-10-08): with
    "income" chosen, coins that never had any income are shown dimmed. Each field is
    asked without its own value, so it shows its alternatives."""
    from dataclasses import replace

    view, _, its = prepare(db)
    coins: set[str] = set()
    for i in choose(db, view, its, replace(q, asset=None)):
        for r in service.lines_rows(i):
            coins |= {r[side][0] for side in ("incoming", "outgoing", "fee") if r[side][0]}
    kinds: set[str] = set()
    for i in choose(db, view, its, replace(q, kind=None)):
        if i["type"] == "transfer":
            kinds.add("transfer")
            continue
        if i["type"] == "position":
            kinds.add("futures_position")
        for r in service.lines_rows(i):
            kinds.add(r["kind"])
            if r["kind"] == "income" and r["income_kind"]:
                kinds.add(f"income:{r['income_kind']}")
    places: set[int] = set()
    for i in choose(db, view, its, replace(q, source_id=None, wallet_id=None)):
        places |= {r["source_id"] for r in service.lines_rows(i)}
    return {"assets": sorted(coins), "kinds": sorted(kinds), "sources": sorted(places)}


@router.get("")
def merged(
    q: ListQuery = Depends(),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_session),
) -> dict:
    view, summary, selected = select_items(db, q)
    page = selected[offset : offset + limit]
    valuer = Valuer(db)
    currency = settings_service.all_settings(db)["general.currency"]
    for i in page:
        # what each amount was worth at the time, in the display currency (Vanixxx, 2026-10-06)
        for r in (
            (i["send"], i["receive"], *i["extras"])
            if i["type"] == "transfer"
            else i.get("rows", [i.get("row")])
        ):
            if r is not None:
                r["values"] = service.row_values(valuer, view, r, currency)
        if i["type"] == "row" and i["row"]["kind"] == "trade":
            i["result"] = service.trade_result(valuer, view, view.rows[i["row"]["id"]], currency)
    return {"total": len(selected), "summary": summary, "items": page}


@router.get("/assets")
def assets(db: Session = Depends(get_session)) -> list[dict]:
    """Every coin in the valid rows, read as the coin it stands for (ADR 0038), for the coin
    filter: name and icon from the prices page, spam left out."""
    view = service.build(db)
    seen: set[str] = set()
    for r in view.rows.values():
        if not view.is_spam(r):
            seen |= {view.asset(a) for a in (r.incoming_asset, r.outgoing_asset, r.fee_asset) if a}
    info = {
        a: (n, i)
        for a, n, i in db.execute(select(PriceAsset.asset, PriceAsset.name, PriceAsset.icon))
    }
    return [
        {
            "asset": a,
            "name": info.get(a, (None, None))[0],
            "icon": info.get(a, (None, None))[1] or a,
        }
        for a in sorted(seen - view.spam_assets)
    ]


def _with_positions(db: Session, view: service.View, its: list[dict]) -> list[dict]:
    """Closed futures positions as one line each, with their results, funding and fees
    inside (ADR 0040); open ones stay on the holdings page."""
    currency = settings_service.all_settings(db)["general.currency"]
    groups = [g for g in portfolio.futures_positions(db, currency) if not g["open"]]
    member = {rid for g in groups for rid in g["row_ids"]}
    out = [i for i in its if not (i["type"] == "row" and i["row"]["id"] in member)]
    for g in groups:
        rows = [service.row_dict(view, view.rows[rid]) for rid in g["row_ids"] if rid in view.rows]
        rows.sort(key=lambda r: r["timestamp"])
        out.append({"type": "position", "at": g["closed"], **g, "rows": rows})
    out.sort(key=lambda i: i["at"], reverse=True)
    return out


@router.get("/candidates/{raw_id}")
def candidates(raw_id: int, db: Session = Depends(get_session)) -> list[dict]:
    return service.candidates_for(db, raw_id)


class TransferIn(BaseModel):
    send_id: int
    target_source_id: int


@router.post("/make-transfer")
def make_transfer(body: TransferIn, db: Session = Depends(get_session)) -> dict:
    tz = settings_service.all_settings(db)["general.timezone"]
    return service.make_transfer(db, body.send_id, body.target_source_id, tz)


class ExtraIn(BaseModel):
    send_id: int
    extra_id: int


@router.get("/attachable/{send_id}")
def attachable(send_id: int, db: Session = Depends(get_session)) -> list[dict]:
    return service.attachable(db, send_id)


@router.get("/transfers-for/{extra_id}")
def transfers_for(extra_id: int, db: Session = Depends(get_session)) -> list[dict]:
    return service.transfers_for(db, extra_id)


@router.post("/attach", status_code=204)
def attach(body: ExtraIn, db: Session = Depends(get_session)) -> None:
    service.attach(db, body.send_id, body.extra_id)


@router.post("/detach/{extra_id}", status_code=204)
def detach(extra_id: int, db: Session = Depends(get_session)) -> None:
    service.detach(db, extra_id)


class NoteIn(BaseModel):
    raw_id: int
    text: str | None = None


@router.put("/note", status_code=204)
def note(body: NoteIn, db: Session = Depends(get_session)) -> None:
    service.set_note(db, body.raw_id, body.text)


class DustIn(BaseModel):
    raw_ids: list[int]
    dust: bool


@router.post("/dust")
def dust(body: DustIn, db: Session = Depends(get_session)) -> dict:
    return {"rows": service.set_dust(db, body.raw_ids, body.dust)}


@router.post("/link", status_code=204)
def link(body: PairIn, db: Session = Depends(get_session)) -> None:
    service.link(db, body.send_id, body.receive_id)


@router.post("/split", status_code=204)
def split(body: PairIn, db: Session = Depends(get_session)) -> None:
    service.split(db, body.send_id, body.receive_id)


@router.post("/open-mark", status_code=204)
def open_mark(body: MarkIn, db: Session = Depends(get_session)) -> None:
    service.mark_open(db, body.send_id, body.mark, body.note)


@router.post("/spam")
def spam(body: SpamIn, db: Session = Depends(get_session)) -> dict:
    return {"rows": service.set_spam(db, body.raw_ids, body.spam)}
