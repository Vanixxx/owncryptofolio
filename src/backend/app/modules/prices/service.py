"""Prices: what is needed, from where, fetched how, and worth what in euro (ADR 0019).

The order of a full run: find which asset is needed since when (from the raw layer),
suggest a mapping for new assets (never touching existing ones), fetch USD→EUR, fetch each
asset rank by rank, note what stays missing.
"""

from __future__ import annotations

import contextlib
import logging
import re
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, literal, select, true, union_all
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.prices import sources
from app.modules.prices.models import (
    AssetAlias,
    FxDaily,
    PriceAsset,
    PriceDaily,
    PriceGap,
    PriceLatest,
    PriceMappingChange,
    PriceSource,
)
from app.modules.raw.models import RawTransaction, current

log = logging.getLogger(__name__)

FIAT = {"EUR", "USD"}
QUOTES = {"yahoo": "USD", "bitget": "USDT", "binance": "USDT", "coingecko": "USD"}
HOLE_TOLERANCE = 3
"""From how many missing days in a row the next rank is asked. Single missing days are
covered by the fallback to the last known price; asking a second source for them would
be forty needless calls per run."""
MAX_AGE_DAYS = 7
"""How old a price may be and still count. Without it the portfolio would read zero
every morning (yesterday's close is the newest); older than a week means a dead source,
and then the position is unvalued — on purpose."""
SPAM = re.compile(
    r"\s|\.(COM|EU|LOL|LINK|ORG|IO|NET)\b|T\.LY|WWW|CLAIM|VISIT|VOUCHER|AIRDROP|REDEEM", re.I
)
"""Airdropped spam names tokens like "VISIT WEBSITE LINKGIVEAWAY .COM TO CLAIM". Such an
asset is suggested as ignored (unconfirmed) instead of searching a price for it."""


def looks_spam(asset: str) -> bool:
    """A spam name, or a symbol with characters no real ticker has: invisible marks between
    the letters ("B឵N឵B", a fake BNB sent along the real one to poison the address book) or
    look-alike letters from other alphabets ("UЅDС") (Vanixxx, 2026-10-09)."""
    return bool(SPAM.search(asset)) or any(not (" " <= ch <= "~") for ch in asset)


# --- what is needed -----------------------------------------------------------


def needs(session: Session) -> dict[str, date]:
    """Asset → first day it appears in a valid raw row (any side, fees included)."""
    sides = [
        select(
            getattr(RawTransaction, f"{s}_asset").label("asset"),
            RawTransaction.timestamp.label("t"),
        ).where(getattr(RawTransaction, f"{s}_asset").is_not(None), current())
        for s in ("incoming", "outgoing", "fee")
    ]
    u = union_all(*sides).subquery()
    rows = session.execute(select(u.c.asset, func.min(u.c.t)).group_by(u.c.asset)).all()
    canon = aliases(session)
    out: dict[str, date] = {}
    for asset, t in rows:
        asset = canon.get(asset, asset)  # NTGL counts as the coin it stands for
        if asset not in FIAT:
            day = t.astimezone(UTC).date()
            out[asset] = min(out.get(asset, day), day)
    return out


def aliases(session: Session) -> dict[str, str]:
    return dict(session.execute(select(AssetAlias.alias, AssetAlias.asset)).all())


# --- mapping ---------------------------------------------------------------------


def _covers(fetch: str, ticker: str, first_day: date) -> bool:
    with contextlib.suppress(sources.SourceUnavailable):
        points = getattr(sources, fetch)(ticker, first_day, first_day + timedelta(days=30))
        return len(points) >= 20  # a month is not nearly there otherwise
    return False


def suggest(
    asset: str,
    first_day: date,
    pairs: dict[str, Decimal | None],
    order: tuple[str, ...] = ("yahoo", "bitget", "binance"),
) -> list[tuple[str, str]]:
    """Ranked (source, ticker) that can contribute: Yahoo, Bitget, Binance. Checked is
    whether a source COVERS the needed period (20 of the first 30 days), not whether it
    knows the ticker: Yahoo has S-USD — with a single day. Bitget is asked directly when
    the pair is no longer listed (GRT: delisted, candles still there). Binance only when
    neither covers (MATIC, FTM). CoinGecko is never suggested: its id cannot be guessed
    from an ambiguous symbol. Yahoo's numbered tickers (GRT6719-USD) are entered by hand."""
    pair = f"{asset}USDT"
    covers = {
        "yahoo": lambda: _covers("yahoo_daily", f"{asset}-USD", first_day),
        "bitget": lambda: pair in pairs or _covers("bitget_daily", pair, first_day),
        "binance": lambda: asset != "USDT" and _covers("binance_daily", pair, first_day),
    }
    tickers = {"yahoo": f"{asset}-USD", "bitget": pair, "binance": pair}
    found: list[tuple[str, str]] = []
    for source in order:
        # Binance only fills in when nothing else covers (MATIC, FTM), unless put first.
        if source == "binance" and found and order[0] != "binance":
            continue
        if covers[source]():
            found.append((source, tickers[source]))
    return found


