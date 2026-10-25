"""Vanixxx's decisions about the merged view (ADR 0005, 0039). The view itself is computed on
every request; only what a human decided is stored, anchored on the raw row's fingerprint
(it survives a revert and a re-import, an id does not)."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class TransferDecision(Base):
    """A send and a receive linked by hand (`linked`) or kept apart (`split`). A split
    keeps both halves single until one is linked by hand. A link occupies both."""

    __tablename__ = "transfer_decision"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    send_fp: Mapped[str] = mapped_column(String(64), index=True)
    receive_fp: Mapped[str] = mapped_column(String(64), index=True)
    decision: Mapped[str] = mapped_column(String(10))  # linked | split
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("send_fp", "receive_fp", name="uq_transfer_pair"),)


class OpenSendMark(Base):
    """A send without counterpart, explained by Vanixxx: `external` (a real disposal, e.g. a
    payment), `own_untracked` (an own wallet that is not set up here) or `lost` (gone for
    good, e.g. a provider gone bust: Trastra, Vanixxx 2026-10-11). Since 2026-10-11 a receive
    without counterpart is marked here too: `own_untracked`, `bought` or `income`."""

    __tablename__ = "open_send_mark"

    send_fp: Mapped[str] = mapped_column(String(64), primary_key=True)
    mark: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SpamMark(Base):
    """One transaction marked as spam (dust). Whole spam coins are `price_asset.ignored`."""

    __tablename__ = "spam_mark"

    fingerprint: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TransferExtra(Base):
    """A separate booking that belongs to a transfer, e.g. Bitget's 0.1 USDT withdrawal fee
    booked as its own line (Vanixxx, 2026-10-06). Shown inside the transfer, counted as its
    fee; anchored on fingerprints like every decision."""

    __tablename__ = "transfer_extra"

    extra_fp: Mapped[str] = mapped_column(String(64), primary_key=True)
    send_fp: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TxNote(Base):
    """Vanixxx's own note on a transaction (on a transfer: on its send). Kept apart from the
    raw row, so writing one neither changes the data nor marks the line as edited; a
    source's own comment stays as delivered."""

    __tablename__ = "tx_note"

    fingerprint: Mapped[str] = mapped_column(String(64), primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class NotDustMark(Base):
    """A small receive that is no dust attack, as Vanixxx decided: the "dust?" suggestion
    leaves it alone (2026-10-06)."""

    __tablename__ = "not_dust_mark"

    fingerprint: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
