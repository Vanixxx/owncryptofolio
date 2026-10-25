"""Fills a demo database with an invented portfolio, for screenshots (Vanixxx, 2026-10-23).

Everything here is made up: wallets, addresses, transaction ids, amounts, dates. Only the market
prices are real (Yahoo, as the app itself uses them). It refuses any database whose name does
not end in `_demo`, so a real portfolio can never be touched.

    DATABASE_URL=…/owncryptofolio_demo DATA_DIR=/tmp/ocf-demo BACKGROUND_WORKERS=false \
        uv run python -m scripts.demo_data
"""

from __future__ import annotations

import random
import secrets
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_DOWN, Decimal

from app.bootstrap.run import run_bootstrap
from app.core.config import get_settings
from app.core.db import _session_factory
from app.modules import models  # noqa: F401
from app.modules.auth import service as auth
from app.modules.balances.service import store
from app.modules.plugins.contract import IncomeKind, Kind, Movement
from app.modules.prices import service as prices
from app.modules.prices.sources import yahoo_daily
from app.modules.raw import service as raw
from app.modules.settings import service as settings
from app.modules.sources import service as sources

PASSWORD = "demo password 123"
START, END = date(2022, 1, 3), date(2026, 10, 20)
COINS = {
    "BTC": "BTC-EUR",
    "ETH": "ETH-EUR",
    "SOL": "SOL-EUR",
    "ADA": "ADA-EUR",
    "LINK": "LINK-EUR",
    "DOT": "DOT-EUR",
}
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
rnd = random.Random(20261023)


def q(v: Decimal, places: int = 8) -> Decimal:
    return v.quantize(Decimal(1).scaleb(-places), rounding=ROUND_DOWN)


def txid() -> str:
    return secrets.token_hex(32)


def at(d: date, hour: int | None = None) -> datetime:
    return datetime(
        d.year,
        d.month,
        d.day,
        hour if hour is not None else rnd.randint(8, 21),
        rnd.randint(0, 59),
        tzinfo=UTC,
    )


class Prices:
    def __init__(self) -> None:
        self.by: dict[str, dict[date, Decimal]] = {}
        for coin, ticker in COINS.items():
            self.by[coin] = {
                p.day: p.close for p in yahoo_daily(ticker, START - timedelta(days=5), END)
            }

    def eur(self, coin: str, d: date) -> Decimal:
        days = self.by[coin]
        while d not in days:
            d -= timedelta(days=1)
        return days[d]


