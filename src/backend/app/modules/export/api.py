"""Downloads: transactions as listed, holdings — Excel or CSV."""

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.modules.export import service
from app.modules.merged import service as merged
from app.modules.merged.api import ListQuery, select_items
from app.modules.portfolio import service as portfolio
from app.modules.prices.service import Valuer
from app.modules.settings import service as settings_service
from app.modules.sources.models import Source, Wallet

router = APIRouter(prefix="/api/export", tags=["export"])
TYPES = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _names(db: Session):
    wallets = dict(db.execute(select(Wallet.id, Wallet.name)).all())
    sources = {s.id: s for s in db.scalars(select(Source))}

    def name(source_id: int | None) -> str:
        s = sources.get(source_id)
        if s is None:
            return ""
        w = wallets.get(s.wallet_id)
        return f"{w} – {s.label}" if w else s.label

    return name


def _file(
    kind: str, fmt: str, sheet: str, header: list[str], rows: list[list], lang: str
) -> Response:
    body = (
        service.to_xlsx(sheet, header, rows)
        if fmt == "xlsx"
        else service.to_csv(header, rows, lang)
    )
    day = datetime.now(UTC).date().isoformat()
    return Response(
        body,
        media_type=TYPES[fmt],
        headers={
            "Content-Disposition": f'attachment; filename="owncryptofolio-{kind}-{day}.{fmt}"'
        },
    )


@router.get("/transactions")
def transactions(
    q: ListQuery = Depends(),
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    db: Session = Depends(get_session),
) -> Response:
    settings = settings_service.all_settings(db)
    lang, cur, tz = (
        settings["general.language"],
        settings["general.currency"],
        settings["general.timezone"],
    )
    view, _, items = select_items(db, q)
    valuer = Valuer(db)
    eur = merged.item_values(db, view, items)
    values = {}
    for i in items:
        if id(i) in eur:
            v = valuer.in_currency(eur[id(i)], datetime.fromisoformat(i["at"]).date(), cur)
            values[id(i)] = None if v is None else v.quantize(Decimal("0.01"))
    L = service.LABELS[lang if lang in service.LABELS else "de"]
    header = [h.format(cur=cur) for h in L["tx"]]
    rows = service.transaction_rows(
        items, values, _names(db), lang if lang in service.LABELS else "de", tz
    )
    return _file(
        "transaktionen" if lang == "de" else "transactions",
        format,
        L["sheet_tx"],
        header,
        rows,
        lang,
    )


@router.get("/holdings")
def holdings(
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"), db: Session = Depends(get_session)
) -> Response:
    settings = settings_service.all_settings(db)
    lang, cur = settings["general.language"], settings["general.currency"]
    lang = lang if lang in service.LABELS else "de"
    L = service.LABELS[lang]
    data = portfolio.holdings(db, cur)
    header = [h.format(cur=cur) for h in L["holdings"]]
    rows = service.holding_rows(data["items"], _names(db), lang)
    return _file(
        "bestaende" if lang == "de" else "holdings", format, L["sheet_holdings"], header, rows, lang
    )
