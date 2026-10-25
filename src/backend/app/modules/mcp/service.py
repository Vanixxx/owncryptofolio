"""Tokens for Claude (MCP) and the JSON API (ADR 0049/0050): apart from the web login, shown
once, kept as a hash. Each token belongs to one door (`kind`); an MCP token also carries its
level (read or edit). Each door has its own on/off switch."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.mcp.models import McpToken
from app.modules.settings import service as settings_service

PREFIXES = {"mcp": "ocf_mcp_", "api": "ocf_api_"}
KINDS = ("mcp", "api")
LEVELS = ("read", "edit")
TOUCH = timedelta(minutes=1)  # "last used" is written at most once a minute

last_call: dict = {}
"""The latest call (in memory): tool, token, time — for the settings and system pages."""


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def enabled(session: Session, kind: str) -> bool:
    return bool(settings_service.all_settings(session)[f"{kind}.enabled"])


def tokens(session: Session) -> list[dict]:
    return [
        {
            "id": t.id,
            "name": t.name,
            "kind": t.kind,
            "level": t.level if t.kind == "mcp" else "read",
            "created_at": t.created_at.isoformat(),
            "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
        }
        for t in session.scalars(select(McpToken).order_by(McpToken.id))
    ]


def create(session: Session, name: str, kind: str = "mcp", level: str = "read") -> dict:
    name = name.strip()
    if not name:
        raise AppError("mcp.name_required", 400)
    if kind not in KINDS or level not in LEVELS or (kind == "api" and level != "read"):
        raise AppError("mcp.token_invalid_kind", 400)
    plain = PREFIXES[kind] + secrets.token_urlsafe(32)
    row = McpToken(name=name[:80], token_hash=_hash(plain), kind=kind, level=level)
    session.add(row)
    session.commit()
    return {"id": row.id, "name": row.name, "kind": kind, "level": level, "token": plain}


def set_level(session: Session, token_id: int, level: str) -> None:
    row = session.get(McpToken, token_id)
    if row is None:
        raise AppError("mcp.token_not_found", 404)
    if row.kind != "mcp" or level not in LEVELS:
        raise AppError("mcp.token_invalid_kind", 400)
    row.level = level
    session.commit()


def revoke(session: Session, token_id: int) -> None:
    row = session.get(McpToken, token_id)
    if row is None:
        raise AppError("mcp.token_not_found", 404)
    session.delete(row)
    session.commit()


def verify(session: Session, plain: str | None, kind: str) -> McpToken | None:
    """The token, if it is one for this door."""
    if not plain or not plain.startswith(PREFIXES[kind]):
        return None
    row = session.scalar(
        select(McpToken).where(McpToken.token_hash == _hash(plain), McpToken.kind == kind)
    )
    if row is not None:
        now = datetime.now(UTC)
        if row.last_used_at is None or now - row.last_used_at > TOUCH:
            row.last_used_at = now
            session.commit()
    return row
