from pathlib import Path

import pytest

from velox.sources import SourceResolutionError, resolve_sources

FIXTURE = Path(__file__).parent.parent / "fixtures" / "2026-W33" / "poliziadistato.html"


def test_resolves_all_twenty_regions_and_both_fixed_lists():
    links = resolve_sources(FIXTURE.read_text(encoding="utf-8", errors="replace"))
    assert len(links.regional) == 20
    assert links.regional["Lombardia"].endswith("/lombardia.pdf")
    assert links.regional["Lombardia"].startswith("https://www.poliziadistato.it/statics/")
    assert "mvpostazionefissaaut" in links.fixed_auto
    assert "mvpostazionefissaord" in links.fixed_ord


def test_urls_are_absolute():
    links = resolve_sources(FIXTURE.read_text(encoding="utf-8", errors="replace"))
    for url in [*links.regional.values(), links.fixed_auto, links.fixed_ord]:
        assert url.startswith("https://")


def test_missing_documenti_block_raises_rather_than_falling_back():
    with pytest.raises(SourceResolutionError):
        resolve_sources("<html><body>nothing here</body></html>")


def test_partial_region_list_raises():
    html = "<a href='/statics/04/abruzzo.pdf'>Abruzzo</a>"
    with pytest.raises(SourceResolutionError):
        resolve_sources(html)
