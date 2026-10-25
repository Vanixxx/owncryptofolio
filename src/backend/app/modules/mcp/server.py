"""owncryptofolio as an MCP server for Claude (ADR 0049), stage 1: reading only.

Each tool is a thin shell around what the web pages use, no logic of its own: it opens a
session, calls the same function, trims the answer to what helps and masks it like the
live log (keys out, addresses shortened). Every call is logged with tool, token and time.
The gateway in front checks the token and the mode before the SDK sees the request.
"""

import contextvars
import functools
import inspect
import logging
import time
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from app.core import logs
from app.core.db import get_engine
from app.core.errors import AppError
from app.core.version import app_version
from app.modules.manual.service import EntryIn
from app.modules.mcp import service

log = logging.getLogger("mcp")
MAX_ROWS = 200
token_name: contextvars.ContextVar[str] = contextvars.ContextVar("mcp_token", default="?")
token_level: contextvars.ContextVar[str] = contextvars.ContextVar("mcp_level", default="read")
READERS: dict[str, Callable] = {}
"""The reading tools by name: the REST API (/api/v1) serves the same ones (ADR 0050)."""

INSTRUCTIONS = """owncryptofolio: a self-hosted crypto portfolio and German tax tracker
(single user).
Read-only access. Amounts are strings (exact decimals); values are in the display currency
the answers name; times are ISO with time zone. Addresses are shortened on purpose.
Tax follows German law (§ 23 EStG private sales: one-year holding period, Freigrenze;
§ 22 Nr. 3 other income). Raw data is never changed; corrections are made by the user in
the app. Answer the user in their language (usually German)."""


# --- shaping ----------------------------------------------------------------------------


def clean(v: Any) -> Any:
    """JSON-safe and masked: decimals as text, dates as ISO, every string through the
    same mask as the live log."""
    if isinstance(v, dict):
        return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, list | tuple | set):
        return [clean(x) for x in v]
    if isinstance(v, Decimal):
        return f"{v.normalize():f}"
    if isinstance(v, datetime | date):
        return v.isoformat()
    if isinstance(v, str):
        return logs.mask(v)
    return v


def _pick(d: dict, keys: list[str]) -> dict:
    return {k: d[k] for k in keys if k in d}


def _db() -> Session:
    return Session(get_engine())


def _names(db: Session) -> dict[int, str]:
    from app.modules.sources.models import Source

    return {s.id: s.label for s in db.query(Source).all()}


def _settings(db: Session) -> dict:
    from app.modules.settings import service as settings_service

    return settings_service.all_settings(db)


# --- the server -------------------------------------------------------------------------


