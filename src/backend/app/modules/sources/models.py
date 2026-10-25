from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Wallet(Base):
    """A device or app holding several network addresses, e.g. "Tangem" (ADR 0034)."""

    __tablename__ = "wallet"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Source(Base):
    """A configured source: an exchange account or a wallet address.

    An exchange source can be fed through several channels (API and files);
    the plugins for each channel share the provider (ADR 0017, ADR 0033).
    """

    __tablename__ = "source"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    provider: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(20))  # exchange | wallet
    label: Mapped[str] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(String(200))
    auto_fetch: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    """Included in the daily fetch (ADR 0035)."""
    wallet_id: Mapped[int | None] = mapped_column(ForeignKey("wallet.id", ondelete="RESTRICT"))
    """Network addresses belong to a wallet (ADR 0034); exchanges have none."""
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_check_ok: Mapped[bool | None] = mapped_column(Boolean)
    last_check_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("provider", "address", name="uq_source_address"),)


class SourceCredential(Base):
    """One encrypted credential field. Never returned in clear text by the API."""

    __tablename__ = "source_credential"

    source_id: Mapped[int] = mapped_column(
        ForeignKey("source.id", ondelete="CASCADE"), primary_key=True
    )
    field: Mapped[str] = mapped_column(String(60), primary_key=True)
    ciphertext: Mapped[str] = mapped_column(Text)


class ServiceKey(Base):
    """API key of a blockchain service shared by several networks (Etherscan, Cronos).
    Encrypted with the credentials key, never returned in clear text."""

    __tablename__ = "service_key"

    service: Mapped[str] = mapped_column(String(40), primary_key=True)
    ciphertext: Mapped[str] = mapped_column(Text)
