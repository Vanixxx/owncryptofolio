"""Balance check per source (ADR 0039): what the source reports against what the
transactions add up to. A difference is a data-quality signal (missing history, a wrong
row), shown in the UI, never hidden."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.balances.models import BalanceSnapshot
from app.modules.merged.service import valid_rows
from app.modules.plugins.contract import ALIASES, ASSET_MAX
from app.modules.prices.models import AssetAlias, PriceAsset
from app.modules.raw.models import RawTransaction
from app.modules.sources.models import Source

log = logging.getLogger(__name__)

TOLERANCE = Decimal("0.001")  # 0.1 %: exchanges round balances, chains are exact
DUST = Decimal("0.00000001")
# money and dollar coins: exchanges show cents, so a few cents apart is still right
# (Vanixxx, 2026-10-10: "computed 0.03913 EUR, balance 0.03" was flagged)
CENTS = Decimal("0.05")
MONEY = frozenset({"EUR", "USD", "USDT", "USDC", "DAI", "FDUSD", "EURC", "BUSD"})


def known_tokens(session: Session, source: Source) -> dict[str, tuple[str, int]]:
    """Token symbol → (contract, decimals) from the chain rows already read: a balance is
    asked for exactly the tokens this address ever moved."""
    out: dict[str, tuple[str, int]] = {}
    rows = session.scalars(
        select(RawTransaction.raw).where(
            RawTransaction.source_id == source.id, RawTransaction.channel == "chain"
        )
    )
    for raw in rows:
        raw = raw or {}
        info = raw.get("token_info") or {}  # TronGrid's TRC-20 rows
        contract = raw.get("contractAddress") or info.get("address")
        symbol = (
            (raw.get("tokenSymbol") or raw.get("asset") or info.get("symbol") or "").strip().upper()
        )
        decimals = raw.get("tokenDecimal") or raw.get("decimal") or info.get("decimals")
        if contract and symbol and decimals not in (None, ""):
            out.setdefault(symbol, (contract, int(decimals)))
    return out


def symbol(asset: str) -> str:
    """The raw layer's normalisation: spam names longer than 40 characters are cut there
    too, so both sides of the comparison meet."""
    s = asset.strip().upper()[:ASSET_MAX]
    return ALIASES.get(s, s)


def store(
    session: Session, source: Source, amounts: list[tuple[str, str, Decimal]], origin: str
) -> int:
    at = datetime.now(UTC)
    for market, asset, amount in amounts:
        session.add(
            BalanceSnapshot(
                source_id=source.id,
                market=market,
                asset=symbol(asset),
                amount=amount,
                origin=origin,
                at=at,
            )
        )
    session.commit()
    return len(amounts)


ACCRUAL_MIN = Decimal("0.000001")
"""Below this an accrual is rounding, not growth."""


def after_fetch(session: Session, source: Source, module, *, secrets=None, key=None) -> dict:
    """Takes the balance right after a fetch. Never fails the fetch: a source without a
    balance endpoint, or one that is down, leaves the comparison as it was."""
    fn = getattr(module, "balance", None)
    if fn is None:
        return {}
    try:
        if secrets is not None:
            amounts = fn(secrets)
        else:
            amounts = fn(source.address, key=key, tokens=known_tokens(session, source))
        stored = store(session, source, amounts, "api" if secrets is not None else "chain")
    except Exception as exc:  # noqa: BLE001 — the balance is a bonus, the fetch is done
        from app.modules.sources import vault

        # an exchange may echo the signed request, an explorer error the key in its URL:
        # never into the log or the job result (review 2026-10-24)
        text = vault.scrub(str(exc), secrets if secrets is not None else {"key": key or ""})
        log.warning("Balance of source %s failed: %s", source.id, text)
        session.rollback()
        return {"balance_error": text[:200]}
    return {"balance_assets": stored}


def set_manual(
    session: Session, source_id: int, asset: str, amount: str, market: str = "spot"
) -> None:
    source = session.get(Source, source_id)
    if source is None:
        raise AppError("sources.not_found", 404)
    try:
        value = Decimal(str(amount).strip().replace(",", "."))
    except Exception as exc:  # noqa: BLE001
        raise AppError("balances.invalid_amount", 400) from exc
    if not asset.strip() or not value.is_finite() or value < 0:
        raise AppError("balances.invalid_amount", 400)
    store(session, source, [(market, asset.strip(), value)], "manual")


def _plain(v: Decimal | None) -> str | None:
    return None if v is None else format(v.normalize(), "f")


def reconcile(session: Session) -> list[dict]:
    alias = dict(session.execute(select(AssetAlias.alias, AssetAlias.asset)).all())
    spam = set(session.scalars(select(PriceAsset.asset).where(PriceAsset.ignored.is_(True))))
    icons = dict(
        session.execute(
            select(PriceAsset.asset, PriceAsset.icon).where(PriceAsset.icon.is_not(None))
        ).all()
    )
    canon = lambda a: alias.get(a, a)  # noqa: E731
    # money the portfolio assumes paid in by card or PayPal at a buy (2026-10-10): it came
    # in at that place, else the place's euros would show the whole purchase as missing
    from app.modules.portfolio.service import auto_deposits

    auto = auto_deposits(session)
    computed: dict[tuple[int, str, str], Decimal] = {}
    for r in valid_rows(session):
        if r.id in auto:
            key = (r.source_id, r.market, canon(auto[r.id][0]))
            computed[key] = computed.get(key, Decimal(0)) + auto[r.id][1]
        for asset, amount, sign in (
            (r.incoming_asset, r.incoming_amount, 1),
            (r.outgoing_asset, r.outgoing_amount, -1),
            (r.fee_asset, r.fee_amount, -1),
        ):
            if asset and amount:
                key = (r.source_id, r.market, canon(asset))
                computed[key] = computed.get(key, Decimal(0)) + sign * amount
    # A fetch answers for the whole source at one moment: only its latest answer counts,
    # else a coin that is gone now (sold, sent away) would keep its last old amount. A
    # manual balance names single coins, so there the latest entry per coin counts.
    batch = (
        select(BalanceSnapshot.source_id, func.max(BalanceSnapshot.at).label("at"))
        .where(BalanceSnapshot.origin != "manual")
        .group_by(BalanceSnapshot.source_id)
        .subquery()
    )
    manual = (
        select(
            BalanceSnapshot.source_id,
            BalanceSnapshot.market,
            BalanceSnapshot.asset,
            func.max(BalanceSnapshot.at).label("at"),
        )
        .where(BalanceSnapshot.origin == "manual")
        .group_by(BalanceSnapshot.source_id, BalanceSnapshot.market, BalanceSnapshot.asset)
        .subquery()
    )
    latest = list(
        session.scalars(
            select(BalanceSnapshot).join(
                batch,
                (BalanceSnapshot.source_id == batch.c.source_id)
                & (BalanceSnapshot.at == batch.c.at)
                & (BalanceSnapshot.origin != "manual"),
            )
        )
    ) + list(
        session.scalars(
            select(BalanceSnapshot).join(
                manual,
                (BalanceSnapshot.source_id == manual.c.source_id)
                & (BalanceSnapshot.market == manual.c.market)
                & (BalanceSnapshot.asset == manual.c.asset)
                & (BalanceSnapshot.at == manual.c.at)
                & (BalanceSnapshot.origin == "manual"),
            )
        )
    )
    # summed within one answer (several symbols can be one coin); between the fetch and a
    # manual entry for the same coin the newer one counts, never both (review 2026-10-24)
    parts: dict[tuple[bool, tuple[int, str, str]], tuple[Decimal, datetime, str]] = {}
    for b in latest:
        key = (b.source_id, b.market, canon(b.asset))
        prev = parts.get((b.origin == "manual", key))
        parts[(b.origin == "manual", key)] = (
            (prev[0] if prev else Decimal(0)) + b.amount,
            b.at,
            b.origin,
        )
    actual: dict[tuple[int, str, str], tuple[Decimal, datetime, str]] = {}
    for (_, key), value in parts.items():
        if key not in actual or value[1] > actual[key][1]:
            actual[key] = value
    # An exchange lists everything it holds in a market, so a coin missing there is 0. A
    # chain is only asked for known tokens and a manual balance names single coins: there
    # a missing coin is unchecked, not 0 (a BNB token without contract stays open).
    complete = {(k[0], k[1]) for k, v in actual.items() if v[2] == "api"}
    out = []
    for source in session.scalars(select(Source).order_by(Source.kind, Source.label)):
        has_actual = any(k[0] == source.id for k in actual)
        items = []
        for key in sorted(
            {k for k in computed if k[0] == source.id} | {k for k in actual if k[0] == source.id}
        ):
            calc = computed.get(key)
            got = actual.get(key)
            if (calc is None or abs(calc) <= DUST) and (got is None or abs(got[0]) <= DUST):
                continue
            if got is None and key[:2] in complete:
                got = (Decimal(0), None, "api")
            ok = None
            if got is not None:
                floor = CENTS if key[2] in MONEY else DUST
                ok = abs((calc or Decimal(0)) - got[0]) <= max(floor, abs(got[0]) * TOLERANCE)
            items.append(
                {
                    "market": key[1],
                    "asset": key[2],
                    "computed": _plain(calc),
                    "actual": _plain(got[0]) if got else None,
                    "diff": _plain((calc or Decimal(0)) - got[0]) if got else None,
                    "ok": ok,
                    "spam": key[2] in spam,
                    "icon": icons.get(key[2], key[2]),
                    "at": got[1].isoformat() if got and got[1] else None,
                    "origin": got[2] if got else None,
                }
            )
        relevant = [i for i in items if not i["spam"] and i["ok"] is not None]
        out.append(
            {
                "source_id": source.id,
                "checked": has_actual,
                "status": "none"
                if not has_actual
                else ("ok" if all(i["ok"] for i in relevant) else "diff"),
                "differences": sum(1 for i in relevant if not i["ok"]),
                "unchecked": sum(
                    1 for i in items if has_actual and not i["spam"] and i["ok"] is None
                ),
                "at": max((i["at"] for i in items if i["at"]), default=None),
                "items": items,
            }
        )
    return out


def book_accrual(session: Session, source: Source, assets: list[str]) -> dict:
    """What a coin grew by holding (VTHO from VET) has no transaction: whatever the balance
    just taken holds beyond the transactions is booked as income, a reward, at the time of
    the fetch (Vanixxx, 2026-10-09). Less than the transactions is a gap, never booked."""
    from app.modules.plugins.contract import IncomeKind, Kind, Movement
    from app.modules.raw import service as raw
    from app.modules.raw.models import RawTransaction, current

    booked = {}
    for asset in assets:
        snap = session.scalar(
            select(BalanceSnapshot)
            .where(BalanceSnapshot.source_id == source.id, BalanceSnapshot.asset == asset)
            .order_by(BalanceSnapshot.at.desc())
            .limit(1)
        )
        if snap is None:
            continue
        held = Decimal(0)
        for r in session.scalars(
            select(RawTransaction).where(RawTransaction.source_id == source.id, current())
        ):
            if r.incoming_asset == asset:
                held += r.incoming_amount or 0
            if r.outgoing_asset == asset:
                held -= r.outgoing_amount or 0
            if r.fee_asset == asset:
                held -= r.fee_amount or 0
        grown = snap.amount - held
        if grown <= ACCRUAL_MIN:
            continue
        at = snap.at
        raw.import_movements(
            session,
            source,
            "chain",
            "Accrual",
            [
                Movement(
                    timestamp=at,
                    kind=Kind.INCOME,
                    income_kind=IncomeKind.REWARD,
                    incoming_asset=asset,
                    incoming_amount=grown,
                    external_id=f"accrual:{asset}:{at:%Y%m%dT%H%M%S}",
                    comment=f"{asset} generated by holding (balance minus transactions)",
                    raw={"balance": str(snap.amount), "transactions": str(held)},
                )
            ],
        )
        booked[asset] = format(grown.normalize(), "f")
    return {"accrued": booked} if booked else {}
