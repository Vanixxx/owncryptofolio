"""The column mapping of a source's own files (ADR 0048): used again on the next import."""

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ImportMapping(Base):
    __tablename__ = "import_mapping"

    source_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("source.id", ondelete="CASCADE"), primary_key=True
    )
    mapping: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
