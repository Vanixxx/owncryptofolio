"""A ZIP or Excel file (an Excel file is a ZIP too) is checked before it is opened: the
upload limit counts the packed size, a few kilobytes can unpack to gigabytes and take the
app down (review 2026-10-24). Real exports are far below these limits."""

from __future__ import annotations

import zipfile
from pathlib import Path

MAX_UNPACKED = 500 * 1024 * 1024
MAX_MEMBERS = 5000


def check(path: Path) -> None:
    """Raises ValueError for a ZIP that unpacks too large or holds too many files; anything
    that is not a ZIP is left to the reader."""
    if not zipfile.is_zipfile(path):
        return
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
    if len(infos) > MAX_MEMBERS or sum(i.file_size for i in infos) > MAX_UNPACKED:
        raise ValueError("the archive unpacks too large to be read")
