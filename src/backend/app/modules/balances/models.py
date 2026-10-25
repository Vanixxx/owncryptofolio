"""Account balances as the source reports them (ADR 0039): taken with every fetch, or
entered by hand for exchanges without connection. Derived (ADR 0001), the source of truth
for the comparison against the balance computed from the transactions."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class BalanceSnapshot(Base):
    __tablename__ = "balance_snapshot"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("source.id", ondelete="CASCADE"))
    market: Mapped[str] = mapped_column(String(10), default="spot")
    asset: Mapped[str] = mapped_column(String(40))
    amount: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    origin: Mapped[str] = mapped_column(String(10))  # api | chain | manual
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_balance_source_asset", "source_id", "market", "asset", "at"),)
