"""Logos uploaded by the user where no free icon set has one (Tangem, SafeTrade, ...).
Kept in the database, so the backup carries them; no brand logo lands in the code."""

from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CustomLogo(Base):
    __tablename__ = "custom_logo"

    kind: Mapped[str] = mapped_column(String(10), primary_key=True)  # wallet | source | coin
    key: Mapped[str] = mapped_column(String(60), primary_key=True)  # wallet/source id, coin symbol
    mime: Mapped[str] = mapped_column(String(40))
    data: Mapped[bytes] = mapped_column(LargeBinary)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