def build(app) -> tuple[Any, Callable]:
    """The MCP server with its tools, and the gateway (an ASGI app) for the route /mcp."""
    from mcp.server.mcpserver import MCPServer
    from mcp.server.transport_security import TransportSecuritySettings

    server = MCPServer(
        name="owncryptofolio", version=app_version(), instructions=INSTRUCTIONS, log_level="WARNING"
    )

    def tool(fn: Callable | None = None, *, write: bool = False) -> Callable:
        """Register a tool: logged, timed, masked, errors as plain messages. A writing tool
        works only with the mode "edit" (stage 2)."""
        if fn is None:
            return lambda f: tool(f, write=write)

        if fn.__name__.startswith("plan_"):
            fn.__doc__ = (fn.__doc__ or "") + PLAN_NOTE
        if not write:
            READERS[fn.__name__] = fn

        @functools.wraps(fn)
        def run(*args, **kwargs):
            started = time.monotonic()
            shown = {k: v for k, v in kwargs.items() if v not in (None, "", [])}
            status = "error"
            try:
                with _db() as db:
                    if write and token_level.get() != "edit":
                        raise AppError("mcp.edit_off", 403)
                    out = clean(fn(db, *args, **kwargs))
                status = "ok"
                return out
            except AppError as exc:
                status = exc.code
                # a failure the model can read and act on (unknown row, plan expired, …)
                from mcp.server.mcpserver.exceptions import ToolError

                raise ToolError(f"{exc.code} {exc.params or ''}".strip()) from None
            finally:
                ms = int((time.monotonic() - started) * 1000)
                service.last_call.update(
                    tool=fn.__name__, token=token_name.get(), at=datetime.now(UTC).isoformat()
                )
                log.info(
                    "%s=%s client=%s args=%s status=%s ms=%d",
                    "write" if write else "tool",
                    fn.__name__,
                    token_name.get(),
                    shown,
                    status,
                    ms,
                )

        # the SDK reads the signature: drop the session parameter it never sees
        sig = inspect.signature(fn)
        run.__signature__ = sig.replace(parameters=list(sig.parameters.values())[1:])
        from mcp.types import ToolAnnotations

        hints = ToolAnnotations(
            readOnlyHint=not write, destructiveHint=False, idempotentHint=False, openWorldHint=False
        )
        server.tool(annotations=hints)(run)
        return fn

    @tool
    def portfolio(db: Session) -> dict:
        """Today's portfolio: total value, cost, realized and unrealized result, and per coin
        quantity, price, value, average buy price, result and where it is held."""
        from app.modules.portfolio import api as portfolio_api

        h = portfolio_api.holdings(db)
        names = _names(db)
        items = [
            _pick(
                i,
                [
                    "asset",
                    "name",
                    "qty",
                    "price",
                    "value",
                    "cost",
                    "avg_price",
                    "realized",
                    "unrealized",
                    "unrealized_pct",
                    "income",
                    "since",
                    "days_held",
                    "fiat",
                ],
            )
            | {
                "places": [
                    {
                        "source": names.get(p["source_id"], p["source_id"]),
                        "market": p["market"],
                        "qty": p["qty"],
                    }
                    for p in i.get("places") or []
                ]
            }
            for i in h["items"]
        ]
        return {"summary": h["summary"], "coins": items}

    @tool
    def sources(db: Session) -> dict:
        """Exchanges and wallet networks: kind, provider, rows, last fetch and check, and
        current alerts (key rejected, fetch failed, history at risk)."""
        from app.modules.sources import service as sources_service

        rows = [
            _pick(
                s,
                [
                    "id",
                    "label",
                    "provider",
                    "kind",
                    "rows",
                    "last_fetch",
                    "last_check",
                    "auto_fetch",
                    "wallet_id",
                    "address",
                ],
            )
            for s in sources_service.overview(db)
        ]
        return {"sources": rows, "alerts": sources_service.alerts(db)}

    @tool
    def balance_check(db: Session) -> dict:
        """Per source: the balance computed from the transactions against the balance the
        exchange or chain reports (status ok / differences / none), with the differing coins."""
        from app.modules.balances import service as balances

        names = _names(db)
        out = []
        for e in balances.reconcile(db):
            items = e["items"]
            out.append(
                {
                    "source": names.get(e["source_id"], e["source_id"]),
                    "source_id": e["source_id"],
                    "status": e["status"],
                    "at": e["at"],
                    "differences": e["differences"],
                    "coins": [
                        _pick(i, ["asset", "market", "computed", "actual", "diff", "ok"])
                        for i in items
                        if not i.get("ok") or e["status"] != "ok"
                    ],
                }
            )
        return {"sources": out}

    @tool
    def holdings_by_source(
        db: Session,
        asset: Annotated[str | None, Field(description="Only this coin, e.g. BTC")] = None,
    ) -> dict:
        """What each source holds, per coin and market, as computed from the transactions."""
        from app.modules.balances import service as balances

        names = _names(db)
        want = asset.strip().upper() if asset else None
        out = []
        for e in balances.reconcile(db):
            for i in e["items"]:
                if (want is None or i["asset"] == want) and i.get("computed") not in (None, "0"):
                    out.append(
                        {
                            "source": names.get(e["source_id"], e["source_id"]),
                            "asset": i["asset"],
                            "market": i["market"],
                            "qty": i["computed"],
                        }
                    )
        return {"holdings": out[: MAX_ROWS * 2]}

    @tool
    def search_transactions(
        db: Session,
        date_from: Annotated[date | None, Field(description="First day (local time)")] = None,
        date_to: Annotated[date | None, Field(description="Last day (local time)")] = None,
        asset: Annotated[str | None, Field(description="Coin(s), comma separated")] = None,
        kind: Annotated[
            str | None,
            Field(description="trade, send, receive, transfer, income, fiat_deposit, fee, …"),
        ] = None,
        source_id: Annotated[str | None, Field(description="Source id(s), comma separated")] = None,
        text: Annotated[str | None, Field(description="Words in coin, id, comment, note")] = None,
        show: Annotated[
            str,
            Field(description="normal, open (no counterpart), edited, noted, spam, dust, short"),
        ] = "normal",
        limit: Annotated[int, Field(ge=1, le=MAX_ROWS)] = 50,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> dict:
        """Transactions as the transactions page lists them, newest first: one line per
        trade, deposit, withdrawal or matched transfer (send + receive)."""
        from app.modules.merged import api as merged_api

        tz = _settings(db)["general.timezone"]
        q = merged_api.ListQuery(
            date_from=date_from,
            date_to=date_to,
            asset=asset,
            kind=kind,
            source_id=source_id,
            q=text,
            show=show,
            tz=tz,
        )
        page = merged_api.merged(q, offset, limit, db)
        names = _names(db)
        return {
            "total": page["total"],
            "shown": len(page["items"]),
            "more": page["total"] > offset + len(page["items"]),
            "items": [_line(i, names) for i in page["items"]],
        }

    @tool
    def transaction(db: Session, row_id: Annotated[int, Field(description="Row id")]) -> dict:
        """One transaction row with its original raw data (masked) and its tax side (cost,
        gain, holding period) as the tax report sees it."""
        from app.modules.raw.models import RawTransaction
        from app.modules.tax import report

        r = db.get(RawTransaction, row_id)
        if r is None:
            raise AppError("raw.not_found", 404)
        row = {c.name: getattr(r, c.name) for c in RawTransaction.__table__.columns}
        row.pop("fingerprint", None)
        row["source"] = _names(db).get(r.source_id, r.source_id)
        return {"row": row, "tax": report.row_report(db, [row_id])}

    @tool
    def open_transfers(db: Session, limit: Annotated[int, Field(ge=1, le=MAX_ROWS)] = 100) -> dict:
        """Withdrawals and deposits without a counterpart (no matching receive/send found),
        and ambiguous ones with several candidates."""
        return search_transactions(db, show="open", limit=limit)

    @tool
    def prices(
        db: Session,
        asset: Annotated[str, Field(description="Coin, e.g. BTC")],
        days: Annotated[int, Field(ge=7, le=3650)] = 30,
    ) -> dict:
        """Current price and the daily closes of the last `days` days, in the display currency."""
        from app.modules.prices import api as prices_api
        from app.modules.prices import service as prices_service

        name = asset.strip().upper()
        now = prices_api.price_at(name, None, db)
        series = prices_service.history(db, name, days, _settings(db)["general.currency"])
        return {
            "now": now,
            "days": [_pick(d, ["day", "close", "high", "low"]) for d in series][-days:],
        }

    @tool
    def tax_year(
        db: Session,
        year: Annotated[int, Field(ge=2009, le=2100)],
        method: Annotated[str | None, Field(description="fifo or lifo; empty = setting")] = None,
        lines: Annotated[bool, Field(description="Also the single sales and incomes")] = False,
    ) -> dict:
        """Tax report of a year: § 23 sales gains/losses, § 22 income, Freigrenze, loss carry,
        forms; with `lines` also the single disposals and incomes (at most 200 each)."""
        from app.modules.tax import report

        rep = report.year_report(db, year, method)
        out: dict = {
            "summary": rep["summary"],
            "counts": {k: len(v) for k, v in rep["lines"].items() if isinstance(v, list)},
        }
        if lines:
            out["disposals"] = rep["lines"].get("disposals", [])[:MAX_ROWS]
            out["incomes"] = rep["lines"].get("incomes", [])[:MAX_ROWS]
        return out

    @tool
    def loss_carry(db: Session) -> dict:
        """Loss carry of § 23 per year: net result, limit, used, carried back and forward,
        and what the tax office fixed (if entered)."""
        from app.modules.tax import report

        return report.year_report(db, datetime.now(UTC).year, None)["summary"]["carry"]

    @tool
    def tax_free_soon(db: Session, days: Annotated[int, Field(ge=1, le=366)] = 90) -> dict:
        """Which coins become tax-free (one-year holding period) within `days`, and per coin
        how much is tax-free already today."""
        from app.modules.tax import report

        return {
            "upcoming": report.upcoming(db, days),
            "today": report.free_coins(db),
            "limits": report.limits(db),
        }

    @tool
    def origin(
        db: Session,
        row_id: Annotated[
            int | None, Field(description="Row of a sale/withdrawal; empty = today's holdings")
        ] = None,
        asset: Annotated[str | None, Field(description="With no row: only this coin")] = None,
    ) -> dict:
        """Source of funds: where the money of a sale, transfer or withdrawal (or of today's
        holdings) came from — bank, card, gains, income, … with shares and deposits."""
        from app.modules.tax import origin as origin_service

        data = (
            origin_service.explain(db, row_id)
            if row_id
            else origin_service.holdings(db, None, asset.strip().upper() if asset else None)
        )
        out = _pick(data, ["target", "method", "mix", "overview", "lost"])
        out["deposits"] = (data.get("deposits") or [])[:MAX_ROWS]
        return out

    @tool
    def origin_candidates(
        db: Session, limit: Annotated[int, Field(ge=1, le=MAX_ROWS)] = 50
    ) -> dict:
        """Sales, transfers and withdrawals one can trace (newest first), with their row ids."""
        from app.modules.tax import origin as origin_service

        rows = origin_service.candidates(db, None)
        return {"total": len(rows), "items": rows[:limit]}

    @tool
    def system_status(db: Session) -> dict:
        """Version, uptime, database, schema, last backup, fetch and price runs, disk."""
        from app.modules.system import service as system_service

        started = app.state.started_at
        return {
            "version": app_version(),
            "uptime_seconds": int((datetime.now(UTC) - started).total_seconds()),
            "operations": system_service.operations(db),
            "log_level": logs.level(),
        }

    @tool
    def log_excerpt(
        db: Session,
        level: Annotated[
            str, Field(description="DEBUG, INFO, WARNING or ERROR (and above)")
        ] = "WARNING",
        limit: Annotated[int, Field(ge=1, le=MAX_ROWS)] = 50,
    ) -> dict:
        """The latest lines of the app log (backend and browser), from `level` up."""
        rank = {n: i for i, n in enumerate(logs.LEVELS)}
        floor = rank.get(level.upper(), 2)
        lines = [
            x
            for x in logs.ring.since(0, logs.SIZE)
            if rank.get(x["level"], 3) >= floor and x["logger"] != "mcp"
        ]
        return {"lines": lines[-limit:]}

    _edit_tools(tool)

    http = server.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        # reached by IP in the LAN; the token, not the host name, is the protection
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        host="0.0.0.0",
    )
    return server, _gateway(app, http)


