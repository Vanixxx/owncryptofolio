"""Prices, exchange rates and coin identity (ADR 0019). All derived (ADR 0001): they can
be fetched again at any time; only the mapping and its history are the user's work.

    value(SOL, 2024-03-06) = 148.32 USD × 0.9187 EUR/USD = 136.26 EUR

Bitget quotes in USDT, so a link more: price in USDT × USDT in USD × USD in EUR. That is
why USDT is a real series and never fixed at 1 USD.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# SHIB-like prices sit at 0.00000001, BTC at six digits: wide on both sides. Never float.
Price = Numeric(38, 18)


class PriceAsset(Base):
    """One asset as the user sees it: its name, whether its mapping was checked by a
    human, and whether it needs a price at all (spam airdrops do not)."""

    __tablename__ = "price_asset"

    asset: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(120))
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    """A suggestion is not a fact (ADR 0019): unconfirmed mappings stay visible."""
    ignored: Mapped[bool] = mapped_column(Boolean, default=False)
    """No price wanted, e.g. a spam token. Shown as such, never valued with 0."""
    icon: Mapped[str | None] = mapped_column(String(40))
    """Which coin symbol to show when the icon set names it differently (RENDER → RNDR)."""
    worthless_since: Mapped[date | None] = mapped_column(Date)
    """Worth nothing from this day on, as a person decided (a dead token like Entangle,
    Vanixxx 2026-10-08): valued at 0 instead of "no price", so the loss shows. Before the day
    the prices count as usual."""
    prices_until: Mapped[date | None] = mapped_column(Date)
    """The last day with prices, as a person decided (AGIX, merged into FET in 2024; Vanixxx
    2026-10-17): nothing is fetched after it and later prices are removed. Unlike
    worthless_since the coin is not valued at 0 — it simply has no price afterwards."""
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AssetAlias(Base):
    """One coin, several symbols: MEXC writes NTGL, Bitget NGL — both are Entangle. The raw
    rows keep what the source delivered (ADR 0001); everything derived (prices, holdings,
    merging) reads the alias as the asset it stands for. Rz. 91 BMF: correcting values
    because a source names a coin differently leaves valuation consistent."""

    __tablename__ = "asset_alias"

    alias: Mapped[str] = mapped_column(String(40), primary_key=True)
    asset: Mapped[str] = mapped_column(String(40), index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PriceSource(Base):
    """Asset → source → ticker, ranked. Per day the lowest rank that delivers wins;
    later ranks only fill holes (Yahoo's GRT-USD ends in April 2022, Bitget goes on)."""

    __tablename__ = "price_source"

    asset: Mapped[str] = mapped_column(String(40), primary_key=True)
    rank: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(20))  # yahoo | bitget | coingecko
    ticker: Mapped[str] = mapped_column(String(80))  # SOL-USD, SOLUSDT, vara-network
    quote: Mapped[str] = mapped_column(String(10))  # USD | USDT


class PriceMappingChange(Base):
    """Who changed which mapping and why. The BMF wants documented, consistent
    valuation (Rz. 91): a change of source is fine with a reason, so the reason is kept
    as history, not as a field the next change would overwrite."""

    __tablename__ = "price_mapping_change"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    asset: Mapped[str] = mapped_column(String(40), index=True)
    field: Mapped[str] = mapped_column(String(40))
    before: Mapped[str | None] = mapped_column(Text)
    after: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PriceDaily(Base):
    """A daily close (00:00 UTC boundary) as the source delivered it. One price per day;
    `source` says which rank won. High/low are for drawing only, never for values."""

    __tablename__ = "price_daily"

    asset: Mapped[str] = mapped_column(String(40), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    quote: Mapped[str] = mapped_column(String(10))
    close: Mapped[Decimal] = mapped_column(Price)
    high: Mapped[Decimal | None] = mapped_column(Price)
    low: Mapped[Decimal | None] = mapped_column(Price)
    source: Mapped[str] = mapped_column(String(20))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FxDaily(Base):
    """USD → EUR, ECB reference rate via Frankfurter. The ECB has no weekends: then the
    last published rate is used and marked as approximated, with the day it came from."""

    __tablename__ = "fx_daily"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    base: Mapped[str] = mapped_column(String(10), primary_key=True)
    quote: Mapped[str] = mapped_column(String(10), primary_key=True)
    rate: Mapped[Decimal] = mapped_column(Price)
    approximated: Mapped[bool] = mapped_column(Boolean, default=False)
    source_day: Mapped[date] = mapped_column(Date)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PriceGap(Base):
    """What no source could deliver, from the first needed day on — kept, not hidden:
    a missing price is a gap, never a 0 (ADR 0019)."""

    __tablename__ = "price_gap"

    asset: Mapped[str] = mapped_column(String(40), primary_key=True)
    from_day: Mapped[date] = mapped_column(Date)
    to_day: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text)
    noted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PriceLatest(Base):
    """The current price, refreshed in an interval (default 15 minutes). Display only;
    values for a past day always come from `price_daily`."""

    __tablename__ = "price_latest"

    asset: Mapped[str] = mapped_column(String(40), primary_key=True)
    quote: Mapped[str] = mapped_column(String(10))
    price: Mapped[Decimal] = mapped_column(Price)
    source: Mapped[str] = mapped_column(String(20))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PriceFine(Base):
    """A coin's price every 5 minutes (31 days) and every hour (90 days), in the quote of its
    source (ADR 0044): the fine portfolio values are computed from it, and the change over
    24 hours. Kept apart from the daily prices, which stay the base of every result."""

    __tablename__ = "price_fine"

    asset: Mapped[str] = mapped_column(String(40), primary_key=True)
    step: Mapped[str] = mapped_column(String(3), primary_key=True)  # 5m | 1h
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    close: Mapped[Decimal] = mapped_column(Price)
    quote: Mapped[str] = mapped_column(String(10))
    source: Mapped[str] = mapped_column(String(20))  # yahoo | bitget | binance | coingecko | live
