"""Tax (ADR 0042): the report of a year, kept reports, Excel/PDF, holding periods."""

import re
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.modules.settings import service as settings_service
from app.modules.tax import carry, files, origin, origin_files, report

router = APIRouter(prefix="/api/tax", tags=["tax"])

Method = Query(None, pattern="^(fifo|lifo)$")
MEDIA = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


@router.get("/years")
def years(db: Session = Depends(get_session)) -> list[int]:
    return report.years(db)


@router.get("/limits")
def limits(db: Session = Depends(get_session)) -> dict:
    return report.limits(db)


@router.get("/upcoming")
def upcoming(days: int = Query(30, ge=1, le=366), db: Session = Depends(get_session)) -> list[dict]:
    return report.upcoming(db, days)


@router.get("/holdings")
def holdings(db: Session = Depends(get_session)) -> dict:
    return report.holdings(db)


@router.get("/free")
def free(db: Session = Depends(get_session)) -> dict:
    """Per coin today: tax-free and not yet, with values in the display currency."""
    return report.free_coins(db)


class CarryIn(BaseModel):
    amount: Decimal | None = None
    note: str | None = None


@router.put("/carry/{year}", status_code=204)
def set_carry(year: int, body: CarryIn, db: Session = Depends(get_session)) -> None:
    """The loss carry the tax office fixed for the end of `year`; null removes it."""
    carry.set_assessed(db, year, body.amount, body.note)


@router.get("/origin")
def origin_list(method: str | None = Method, db: Session = Depends(get_session)) -> list[dict]:
    """Sales, transfers and withdrawals one can trace the money of (ADR 0046)."""
    return origin.candidates(db, method)


@router.get("/origin/holdings")
def origin_holdings(
    asset: str | None = None, method: str | None = Method, db: Session = Depends(get_session)
) -> dict:
    """Where today's holdings came from, all or one coin (ADR 0046)."""
    return origin.holdings(db, method, asset)


@router.get("/origin/holdings/file")
def origin_holdings_file(
    kind: str = Query(..., pattern="^(xlsx|pdf)$"),
    asset: str | None = None,
    method: str | None = Method,
    db: Session = Depends(get_session),
) -> Response:
    data = origin.holdings(db, method, asset)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "", asset or "")  # into a header: plain characters only
    name = f"mittelherkunft-bestand-{data['target']['at'][:10]}{'-' + safe if safe else ''}"
    return _origin_response(db, data, kind, name)


@router.get("/origin/planned/options")
def origin_planned_options(method: str | None = Method, db: Session = Depends(get_session)):
    """What a planned step can take: per source and coin the quantity held now."""
    return origin.planned_options(db, method)


@router.get("/origin/planned")
def origin_planned(
    source: int,
    asset: str,
    qty: Decimal,
    day: date | None = None,
    method: str | None = Method,
    db: Session = Depends(get_session),
) -> dict:
    """The source of funds of a step not done yet (ADR 0046): nothing is booked."""
    return origin.planned(db, source, asset, qty, day, method)


@router.get("/origin/planned/file")
def origin_planned_file(
    source: int,
    asset: str,
    qty: Decimal,
    kind: str = Query(..., pattern="^(xlsx|pdf)$"),
    day: date | None = None,
    method: str | None = Method,
    db: Session = Depends(get_session),
) -> Response:
    data = origin.planned(db, source, asset, qty, day, method)
    return _origin_response(db, data, kind, f"mittelherkunft-geplant-{data['target']['at'][:10]}")


@router.get("/origin/{row}")
def origin_one(row: int, method: str | None = Method, db: Session = Depends(get_session)) -> dict:
    return origin.explain(db, row, method)


@router.get("/origin/{row}/file")
def origin_file(
    row: int,
    kind: str = Query(..., pattern="^(xlsx|pdf)$"),
    method: str | None = Method,
    db: Session = Depends(get_session),
) -> Response:
    data = origin.explain(db, row, method)
    return _origin_response(db, data, kind, f"mittelherkunft-{data['target']['at'][:10]}-{row}")


def _origin_response(db: Session, data: dict, kind: str, name: str) -> Response:
    s = settings_service.all_settings(db)
    if kind == "xlsx":
        body = origin_files.xlsx(data)
    else:
        body = origin_files.pdf(data, (s["report.name"].strip(), s["report.address"].strip()))
    return Response(
        body,
        media_type=MEDIA[kind],
        headers={"Content-Disposition": f'attachment; filename="{name}.{kind}"'},
    )


@router.get("/rows")
def rows(ids: str = Query(..., pattern=r"^\d+(,\d+)*$"), db: Session = Depends(get_session)):
    """The tax side of one transaction (a transfer passes send, receive and fees)."""
    return report.row_report(db, [int(i) for i in ids.split(",")][:50])


@router.get("/{year}")
def year_report(year: int, method: str | None = Method, db: Session = Depends(get_session)):
    rep = report.year_report(db, year, method)
    return rep | {"frozen": report.frozen(db, year)}


@router.post("/{year}/freeze")
def freeze(
    year: int,
    method: str | None = Method,
    note: str | None = Body(None, embed=True),
    db: Session = Depends(get_session),
) -> dict:
    return report.freeze(db, year, method, note)


@router.patch("/kept/{report_id}")
def kept_note(
    report_id: int, note: str | None = Body(None, embed=True), db: Session = Depends(get_session)
) -> dict:
    return report.kept_note(db, report_id, note)


@router.delete("/kept/{report_id}", status_code=204)
def kept_delete(report_id: int, db: Session = Depends(get_session)) -> None:
    report.kept_delete(db, report_id)


@router.get("/kept/{report_id}/file")
def kept_file(
    report_id: int,
    kind: str = Query(..., pattern="^(xlsx|pdf)$"),
    db: Session = Depends(get_session),
) -> Response:
    body, name = report.kept_file(db, report_id, kind)
    return Response(
        body,
        media_type=MEDIA[kind],
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/{year}/compare")
def compare(year: int, a: int, b: int | None = None, db: Session = Depends(get_session)):
    return report.compare(db, year, a, b)


@router.get("/{year}/file")
def file(
    year: int,
    kind: str = Query(..., pattern="^(xlsx|pdf)$"),
    method: str | None = Method,
    db: Session = Depends(get_session),
) -> Response:
    rep = report.year_report(db, year, method)
    m = rep["summary"]["method"]
    name = f"steuer-{year}-{m}.{kind}"
    if kind == "xlsx":
        body = files.xlsx(rep)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        body, media = files.pdf(rep), "application/pdf"
    return Response(
        body, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'}
    )
