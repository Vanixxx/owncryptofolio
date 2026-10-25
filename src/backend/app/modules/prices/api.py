"""Prices page (ADR 0019): mappings to check, confirm and change, series, cross-check."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.modules.prices import service
from app.modules.settings import service as settings_service

router = APIRouter(prefix="/api/prices", tags=["prices"])


class SourceIn(BaseModel):
    source: str
    ticker: str


class MappingIn(BaseModel):
    name: str | None = None
    sources: list[SourceIn]
    reason: str | None = None
    icon: str | None = None


class AliasIn(BaseModel):
    target: str
    name: str | None = None
    reason: str | None = None


class IgnoreIn(BaseModel):
    ignored: bool
    reason: str | None = None


@router.get("/assets")
def assets(db: Session = Depends(get_session)) -> list[dict]:
    return service.overview(db, _currency(db))


@router.get("/sparks")
def sparks(
    span: str = Query("d90", pattern="^(d1|h24|d7|d30|d90)$"), db: Session = Depends(get_session)
) -> dict[str, list[str]]:
    return service.sparks(db, span, _currency(db))


def _currency(db: Session) -> str:
    return settings_service.all_settings(db)["general.currency"]


@router.put("/assets/{asset}", status_code=204)
def update(asset: str, body: MappingIn, db: Session = Depends(get_session)) -> None:
    service.update_mapping(
        db, asset, body.name, [(s.source, s.ticker) for s in body.sources], body.reason, body.icon
    )


@router.post("/assets/{asset}/confirm", status_code=204)
def confirm(asset: str, db: Session = Depends(get_session)) -> None:
    service.confirm(db, asset)


@router.post("/assets/{asset}/ignore", status_code=204)
def ignore(asset: str, body: IgnoreIn, db: Session = Depends(get_session)) -> None:
    service.set_ignored(db, asset, body.ignored, body.reason)


class UntilIn(BaseModel):
    until: date | None = None
    reason: str | None = None


class WorthlessIn(BaseModel):
    since: date | None = None
    reason: str | None = None


@router.post("/assets/{asset}/until", status_code=204)
def until(asset: str, body: UntilIn, db: Session = Depends(get_session)) -> None:
    service.set_prices_until(db, asset, body.until, body.reason)


@router.post("/assets/{asset}/worthless", status_code=204)
def worthless(asset: str, body: WorthlessIn, db: Session = Depends(get_session)) -> None:
    service.set_worthless(db, asset, body.since, body.reason)


@router.post("/assets/{asset}/fetch")
def fetch_one(asset: str, db: Session = Depends(get_session)) -> dict:
    """Fetch this one coin's prices now (history gaps and today's price)."""
    return service.run_one(db, asset)


@router.get("/assets/{asset}/history")
def history(
    asset: str, days: int = Query(365, ge=7, le=10000), db: Session = Depends(get_session)
) -> list[dict]:
    return service.history(db, asset, days, _currency(db))


@router.get("/assets/{asset}/changes")
def changes(asset: str, db: Session = Depends(get_session)) -> list[dict]:
    return service.changes(db, asset)


@router.get("/assets/{asset}/crosscheck")
def crosscheck(asset: str, db: Session = Depends(get_session)) -> dict:
    return service.crosscheck(db, asset)


@router.post("/assets/{asset}/alias", status_code=204)
def alias(asset: str, body: AliasIn, db: Session = Depends(get_session)) -> None:
    """This symbol is the same coin as `target` (MEXC NTGL = Bitget NGL = Entangle)."""
    service.set_alias(db, asset, body.target, body.name, body.reason)


@router.delete("/aliases/{alias}", status_code=204)
def remove_alias(alias: str, db: Session = Depends(get_session)) -> None:
    service.remove_alias(db, alias)


@router.post("/resuggest", status_code=200)
def resuggest(db: Session = Depends(get_session)) -> dict:
    """New suggestions for unconfirmed coins after the default order changed; the next
    price run fetches them."""
    return {"assets": service.resuggest_unconfirmed(db)}


@router.post("/live")
def live(db: Session = Depends(get_session)) -> dict:
    """While the prices page is open: refresh (throttled) and return the current prices."""
    service.refresh_live(db)
    return service.live_prices(db, _currency(db))


@router.get("/at")
def price_at(asset: str, at: str | None = None, db: Session = Depends(get_session)) -> dict:
    """One coin's market price at a moment, in the display currency — the entry form shows
    it under the coin (Vanixxx, 2026-10-13). No moment: the current price."""
    from datetime import UTC, datetime

    from app.modules.manual.service import local_time
    from app.modules.portfolio.service import _cached

    s = settings_service.all_settings(db)
    currency = s["general.currency"]
    valuer = _cached(db, "valuer", lambda: service.Valuer(db))
    name = asset.strip().upper()
    if at:
        day = local_time(at, s["general.timezone"]).astimezone(UTC).date()
        eur = valuer.eur(name, day)
    else:
        day = datetime.now(UTC).date()
        eur = valuer.latest_eur(name, day)
    price = valuer.in_currency(eur, day, currency)
    return {
        "asset": name,
        "price": None if price is None else f"{price.normalize():f}",
        "currency": currency,
        "day": day.isoformat(),
        "latest": not at,
    }
