from pathlib import Path

from sqlalchemy import func, select

from app.modules.imports.api import safe_name
from app.modules.raw.models import RawTransaction
from tests.bitget_zip import build

NAME = "Order-Verlauf exportieren-2026-08-26 02_55_34.zip"


def _source(authed) -> int:
    authed.post("/api/sources", json={"provider": "bitget", "label": "Bitget"})
    return authed.get("/api/sources").json()[0]["id"]


def _upload(authed, path: Path, sid: int, url: str):
    with path.open("rb") as fh:
        return authed.post(url, data={"source_id": str(sid)}, files={"files": (path.name, fh)})


def test_preview_writes_nothing(authed, tmp_path, db):
    sid = _source(authed)
    r = _upload(authed, build(tmp_path / NAME), sid, "/api/imports/preview").json()
    assert r["read"] == 12 and r["new"] == 12 and r["rejected"] == 0
    assert r["kinds"]["futures:funding"] == 1
    assert db.scalar(select(func.count()).select_from(RawTransaction)) == 0


def test_import_keeps_original_and_skips_duplicates(authed, tmp_path, env):
    sid = _source(authed)
    zip_path = build(tmp_path / NAME)
    run = _upload(authed, zip_path, sid, "/api/imports").json()
    assert (run["added"], run["duplicates"]) == (12, 0)
    (folder,) = (env / "data" / "originals" / str(sid)).iterdir()
    assert (folder / zip_path.name).read_bytes() == zip_path.read_bytes()
    again = _upload(authed, zip_path, sid, "/api/imports").json()
    assert (again["added"], again["duplicates"]) == (0, 12)
    assert len(list((env / "data" / "originals" / str(sid)).iterdir())) == 2
    preview = _upload(authed, zip_path, sid, "/api/imports/preview").json()
    assert preview["duplicates"] == 12 and preview["new"] == 0


def test_raw_list_and_revert(authed, tmp_path):
    sid = _source(authed)
    run = _upload(authed, build(tmp_path / NAME), sid, "/api/imports").json()
    listing = authed.get("/api/raw?market=futures").json()
    assert listing["total"] == 5 and listing["rows"][0]["market"] == "futures"
    assert (
        authed.get("/api/raw?limit=3").json()["rows"][0]["timestamp"]
        >= authed.get("/api/raw?limit=3").json()["rows"][-1]["timestamp"]
    )
    assert authed.delete(f"/api/import-runs/{run['id']}").json() == {"rows": 12}
    assert authed.get("/api/raw").json()["total"] == 0


def test_source_with_imports_cannot_be_deleted(authed, tmp_path):
    sid = _source(authed)
    _upload(authed, build(tmp_path / NAME), sid, "/api/imports")
    r = authed.delete(f"/api/sources/{sid}")
    assert r.status_code == 409 and r.json()["error"]["code"] == "sources.has_imports"


def test_unreadable_file_is_a_400(authed, tmp_path):
    sid = _source(authed)
    bad = tmp_path / "bad.zip"
    bad.write_text("not a zip")
    r = _upload(authed, bad, sid, "/api/imports")
    assert r.status_code == 400 and r.json()["error"]["code"] == "imports.unreadable"
    # nothing booked, so no stored copy left behind (review 2026-10-24)
    from app.core.config import get_settings

    folder = get_settings().data_dir / "originals" / str(sid)
    assert not folder.exists() or not any(folder.iterdir())


def test_wallet_has_no_file_channel(authed, tmp_path):
    authed.post(
        "/api/sources",
        json={
            "provider": "ethereum",
            "label": "L",
            "address": "0x" + "1" * 40,
            "wallet_id": _w(authed),
        },
    )
    sid = authed.get("/api/sources").json()[0]["id"]
    r = _upload(authed, build(tmp_path / NAME), sid, "/api/imports/preview")
    assert r.json()["error"]["code"] == "sources.channel_unavailable"