def refresh_mappings(session: Session, need: dict[str, date]) -> int:
    """New assets get a suggestion (unconfirmed). Existing mappings are never touched — but
    an unconfirmed asset that found no source yet is asked again: sources change."""
    from app.modules.settings import service as settings

    order = tuple(settings.all_settings(session)["prices.source_order"])
    known = set(session.scalars(select(PriceAsset.asset)))
    with_source = set(session.scalars(select(PriceSource.asset)))
    unconfirmed = select(PriceAsset.asset).where(
        PriceAsset.confirmed.is_(False), PriceAsset.ignored.is_(False)
    )
    retry = set(session.scalars(unconfirmed)) - with_source
    new = [a for a in need if a not in known or a in retry]
    if not new:
        return 0
    try:
        pairs = sources.bitget_pairs()
    except sources.SourceUnavailable:
        pairs = {}
        log.warning("Bitget pair list unavailable")
    for asset in new:
        if asset in ("USDT", "USDC") or not looks_spam(asset):
            ranked = suggest(asset, need[asset], pairs, order)
        else:
            ranked = []
        name = None
        if ranked and ranked[0][0] == "yahoo":
            with contextlib.suppress(sources.SourceUnavailable):
                name = sources.yahoo_meta(ranked[0][1])[0]
        entry = session.get(PriceAsset, asset)
        if entry is None:
            spam = looks_spam(asset)
            session.add(PriceAsset(asset=asset, name=name, confirmed=False, ignored=spam))
        elif name and not entry.name:
            entry.name = name
        for rank, (source, ticker) in enumerate(ranked, 1):
            session.add(
                PriceSource(
                    asset=asset, rank=rank, source=source, ticker=ticker, quote=QUOTES[source]
                )
            )
        session.commit()
    return len(new)


def _sources_text(rows: list[PriceSource]) -> str:
    return ", ".join(f"{r.rank}:{r.source}:{r.ticker}" for r in sorted(rows, key=lambda r: r.rank))


def _ticker(source: str, ticker: str) -> str:
    """CoinGecko ids are lower case (`xen-crypto`; `Xen-crypto` is unknown), exchange and
    Yahoo tickers upper case."""
    t = ticker.strip()
    return t.lower() if source == "coingecko" else t.upper()


def update_mapping(
    session: Session,
    asset: str,
    name: str | None,
    ranked: list[tuple[str, str]],
    reason: str | None,
    icon: str | None = None,
) -> None:
    """Change name and/or sources. A change of source, ticker or rank needs a reason
    (Rz. 91: documented); a name alone does not. Unchanged fields leave no history."""
    entry = session.get(PriceAsset, asset)
    if entry is None:
        raise AppError("prices.unknown_asset", 404)
    for source, ticker in ranked:
        if source not in QUOTES or not ticker.strip():
            raise AppError("prices.invalid_source", 400)
    old = list(session.scalars(select(PriceSource).where(PriceSource.asset == asset)))
    new = [
        PriceSource(asset=asset, rank=i, source=s, ticker=_ticker(s, t), quote=QUOTES[s])
        for i, (s, t) in enumerate(ranked, 1)
    ]
    before, after = _sources_text(old), _sources_text(new)
    reason = (reason or "").strip() or None
    if before != after:
        if not reason:
            raise AppError("prices.reason_required", 400)
        for r in old:
            session.delete(r)
        session.flush()
        session.add_all(new)
        session.add(
            PriceMappingChange(
                asset=asset, field="sources", before=before, after=after, reason=reason
            )
        )
        # Prices of the old mapping no longer belong to this asset: fetched anew.
        session.execute(PriceDaily.__table__.delete().where(PriceDaily.asset == asset))
        session.execute(PriceGap.__table__.delete().where(PriceGap.asset == asset))
        session.execute(PriceLatest.__table__.delete().where(PriceLatest.asset == asset))
    icon = (icon or "").strip().upper() or None
    if icon != entry.icon:
        session.add(PriceMappingChange(asset=asset, field="icon", before=entry.icon, after=icon))
        entry.icon = icon
    name = (name or "").strip() or None
    if name != entry.name:
        session.add(
            PriceMappingChange(
                asset=asset, field="name", before=entry.name, after=name, reason=reason
            )
        )
        entry.name = name
    session.commit()


def confirm(session: Session, asset: str) -> None:
    entry = session.get(PriceAsset, asset)
    if entry is None:
        raise AppError("prices.unknown_asset", 404)
    if not entry.confirmed:
        entry.confirmed = True
        session.add(
            PriceMappingChange(asset=asset, field="confirmed", before="false", after="true")
        )
        session.commit()


def set_ignored(session: Session, asset: str, ignored: bool, reason: str | None) -> None:
    entry = session.get(PriceAsset, asset)
    if entry is None:
        raise AppError("prices.unknown_asset", 404)
    if entry.ignored != ignored:
        session.add(
            PriceMappingChange(
                asset=asset,
                field="ignored",
                before=str(entry.ignored).lower(),
                after=str(ignored).lower(),
                reason=(reason or "").strip() or None,
            )
        )
        entry.ignored = ignored
        entry.confirmed = True  # a human decided
        session.commit()


def set_worthless(session: Session, asset: str, since: date | None, reason: str | None) -> None:
    """A dead token is worth 0 from `since` on (Vanixxx, 2026-10-08: Entangle); None undoes it.
    A reason is required, like for every change of how a coin is valued."""
    reason = (reason or "").strip() or None
    if since is not None and not reason:
        raise AppError("prices.reason_required", 400)
    entry = session.get(PriceAsset, asset)
    if entry is None:  # a coin held but never priced has no entry yet
        entry = PriceAsset(asset=asset, confirmed=True, ignored=False)
        session.add(entry)
    if entry.worthless_since != since:
        session.add(
            PriceMappingChange(
                asset=asset,
                field="worthless",
                before=entry.worthless_since.isoformat() if entry.worthless_since else None,
                after=since.isoformat() if since else None,
                reason=reason,
            )
        )
        entry.worthless_since = since
        entry.confirmed = True
        session.commit()


