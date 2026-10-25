"""Builds a small synthetic Bitget export ZIP with the real column layout.
All numbers are invented; no real account data is committed."""

import csv
import io
import zipfile
from pathlib import Path

STAMP = "2026-08-26 02:55:40.532"  # download moment: summer time in Berlin (+02:00)


def _csv(header: list[str], rows: list[list[str]]) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(header)
    w.writerows(rows)
    return "﻿" + out.getvalue()


def build(path: Path, ledger_rows: list[list[str]] | None = None) -> Path:
    files = {
        f"Spot-Order-Details exportieren 1-{STAMP}.csv": _csv(
            [
                "Date",
                "Trading pair",
                "Direction",
                "Base Asset",
                "Quote Asset",
                "Amount",
                "Total",
                "Fee",
                "Fee Coin",
            ],
            [
                [
                    "2024-03-01 10:00:00",
                    "BTCUSDT",
                    "Buy",
                    "BTC",
                    "USDT",
                    "0.01",
                    "600",
                    "-0.00001",
                    "BTC",
                ],
                [
                    "2024-03-02 11:00:00",
                    "BTCUSDT",
                    "Sell",
                    "BTC",
                    "USDT",
                    "0.005",
                    "320",
                    "-0.32",
                    "USDT",
                ],
            ],
        ),
        f"Spot-Transaktionen exportieren 1-{STAMP}.csv": _csv(
            ["order", "Date", "Coin", "Type", "Amount", "Fee", "Available"],
            [
                ["\t1", "2024-03-01 10:00:00", "BTC", "Buy", "0.01", "0", "0.01"],
                ["\t2", "2024-03-03 09:00:00", "USDT", "Ordinary Withdrawal", "-99", "-1", "0"],
                ["\t3", "2024-03-04 08:00:00", "MATIC", "Reduce exchange rate", "-10", "0", "0"],
                ["\t3", "2024-03-04 08:00:00", "POL", "Increase exchange rate", "10", "0", "10"],
                ["\t4", "2024-03-05 08:00:00", "USDT", "Transfer out", "-50", "0", "0"],
                ["\t5", "2024-03-06 08:00:00", "EUR", "Some new type", "5", "0", "5"],
            ],
        ),
        f"Einzahlungs/Auszahlungs-Datensätze exportieren 1-{STAMP}.csv": _csv(
            ["Date", "Type", "Funding account", "Coin", "Quantity", "Address", "TxID", "Status"],
            [
                [
                    "2024-02-28 12:00:00",
                    "Deposit",
                    "-",
                    "USDT",
                    "1000",
                    "0xabc",
                    "tx1",
                    "Successful",
                ],
                [
                    "2024-03-03 09:05:00",
                    "Withdrawal",
                    "-",
                    "USDT",
                    "100",
                    "0xdef",
                    "tx2",
                    "Successful",
                ],
                ["2024-03-03 09:06:00", "Withdrawal", "-", "USDT", "7", "0xdef", "tx3", "Failed"],
            ],
        ),
        f"Spot-Order-Verlauf exportieren 1-{STAMP}.csv": _csv(
            ["Date", "Status"], [["x", "cancelled"]]
        ),
        f"Exportierte USDT-M-Futures-Transaktionen 1-{STAMP}.csv": _csv(
            [
                "Order",
                "Date",
                "Coin",
                "Futures",
                "Margin Mode",
                "Type",
                "Amount",
                "Fee",
                "Wallet balance",
            ],
            ledger_rows if ledger_rows is not None else LEDGER,
        ),
        f"Exportierter USDT-M-Futures-Positionsverlauf 1-{STAMP}.csv": _csv(
            ["Futures", "Opening time", "Closed time", "Realized PnL"],
            [["FETUSDT Short·Isolated", "2024-03-05 20:00:00", "2024-03-05 21:00:00", "0.3USDT"]],
        ),
    }
    with zipfile.ZipFile(path, "w") as z:
        for name, text in files.items():
            z.writestr(name, text.encode())
    return path


# Newest first, like the real export. Balance: 50 in, -0.1 fee, +5 pnl -0.2 fee,
# -0.05 funding; the margin adjustment moves no money.
LEDGER = [
    [
        "\t15",
        "2024-03-05 23:00:00",
        "USDT",
        "FETUSDT",
        "Single",
        "contract_margin_settle_fee",
        "-0.05",
        "0",
        "54.65",
    ],
    [
        "\t14",
        "2024-03-05 22:00:00",
        "USDT",
        "FETUSDT",
        "Single",
        "adjust_margin_ifm",
        "100",
        "0",
        "54.7",
    ],
    [
        "\t13",
        "2024-03-05 21:00:00",
        "USDT",
        "FETUSDT",
        "Single",
        "close_short",
        "5",
        "-0.2",
        "54.7",
    ],
    ["\t12", "2024-03-05 20:00:00", "USDT", "FETUSDT", "Single", "open_short", "0", "-0.1", "49.9"],
    [
        "\t11",
        "2024-03-05 08:00:00",
        "USDT",
        "NULL",
        "Single",
        "trans_from_exchange",
        "50",
        "0",
        "50",
    ],
]
