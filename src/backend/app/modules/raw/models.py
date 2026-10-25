"""The raw layer — untouchable (ADR 0001). Two sided (ADR 0011), futures aware (ADR 0029)."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# 38 digits, 18 after the point: covers wei and every fiat currency. Never float.
Amount = Numeric(38, 18)


class ImportRun(Base):
    """One import: a file, an API fetch or a chain fetch. The unit of revert."""

    __tablename__ = "import_run"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("source.id", ondelete="RESTRICT"))
    channel: Mapped[str] = mapped_column(String(20))
    label: Mapped[str] = mapped_column(String(300))  # file name or "API"
    original_file: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="done")
    read: Mapped[int] = mapped_column(Integer, default=0)
    added: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    rejected: Mapped[int] = mapped_column(Integer, default=0)
    # rows the source delivered again with other values: held back for Vanixxx (2026-10-23)
    changed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    problems: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    data_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RawTransaction(Base):
    """A row as the source delivered it. Never changed after insert (ADR 0001, 0021)."""

    __tablename__ = "raw_transaction"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("source.id", ondelete="RESTRICT"))
    channel: Mapped[str] = mapped_column(String(20))
    import_run_id: Mapped[int] = mapped_column(ForeignKey("import_run.id", ondelete="RESTRICT"))

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    kind: Mapped[str] = mapped_column(String(30))
    income_kind: Mapped[str | None] = mapped_column(String(20))
    market: Mapped[str] = mapped_column(String(10), default="spot")

    incoming_asset: Mapped[str | None] = mapped_column(String(40))
    incoming_amount: Mapped[Decimal | None] = mapped_column(Amount)
    outgoing_asset: Mapped[str | None] = mapped_column(String(40))
    outgoing_amount: Mapped[Decimal | None] = mapped_column(Amount)
    fee_asset: Mapped[str | None] = mapped_column(String(40))
    fee_amount: Mapped[Decimal | None] = mapped_column(Amount)

    external_id: Mapped[str | None] = mapped_column(String(200))
    fingerprint: Mapped[str] = mapped_column(String(64))
    comment: Mapped[str | None] = mapped_column(Text)
    counterparty: Mapped[str | None] = mapped_column(String(200))
    instrument: Mapped[str | None] = mapped_column(String(60))
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        # Duplicate lock in the database: safer than a check in code under parallel runs.
        UniqueConstraint("source_id", "channel", "fingerprint", name="uq_raw_fingerprint"),
        Index("ix_raw_source_time", "source_id", "timestamp"),
        Index("ix_raw_run", "import_run_id"),
        Index("ix_raw_incoming", "incoming_asset", "timestamp"),
        Index("ix_raw_outgoing", "outgoing_asset", "timestamp"),
    )


class RawRetraction(Base):
    """A manual raw row that was edited or deleted (ADR 0036).

    The row itself stays untouched (ADR 0001); this note says it no longer counts.
    `replaced_by_id` points to the new version of an edit, NULL for a deletion.
    Only rows of the channel `manual` are ever retracted.
    """

    __tablename__ = "raw_retraction"

    raw_id: Mapped[int] = mapped_column(
        ForeignKey("raw_transaction.id", ondelete="RESTRICT"), primary_key=True
    )
    replaced_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("raw_transaction.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceChange(Base):
    """A row the source delivered again with other values (Vanixxx, 2026-10-23): same id,
    time and kind, other amounts. Not added on its own; Vanixxx takes it over (the new row
    replaces the old, which stays stored, ADR 0001) or keeps the old one."""

    __tablename__ = "raw_source_change"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    raw_id: Mapped[int] = mapped_column(ForeignKey("raw_transaction.id", ondelete="RESTRICT"))
    import_run_id: Mapped[int] = mapped_column(ForeignKey("import_run.id", ondelete="CASCADE"))
    fingerprint: Mapped[str] = mapped_column(String(64))
    movement: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(10), default="open")  # open | taken | kept
    replaced_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("raw_transaction.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("raw_id", "fingerprint"),)


def current():
    """Filter for rows that still count: not retracted (ADR 0036)."""
    from sqlalchemy import select

    return RawTransaction.id.not_in(select(RawRetraction.raw_id))


from app.modules.raw.guard import activate  # noqa: E402

# Activated at import time: whoever imports RawTransaction — app, test or ad-hoc
# script — gets the guard. There is no way to the class without it.
activate(RawTransaction)