def set_prices_until(session: Session, asset: str, until: date | None, reason: str | None) -> None:
    """Prices end on `until` (a coin merged into another, Vanixxx 2026-10-17): later daily,
    fine and current prices go, none are fetched any more. None undoes it; the next run
    fetches again. A reason is required, like for every change of how a coin is valued."""
    from app.modules.prices.models import PriceFine

    reason = (reason or "").strip() or None
    if until is not None and not reason:
        raise AppError("prices.reason_required", 400)
    entry = session.get(PriceAsset, asset)
    if entry is None:
        raise AppError("prices.unknown_asset", 404)
    if entry.prices_until == until:
        return
    session.add(
        PriceMappingChange(
            asset=asset,
            field="until",
            before=entry.prices_until.isoformat() if entry.prices_until else None,
            after=until.isoformat() if until else None,
            reason=reason,
        )
    )
    entry.prices_until = until
    entry.confirmed = True
    if until is not None:
        end = datetime.combine(until + timedelta(days=1), time(), UTC)
        session.execute(
            PriceDaily.__table__.delete().where(PriceDaily.asset == asset, PriceDaily.day > until)
        )
        session.execute(
            PriceFine.__table__.delete().where(PriceFine.asset == asset, PriceFine.at >= end)
        )
        for table in (PriceLatest, PriceGap):
            session.execute(table.__table__.delete().where(table.asset == asset))
    session.commit()


def until_days(session: Session) -> dict[str, date]:
    return dict(
        session.execute(
            select(PriceAsset.asset, PriceAsset.prices_until).where(
                PriceAsset.prices_until.is_not(None)
            )
        ).all()
    )


def _forget_prices(session: Session, asset: str) -> None:
    for table in (PriceDaily, PriceGap, PriceLatest, PriceSource):
        session.execute(table.__table__.delete().where(table.asset == asset))


def set_alias(
    session: Session, alias: str, target: str, name: str | None, reason: str | None
) -> None:
    """`alias` is the same coin as `target` under another symbol; its raw rows count for the
    target from now on. A reason is required: it documents the correction.

    Nothing is deleted: the alias's own entry, mapping and prices rest while merged (hidden
    on the prices page, not fetched) and come back when the merge is undone. A target with
    no price source of its own gets a copy of the alias's (NGL was only Bitget's price name
    for NTGL; merging used to lose it, and splitting lost NGL, 2026-10-06)."""
    alias, target = alias.strip().upper(), target.strip().upper()
    reason = (reason or "").strip() or None
    if not reason:
        raise AppError("prices.reason_required", 400)
    canon = aliases(session)
    target = canon.get(target, target)
    if not target or target == alias or alias in FIAT or target in FIAT:
        raise AppError("prices.invalid_alias", 400)
    if any(a == alias for a in canon.values()):
        raise AppError("prices.alias_has_aliases", 409)
    session.merge(AssetAlias(alias=alias, asset=target, reason=reason))
    entry = session.get(PriceAsset, target)
    if entry is None:
        session.add(PriceAsset(asset=target, name=(name or "").strip() or None, confirmed=False))
    elif name and not entry.name:
        entry.name = name.strip()
    session.flush()
    has_own = session.scalar(
        select(func.count()).select_from(PriceSource).where(PriceSource.asset == target)
    )
    if not has_own:
        _forget_prices(session, target)  # a gap note or a stray latest price of its own
        for table in (PriceSource, PriceDaily, PriceGap, PriceLatest):
            _copy_prices(session, table, alias, target)
    session.add(
        PriceMappingChange(asset=target, field="alias", before=None, after=alias, reason=reason)
    )
    session.commit()


def _copy_prices(session: Session, table: type, src: str, dst: str) -> None:
    t = table.__table__
    cols = [c.name for c in t.columns]
    picked = [literal(dst).label("asset") if c == "asset" else t.c[c] for c in cols]
    session.execute(t.insert().from_select(cols, select(*picked).where(t.c.asset == src)))


def remove_alias(session: Session, alias: str) -> None:
    """Undo a merge: the symbol shows again with what it had before (entry, mapping, prices).
    What the target copied from it stays: both show the same price then."""
    row = session.get(AssetAlias, alias)
    if row is None:
        raise AppError("prices.unknown_asset", 404)
    session.add(PriceMappingChange(asset=row.asset, field="alias", before=alias, after=None))
    session.delete(row)
    session.commit()
    if session.get(PriceAsset, alias) is not None:
        return
    # merged before 2026-10-06, when merging still deleted the entry: it comes back with a
    # suggestion, else the coin vanished from the prices page (NTGL, 2026-10-05)
    session.add(PriceAsset(asset=alias, confirmed=False))
    session.commit()
    need = needs(session)
    if alias in need:
        with contextlib.suppress(Exception):  # a source being down must not undo the split
            refresh_mappings(session, {alias: need[alias]})


def resuggest_unconfirmed(session: Session) -> int:
    """After changing the default order: unconfirmed, not ignored assets get a fresh
    suggestion (and their prices are fetched again). Confirmed ones stay as they are."""
    open_assets = list(
        session.scalars(
            select(PriceAsset).where(
                PriceAsset.confirmed.is_(False),
                PriceAsset.ignored.is_(False),
                PriceAsset.asset.not_in(select(AssetAlias.alias)),
            )
        )
    )
    for a in open_assets:
        _forget_prices(session, a.asset)
        session.add(
            PriceMappingChange(
                asset=a.asset,
                field="sources",
                before=None,
                after="new suggestion",
                reason="default source order changed",
            )
        )
    session.commit()
    return len(open_assets)


# --- fetching ----------------------------------------------------------------------

FETCHERS: dict[str, str] = {
    "yahoo": "yahoo_daily",
    "bitget": "bitget_daily",
    "binance": "binance_daily",
    "coingecko": "coingecko_daily",
}
"""Names, not functions: a table of functions would pin them at import time, and tests
that replace a source would quietly run against the real network."""


def _longest_hole(missing: set[date]) -> int:
    longest = run = 0
    prev = None
    for d in sorted(missing):
        run = run + 1 if prev is not None and d == prev + timedelta(days=1) else 1
        longest, prev = max(longest, run), d
    return longest