# --- stage 2: plans the user confirms as a whole -----------------------------------------

PLAN_NOTE = (
    " Returns a preview: every item with its current state and whether it will apply, and a "
    "plan_id. Nothing is changed yet. Show the user the COMPLETE list and call apply_plan "
    "only after their explicit OK. Needs a token with the level 'Bearbeiten' (edit) in "
    "owncryptofolio."
)


class Pair(BaseModel):
    send_id: int
    receive_id: int


class NoteItem(BaseModel):
    row_id: int
    text: str | None = Field(None, description="Empty or null removes the note", max_length=500)


class MarkItem(BaseModel):
    row_id: int
    mark: Literal["external", "own_untracked", "lost", "bought", "income"] | None = Field(
        None,
        description="send: external, own_untracked, lost; receive: own_untracked, bought, "
        "income; null removes the mark",
    )
    note: str | None = Field(None, max_length=300)


class NewEntry(BaseModel):
    source_id: int
    entry: EntryIn


class Correction(BaseModel):
    row_id: int
    entry: EntryIn


def _edit_tools(tool: Callable) -> None:
    from app.modules.mcp import edit

    def plan(action: str, items: list) -> dict:
        dumped = [i.model_dump(mode="json") if isinstance(i, BaseModel) else i for i in items]
        return edit.plan(action, dumped, token_name.get())

    @tool(write=True)
    def plan_link_transfers(
        db: Session, pairs: Annotated[list[Pair], Field(min_length=1, max_length=50)]
    ) -> dict:
        """Plan: join withdrawals (send) and deposits (receive) as transfers between own
        accounts."""
        return plan("link_transfers", pairs)

    @tool(write=True)
    def plan_split_transfers(
        db: Session, pairs: Annotated[list[Pair], Field(min_length=1, max_length=50)]
    ) -> dict:
        """Plan: undo transfers (send and receive count as separate again)."""
        return plan("split_transfers", pairs)

    @tool(write=True)
    def plan_notes(
        db: Session, items: Annotated[list[NoteItem], Field(min_length=1, max_length=50)]
    ) -> dict:
        """Plan: set or remove the note of transactions."""
        return plan("notes", items)

    @tool(write=True)
    def plan_open_marks(
        db: Session, items: Annotated[list[MarkItem], Field(min_length=1, max_length=50)]
    ) -> dict:
        """Plan: mark withdrawals/deposits without counterpart (to someone else, own account
        not tracked, lost; bought, income) or remove the mark."""
        return plan("open_marks", items)

    @tool(write=True)
    def plan_spam(
        db: Session,
        row_ids: Annotated[list[int], Field(min_length=1, max_length=50)],
        spam: Annotated[bool, Field(description="true hides as spam, false shows again")],
    ) -> dict:
        """Plan: hide rows as spam (scam tokens) or show them again."""
        return plan("spam", [{"row_id": r, "spam": spam} for r in row_ids])

    @tool(write=True)
    def plan_hide_rows(
        db: Session, row_ids: Annotated[list[int], Field(min_length=1, max_length=50)]
    ) -> dict:
        """Plan: hide transactions (they stay stored and can be restored; nothing is
        deleted)."""
        return plan("hide_rows", [{"row_id": r} for r in row_ids])

    @tool(write=True)
    def plan_restore_rows(
        db: Session, row_ids: Annotated[list[int], Field(min_length=1, max_length=50)]
    ) -> dict:
        """Plan: make a hidden or replaced version of a transaction the valid one again
        (also "reset a correction to the original")."""
        return plan("restore_rows", [{"row_id": r} for r in row_ids])

    @tool(write=True)
    def plan_add_entries(
        db: Session, items: Annotated[list[NewEntry], Field(min_length=1, max_length=50)]
    ) -> dict:
        """Plan: new manual entries at a source (time is local time of the app's time zone,
        "YYYY-MM-DDTHH:MM[:SS]"; amounts as text). The preview also shows how the holdings
        change per coin."""
        return plan("add_entries", items)

    @tool(write=True)
    def plan_correct_rows(
        db: Session, items: Annotated[list[Correction], Field(min_length=1, max_length=50)]
    ) -> dict:
        """Plan: correct transactions. The original stays stored; the corrected version is a
        manual row that replaces it (undo with plan_restore_rows on the original id). The
        preview also shows how the holdings change per coin."""
        return plan("correct_rows", items)

    @tool(write=True)
    def apply_plan(
        db: Session,
        plan_id: Annotated[str, Field(description="From a plan_* tool")],
        only: Annotated[
            list[int] | None,
            Field(
                description="Numbers (n) of the preview to carry out, as the user chose; "
                "empty = all"
            ),
        ] = None,
    ) -> dict:
        """Carry out a plan the user has confirmed: the previewed items (or the chosen part
        of them), nothing else. Items skipped in the preview stay skipped. One use per plan."""
        return edit.apply(plan_id, token_name.get(), _db, only)

    @tool(write=True)
    def start_fetch(
        db: Session,
        source_ids: Annotated[
            list[int], Field(min_length=1, max_length=50, description="Sources to fetch")
        ],
    ) -> dict:
        """Start fetching sources (API or chain) in the background now; changes no decision,
        only reads new rows. See sources/system_status for the result."""
        from app.modules.jobs import service as jobs

        return {"jobs": [jobs.job_dict(jobs.enqueue(db, "fetch", sid)) for sid in source_ids]}


