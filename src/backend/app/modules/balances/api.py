"""Balance check (ADR 0039)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.modules.balances import service

router = APIRouter(prefix="/api/balances", tags=["balances"])


class ManualIn(BaseModel):
    asset: str
    amount: str
    market: str = "spot"


@router.get("")
def balances(db: Session = Depends(get_session)) -> list[dict]:
    return service.reconcile(db)


@router.post("/{source_id}", status_code=204)
def manual(source_id: int, body: ManualIn, db: Session = Depends(get_session)) -> None:
    service.set_manual(db, source_id, body.asset, body.amount, body.market)