def _upsert_prices(
    session: Session, asset: str, rows: dict[date, tuple[PriceSource, sources.Point]]
) -> int:
    if not rows:
        return 0
    values = [
        {
            "asset": asset,
            "day": d,
            "quote": src.quote,
            "close": p.close,
            "high": p.high,
            "low": p.low,
            "source": src.source,
            "fetched_at": datetime.now(UTC),
        }
        for d, (src, p) in rows.items()
    ]
    for i in range(0, len(values), 1000):
        stmt = insert(PriceDaily).values(values[i : i + 1000])
        stmt = stmt.on_conflict_do_update(
            index_elements=["asset", "day"],
            set_={
                c: stmt.excluded[c]
                for c in ("quote", "close", "high", "low", "source", "fetched_at")
            },
        )
        session.execute(stmt)
    return len(values)


def fetch_history(session: Session, asset: str, first_day: date, today: date | None = None) -> dict:
    """Rank by rank until the holes are closed. Per day the lowest rank that delivers
    wins; later ranks only fill. Today's candle is still running: not a gap."""
    today = today or datetime.now(UTC).date()
    last_closed = today - timedelta(days=1)
    ranked = list(
        session.scalars(
            select(PriceSource).where(PriceSource.asset == asset).order_by(PriceSource.rank)
        )
    )
    if not ranked:
        _note_gap(session, asset, first_day, last_closed, "no source mapped")
        return {"asset": asset, "written": 0, "gap": True}
    needed = {first_day + timedelta(days=i) for i in range((last_closed - first_day).days + 1)}
    have = set(
        session.scalars(
            select(PriceDaily.day).where(PriceDaily.asset == asset, PriceDaily.day >= first_day)
        )
    )
    # Known history stays: only the last week is refreshed, unless older days are missing.
    recent = last_closed - timedelta(days=7)
    old_missing = {d for d in needed if d < recent} - have
    gap = session.get(PriceGap, asset)
    # a start no source has: asked again once a week (a new mapping clears the gap at once),
    # not on every run with the whole history from every source (review 2026-10-24)
    if (
        gap is not None
        and gap.from_day <= first_day
        and gap.noted_at is not None
        and datetime.now(UTC) - gap.noted_at < timedelta(days=7)
    ):
        old_missing = {d for d in old_missing if d > gap.to_day}
    start = first_day if old_missing else max(first_day, recent)
    chosen: dict[date, tuple[PriceSource, sources.Point]] = {}
    covered = {d for d in have if d < start}
    errors: list[str] = []
    for src in ranked:
        if covered and _longest_hole({d for d in needed if d >= start} - covered) <= HOLE_TOLERANCE:
            break
        fetch = getattr(sources, FETCHERS[src.source])
        try:
            points = fetch(src.ticker, start, last_closed)
        except sources.SourceUnavailable as exc:
            errors.append(f"{src.source}: {exc}")
            continue
        for p in points:
            if p.day not in chosen and p.day not in covered:
                chosen[p.day] = (src, p)
        covered |= {p.day for p in points}
    written = _upsert_prices(session, asset, chosen)
    all_days = set(session.scalars(select(PriceDaily.day).where(PriceDaily.asset == asset)))
    missing = sorted(needed - all_days)
    if not all_days:
        _note_gap(
            session, asset, first_day, last_closed, "; ".join(errors) or "no source delivered"
        )
    elif missing and missing[0] == first_day:
        # Only a missing START is a gap: holes in the middle are covered by the fallback,
        # before the first price there is nothing to fall back on.
        end = missing[0]
        for d in missing[1:]:
            if d != end + timedelta(days=1):
                break
            end = d
        _note_gap(
            session,
            asset,
            first_day,
            end,
            "not covered by: " + ", ".join(f"{s.source} ({s.ticker})" for s in ranked),
        )
    else:
        session.execute(PriceGap.__table__.delete().where(PriceGap.asset == asset))
    session.commit()
    return {"asset": asset, "written": written, "errors": errors}


def _note_gap(session: Session, asset: str, start: date, end: date, reason: str) -> None:
    stmt = insert(PriceGap).values(asset=asset, from_day=start, to_day=end, reason=reason[:500])
    session.execute(
        stmt.on_conflict_do_update(
            index_elements=["asset"],
            set_={"from_day": start, "to_day": end, "reason": reason[:500], "noted_at": func.now()},
        )
    )
    session.commit()


def fetch_fx(session: Session, start: date, today: date | None = None) -> int:
    """USD → EUR from `start`. Asked from ten days earlier: a start on a weekend would
    otherwise have nothing to approximate from."""
    today = today or datetime.now(UTC).date()
    have = session.scalar(
        select(func.max(FxDaily.day)).where(FxDaily.base == "USD", FxDaily.quote == "EUR")
    )
    first = session.scalar(
        select(func.min(FxDaily.day)).where(FxDaily.base == "USD", FxDaily.quote == "EUR")
    )
    begin = (
        start if first is None or first > start else max(start, (have or start) - timedelta(days=7))
    )
    try:
        series = sources.ecb_usd_eur(begin - timedelta(days=10), today)
    except sources.SourceUnavailable as exc:
        # the rate service down must not stop the coin prices: the rates on hand carry the
        # valuation (up to 7 days back), the next run fills the gap (review 2026-10-24)
        log.warning("USD/EUR rates not fetched: %s", exc)
        return 0
    values = [
        {
            "day": d,
            "base": "USD",
            "quote": "EUR",
            "rate": r,
            "approximated": a,
            "source_day": sd,
            "fetched_at": datetime.now(UTC),
        }
        for d, r, a, sd in series
        if d >= begin
    ]
    for i in range(0, len(values), 1000):
        stmt = insert(FxDaily).values(values[i : i + 1000])
        session.execute(
            stmt.on_conflict_do_update(
                index_elements=["day", "base", "quote"],
                set_={
                    c: stmt.excluded[c]
                    for c in ("rate", "approximated", "source_day", "fetched_at")
                },
            )
        )
    session.commit()
    return len(values)


