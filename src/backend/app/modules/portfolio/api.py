"""Portfolio (ADR 0040): holdings and P/L, daily history, gap search, futures positions."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.modules.portfolio import service
from app.modules.settings import service as settings_service

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def _currency(db: Session) -> str:
    return settings_service.all_settings(db)["general.currency"]


@router.get("")
def holdings(db: Session = Depends(get_session)) -> dict:
    return service.holdings(db, _currency(db))


@router.get("/history")
def history(db: Session = Depends(get_session)) -> list[dict]:
    return service.history(db, _currency(db))


@router.get("/ticks")
def ticks(
    hours: int = Query(24, ge=1, le=24 * 90), db: Session = Depends(get_session)
) -> list[dict]:
    return service.ticks(db, hours, _currency(db))


@router.get("/dca/{asset}")
def dca(asset: str, db: Session = Depends(get_session)) -> list[dict]:
    return service.dca(db, asset, _currency(db))


@router.get("/balance-at")
def balance_at(
    source_id: int,
    asset: str,
    at: str,
    market: str = Query("spot", pattern="^(spot|futures)$"),
    skip: int | None = None,
    db: Session = Depends(get_session),
) -> dict:
    """The balance of one coin at one source at a moment, before a row being edited. The
    moment as the form has it, local time in the configured zone, or with an offset."""
    from app.modules.manual.service import local_time

    when = local_time(at, settings_service.all_settings(db)["general.timezone"])
    return {"amount": service._q(service.balance_at(db, source_id, market, asset, when, skip))}


@router.get("/gaps")
def gaps(db: Session = Depends(get_session)) -> list[dict]:
    return service.gaps(db, _currency(db))


@router.get("/futures")
def futures(db: Session = Depends(get_session)) -> list[dict]:
    return service.futures_positions(db, _currency(db))
