from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from app.modules.plugins.contract import Kind, Market, Movement, fingerprint
from app.modules.plugins.registry import discover

T = datetime(2024, 3, 1, 12, tzinfo=UTC)


def test_naive_timestamp_is_refused():
    with pytest.raises(ValueError, match="time zone"):
        Movement(timestamp=datetime(2024, 1, 1), kind=Kind.OTHER)


def test_timestamp_is_converted_to_utc():
    m = Movement(
        timestamp=datetime(2024, 1, 1, 12, tzinfo=timezone(timedelta(hours=2))),
        kind=Kind.RECEIVE,
        incoming_asset="eth",
        incoming_amount=Decimal(1),
    )
    assert m.timestamp.hour == 10 and m.incoming_asset == "ETH"


def test_asset_alias_and_cut():
    m = Movement(timestamp=T, kind=Kind.RECEIVE, incoming_asset="mngl", incoming_amount=Decimal(1))
    assert m.incoming_asset == "NTGL"
    long = Movement(
        timestamp=T, kind=Kind.RECEIVE, incoming_asset="X" * 60, incoming_amount=Decimal(1)
    )
    assert len(long.incoming_asset) == 40


@pytest.mark.parametrize(
    "kwargs, message",
    [
        (
            {"kind": Kind.TRADE, "incoming_asset": "BTC", "incoming_amount": Decimal(1)},
            "both sides",
        ),
        ({"kind": Kind.RECEIVE, "incoming_asset": "BTC"}, "together"),
        ({"kind": Kind.SEND, "outgoing_asset": "BTC", "outgoing_amount": Decimal(-1)}, "negative"),
        (
            {"kind": Kind.INCOME, "incoming_asset": "ETH", "incoming_amount": Decimal(1)},
            "income_kind",
        ),
        (
            {"kind": Kind.FUNDING, "incoming_asset": "USDT", "incoming_amount": Decimal(1)},
            "futures",
        ),
        ({"kind": Kind.FUTURES_POSITION, "market": Market.FUTURES}, "instrument"),
        ({"kind": Kind.OTHER}, "empty"),
    ],
)
def test_check_rules(kwargs, message):
    with pytest.raises(ValueError, match=message):
        Movement(timestamp=T, **kwargs).check()


def test_position_without_sides_is_valid():
    Movement(
        timestamp=T, kind=Kind.FUTURES_POSITION, market=Market.FUTURES, instrument="BTCUSDT"
    ).check()


def test_fingerprint_ignores_number_notation_but_not_values():
    a = Movement(
        timestamp=T, kind=Kind.RECEIVE, incoming_asset="BTC", incoming_amount=Decimal("1.50")
    )
    b = Movement(
        timestamp=T, kind=Kind.RECEIVE, incoming_asset="BTC", incoming_amount=Decimal("1.5")
    )
    c = Movement(
        timestamp=T, kind=Kind.RECEIVE, incoming_asset="BTC", incoming_amount=Decimal("1.51")
    )
    assert fingerprint("1:file", a) == fingerprint("1:file", b) != fingerprint("1:file", c)
    assert fingerprint("1:file", a) != fingerprint("2:file", a)


def test_registry_finds_the_pilot_plugins():
    reg = discover()
    assert {"bitget_file", "bitget_api", "chain_ethereum"} <= set(reg.plugins)
    assert reg.errors == {}
    assert reg.find("bitget", reg.plugins["bitget_api"].channel).key == "bitget_api"


def test_broken_plugin_is_reported_not_fatal(tmp_path: Path, monkeypatch):
    pkg = tmp_path / "fakeplugins"
    (pkg / "broken").mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "broken" / "__init__.py").write_text("")
    (pkg / "broken" / "plugin.toml").write_text("[plugin]\nname = 'x'\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    reg = discover(pkg, "fakeplugins")
    assert reg.plugins == {} and "broken" in reg.errors
