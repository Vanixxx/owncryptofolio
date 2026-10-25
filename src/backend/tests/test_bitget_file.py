from collections import Counter
from decimal import Decimal

import pytest

from integrations.bitget_file import reader
from tests.bitget_zip import LEDGER, build


@pytest.fixture
def export(tmp_path):
    return build(tmp_path / "Order-Verlauf exportieren-2026-08-26 02_55_34.zip")


def test_reads_all_parts(export):
    ms = list(reader.read(export, {"timezone": "Europe/Berlin"}))
    for m in ms:
        m.check()
    kinds = Counter(f"{m.market.value}:{m.kind.value}" for m in ms)
    assert kinds == {
        "spot:trade": 2,
        "spot:receive": 1,
        "spot:send": 1,
        "spot:migration": 1,
        "spot:internal_transfer": 1,
        "spot:other": 1,
        "futures:internal_transfer": 1,
        "futures:fee": 1,
        "futures:realized_pnl": 1,
        "futures:funding": 1,
        "futures:futures_position": 1,
    }


def test_time_zone_from_download_date(export):
    # Download in August -> CEST (+02:00): 10:00 local is 08:00 UTC.
    trade = next(
        m for m in reader.read(export, {"timezone": "Europe/Berlin"}) if m.kind.value == "trade"
    )
    assert trade.timestamp.hour == 8


def test_withdrawal_net_and_fee_by_arithmetic(export):
    send = next(m for m in reader.read(export, {}) if m.kind.value == "send")
    assert send.outgoing_amount == Decimal("99") and send.fee_amount == Decimal("1")
    assert send.external_id == "tx2" and send.counterparty == "0xdef"


def test_failed_withdrawal_is_not_booked(export):
    assert all(m.external_id != "tx3" for m in reader.read(export, {}))


def test_trades_are_not_doubled_from_transactions(export):
    assert sum(1 for m in reader.read(export, {}) if m.kind.value == "trade") == 2


def test_migration_is_not_a_trade(export):
    mig = next(m for m in reader.read(export, {}) if m.kind.value == "migration")
    assert (mig.outgoing_asset, mig.incoming_asset) == ("MATIC", "POL")


def test_margin_adjustment_is_skipped_and_ledger_adds_up(export):
    ms = [m for m in reader.read(export, {}) if m.market.value == "futures"]
    assert all(m.comment != "adjust_margin_ifm" for m in ms)
    pnl = next(m for m in ms if m.kind.value == "realized_pnl")
    assert pnl.incoming_amount == Decimal(5) and pnl.fee_amount == Decimal("0.2")


def test_ledger_that_does_not_add_up_is_rejected(tmp_path):
    broken = [row[:] for row in LEDGER]
    broken[0][8] = "60"  # reported final balance no longer matches the movements
    path = build(tmp_path / "Order-Verlauf exportieren-2026-08-26 02_55_34.zip", broken)
    with pytest.raises(ValueError, match="does not add up"):
        list(reader.read(path, {}))


def test_unknown_type_is_kept_as_other(export):
    other = next(m for m in reader.read(export, {}) if m.kind.value == "other")
    assert other.comment == "Some new type" and other.incoming_amount == Decimal(5)


def test_skipped_files_are_named(export):
    assert any("Spot-Order-Verlauf" in name for name in reader.skipped(export))


def test_not_a_zip_is_refused(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError, match="ZIP"):
        list(reader.read(p, {}))