def run_all(session: Session, progress: Callable[[dict], None] | None = None) -> dict:
    need = needs(session)
    # Bitget quotes in USDT: its series is a link of every Bitget price, held or not.
    need.setdefault("USDT", min(need.values(), default=datetime.now(UTC).date()))
    suggested = refresh_mappings(session, need)
    if progress:
        progress({"step": "mapping", "done": 0, "total": len(need)})
    fx = fetch_fx(session, min(need.values(), default=datetime.now(UTC).date()))
    ignored = set(session.scalars(select(PriceAsset.asset).where(PriceAsset.ignored.is_(True))))
    results, failed = 0, []
    until = until_days(session)
    todo = sorted(a for a in need if a not in ignored and need[a] <= until.get(a, need[a]))
    for i, asset in enumerate(todo, 1):
        try:
            r = fetch_history(session, asset, need[asset], _until_today(until, asset))
            results += r["written"]
            if r.get("errors"):
                failed.append(asset)
        except Exception as exc:  # noqa: BLE001 — one broken asset must not stop the run
            session.rollback()
            log.warning("Prices for %s failed: %s", asset, exc)
            failed.append(asset)
        if progress:
            progress({"step": "prices", "done": i, "total": len(todo), "rows": results})
    latest = refresh_latest(session)
    return {
        "assets": len(todo),
        "suggested": suggested,
        "prices": results,
        "fx_days": fx,
        "latest": latest,
        "with_errors": failed,
    }


def _until_today(until: dict[str, date], asset: str) -> date | None:
    """For a coin whose prices end: the day after, so the last fetched close is that day."""
    return until[asset] + timedelta(days=1) if asset in until else None


def run_one(session: Session, asset: str) -> dict:
    """The price run for one coin only, from its prices page row (Vanixxx, 2026-10-10): after
    changing its sources one need not wait for every other coin."""
    from app.core.errors import AppError

    asset = asset.upper()
    start = needs(session).get(asset)
    if start is None:
        raise AppError("prices.unknown_asset", 404)
    suggested = refresh_mappings(session, {asset: start})
    fetch_fx(session, start)
    r = fetch_history(session, asset, start, _until_today(until_days(session), asset))
    latest = refresh_latest(session, only={asset})
    return {
        "asset": asset,
        "suggested": suggested,
        "prices": r["written"],
        "latest": latest,
        "with_errors": [asset] if r.get("errors") else [],
    }


def refresh_latest(session: Session, only: set[str] | None = None) -> int:
    """Current prices of every priced asset, one call per source where possible."""
    first_rank = {
        s.asset: s
        for s in session.scalars(select(PriceSource).where(PriceSource.rank == 1))
        if only is None or s.asset in only
    }
    ignored = set(session.scalars(select(PriceAsset.asset).where(PriceAsset.ignored.is_(True))))
    ignored |= ended(session, datetime.now(UTC).date()) | set(aliases(session))
    pairs: dict[str, Decimal | None] | None = None
    now = datetime.now(UTC)
    written = 0
    for asset, src in first_rank.items():
        if asset in ignored:
            continue
        price = None
        try:
            if src.source == "yahoo":
                price = sources.yahoo_meta(src.ticker)[1]
            elif src.source == "bitget":
                pairs = pairs if pairs is not None else sources.bitget_pairs()
                price = pairs.get(src.ticker)
            elif src.source == "binance":
                price = sources.binance_latest(src.ticker)
            elif src.source == "coingecko":
                price = sources.coingecko_latest(src.ticker)
        except sources.SourceUnavailable:
            continue
        if price is None:
            continue
        stmt = insert(PriceLatest).values(
            asset=asset, quote=src.quote, price=price, source=src.source, at=now
        )
        session.execute(
            stmt.on_conflict_do_update(
                index_elements=["asset"],
                set_={"quote": src.quote, "price": price, "source": src.source, "at": now},
            )
        )
        from app.modules.prices import fine

        fine.record_live(session, asset, price, src.quote, now)
        written += 1
    session.commit()
    return written


def ended(session: Session, today: date) -> set[str]:
    """Coins whose daily series stopped more than a week ago (FTM after the switch to S).
    An exchange still reports the last price of a delisted pair — shown as today's price
    it would be wrong, so they get none, and an old latest price is removed."""
    stale = {
        a
        for a, last in session.execute(
            select(PriceDaily.asset, func.max(PriceDaily.day)).group_by(PriceDaily.asset)
        )
        if last < today - timedelta(days=MAX_AGE_DAYS)
    } | {a for a, end in until_days(session).items() if end < today}  # an end still to come
    # keeps its prices until then (review 2026-10-24)
    if stale:
        session.execute(PriceLatest.__table__.delete().where(PriceLatest.asset.in_(stale)))
    return stale


LIVE_MIN_SECONDS = 20
"""The open prices page asks every 30 s; more than one refresh per 20 s helps nobody."""
YAHOO_LIVE_SECONDS = 300
"""Yahoo needs one call per coin: for coins only Yahoo knows, at most every 5 minutes."""
_last_live: datetime | None = None


