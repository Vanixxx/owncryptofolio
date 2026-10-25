import zipfile
from decimal import Decimal

import pytest

from integrations.kraken_file.reader import read as kraken
from integrations.kucoin_file.reader import read as kucoin

KRAKEN_HEAD = "txid,refid,time,type,subtype,aclass,asset,wallet,amount,fee,balance"


def kraken_csv(tmp_path, rows):
    p = tmp_path / "ledgers.csv"
    p.write_text("\n".join([KRAKEN_HEAD, *rows]) + "\n")
    return p


def test_kraken_trade_deposit_withdrawal(tmp_path):
    p = kraken_csv(
        tmp_path,
        [
            "L1,R1,2024-03-17 10:00:00,deposit,,currency,ZEUR,spot,179,0,179",
            "L2,R2,2024-03-17 11:00:00,trade,,currency,ZEUR,spot,-149.25,0.388,29.36",
            "L3,R2,2024-03-17 11:00:00,trade,,currency,DOT.S,spot,20,0,20",
            "L4,R3,2024-03-17 12:00:00,withdrawal,,currency,USDT,spot,-120.7,1,0",
        ],
    )
    ms = {m.kind.value: m for m in kraken(p)}
    assert ms["fiat_deposit"].incoming_asset == "EUR"
    t = ms["trade"]
    assert (t.outgoing_asset, t.incoming_asset, t.fee_asset) == ("EUR", "DOT", "EUR")
    assert (ms["send"].outgoing_amount, ms["send"].fee_amount) == (Decimal("120.7"), Decimal(1))
    assert ms["send"].timestamp.utcoffset().total_seconds() == 0


def test_kraken_futures_transfers_must_net_to_zero(tmp_path):
    ok = kraken_csv(
        tmp_path,
        [
            "L1,R1,2024-03-17 10:00:00,transfer,spottofutures,currency,USDT,spot,-50,0,0",
            "L2,R2,2024-03-18 10:00:00,transfer,spotfromfutures,currency,USDT,spot,50,0,50",
        ],
    )
    assert [m.kind.value for m in kraken(ok)] == ["internal_transfer", "internal_transfer"]
    bad = kraken_csv(
        tmp_path,
        [
            "L1,R1,2024-03-17 10:00:00,transfer,spottofutures,currency,USDT,spot,-50,0,0",
            "L2,R2,2024-03-18 10:00:00,transfer,spotfromfutures,currency,USDT,spot,30,0,30",
        ],
    )
    with pytest.raises(ValueError, match="net to zero"):
        list(kraken(bad))


def test_kraken_unknown_type_rejected(tmp_path):
    p = kraken_csv(tmp_path, ["L1,R1,2024-03-17 10:00:00,staking,,currency,DOT,spot,1,0,1"])
    with pytest.raises(ValueError, match="unknown booking types"):
        list(kraken(p))


def kucoin_zip(tmp_path, files):
    p = tmp_path / "BillingHistory.zip"
    with zipfile.ZipFile(p, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return p


def test_kucoin_reads_topic_files_events_and_futures(tmp_path):
    p = kucoin_zip(
        tmp_path,
        {
            "Spot-Orders_Erfüllte Aufträge.csv": "UID,Order ID,Symbol,Side,Filled Amount,Filled Volume,Fee,Fee Currency,Filled Time(UTC+02:00)\n"
            "1,o1,VET-USDT,BUY,1000,40,0.04,USDT,2024-03-20 12:00:00\n",
            "Einzahlungs-_Auszahlungsverlauf_Einzahlungsverlauf.csv": "UID,Time(UTC+02:00),Coin,Amount,Fee,Status,Remarks\n1,2024-03-17 12:03:00,USDT,120.7,0,SUCCESS,\n",
            "Fiat-Währungsaufträge_Fiat-Währungseinzahlungen.csv": "UID,Order ID,Time(UTC+02:00),Currency (Fiat),Fiat Amount,Fee,Status,Deposit Method\n"
            "1,f1,2024-03-15 10:00:00,EUR,180,0,CANCELLED,SEPA\n",
            "Kontoverlauf_Handelskonto.csv": "UID,Time(UTC+02:00),Currency,Amount,Type,Side\n"
            "1,2024-04-25 10:00:00,VTHO,56.276201,KuCoin Event,Deposit\n"
            "1,2024-03-20 12:00:00,USDT,40,Spot,Withdrawal\n",
            "Futures-Orders_Realisierte GuV.csv": "UID,Account Type,Symbol,Close Type,Realized PNL,Position Opening Time(UTC+02:00),"
            '",Position Closing Time(UTC+02:00)"\n'
            "1,main,VETUSDTM,CLOSE_LONG,-19.69870666,2024-03-21 20:02:00,2024-03-22 15:22:28\n",
        },
    )
    ms = list(kucoin(p))
    kinds = sorted(f"{m.market.value}:{m.kind.value}" for m in ms)
    assert kinds == [
        "futures:futures_position",
        "futures:realized_pnl",
        "spot:income",
        "spot:receive",
        "spot:trade",
    ]  # cancelled fiat deposit is not booked
    pnl = next(m for m in ms if m.kind.value == "realized_pnl")
    assert (pnl.outgoing_asset, pnl.outgoing_amount, pnl.timestamp.hour) == (
        "USDT",
        Decimal("19.69870666"),
        13,
    )
    for m in ms:
        m.check()


def test_kucoin_unknown_history_type_rejected(tmp_path):
    p = kucoin_zip(
        tmp_path,
        {
            "Kontoverlauf_Handelskonto.csv": "UID,Time(UTC+02:00),Currency,Amount,Type,Side\n1,2024-04-25 10:00:00,X,1,Lucky Draw,Deposit\n"
        },
    )
    with pytest.raises(ValueError, match="unknown booking type"):
        list(kucoin(p))


def test_kucoin_transfers_to_futures_from_the_account_history(tmp_path):
    """A transfer without its twin in the other spot account went to futures (2026-10-11)."""
    head = "UID,Account Type,Currency,Side,Amount,Fee,Time(UTC+02:00),Remark,Type\n"
    p = kucoin_zip(
        tmp_path,
        {
            "Kontoverlauf_Handelskonto.csv": head
            + "1,main,USDT,Withdrawal,110.83843666,0,2024-03-21 19:55:35,Finanzierungskonto,Transfer\n"
            "1,main,USDT,Deposit,91.13973,0,2024-03-22 23:02:09,,Transfer\n",
            "Kontoverlauf_Finanzierungskonto.csv": head
            + "1,main,USDT,Deposit,110.83843666,0,2024-03-21 19:55:35,Finanzierungskonto,Transfer\n"
            "1,main,USDT,Withdrawal,110.83843666,0,2024-03-21 19:56:24,Futures-Konto,Transfer\n",
        },
    )
    ms = [m for m in kucoin(p) if m.kind.value == "internal_transfer"]
    got = sorted(
        (m.timestamp.hour, m.market.value, m.outgoing_amount or -m.incoming_amount) for m in ms
    )
    assert got == [
        (17, "futures", Decimal("-110.83843666")),
        (17, "spot", Decimal("110.83843666")),
        (21, "futures", Decimal("91.13973")),
        (21, "spot", Decimal("-91.13973")),
    ]
    for m in ms:
        m.check()
