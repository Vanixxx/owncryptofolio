"""Tokens for Claude's access through MCP (ADR 0049): only a hash is kept."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class McpToken(Base):
    __tablename__ = "mcp_token"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)  # sha256, hex
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    kind: Mapped[str] = mapped_column(String(10), default="mcp", server_default="mcp")
    """"mcp" (Claude) or "api" (/api/v1): a token opens only its own door (Vanixxx, 2026-10-20)."""
    level: Mapped[str] = mapped_column(String(10), default="read", server_default="read")
    """MCP only: "read" or "edit" — per token, not for all (Vanixxx, 2026-10-20)."""


class McpChange(Base):
    """One change Claude made (ADR 0049, stage 2): which plan, which rows, with what result.
    The transactions page filters on the rows ("changed by Claude")."""

    __tablename__ = "mcp_change"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    token: Mapped[str] = mapped_column(String(80))
    plan_id: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(40))
    item: Mapped[dict] = mapped_column(JSON)
    row_ids: Mapped[list] = mapped_column(JSON)
    ok: Mapped[bool] = mapped_column(Boolean)
    message: Mapped[str | None] = mapped_column(Text)