def refresh_live(session: Session, now: datetime | None = None) -> int:
    """Current prices while the page is open (display only). One call for all Bitget
    pairs and one for all Binance pairs; Yahoo per coin and throttled. The ranking on the
    prices page counts here too: an exchange at rank 2 is no live substitute for Yahoo at
    rank 1 (Bitget's CROUSDT was 23 % below Yahoo, CoinGecko and Crypto.com, and the
    portfolio jumped by 146 € with every open prices page, 2026-10-05)."""
    global _last_live
    now = now or datetime.now(UTC)
    if _last_live is not None and (now - _last_live).total_seconds() < LIVE_MIN_SECONDS:
        return 0
    _last_live = now
    ignored = set(session.scalars(select(PriceAsset.asset).where(PriceAsset.ignored.is_(True))))
    ignored |= ended(session, now.date()) | set(aliases(session))  # merged ones rest
    by_asset: dict[str, list[PriceSource]] = {}
    for src in session.scalars(select(PriceSource).order_by(PriceSource.asset, PriceSource.rank)):
        if src.asset not in ignored:
            by_asset.setdefault(src.asset, []).append(src)
    latest_at = dict(session.execute(select(PriceLatest.asset, PriceLatest.at)).all())
    books: dict[str, dict[str, Decimal | None]] = {}

    def book(source: str) -> dict[str, Decimal | None]:
        if source not in books:
            try:
                books[source] = (
                    sources.bitget_pairs() if source == "bitget" else sources.binance_prices()
                )
            except sources.SourceUnavailable:
                books[source] = {}
        return books[source]

    written = 0
    for asset, ranked in by_asset.items():
        first = ranked[0]
        choice = first if first.source in ("bitget", "binance") else None
        price = None
        if choice is not None:
            price = book(choice.source).get(choice.ticker)
        if price is None:
            yahoo = first if first.source == "yahoo" else None
            last = latest_at.get(asset)
            if yahoo is None or (
                last is not None and (now - last).total_seconds() < YAHOO_LIVE_SECONDS
            ):
                continue
            with contextlib.suppress(sources.SourceUnavailable):
                price = sources.yahoo_meta(yahoo.ticker)[1]
            choice = yahoo
        if price is None:
            continue
        stmt = insert(PriceLatest).values(
            asset=asset, quote=choice.quote, price=price, source=choice.source, at=now
        )
        session.execute(
            stmt.on_conflict_do_update(
                index_elements=["asset"],
                set_={"quote": choice.quote, "price": price, "source": choice.source, "at": now},
            )
        )
        written += 1
    session.commit()
    return written


def live_prices(session: Session, currency: str = "EUR") -> dict[str, dict]:
    today = datetime.now(UTC).date()
    valuer = Valuer(session)
    out = {}
    for asset, at in session.execute(select(PriceLatest.asset, PriceLatest.at)).all():
        price = valuer.in_currency(valuer.latest_eur(asset, today), today, currency)
        if price is not None:
            out[asset] = {
                "price": format(price.normalize(), "f"),
                "at": at.isoformat(),
                "currency": currency,
            }
    return out


# --- valuing ------------------------------------------------------------------------


class Valuer:
    """Asset × day → euro from the database. Loads all once: about 70,000 prices are a few
    megabytes; one query per transaction and day would be tens of thousands.

    Missing day → the last one before, at most MAX_AGE_DAYS old, and counted. `None` means
    unvalued — explicitly never 0 (ADR 0019)."""

    def __init__(self, session: Session) -> None:
        self.prices: dict[tuple[str, date], tuple[Decimal, str]] = {
            (a, d): (c, q)
            for a, d, c, q in session.execute(
                select(PriceDaily.asset, PriceDaily.day, PriceDaily.close, PriceDaily.quote)
            )
        }
        self.fx: dict[date, Decimal] = dict(
            session.execute(
                select(FxDaily.day, FxDaily.rate).where(
                    FxDaily.base == "USD", FxDaily.quote == "EUR"
                )
            ).all()
        )
        self.latest = {
            a: (p, q)
            for a, p, q in session.execute(
                select(PriceLatest.asset, PriceLatest.price, PriceLatest.quote)
            )
        }
        self.fell_back: set[tuple[str, date]] = set()
        self.aliases = aliases(session)
        self.worthless: dict[str, date] = dict(
            session.execute(
                select(PriceAsset.asset, PriceAsset.worthless_since).where(
                    PriceAsset.worthless_since.is_not(None)
                )
            ).all()
        )

    def _dead(self, asset: str, day: date) -> bool:
        since = self.worthless.get(asset)
        return since is not None and day >= since

    def _back(self, table: dict, key, day: date, name: str):
        for back in range(MAX_AGE_DAYS + 1):
            k = (key, day - timedelta(days=back)) if key is not None else day - timedelta(days=back)
            if k in table:
                if back:
                    self.fell_back.add((name, day))
                return table[k]
        return None

    def usd_eur(self, day: date) -> Decimal | None:
        return self._back(self.fx, None, day, "USD/EUR")

    def _to_eur(self, value: Decimal, quote: str, day: date) -> Decimal | None:
        if quote == "USDT":
            usdt = self._back(self.prices, "USDT", day, "USDT")
            if usdt is None:
                return None
            value, quote = value * usdt[0], usdt[1]
        if quote == "USD":
            fx = self.usd_eur(day)
            return None if fx is None else value * fx
        return value if quote == "EUR" else None

    def eur(self, asset: str, day: date) -> Decimal | None:
        asset = self.aliases.get(asset, asset)
        if asset == "EUR":
            return Decimal(1)
        if asset == "USD":
            return self.usd_eur(day)
        if self._dead(asset, day):
            return Decimal(0)  # declared worthless: the loss shows, it is not "unvalued"
        entry = self._back(self.prices, asset, day, asset)
        return None if entry is None else self._to_eur(entry[0], entry[1], day)

    def in_currency(self, eur: Decimal | None, day: date, currency: str) -> Decimal | None:
        """EUR → the display currency (setting `general.currency`) over the same ECB rate."""
        if eur is None or currency == "EUR":
            return eur
        fx = self.usd_eur(day)
        return None if not fx else eur / fx

    def latest_eur(self, asset: str, today: date) -> Decimal | None:
        asset = self.aliases.get(asset, asset)
        if asset in ("EUR", "USD") or self._dead(asset, today):
            return self.eur(asset, today)
        entry = self.latest.get(asset)
        if entry is None:
            return self.eur(asset, today)
        return self._to_eur(entry[0], entry[1], today)


# --- overview for the page -----------------------------------------------------------


SPARK_DAYS, SPARK_STEP = 90, 2
"""The list shows a 90-day curve without axes: a mixed-up coin shows in its shape faster
than in any number. Every second day is plenty for a thumbnail."""


