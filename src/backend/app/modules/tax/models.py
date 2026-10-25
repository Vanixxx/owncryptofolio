"""A tax report kept as it was made (ADR 0012/0042): day, method, parameters and result. A
later pass that comes out different is reported, never silently recomputed away."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Integer, LargeBinary, Numeric, String, func
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.core.db import Base


class TaxReport(Base):
    __tablename__ = "tax_report"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    method: Mapped[str] = mapped_column(String(10))
    digest: Mapped[str] = mapped_column(String(64))
    """sha256 over every line of the report: equal means nothing changed."""
    summary: Mapped[dict] = mapped_column(JSON)
    lines: Mapped[dict | None] = mapped_column(JSON)
    """Every line as it was: what a later comparison shows line by line."""
    xlsx: Mapped[bytes | None] = deferred(mapped_column(LargeBinary))
    pdf: Mapped[bytes | None] = deferred(mapped_column(LargeBinary))
    """The files as they were handed out: a later version of the app may lay them out
    differently, the kept document stays the same (Vanixxx, 2026-10-13)."""
    note: Mapped[str | None] = mapped_column(String(200))
    """Vanixxx's word on it, e.g. "an den Steuerberater"."""


class TaxLossAssessed(Base):
    """The loss carry-forward of § 23 as the tax office fixed it for the end of a year
    (Feststellungsbescheid, ADR 0045). It wins over the computed one; a year before the
    first one with data holds the carry from earlier years."""

    __tablename__ = "tax_loss_assessed"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    note: Mapped[str | None] = mapped_column(String(200))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
