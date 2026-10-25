"""Settings side of MCP and the JSON API: tokens and the state for the settings and system
pages."""

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.modules.mcp import service

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


@router.get("")
def status(db: Session = Depends(get_session)) -> dict:
    return {
        "enabled": service.enabled(db, "mcp"),
        "api_enabled": service.enabled(db, "api"),
        "tokens": service.tokens(db),
        "last_call": service.last_call or None,
    }


@router.post("/tokens", status_code=201)
def create(
    name: str = Body(..., embed=True),
    kind: str = Body("mcp", embed=True),
    level: str = Body("read", embed=True),
    db: Session = Depends(get_session),
) -> dict:
    """The token in plain text, this one time only."""
    return service.create(db, name, kind, level)


@router.patch("/tokens/{token_id}", status_code=204)
def set_level(
    token_id: int, level: str = Body(..., embed=True), db: Session = Depends(get_session)
) -> None:
    """Claude with this token: read only, or also edit."""
    service.set_level(db, token_id, level)


@router.delete("/tokens/{token_id}", status_code=204)
def revoke(token_id: int, db: Session = Depends(get_session)) -> None:
    service.revoke(db, token_id)