def build(px: Prices) -> dict[str, list[Movement]]:
    out: dict[str, list[Movement]] = {
        k: [] for k in ("kraken", "bitget", "coinbase", "btc_cold", "eth_ledger", "sol_phone")
    }
    held = {
        "kraken": {"BTC": Decimal(0), "ETH": Decimal(0)},
        "bitget": {"SOL": Decimal(0), "ADA": Decimal(0), "LINK": Decimal(0)},
    }

    def buy(place: str, coin: str, eur: Decimal, d: date, quote: str = "EUR") -> None:
        price = px.eur(coin, d) * Decimal("1.002")
        qty = q(eur / price)
        fee = q(eur * Decimal("0.0026"), 2)
        out[place].append(
            Movement(
                timestamp=at(d),
                kind=Kind.TRADE,
                incoming_asset=coin,
                incoming_amount=qty,
                outgoing_asset=quote,
                outgoing_amount=eur,
                fee_asset=quote,
                fee_amount=fee,
                external_id=txid()[:24],
            )
        )
        held.setdefault(place, {}).setdefault(coin, Decimal(0))
        held[place][coin] += qty

    def sell(place: str, coin: str, qty: Decimal, d: date) -> None:
        eur = q(qty * px.eur(coin, d) * Decimal("0.998"), 2)
        out[place].append(
            Movement(
                timestamp=at(d),
                kind=Kind.TRADE,
                incoming_asset="EUR",
                incoming_amount=eur,
                outgoing_asset=coin,
                outgoing_amount=qty,
                fee_asset="EUR",
                fee_amount=q(eur * Decimal("0.0026"), 2),
                external_id=txid()[:24],
            )
        )
        held[place][coin] -= qty
        return eur - q(eur * Decimal("0.0026"), 2)

    def transfer(src: str, dst: str, coin: str, qty: Decimal, d: date, fee: Decimal) -> None:
        h = txid()
        when = at(d)
        out[src].append(
            Movement(
                timestamp=when,
                kind=Kind.SEND,
                outgoing_asset=coin,
                outgoing_amount=qty,
                fee_asset=coin,
                fee_amount=fee,
                external_id=h,
            )
        )
        out[dst].append(
            Movement(
                timestamp=when + timedelta(minutes=rnd.randint(4, 25)),
                kind=Kind.RECEIVE,
                incoming_asset=coin,
                incoming_amount=qty,
                external_id=h,
            )
        )
        held[src][coin] -= qty + fee
        held.setdefault(dst, {}).setdefault(coin, Decimal(0))
        held[dst][coin] += qty

    events: list[tuple[date, int, object]] = []

    def on(d: date, fn) -> None:
        if d <= END:
            events.append((d, len(events), fn))

    # Kraken: a savings plan from 2022 on, 250–600 € a month into BTC and ETH
    d = START
    while d <= END:
        amount = Decimal(rnd.choice([250, 300, 400, 500, 600]))

        def plan(d=d, amount=amount):
            out["kraken"].append(
                Movement(
                    timestamp=at(d, 7),
                    kind=Kind.FIAT_DEPOSIT,
                    incoming_asset="EUR",
                    incoming_amount=amount,
                    external_id=txid()[:24],
                )
            )
            buy("kraken", "BTC", q(amount * Decimal("0.59"), 2), d)
            buy("kraken", "ETH", q(amount * Decimal("0.39"), 2), d)

        on(d, plan)
        if d.year >= 2023:  # ETH staked on Kraken: a little income each month

            def stake_eth(d=d + timedelta(days=14)):
                reward = q(held["kraken"]["ETH"] * Decimal("0.0028"))
                if reward > 0:
                    out["kraken"].append(
                        Movement(
                            timestamp=at(d),
                            kind=Kind.INCOME,
                            income_kind=IncomeKind.STAKING,
                            incoming_asset="ETH",
                            incoming_amount=reward,
                            external_id=txid()[:24],
                        )
                    )
                    held["kraken"]["ETH"] += reward

            on(d + timedelta(days=14), stake_eth)
        if d.month in (6, 12):  # twice a year the bitcoin goes to the cold wallet

            def to_cold(d=d + timedelta(days=7)):
                btc = q(held["kraken"]["BTC"] * Decimal("0.9"), 6)
                if btc > Decimal("0.001"):
                    transfer("kraken", "btc_cold", "BTC", btc, d, Decimal("0.00002"))
                eth = q(held["kraken"]["ETH"] * Decimal("0.7"), 6)
                if d.month == 12 and eth > Decimal("0.01"):
                    transfer(
                        "kraken", "eth_ledger", "ETH", eth, d + timedelta(days=1), Decimal("0.0015")
                    )

            on(d + timedelta(days=7), to_cold)
        d = (d.replace(day=1) + timedelta(days=32)).replace(day=3)

    # Bitget from 2023: altcoins, staking, a sale with gain, one with loss
    for n, d in enumerate(
        [
            date(2023, 2, 14),
            date(2023, 5, 2),
            date(2023, 9, 18),
            date(2024, 1, 9),
            date(2024, 6, 21),
        ]
    ):

        def alt(d=d, n=n):
            out["bitget"].append(
                Movement(
                    timestamp=at(d, 9),
                    kind=Kind.FIAT_DEPOSIT,
                    incoming_asset="EUR",
                    incoming_amount=Decimal(1500),
                    external_id=txid()[:24],
                )
            )
            buy("bitget", "SOL", Decimal(700), d + timedelta(days=1))
            buy("bitget", ["ADA", "LINK"][n % 2], Decimal(500), d + timedelta(days=2))

        on(d, alt)
    for n in range(42):

        def stake_sol(d=date(2023, 3, 1) + timedelta(days=30 * n)):
            if held["bitget"]["SOL"] > 0:
                reward = q(held["bitget"]["SOL"] * Decimal("0.0055"))
                out["bitget"].append(
                    Movement(
                        timestamp=at(d),
                        kind=Kind.INCOME,
                        income_kind=IncomeKind.STAKING,
                        incoming_asset="SOL",
                        incoming_amount=reward,
                        external_id=txid()[:24],
                    )
                )
                held["bitget"]["SOL"] += reward

        on(date(2023, 3, 1) + timedelta(days=30 * n), stake_sol)
    on(
        date(2024, 3, 12),
        lambda: sell(
            "bitget", "ADA", q(held["bitget"]["ADA"] * Decimal("0.6"), 4), date(2024, 3, 12)
        ),
    )
    on(
        date(2025, 2, 4),
        lambda: sell(
            "bitget", "LINK", q(held["bitget"]["LINK"] * Decimal("0.5"), 4), date(2025, 2, 4)
        ),
    )

    # a short trade inside the holding period: a taxable gain for the tax report
    def swing_buy():
        out["bitget"].append(
            Movement(
                timestamp=at(date(2025, 3, 10), 9),
                kind=Kind.FIAT_DEPOSIT,
                incoming_asset="EUR",
                incoming_amount=Decimal(3000),
                external_id=txid()[:24],
            )
        )
        buy("bitget", "ETH", Decimal(2990), date(2025, 3, 11))

    on(date(2025, 3, 10), swing_buy)
    on(
        date(2025, 9, 15),
        lambda: sell(
            "bitget", "ETH", q(held["bitget"]["ETH"] * Decimal("0.9"), 4), date(2025, 9, 15)
        ),
    )
    on(
        date(2025, 7, 3),
        lambda: transfer(
            "bitget",
            "sol_phone",
            "SOL",
            q(held["bitget"]["SOL"] * Decimal("0.5"), 4),
            date(2025, 7, 3),
            Decimal("0.01"),
        ),
    )

    # a bitcoin sale after more than a year, the money out to the bank
    def cash_out():
        # bitcoin back from the cold wallet, sold after more than a year, the euro to the bank
        transfer(
            "btc_cold", "kraken", "BTC", Decimal("0.12"), date(2025, 12, 15), Decimal("0.00003")
        )
        eur = sell(
            "kraken", "BTC", q(held["kraken"]["BTC"] * Decimal("0.8"), 6), date(2025, 12, 20)
        )
        out["kraken"].append(
            Movement(
                timestamp=at(date(2025, 12, 21)),
                kind=Kind.FIAT_WITHDRAWAL,
                outgoing_asset="EUR",
                outgoing_amount=q(eur * Decimal("0.95"), 0),
                external_id=txid()[:24],
            )
        )

    on(date(2025, 12, 20), cash_out)

    # Coinbase: one early DOT purchase, still held
    def dot():
        out["coinbase"].append(
            Movement(
                timestamp=at(date(2022, 3, 1), 10),
                kind=Kind.FIAT_DEPOSIT,
                incoming_asset="EUR",
                incoming_amount=Decimal(800),
                external_id=txid()[:24],
            )
        )
        buy("coinbase", "DOT", Decimal(790), date(2022, 3, 2))

    on(date(2022, 3, 1), dot)
    for _, _, fn in sorted(events, key=lambda e: (e[0], e[1])):
        fn()
    return out


