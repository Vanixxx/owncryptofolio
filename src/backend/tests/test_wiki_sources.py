"""The table of all sources in the wiki stays complete, in German and English (Vanixxx,
2026-10-23)."""

from pathlib import Path

import pytest

from app.modules.plugins.registry import registry

ROOT = Path(__file__).resolve().parents[3] / "wiki"
GERMAN = {
    "Exchange without connection": "Börse ohne Anbindung",
    "Network without connection": "Netzwerk ohne Anbindung",
}
# (page, provider names as written there, status words) per wiki edition
EDITIONS = [
    (ROOT / "anleitungen" / "quellen.md", GERMAN, ("getestet", "Beta")),
    (ROOT / "en" / "guides" / "sources.md", {}, ("tested", "beta")),
]


@pytest.mark.parametrize(("page", "names", "words"), EDITIONS, ids=["de", "en"])
def test_every_source_is_in_the_wiki_table(page, names, words):
    text = page.read_text(encoding="utf-8")
    providers = {p.manifest.source.provider_name for p in registry().plugins.values()}
    missing = sorted(n for n in providers if f"| {names.get(n, n)} |" not in text)
    assert not missing, f"add to {page.name}: {missing}"


@pytest.mark.parametrize(("page", "names", "words"), EDITIONS, ids=["de", "en"])
def test_the_wiki_status_matches_the_plugins(page, names, words):
    text = page.read_text(encoding="utf-8")
    for p in registry().plugins.values():
        m = p.manifest
        if m.ccxt and m.plugin.status != "tested":
            continue  # the ccxt grid: all beta, stated once above it
        name = names.get(m.source.provider_name, m.source.provider_name)
        row = next(line for line in text.splitlines() if line.startswith(f"| {name} |"))
        status = (
            words[0]
            if any(
                q.manifest.plugin.status == "tested"
                for q in registry().plugins.values()
                if q.manifest.source.provider == m.source.provider
            )
            else words[1]
        )
        assert row.rstrip().endswith(f"| {status} |"), row
