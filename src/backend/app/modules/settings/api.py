from typing import Any

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.modules.settings import service

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def read(db: Session = Depends(get_session)) -> dict[str, Any]:
    return service.all_settings(db)


@router.patch("")
def update(changes: dict[str, Any] = Body(...), db: Session = Depends(get_session)) -> dict:
    return service.update(db, changes)


@router.get("/schema")
def schema() -> dict[str, Any]:
    return service.schema()