def fake_address(kind: str) -> str:
    if kind == "bitcoin":
        return "bc1q" + "".join(rnd.choice("023456789acdefghjklmnpqrstuvwxyz") for _ in range(38))
    if kind == "ethereum":
        return "0x" + secrets.token_hex(20)
    return "".join(rnd.choice(B58) for _ in range(44))


def main() -> int:
    s = get_settings()
    if not s.database_url.endswith("_demo"):
        print("refused: the database name must end in _demo", file=sys.stderr)
        return 1
    run_bootstrap(s, 30)
    px = Prices()
    data = build(px)
    with _session_factory()() as db:
        if not auth.is_set_up(db):
            auth.set_password(db, PASSWORD)
        settings.update(
            db,
            {
                "general.currency": "EUR",
                "report.name": "Max Mustermann",
                "report.address": "Musterstraße 1, 12345 Musterstadt",
                "report.tax_number": "123/456/78901",
            },
        )
        made = {
            "kraken": sources.create(db, "kraken", "Kraken", None),
            "bitget": sources.create(db, "bitget", "Bitget", None),
            "coinbase": sources.create(db, "coinbase", "Coinbase", None),
        }
        cold = sources.create_wallet(db, "Ledger Nano")
        phone = sources.create_wallet(db, "Phantom")
        made["btc_cold"] = sources.create(
            db, "bitcoin", "Bitcoin", fake_address("bitcoin"), cold.id
        )
        made["eth_ledger"] = sources.create(
            db, "ethereum", "Ethereum", fake_address("ethereum"), cold.id
        )
        made["sol_phone"] = sources.create(db, "solana", "Solana", fake_address("solana"), phone.id)
        for src in made.values():
            src.auto_fetch = False
        db.commit()
        for key, rows in data.items():
            channel = "chain" if made[key].kind == "wallet" else "api"
            run = raw.import_movements(
                db, made[key], channel, "Beispieldaten", sorted(rows, key=lambda m: m.timestamp)
            )
            print(key, run.added, "Zeilen")
        print("Kurse:", prices.run_all(db))
        # balances as the places would report them: what the rows add up to
        for key, rows in data.items():
            totals: dict[str, Decimal] = {}
            for m in rows:
                for asset, amount, sign in (
                    (m.incoming_asset, m.incoming_amount, 1),
                    (m.outgoing_asset, m.outgoing_amount, -1),
                    (m.fee_asset, m.fee_amount, -1),
                ):
                    if asset and amount:
                        totals[asset] = totals.get(asset, Decimal(0)) + sign * amount
            store(
                db,
                made[key],
                [("spot", a, v) for a, v in totals.items() if v >= 0],
                "chain" if made[key].kind == "wallet" else "api",
            )
        db.commit()
    print("fertig — anmelden mit:", PASSWORD)
    return 0


if __name__ == "__main__":
    sys.exit(main())
