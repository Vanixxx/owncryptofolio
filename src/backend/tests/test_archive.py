"""Archives are checked before they are opened (review 2026-10-24)."""

import zipfile

import pytest

from app.modules.plugins import archive


def test_an_archive_that_unpacks_too_large_is_refused(tmp_path, monkeypatch):
    path = tmp_path / "bomb.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("a.csv", "0" * 100_000)  # packs to a few hundred bytes
    monkeypatch.setattr(archive, "MAX_UNPACKED", 50_000)
    with pytest.raises(ValueError, match="too large"):
        archive.check(path)
    monkeypatch.setattr(archive, "MAX_UNPACKED", 200_000)
    archive.check(path)  # fine
    (tmp_path / "plain.csv").write_text("a,b\n")
    archive.check(tmp_path / "plain.csv")  # not a ZIP: the reader decides


def test_the_readers_refuse_it_too(tmp_path, monkeypatch):
    from integrations.bitget_file import reader as bitget

    path = tmp_path / "Bitget.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("spot.csv", "0" * 100_000)
    monkeypatch.setattr(archive, "MAX_UNPACKED", 50_000)
    with pytest.raises(ValueError, match="too large"):
        list(bitget.read(path))
