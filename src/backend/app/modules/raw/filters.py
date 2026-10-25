"""Filters shared by the raw list and the merged view: source or whole wallet, period in
the user's time zone, kind, coin (with every symbol a source uses for it, ADR 0038)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.prices.models import AssetAlias
from app.modules.raw.models import RawTransaction
from app.modules.sources.models import Source


@dataclass
class Filter:
    source_ids: set[int] | None = None
    start: datetime | None = None
    end: datetime | None = None
    kinds: set[str] | None = None
    assets: set[str] | None = None

    def where(self) -> list:
        out = []
        if self.source_ids is not None:
            out.append(RawTransaction.source_id.in_(self.source_ids))
        if self.start is not None:
            out.append(RawTransaction.timestamp >= self.start)
        if self.end is not None:
            out.append(RawTransaction.timestamp < self.end)
        if self.kinds is not None:
            plain, incomes = split_kinds(self.kinds)
            out.append(
                or_(
                    RawTransaction.kind.in_(plain),
                    (RawTransaction.kind == "income") & RawTransaction.income_kind.in_(incomes),
                )
            )
        if self.assets is not None:
            out.append(
                or_(
                    RawTransaction.incoming_asset.in_(self.assets),
                    RawTransaction.outgoing_asset.in_(self.assets),
                    RawTransaction.fee_asset.in_(self.assets),
                )
            )
        return out

    def matches(self, r: RawTransaction, *, kind: bool = True) -> bool:
        return (
            (self.source_ids is None or r.source_id in self.source_ids)
            and (self.start is None or r.timestamp >= self.start)
            and (self.end is None or r.timestamp < self.end)
            and (not kind or self.kinds is None or kind_matches(self.kinds, r.kind, r.income_kind))
            and (
                self.assets is None
                or bool({r.incoming_asset, r.outgoing_asset, r.fee_asset} & self.assets)
            )
        )


def split_kinds(kinds: set[str]) -> tuple[set[str], set[str]]:
    """Kinds as filtered: "income:staking" picks one kind of income (Vanixxx, 2026-10-08)."""
    incomes = {k.split(":", 1)[1] for k in kinds if k.startswith("income:")}
    return {k for k in kinds if ":" not in k}, incomes


def kind_matches(kinds: set[str], kind: str, income_kind: str | None) -> bool:
    plain, incomes = split_kinds(kinds)
    return kind in plain or (kind == "income" and income_kind in incomes)


def values(text: str | None) -> list[str]:
    """A filter field with several values, comma-separated ("send,receive")."""
    return [v.strip() for v in (text or "").split(",") if v.strip()]


def ids(text: str | int | None) -> list[int]:
    try:
        return [int(v) for v in values(str(text) if text is not None else None)]
    except ValueError as exc:
        raise AppError("raw.invalid_filter", 400) from exc


def build(
    session: Session,
    *,
    source_id: str | int | None = None,
    wallet_id: str | int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    tz: str = "UTC",
    kind: str | None = None,
    asset: str | None = None,
) -> Filter:
    """Each of source, wallet, kind and coin may hold several values (Vanixxx, 2026-10-07):
    any of them matches; sources and whole wallets add up."""
    f = Filter(kinds=set(values(kind)) or None)
    sources, wallets = ids(source_id), ids(wallet_id)
    if sources or wallets:
        f.source_ids = set(sources)
        if wallets:
            f.source_ids |= set(
                session.scalars(select(Source.id).where(Source.wallet_id.in_(wallets)))
            )
    try:
        zone = ZoneInfo(tz)
    except (KeyError, ValueError) as exc:
        raise AppError("raw.invalid_timezone", 400) from exc
    if date_from is not None:
        f.start = datetime.combine(date_from, time(), zone)
    if date_to is not None:  # inclusive: up to the end of that day
        f.end = datetime.combine(date_to + timedelta(days=1), time(), zone)
    coins = [a.upper() for a in values(asset)]
    if coins:
        aliases = dict(session.execute(select(AssetAlias.alias, AssetAlias.asset)).all())
        f.assets = set()
        for a in coins:
            coin = aliases.get(a, a)
            f.assets |= {coin} | {k for k, v in aliases.items() if v == coin}
    return f
