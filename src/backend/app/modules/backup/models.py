from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class BackupRun(Base):
    """One backup. Retention deletes only files listed here — never anything else
    in the backup folder (old backups from before the restart live there too)."""

    __tablename__ = "backup_run"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trigger: Mapped[str] = mapped_column(String(20))  # manual | schedule
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|done|failed
    dump_file: Mapped[str | None] = mapped_column(String(300))
    export_file: Mapped[str | None] = mapped_column(String(300))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    rows: Mapped[int | None] = mapped_column(Integer)
    probe_ok: Mapped[bool | None] = mapped_column(Boolean)
    message: Mapped[str | None] = mapped_column(Text)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)  # removed by retention