def _line(i: dict, names: dict[int, str]) -> dict:
    """One line of the transactions list, compact."""

    def row(r: dict) -> dict:
        out = {
            "id": r["id"],
            "at": r["timestamp"],
            "source": names.get(r["source_id"], r["source_id"]),
            "kind": r["kind"],
            "market": r["market"],
        }
        for side in ("incoming", "outgoing", "fee"):
            asset, amount = (r.get(side) or [None, None])[:2]
            if asset:
                out[side] = f"{amount} {asset}"
        for k in ("income_kind", "comment", "note", "counterparty", "external_id"):
            if r.get(k):
                out[k] = r[k]
        if r.get("values"):
            out["values"] = r["values"]
        if r.get("modified") or r.get("edited"):
            out["edited"] = True
        return out

    if i["type"] == "transfer":
        return {
            "type": "transfer",
            "at": i["at"],
            "send": row(i["send"]),
            "receive": row(i["receive"]),
            "network_fee": i.get("network_fee"),
        }
    if i["type"] == "position":
        return {"type": "position", "at": i["at"], "rows": [row(r) for r in i.get("rows", [])][:20]}
    out = {"type": "row", **row(i["row"])}
    for flag in ("open", "ambiguous", "spam", "dust"):
        if i.get(flag):
            out[flag] = True
    if i.get("result"):
        out["result"] = i["result"]
    return out


def _gateway(app, http) -> Callable:
    """Token and mode first; only then the SDK. Answers in plain JSON-RPC-free errors."""

    async def gate(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await http(scope, receive, send)
        if not app.state.ready:
            return await JSONResponse({"error": "db.unavailable"}, 503)(scope, receive, send)
        auth = dict(scope["headers"]).get(b"authorization", b"").decode()
        plain = auth[7:].strip() if auth.lower().startswith("bearer ") else None
        with _db() as db:
            on = service.enabled(db, "mcp")
            row = service.verify(db, plain, "mcp")
            name, level = (row.name, row.level) if row else (None, "read")
        if row is None:
            log.warning("refused: no valid token")
            return await JSONResponse(
                {"error": "mcp.token_invalid"}, 401, headers={"WWW-Authenticate": "Bearer"}
            )(scope, receive, send)
        if not on:
            return await JSONResponse({"error": "mcp.off"}, 403)(scope, receive, send)
        token_name.set(name)
        token_level.set(level)
        await http(scope, receive, send)

    class Gate:  # an object, not a function: Starlette routes it as a plain ASGI app
        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            await gate(scope, receive, send)

    return Gate()
