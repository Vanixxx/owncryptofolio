"""Prices (ADR 0019): needs, suggestions, rank filling, gaps, FX weekends, valuing."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app.modules.plugins.contract import Kind, Movement
from app.modules.prices import service, sources
from app.modules.prices.models import FxDaily, PriceAsset, PriceDaily, PriceGap, PriceSource
from app.modules.prices.sources import Point

D0 = date(2024, 3, 1)


def days(start: date, n: int, price: str = "100") -> list[Point]:
    return [
        Point(start + timedelta(days=i), Decimal(price), Decimal(price) * 2, Decimal(price) / 2)
        for i in range(n)
    ]


@pytest.fixture
def raw_rows(authed, db):
    from app.modules.raw import service as raw
    from app.modules.sources.models import Source

    authed.post("/api/sources", json={"provider": "manual", "label": "X"})
    source = db.query(Source).one()
    t = datetime(2024, 3, 1, 12, tzinfo=UTC)
    moves = [
        Movement(
            timestamp=t,
            kind=Kind.TRADE,
            incoming_asset="SOL",
            incoming_amount=Decimal(1),
            outgoing_asset="EUR",
            outgoing_amount=Decimal(100),
            fee_asset="USDT",
            fee_amount=Decimal("0.1"),
        ),
        Movement(
            timestamp=t + timedelta(days=5),
            kind=Kind.RECEIVE,
            incoming_asset="KAS",
            incoming_amount=Decimal(10),
        ),
        Movement(
            timestamp=t + timedelta(days=6),
            kind=Kind.RECEIVE,
            incoming_asset="VISIT WEBSITE LINKGIVEAWAY .COM TO CLAIM",
            incoming_amount=Decimal(1),
        ),
    ]
    raw.import_movements(db, source, "file", "x", moves)
    return source


def test_needs_from_raw_without_fiat(raw_rows, db):
    need = service.needs(db)
    assert need["SOL"] == D0 and need["USDT"] == D0 and need["KAS"] == date(2024, 3, 6)
    assert "EUR" not in need and "VISIT WEBSITE LINKGIVEAWAY .COM TO CLAIM" in need


def test_usable_treats_zero_as_no_price():
    assert (
        sources.usable("0.0") is None and sources.usable(0) is None and sources.usable(None) is None
    )
    assert sources.usable("5.5e-09") == Decimal("5.5e-09")


def test_suggestions_check_coverage_and_spam_is_ignored(raw_rows, db, monkeypatch):
    def yahoo(ticker, start, end):
        if ticker in ("SOL-USD", "USDT-USD"):
            return days(start, 30)
        if ticker == "KAS-USD":
            return days(start, 1)  # a name match with a single day is no match
        raise sources.SourceUnavailable("unknown")

    monkeypatch.setattr(sources, "yahoo_daily", yahoo)
    monkeypatch.setattr(sources, "bitget_daily", lambda t, a, b: [])  # never the network in tests
    monkeypatch.setattr(sources, "binance_daily", lambda t, a, b: [])
    monkeypatch.setattr(
        sources, "bitget_pairs", lambda: {"KASUSDT": Decimal("0.1"), "SOLUSDT": Decimal(150)}
    )
    monkeypatch.setattr(
        sources, "yahoo_meta", lambda t: ("Solana" if t == "SOL-USD" else None, Decimal(150))
    )
    service.refresh_mappings(db, service.needs(db))
    mapped = {(s.asset, s.rank): (s.source, s.ticker) for s in db.query(PriceSource)}
    assert mapped[("SOL", 1)] == ("yahoo", "SOL-USD") and mapped[("SOL", 2)] == (
        "bitget",
        "SOLUSDT",
    )
    assert mapped[("KAS", 1)] == ("bitget", "KASUSDT") and ("KAS", 2) not in mapped
    sol = db.get(PriceAsset, "SOL")
    assert sol.name == "Solana" and not sol.confirmed
    spam = db.get(PriceAsset, "VISIT WEBSITE LINKGIVEAWAY .COM TO CLAIM")
    assert spam.ignored and not spam.confirmed
    # existing mappings are never touched by a new suggestion run
    db.query(PriceSource).filter_by(asset="SOL", rank=2).delete()
    db.commit()
    service.refresh_mappings(db, service.needs(db))
    assert db.query(PriceSource).filter_by(asset="SOL").count() == 1


def _map(db, asset, *ranked):
    db.add(PriceAsset(asset=asset, confirmed=True))
    for i, (src, ticker) in enumerate(ranked, 1):
        db.add(
            PriceSource(asset=asset, rank=i, source=src, ticker=ticker, quote=service.QUOTES[src])
        )
    db.commit()


def test_lower_rank_wins_and_the_next_fills_a_real_hole(db, monkeypatch):
    _map(db, "GRT", ("yahoo", "GRT-USD"), ("bitget", "GRTUSDT"))
    today = D0 + timedelta(days=21)
    monkeypatch.setattr(sources, "yahoo_daily", lambda t, s, e: days(D0, 10, "1"))  # ends early
    monkeypatch.setattr(sources, "bitget_daily", lambda t, s, e: days(D0, 20, "2"))
    service.fetch_history(db, "GRT", D0, today)
    rows = {r.day: (r.source, r.close) for r in db.query(PriceDaily).filter_by(asset="GRT")}
    assert len(rows) == 20 and db.get(PriceGap, "GRT") is None
    assert rows[D0] == ("yahoo", Decimal(1)) and rows[D0 + timedelta(days=15)] == (
        "bitget",
        Decimal(2),
    )


def test_a_small_hole_does_not_ask_the_next_rank(db, monkeypatch):
    _map(db, "SOL", ("yahoo", "SOL-USD"), ("bitget", "SOLUSDT"))
    asked = []
    pts = [p for p in days(D0, 20) if p.day != D0 + timedelta(days=5)]
    monkeypatch.setattr(sources, "yahoo_daily", lambda t, s, e: pts)
    monkeypatch.setattr(sources, "bitget_daily", lambda t, s, e: asked.append(t) or [])
    service.fetch_history(db, "SOL", D0, D0 + timedelta(days=20))
    assert asked == []


def test_missing_start_is_noted_as_gap(db, monkeypatch):
    _map(db, "VARA", ("coingecko", "vara-network"))
    monkeypatch.setattr(
        sources, "coingecko_daily", lambda t, s, e: days(D0 + timedelta(days=10), 10)
    )
    service.fetch_history(db, "VARA", D0, D0 + timedelta(days=20))
    gap = db.get(PriceGap, "VARA")
    assert (gap.from_day, gap.to_day) == (D0, D0 + timedelta(days=9))


def test_fx_weekend_takes_friday_marked(db, monkeypatch):
    friday = date(2024, 3, 1)
    monkeypatch.setattr(
        sources,
        "get_json",
        lambda url: {
            "rates": {
                "2024-02-29": {"EUR": 0.92},
                "2024-03-01": {"EUR": 0.921},
                "2024-03-04": {"EUR": 0.923},
            }
        },
    )
    service.fetch_fx(db, friday, date(2024, 3, 4))
    sunday = db.get(FxDaily, (date(2024, 3, 3), "USD", "EUR"))
    assert sunday.approximated and sunday.source_day == friday and sunday.rate == Decimal("0.921")
    assert not db.get(FxDaily, (friday, "USD", "EUR")).approximated


def test_valuer_links_usdt_falls_back_a_week_and_never_says_zero(db):
    day = date(2024, 3, 10)
    db.add_all(
        [
            PriceDaily(asset="KAS", day=day, quote="USDT", close=Decimal("0.2"), source="bitget"),
            PriceDaily(asset="USDT", day=day, quote="USD", close=Decimal("0.999"), source="yahoo"),
            FxDaily(
                day=day,
                base="USD",
                quote="EUR",
                rate=Decimal("0.9"),
                approximated=False,
                source_day=day,
            ),
        ]
    )
    db.commit()
    v = service.Valuer(db)
    assert v.eur("KAS", day) == Decimal("0.2") * Decimal("0.999") * Decimal("0.9")
    assert (
        v.eur("KAS", day + timedelta(days=7)) is not None
        and ("KAS", day + timedelta(days=7)) in v.fell_back
    )
    assert v.eur("KAS", day + timedelta(days=8)) is None  # a dead source shows, no 0
    assert v.eur("EUR", day) == 1 and v.eur("USD", day) == Decimal("0.9")


def test_changing_sources_needs_a_reason_and_is_kept_as_history(db):
    _map(db, "S", ("yahoo", "S-USD"))
    db.add(PriceDaily(asset="S", day=D0, quote="USD", close=Decimal(1), source="yahoo"))
    db.commit()
    with pytest.raises(Exception, match="prices.reason_required"):
        service.update_mapping(db, "S", "Sonic", [("bitget", "SUSDT")], None)
    service.update_mapping(db, "S", "Sonic", [("bitget", "SUSDT")], "Yahoo S-USD is another coin")
    assert [(s.source, s.quote) for s in db.query(PriceSource).filter_by(asset="S")] == [
        ("bitget", "USDT")
    ]
    assert db.query(PriceDaily).filter_by(asset="S").count() == 0  # old prices were another coin
    ch = service.changes(db, "S")
    assert {c["field"] for c in ch} == {"sources", "name"}
    assert next(c for c in ch if c["field"] == "sources")["reason"] == "Yahoo S-USD is another coin"
    service.update_mapping(
        db, "S", "Sonic", [("bitget", "SUSDT")], None
    )  # unchanged: no history, no reason
    assert len(service.changes(db, "S")) == 2


def test_api_overview_confirm_ignore(authed, db, raw_rows):
    _map(db, "SOL", ("yahoo", "SOL-USD"))
    db.add(PriceAsset(asset="KAS"))
    db.commit()
    rows = {r["asset"]: r for r in authed.get("/api/prices/assets").json()}
    assert rows["SOL"]["sources"][0]["ticker"] == "SOL-USD" and rows["SOL"]["rows"] == 1
    assert (
        rows["KAS"]["confirmed"] is False
        and rows["KAS"]["price"] is None
        and rows["KAS"]["currency"] == "EUR"
    )
    assert authed.post("/api/prices/assets/KAS/confirm").status_code == 204
    assert (
        authed.post(
            "/api/prices/assets/KAS/ignore", json={"ignored": True, "reason": "spam"}
        ).status_code
        == 204
    )
    kas = next(r for r in authed.get("/api/prices/assets").json() if r["asset"] == "KAS")
    assert kas["confirmed"] and kas["ignored"]
    r = authed.put(
        "/api/prices/assets/SOL",
        json={"sources": [{"source": "nope", "ticker": "x"}], "reason": "x"},
    )
    assert r.json()["error"]["code"] == "prices.invalid_source"


def test_daily_price_run_is_scheduled_once(client, monkeypatch):
    from app.modules.backup import schedule
    from app.modules.jobs import service as jobs

    monkeypatch.setattr(jobs, "RUNNERS", {**jobs.RUNNERS, "prices": lambda s, j, p: {}})
    after = datetime(2026, 10, 4, 3, 0, tzinfo=UTC)  # 05:00 Berlin, after 04:30
    assert schedule.prices_once(after) is True
    assert schedule.prices_once(after + timedelta(minutes=5)) is False


def test_delisted_coins_come_from_bitget_candles_or_binance_and_are_asked_again(
    raw_rows, db, monkeypatch
):
    calls = []

    def no_yahoo(ticker, start, end):
        raise sources.SourceUnavailable("HTTP 404")

    def bitget(ticker, start, end):
        calls.append(("bitget", ticker))
        return days(start, 30) if ticker == "KASUSDT" else []  # delisted pair, candles still there

    binance_up = {"on": False}

    def binance(ticker, start, end):
        calls.append(("binance", ticker))
        return days(start, 30) if binance_up["on"] and ticker == "SOLUSDT" else []

    monkeypatch.setattr(sources, "yahoo_daily", no_yahoo)
    monkeypatch.setattr(sources, "bitget_pairs", lambda: {})
    monkeypatch.setattr(sources, "bitget_daily", bitget)
    monkeypatch.setattr(sources, "binance_daily", binance)
    need = service.needs(db)
    service.refresh_mappings(db, need)
    assert [(s.source, s.ticker) for s in db.query(PriceSource).filter_by(asset="KAS")] == [
        ("bitget", "KASUSDT")
    ]
    assert db.query(PriceSource).filter_by(asset="SOL").count() == 0
    binance_up["on"] = True  # a source appears later: unconfirmed, unmapped assets are asked again
    service.refresh_mappings(db, need)
    assert [(s.source, s.quote) for s in db.query(PriceSource).filter_by(asset="SOL")] == [
        ("binance", "USDT")
    ]
    assert ("binance", "USDTUSDT") not in calls


def test_display_currency_usd_over_the_ecb_rate(db):
    day = date(2024, 3, 10)
    db.add_all(
        [
            PriceDaily(asset="SOL", day=day, quote="USD", close=Decimal(100), source="yahoo"),
            FxDaily(
                day=day,
                base="USD",
                quote="EUR",
                rate=Decimal("0.9"),
                approximated=False,
                source_day=day,
            ),
        ]
    )
    db.commit()
    v = service.Valuer(db)
    eur = v.eur("SOL", day)
    assert (
        eur == Decimal(90)
        and v.in_currency(eur, day, "USD") == Decimal(100)
        and v.in_currency(eur, day, "EUR") == eur
    )


def test_alias_counts_for_the_coin_it_stands_for(raw_rows, db, monkeypatch):
    from app.modules.prices.models import AssetAlias

    _map(db, "KAS", ("bitget", "KASUSDT"))
    db.add(PriceDaily(asset="KAS", day=D0, quote="USD", close=Decimal(1), source="bitget"))
    db.commit()
    with pytest.raises(Exception, match="prices.reason_required"):
        service.set_alias(db, "KAS", "NGL", "Entangle", None)
    with pytest.raises(Exception, match="prices.invalid_alias"):
        service.set_alias(db, "KAS", "kas", None, "same")
    service.set_alias(db, "kas", "ngl", "Entangle", "MEXC writes NTGL, Bitget NGL")
    assert db.get(AssetAlias, "KAS").asset == "NGL"
    # KAS rests while merged: kept, but neither listed nor fetched
    assert db.query(PriceDaily).filter_by(asset="KAS").count() == 1
    assert db.get(PriceAsset, "NGL").name == "Entangle"
    need = service.needs(db)
    assert "KAS" not in need and need["NGL"] == date(2024, 3, 6)
    rows = {r["asset"]: r for r in service.overview(db)}
    assert rows["NGL"]["aliases"] == ["KAS"] and rows["NGL"]["rows"] == 1 and "KAS" not in rows
    # NGL had no source of its own: it took over KAS's mapping and history (2026-10-06)
    assert [x.ticker for x in db.query(PriceSource).filter_by(asset="NGL")] == ["KASUSDT"]
    db.query(PriceDaily).filter_by(asset="NGL").delete()
    db.add(PriceDaily(asset="NGL", day=D0, quote="EUR", close=Decimal(2), source="coingecko"))
    db.commit()
    assert service.Valuer(db).eur("KAS", D0) == Decimal(2)  # the raw symbol is valued as NGL
    assert any(c["field"] == "alias" for c in service.changes(db, "NGL"))
    service.remove_alias(db, "KAS")
    assert "KAS" in service.needs(db)
    # split: KAS is back with its own mapping and price, NGL keeps its copy
    rows = {r["asset"]: r for r in service.overview(db)}
    assert rows["KAS"]["sources"][0]["ticker"] == "KASUSDT" and rows["KAS"]["days"] == 1
    assert rows["NGL"]["sources"][0]["ticker"] == "KASUSDT"


def test_default_source_order_puts_the_exchange_first(raw_rows, db, monkeypatch):
    from app.modules.settings import service as settings

    monkeypatch.setattr(sources, "yahoo_daily", lambda t, s, e: days(s, 30))
    monkeypatch.setattr(sources, "bitget_daily", lambda t, s, e: [])
    monkeypatch.setattr(sources, "binance_daily", lambda t, s, e: [])
    monkeypatch.setattr(sources, "bitget_pairs", lambda: {"SOLUSDT": Decimal(1)})
    monkeypatch.setattr(sources, "yahoo_meta", lambda t: (None, None))
    settings.update(db, {"prices.source_order": ["bitget", "yahoo", "binance"]})
    service.refresh_mappings(db, {"SOL": D0})
    assert [
        s.source for s in db.query(PriceSource).filter_by(asset="SOL").order_by(PriceSource.rank)
    ] == ["bitget", "yahoo"]
    with pytest.raises(Exception, match="settings.invalid_value"):
        settings.update(db, {"prices.source_order": ["bitget", "bitget"]})
    # unconfirmed coins get a fresh suggestion after the order changed; confirmed stay
    db.get(PriceAsset, "SOL").confirmed = False
    db.commit()
    assert service.resuggest_unconfirmed(db) >= 1
    assert db.query(PriceSource).filter_by(asset="SOL").count() == 0


def test_icon_override_is_kept_with_history(db):
    _map(db, "RENDER", ("yahoo", "RENDER-USD"))
    service.update_mapping(db, "RENDER", None, [("yahoo", "RENDER-USD")], None, icon="rndr")
    assert db.get(PriceAsset, "RENDER").icon == "RNDR"
    assert [c["field"] for c in service.changes(db, "RENDER")] == ["icon"]


def test_live_prices_batch_exchanges_and_throttle_yahoo(db, monkeypatch):
    _map(db, "SOL", ("yahoo", "SOL-USD"), ("bitget", "SOLUSDT"))
    _map(db, "AMP", ("yahoo", "AMP-USD"))
    _map(db, "FTM", ("binance", "FTMUSDT"))
    calls = []
    monkeypatch.setattr(
        sources, "bitget_pairs", lambda: calls.append("bitget") or {"SOLUSDT": Decimal(150)}
    )
    monkeypatch.setattr(
        sources, "binance_prices", lambda: calls.append("binance") or {"FTMUSDT": Decimal("0.5")}
    )
    monkeypatch.setattr(
        sources, "yahoo_meta", lambda t: calls.append(t) or (None, Decimal("0.004"))
    )
    monkeypatch.setattr(service, "_last_live", None)
    t0 = datetime(2026, 10, 4, 12, tzinfo=UTC)
    assert service.refresh_live(db, t0) == 3
    # the ranking counts: SOL has Yahoo first, so no Bitget substitute (CRO, 2026-10-05)
    assert sorted(calls) == ["AMP-USD", "SOL-USD", "binance"]
    calls.clear()
    assert service.refresh_live(db, t0 + timedelta(seconds=5)) == 0  # throttled
    service.refresh_live(db, t0 + timedelta(seconds=60))
    assert "AMP-USD" not in calls and "bitget" not in calls  # Yahoo at most every 5 minutes


def _chart(closes):
    start = 1719532800
    return {
        "chart": {
            "result": [
                {
                    "meta": {},
                    "timestamp": [start + i * 86400 for i in range(len(closes))],
                    "indicators": {"quote": [{"close": closes, "high": closes, "low": closes}]},
                }
            ]
        }
    }


def test_yahoo_series_below_a_ten_thousandth_is_refused(monkeypatch):
    monkeypatch.setattr(sources, "get_json", lambda url: _chart([9.999999974752427e-07] * 20))
    with pytest.raises(sources.SourceUnavailable, match="six decimals"):
        sources.yahoo_daily("QUBIC-USD", date(2024, 6, 1), date(2024, 8, 1))
    monkeypatch.setattr(sources, "get_json", lambda url: _chart([0.4] * 20))
    assert len(sources.yahoo_daily("FTM-USD", date(2024, 6, 1), date(2024, 8, 1))) == 20


def test_ended_series_shows_no_current_price(db, monkeypatch):
    from app.modules.prices.models import PriceLatest

    _map(db, "FTM", ("binance", "FTMUSDT"))
    db.add(
        PriceDaily(
            asset="FTM", day=date(2025, 1, 13), quote="USDT", close=Decimal("0.7"), source="binance"
        )
    )
    db.add(
        PriceLatest(
            asset="FTM", quote="USDT", price=Decimal("0.7"), source="binance", at=datetime.now(UTC)
        )
    )
    db.commit()
    row = next(r for r in service.overview(db) if r["asset"] == "FTM")
    assert row["price"] is None and row["ended_on"] == "2025-01-13"
    monkeypatch.setattr(service, "_last_live", None)
    monkeypatch.setattr(
        sources, "binance_prices", lambda: {"FTMUSDT": Decimal("0.7")}
    )  # the stale last price
    service.refresh_live(db)
    assert db.get(PriceLatest, "FTM") is None


def test_coingecko_ids_are_lower_case(db):
    _map(db, "XEN", ("yahoo", "XEN-USD"))
    service.update_mapping(db, "XEN", None, [("coingecko", "Xen-crypto")], "Yahoo rounds XEN to 0")
    assert db.query(PriceSource).filter_by(asset="XEN").one().ticker == "xen-crypto"


def test_removing_an_alias_brings_the_coin_back(db, monkeypatch):
    from datetime import datetime as dt

    from app.modules.plugins.contract import Kind, Movement
    from app.modules.raw import service as raw
    from app.modules.sources.models import Source

    db.add(Source(provider="manual", kind="exchange", label="X"))
    db.commit()
    src = db.query(Source).one()
    raw.import_movements(
        db,
        src,
        "file",
        "t",
        [
            Movement(
                timestamp=dt(2025, 1, 1, tzinfo=UTC),
                kind=Kind.RECEIVE,
                incoming_asset="NTGL",
                incoming_amount=Decimal(1),
            )
        ],
    )
    _map(db, "NGL", ("bitget", "NGLUSDT"))
    monkeypatch.setattr(service, "refresh_mappings", lambda s, need: 0)
    service.set_alias(db, "NTGL", "NGL", None, "same coin")
    # merged before 2026-10-06: the entry was deleted (here it never existed)
    assert db.get(PriceAsset, "NTGL") is None
    service.remove_alias(db, "NTGL")
    assert db.get(PriceAsset, "NTGL") is not None


def test_merging_keeps_the_price_source_when_the_target_has_none(db):
    from datetime import date as d

    from app.modules.prices.models import PriceDaily

    _map(db, "NGL", ("bitget", "NGLUSDT"))
    db.add(
        PriceDaily(
            asset="NGL", day=d(2025, 1, 1), quote="USDT", close=Decimal("0.3"), source="bitget"
        )
    )
    db.add(PriceAsset(asset="NTGL", confirmed=False))
    db.commit()
    service.set_alias(db, "NGL", "NTGL", None, "Bitget's name")
    assert [s.ticker for s in db.query(PriceSource).filter_by(asset="NTGL")] == ["NGLUSDT"]
    assert db.query(PriceDaily).filter_by(asset="NTGL").count() == 1
    assert [r["asset"] for r in service.overview(db)] == ["NTGL"]
    # splitting shows both again, each with the price (Vanixxx, 2026-10-06)
    service.remove_alias(db, "NGL")
    rows = {r["asset"]: r for r in service.overview(db)}
    assert set(rows) == {"NGL", "NTGL"}
    assert all(r["sources"][0]["ticker"] == "NGLUSDT" and r["days"] == 1 for r in rows.values())
    # merging again keeps NTGL's copy and does not stack a second one
    service.set_alias(db, "NGL", "NTGL", None, "Bitget's name")
    assert db.query(PriceSource).filter_by(asset="NTGL").count() == 1


def test_tickers_with_hidden_or_foreign_letters_are_spam():
    assert service.looks_spam("B៙N៙B") and service.looks_spam("UЅDС")
    assert not service.looks_spam("BNB") and not service.looks_spam("USDC.E")


def test_one_coin_is_fetched_alone(raw_rows, authed, db, monkeypatch):
    """The prices page fetches a single coin (Vanixxx, 2026-10-10): only its tickers are asked."""
    _map(db, "SOL", ("yahoo", "SOL-USD"))
    _map(db, "KAS", ("yahoo", "KAS-USD"))
    asked: list[str] = []
    # up to yesterday: a series that stopped long ago gets no current price
    monkeypatch.setattr(
        sources, "yahoo_daily", lambda t, s, e: asked.append(t) or days(e - timedelta(days=2), 3)
    )
    monkeypatch.setattr(
        sources, "yahoo_meta", lambda t: asked.append(f"now {t}") or (None, Decimal(7))
    )
    monkeypatch.setattr(service, "fetch_fx", lambda session, start: 0)
    body = authed.post("/api/prices/assets/sol/fetch").json()
    assert body["asset"] == "SOL" and body["prices"] >= 1 and body["latest"] == 1
    assert set(asked) == {"SOL-USD", "now SOL-USD"}
    assert authed.post("/api/prices/assets/NOPE/fetch").status_code == 404


def test_price_at_a_moment_and_now(authed, db):
    from datetime import UTC, date, datetime
    from decimal import Decimal

    from app.modules.prices.models import PriceDaily, PriceLatest

    db.add(
        PriceDaily(
            asset="BTC", day=date(2024, 3, 12), quote="EUR", close=Decimal(60000), source="t"
        )
    )
    db.add(
        PriceLatest(
            asset="BTC", quote="EUR", price=Decimal(90000), source="t", at=datetime.now(UTC)
        )
    )
    db.commit()
    then = authed.get("/api/prices/at?asset=btc&at=2024-03-12T14:00").json()
    assert (then["price"], then["latest"], then["day"]) == ("60000", False, "2024-03-12")
    assert authed.get("/api/prices/at?asset=BTC").json()["price"] == "90000"
    assert authed.get("/api/prices/at?asset=NOPE").json()["price"] is None


def test_the_rate_service_down_does_not_stop_the_coin_prices(db, monkeypatch):
    """Review 2026-10-24: a Frankfurter outage raised and ended the whole price run."""
    from datetime import date

    from app.modules.prices import service, sources

    def down(*_a, **_k):
        raise sources.SourceUnavailable("HTTP 503")

    monkeypatch.setattr(sources, "ecb_usd_eur", down)
    assert service.fetch_fx(db, date(2025, 1, 1)) == 0


def test_a_price_end_still_to_come_keeps_the_prices_until_then(db):
    """Review 2026-10-24: any end date made the coin 'ended' at once."""
    from datetime import date, timedelta

    from app.modules.prices import service
    from app.modules.prices.models import PriceAsset

    today = date(2026, 10, 24)
    db.add(PriceAsset(asset="AAA", prices_until=today + timedelta(days=30)))
    db.add(PriceAsset(asset="BBB", prices_until=today - timedelta(days=1)))
    db.commit()
    gone = service.ended(db, today)
    assert "BBB" in gone and "AAA" not in gone


def test_a_merged_symbol_gets_no_fine_prices(db):
    from app.modules.prices import fine
    from app.modules.prices.models import AssetAlias, PriceSource

    db.add(PriceSource(asset="OLD", rank=1, source="yahoo", ticker="OLD-USD", quote="USD"))
    db.add(PriceSource(asset="NEW", rank=1, source="yahoo", ticker="NEW-USD", quote="USD"))
    db.add(AssetAlias(alias="OLD", asset="NEW"))
    db.commit()
    assert fine._assets(db) == ["NEW"]
