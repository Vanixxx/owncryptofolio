"""Text from outside (token names from airdrops, comments, counterparties) must never become a
formula in a spreadsheet the user opens (review 2026-10-24): a spam token called
`=HYPERLINK(...)` would otherwise be a live link."""

from openpyxl.worksheet.worksheet import Worksheet

START = ("=", "+", "-", "@", "\t", "\r")


def csv_text(text: str) -> str:
    """A leading apostrophe tells the spreadsheet: this is text."""
    return "'" + text if text.startswith(START) else text


def as_text(ws: Worksheet) -> Worksheet:
    """Every cell openpyxl took for a formula is plain text again: the app writes no formulas."""
    for row in ws.iter_rows():
        for cell in row:
            if cell.data_type == "f":
                cell.data_type = "s"
    return ws
