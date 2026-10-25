"""The portfolio value every 5 minutes (M7, Vanixxx 2026-10-05): the only thing kept, because
a live value is gone once the next price arrives. Thinned: 5-minute points for 7 days, then
one per hour up to 90 days; beyond that the daily history covers it."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PortfolioTick(Base):
    __tablename__ = "portfolio_tick"

    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    value: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    """EUR: coins at the current price plus cash."""