def overview(session: Session, currency: str = "EUR") -> list[dict]:
    need = needs(session)
    today = datetime.now(UTC).date()
    valuer = Valuer(session)
    canon = aliases(session)
    usage: dict[str, int] = {}
    for asset, n in session.execute(_usage_query()).all():
        usage[canon.get(asset, asset)] = usage.get(canon.get(asset, asset), 0) + n
    alias_of: dict[str, list[str]] = {}
    for alias, asset in canon.items():
        alias_of.setdefault(asset, []).append(alias)
    stats = {
        a: (n, lo, hi)
        for a, n, lo, hi in session.execute(
            select(
                PriceDaily.asset, func.count(), func.min(PriceDaily.day), func.max(PriceDaily.day)
            ).group_by(PriceDaily.asset)
        )
    }
    gaps = {g.asset: g for g in session.scalars(select(PriceGap))}
    contributions: dict[str, dict[str, int]] = {}
    for asset, source, n in session.execute(
        select(PriceDaily.asset, PriceDaily.source, func.count()).group_by(
            PriceDaily.asset, PriceDaily.source
        )
    ):
        contributions.setdefault(asset, {})[source] = n
    spark: dict[str, list[str]] = {}
    since = today - timedelta(days=SPARK_DAYS)
    for r in session.scalars(
        select(PriceDaily).where(PriceDaily.day >= since).order_by(PriceDaily.asset, PriceDaily.day)
    ):
        eur = valuer.in_currency(valuer._to_eur(r.close, r.quote, r.day), r.day, currency)
        if eur is not None:
            spark.setdefault(r.asset, []).append(format(eur.normalize(), "f"))
    latest_at = dict(session.execute(select(PriceLatest.asset, PriceLatest.at)).all())
    srcs: dict[str, list[dict]] = {}
    for s in session.scalars(select(PriceSource).order_by(PriceSource.asset, PriceSource.rank)):
        srcs.setdefault(s.asset, []).append(
            {"rank": s.rank, "source": s.source, "ticker": s.ticker, "quote": s.quote}
        )
    # the price 24 hours ago from the fine prices (ADR 0044): the last one before that moment
    from app.modules.prices.models import PriceFine

    ago = datetime.now(UTC) - timedelta(hours=24)
    day_ago: dict[str, tuple[Decimal, str]] = {}
    for asset, close, quote in session.execute(
        select(PriceFine.asset, PriceFine.close, PriceFine.quote)
        .where(PriceFine.at <= ago, PriceFine.at > ago - timedelta(hours=2))
        .order_by(PriceFine.asset, PriceFine.at)
    ):
        day_ago[asset] = (close, quote)
    out = []
    for a in sorted(
        session.scalars(select(PriceAsset)), key=lambda x: (-usage.get(x.asset, 0), x.asset)
    ):
        if a.asset in canon:
            continue  # merged: rests until the merge is undone
        n, lo, hi = stats.get(a.asset, (0, None, None))
        g = gaps.get(a.asset)
        is_ended = hi is not None and hi < today - timedelta(days=MAX_AGE_DAYS)
        price = valuer.in_currency(valuer.latest_eur(a.asset, today), today, currency)
        # the change against the close before today and 7/30/90 days back (Vanixxx, 2026-10-14)
        changes = {}
        if a.asset in day_ago and price is not None:
            close, quote = day_ago[a.asset]
            then = valuer.in_currency(
                valuer._to_eur(close, quote, ago.date()), ago.date(), currency
            )
            changes["h24"] = (
                format(((price - then) / then * 100).quantize(Decimal("0.01")), "f")
                if then
                else None
            )
        else:
            changes["h24"] = None
        for key, back in (("d1", 1), ("d7", 7), ("d30", 30), ("d90", 90)):
            day = today - timedelta(days=back)
            then = valuer.in_currency(valuer.eur(a.asset, day), day, currency)
            changes[key] = (
                format(((price - then) / then * 100).quantize(Decimal("0.01")), "f")
                if price is not None and then
                else None
            )
        out.append(
            {
                "asset": a.asset,
                "name": a.name,
                "confirmed": a.confirmed,
                "ignored": a.ignored,
                "worthless_since": a.worthless_since.isoformat() if a.worthless_since else None,
                "prices_until": a.prices_until.isoformat() if a.prices_until else None,
                "icon": a.icon,
                "aliases": sorted(alias_of.get(a.asset, [])),
                "sources": srcs.get(a.asset, []),
                "needed_from": need.get(a.asset).isoformat() if a.asset in need else None,
                "rows": usage.get(a.asset, 0),
                "days": n,
                "first_day": lo.isoformat() if lo else None,
                "last_day": hi.isoformat() if hi else None,
                "gap": {
                    "from": g.from_day.isoformat(),
                    "to": g.to_day.isoformat(),
                    "reason": g.reason,
                }
                if g
                else None,
                "price": None if price is None or is_ended else format(price.normalize(), "f"),
                "ended_on": hi.isoformat() if is_ended else None,
                "currency": currency,
                "contributions": contributions.get(a.asset, {}),
                "spark": spark.get(a.asset, [])[::SPARK_STEP],
                "changes": changes,
                "price_at": latest_at[a.asset].isoformat()
                if a.asset in latest_at
                else (hi.isoformat() if hi else None),
            }
        )
    return out


SPARK_SPANS = {
    # span: (step of the fine prices, one point per, how far back)
    "h24": ("5m", timedelta(minutes=30), timedelta(hours=24)),
    "d7": ("1h", timedelta(hours=3), timedelta(days=7)),
    "d30": ("1h", timedelta(hours=12), timedelta(days=30)),
}
"""The curve follows the span chosen on the page (Vanixxx, 2026-10-16): about 50 points each."""


