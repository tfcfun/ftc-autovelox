"""Resolve current source URLs from the live page.

The /statics/<NN>/ folder number changes whenever a file is republished, so URLs
are never hardcoded. If the Documenti block cannot be read, the run fails rather
than falling back to a stale path.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from velox.constants import REGIONS

BASE_URL = "https://www.poliziadistato.it"

# The page writes hrefs with single quotes: href='/statics/04/abruzzo.pdf'
_PDF_HREF = re.compile(r"""href=['"](/statics/\d+/[^'"]+\.pdf)['"]""", re.IGNORECASE)


class SourceResolutionError(RuntimeError):
    """The Documenti block was missing or did not contain the expected files."""


@dataclass(frozen=True)
class SourceLinks:
    regional: dict[str, str]
    fixed_auto: str
    fixed_ord: str


def _slug(text: str) -> str:
    """Fold a region name to its filename form: "Valle d'Aosta" -> "valledaosta"."""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", folded.lower())


def resolve_sources(html: str, base_url: str = BASE_URL) -> SourceLinks:
    paths = _PDF_HREF.findall(html)
    if not paths:
        raise SourceResolutionError("no /statics/*.pdf links found on the page")

    by_slug: dict[str, str] = {}
    fixed_auto = fixed_ord = None
    for path in paths:
        filename = path.rsplit("/", 1)[-1]
        stem = filename[:-4]
        if stem.startswith("mvpostazionefissaaut"):
            fixed_auto = base_url + path
        elif stem.startswith("mvpostazionefissaord"):
            fixed_ord = base_url + path
        else:
            by_slug[_slug(stem)] = base_url + path

    regional: dict[str, str] = {}
    missing: list[str] = []
    for region in REGIONS:
        url = by_slug.get(_slug(region))
        if url is None:
            missing.append(region)
        else:
            regional[region] = url

    if missing:
        raise SourceResolutionError(f"regional PDFs not found for: {', '.join(missing)}")
    if fixed_auto is None:
        raise SourceResolutionError("motorway fixed-installation PDF not found")
    if fixed_ord is None:
        raise SourceResolutionError("ordinary-road fixed-installation PDF not found")

    return SourceLinks(regional=regional, fixed_auto=fixed_auto, fixed_ord=fixed_ord)