def test_safe_name():
    assert safe_name("../../etc/passwd") == "passwd"
    assert safe_name("..") == "upload"
    assert safe_name("a\x00b.zip") == "ab.zip"
    assert safe_name("C:\\x\\y.zip").endswith("y.zip")


def _w(authed) -> int:
    existing = authed.get("/api/wallets").json()
    if existing:
        return existing[0]["id"]
    return authed.post("/api/wallets", json={"name": "W"}).json()["id"]


def test_several_files_in_one_import(authed, tmp_path, monkeypatch):
    """A reader gets a folder when several files belong to one import (MEXC)."""
    from app.modules.plugins import registry as reg

    sid = _source(authed)
    seen = {}

    def fake_read(path, options):
        seen["path"] = path
        return iter(())

    monkeypatch.setattr(reg.registry().plugins["bitget_file"].module, "read", fake_read)
    a, b = tmp_path / "a.xlsx", tmp_path / "b.xlsx"
    a.write_bytes(b"1")
    b.write_bytes(b"2")
    with a.open("rb") as fa, b.open("rb") as fb:
        r = authed.post(
            "/api/imports",
            data={"source_id": str(sid)},
            files=[("files", ("a.xlsx", fa)), ("files", ("b.xlsx", fb))],
        )
    assert r.status_code == 200, r.text
    assert seen["path"].is_dir() and sorted(p.name for p in seen["path"].iterdir()) == [
        "a.xlsx",
        "b.xlsx",
    ]
    assert r.json()["label"] == "a.xlsx (+1)"


def test_preview_counts_duplicates_inside_one_upload(authed, tmp_path, monkeypatch):
    """Overlapping exports in one upload: the preview must say what the import will do."""
    from datetime import UTC, datetime
    from decimal import Decimal

    from app.modules.plugins import registry as reg
    from app.modules.plugins.contract import Kind, Movement

    sid = _source(authed)
    row = Movement(
        timestamp=datetime(2025, 1, 8, 20, 44, 44, tzinfo=UTC),
        kind=Kind.SEND,
        outgoing_asset="USDT",
        outgoing_amount=Decimal(110),
    )
    monkeypatch.setattr(
        reg.registry().plugins["bitget_file"].module,
        "read",
        lambda path, options: iter([row, row.model_copy()]),
    )
    f = tmp_path / "x.zip"
    f.write_bytes(b"x")
    preview = _upload(authed, f, sid, "/api/imports/preview").json()
    assert (preview["read"], preview["duplicates"], preview["new"]) == (2, 1, 1)
    run = _upload(authed, f, sid, "/api/imports").json()
    assert (run["added"], run["duplicates"]) == (1, 1)  # preview and import agree


def test_paging_does_not_skip_rows_of_the_same_moment(authed, db):
    """Five rows at one second, two per page: all five arrive (review 2026-10-24)."""
    from datetime import UTC, datetime
    from decimal import Decimal

    from app.modules.plugins.contract import Kind, Movement
    from app.modules.raw import service as raw
    from app.modules.sources.models import Source

    authed.post("/api/sources", json={"provider": "manual", "label": "Same second"})
    source = db.query(Source).one()
    at = datetime(2025, 3, 1, 12, tzinfo=UTC)
    raw.import_movements(
        db,
        source,
        "manual",
        "m",
        [
            Movement(
                timestamp=at, kind=Kind.RECEIVE, incoming_asset="BTC", incoming_amount=Decimal(i)
            )
            for i in range(1, 6)
        ],
    )
    for desc, side in ((True, "before"), (False, "after")):
        seen, cursor = [], ""
        for _ in range(5):
            page = authed.get(f"/api/raw?limit=2&desc={str(desc).lower()}{cursor}").json()
            if not page["rows"]:
                break
            seen += [r["id"] for r in page["rows"]]
            last = page["rows"][-1]
            cursor = f"&{side}={last['timestamp'].replace('+', '%2B')}&cursor_id={last['id']}"
        assert len(seen) == len(set(seen)) == 5