def sparks(session: Session, span: str, currency: str = "EUR") -> dict[str, list[str]]:
    """Per coin the curve over the span, ending with today's price. "d1" runs from the close
    before today (what its change compares with) through today's 5-minute prices; "d90" is
    the daily curve of the overview. Coins without fine prices fall back to daily closes."""
    from app.modules.prices.models import PriceFine

    now = datetime.now(UTC)
    today = now.date()
    valuer = Valuer(session)

    def money(close: Decimal, quote: str, day: date) -> str | None:
        v = valuer.in_currency(valuer._to_eur(close, quote, day), day, currency)
        return None if v is None else format(v.normalize(), "f")

    if span == "d1":
        step, every, since = "5m", timedelta(minutes=15), datetime.combine(today, time(), UTC)
    elif span in SPARK_SPANS:
        step, every, back = SPARK_SPANS[span]
        since = now - back
    else:
        step, every, since = None, None, now - timedelta(days=SPARK_DAYS)
    out: dict[str, list[str]] = {}
    if step:
        kept: dict[str, dict[int, tuple]] = {}
        for asset, at, close, quote in session.execute(
            select(PriceFine.asset, PriceFine.at, PriceFine.close, PriceFine.quote)
            .where(PriceFine.step == step, PriceFine.at >= since)
            .order_by(PriceFine.asset, PriceFine.at)
        ):
            # the last price of each bucket
            kept.setdefault(asset, {})[int((at - since) / every)] = (close, quote, at.date())
        for asset, buckets in kept.items():
            out[asset] = [v for v in (money(*buckets[k]) for k in sorted(buckets)) if v is not None]
    # daily closes: the 90-day curve, and where fine prices are missing
    first = today - timedelta(days=1) if span == "d1" else since.date()
    daily: dict[str, list[str]] = {}
    for r in session.scalars(
        select(PriceDaily)
        .where(PriceDaily.day >= first, PriceDaily.day < today if span == "d1" else true())
        .order_by(PriceDaily.asset, PriceDaily.day)
    ):
        v = money(r.close, r.quote, r.day)
        if v is not None:
            daily.setdefault(r.asset, []).append(v)
    if span == "d1":
        for asset, values in daily.items():
            if asset in out:
                out[asset] = values[-1:] + out[asset]
    elif span != "h24":
        for asset, values in daily.items():
            out.setdefault(asset, values[:: SPARK_STEP if span == "d90" else 1])
    for asset, values in out.items():
        price = valuer.in_currency(valuer.latest_eur(asset, today), today, currency)
        if price is not None:
            values.append(format(price.normalize(), "f"))
    return {a: v for a, v in out.items() if len(v) > 1}


def _usage_query():
    sides = [
        select(getattr(RawTransaction, f"{s}_asset").label("asset")).where(
            getattr(RawTransaction, f"{s}_asset").is_not(None), current()
        )
        for s in ("incoming", "outgoing", "fee")
    ]
    u = union_all(*sides).subquery()
    return select(u.c.asset, func.count()).group_by(u.c.asset)


def history(session: Session, asset: str, days: int, currency: str = "EUR") -> list[dict]:
    """The asset's daily series in euro, for the chart: close, high, low and source."""
    if session.get(PriceAsset, asset) is None and asset not in FIAT:
        raise AppError("prices.unknown_asset", 404)
    valuer = Valuer(session)
    since = datetime.now(UTC).date() - timedelta(days=days)
    rows = session.scalars(
        select(PriceDaily)
        .where(PriceDaily.asset == asset, PriceDaily.day >= since)
        .order_by(PriceDaily.day)
    ).all()
    out = []
    for r in rows:
        eur = valuer.in_currency(valuer._to_eur(r.close, r.quote, r.day), r.day, currency)
        if eur is None:
            continue
        factor = eur / r.close
        out.append(
            {
                "day": r.day.isoformat(),
                "close": format(eur.normalize(), "f"),
                "high": format((r.high * factor).normalize(), "f") if r.high else None,
                "low": format((r.low * factor).normalize(), "f") if r.low else None,
                "source": r.source,
            }
        )
    return out


def changes(session: Session, asset: str) -> list[dict]:
    return [
        {
            "field": c.field,
            "before": c.before,
            "after": c.after,
            "reason": c.reason,
            "at": c.changed_at.isoformat(),
        }
        for c in session.scalars(
            select(PriceMappingChange)
            .where(PriceMappingChange.asset == asset)
            .order_by(PriceMappingChange.id.desc())
        )
    ]


CROSSCHECK_DAYS = 90
CROSSCHECK_FINE = Decimal("2")
"""Up to 2 % mean deviation is unremarkable: measured, Yahoo and Bitget lie 0.2 % apart; a
mix-up of coins is off by orders of magnitude, not by two percent."""


def crosscheck(session: Session, asset: str) -> dict:
    """Two agreeing sources are evidence, one alone is a claim: Yahoo vs Bitget, 90 days,
    both in USD (Bitget via the USDT series). Changes nothing."""
    if session.get(PriceAsset, asset) is None:
        raise AppError("prices.unknown_asset", 404)
    end = datetime.now(UTC).date() - timedelta(days=1)
    start = end - timedelta(days=CROSSCHECK_DAYS)
    try:
        yahoo = {p.day: p.close for p in sources.yahoo_daily(f"{asset}-USD", start, end)}
        bitget = (
            {p.day: p.close for p in sources.bitget_daily(f"{asset}USDT", start, end)}
            if asset != "USDT"
            else {}
        )
    except sources.SourceUnavailable as exc:
        return {"asset": asset, "days": 0, "verdict": "unavailable", "reason": str(exc)}
    usdt = Valuer(session).prices
    diffs = []
    for day, y in yahoo.items():
        b = bitget.get(day)
        u = usdt.get(("USDT", day))
        if b is None or u is None:
            continue
        diffs.append(abs(b * u[0] - y) / y * 100)
    if not diffs:
        return {"asset": asset, "days": 0, "verdict": "no_overlap"}
    mean = sum(diffs) / len(diffs)
    return {
        "asset": asset,
        "days": len(diffs),
        "mean_pct": format(mean.quantize(Decimal("0.01")), "f"),
        "max_pct": format(max(diffs).quantize(Decimal("0.01")), "f"),
        "verdict": "ok" if mean <= CROSSCHECK_FINE else "deviates",
    }
