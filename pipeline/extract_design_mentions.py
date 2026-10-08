#!/usr/bin/env python3
"""Find standard lookout design names in cached page prose and keep only the names.

The register sites (NHLR, FFLOS), firelookout.com and the eastern / central US weebly sites
describe each lookout in a paragraph of prose. Firefinder keeps facts, not prose (DESIGN.md §1),
so the fetchers drop those paragraphs; but the paragraph is often the only place a page says
"Aermotor MC-39" or "CT-2 tower with an L-4 cab". This script reads the cached pages (the
git-ignored crawl cache, $FIREFINDER_RAW_ROOT), finds design names with pipeline/designs.py, and
writes each record's names -- short terms such as "Aermotor", "MC-39", "R-6", never sentences --
to data/design_mentions.json, keyed by the record's key in its source extract:

    {"title": ..., "generated": "YYYY-MM-DD", "sources": {"nhlr": {"pages": 1850, "read": 1849,
     "with_mentions": 700}, ...}, "mentions": {"nhlr:US 844": ["Aermotor", "MC-39"], ...},
     "several_structures": ["fflos:US 12", ...]}

"several_structures" lists the records whose prose names two or more designs and also says the
site had more than one structure ("replaced", "the original cab"...), so build_site_data does not
pair their designs as one lookout's cab and tower.

pipeline/build_site_data.py adds the names to each record's design wording, so the designs guide
and the map's design filter see them. The file is committed: CI has no crawl cache.

Re-run after changing designs.PATTERNS or re-crawling a source (needs the crawl cache):
    python3 pipeline/extract_design_mentions.py
Python 3.12, standard library only.
"""

from __future__ import annotations

import datetime as dt
import html as htmllib
import json
import re
import sys
from pathlib import Path
from typing import Callable, Iterator
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import designs  # noqa: E402
from common import RAW_ROOT, cached_body  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SOURCES_DIR = REPO / "data" / "sources"
OUT = REPO / "data" / "design_mentions.json"


def _text(fragment: str) -> str:
    fragment = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", fragment)
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def register_description(page: str) -> str:
    """The Description paragraph of an NHLR / FFLOS lookout page (the same layout on both)."""
    i = page.find("<h2>Description</h2>")
    if i < 0:
        return ""
    j = page.find("</div>", i)
    return _text(page[i + len("<h2>Description</h2>") : j if j > 0 else None])


FLC_PROSE = re.compile(r"<TD[^>]*ROWSPAN[^>]*>\s*<H5>(.*?)</H5>", re.I | re.S)


def firelookout_com_prose(page: str) -> str:
    """firelookout.com's one paragraph about the lookout (the same cell its fetcher reads)."""
    m = FLC_PROSE.search(page)
    return _text(m.group(1)) if m else ""


def weebly_content(page: str) -> str:
    """A weebly lookout page's own content: from its first <h2> (before it is the shared site
    navigation) to the end."""
    m = re.search(r"<h2\b", page, re.I)
    return _text(page[m.start() :]) if m else ""


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _register_page(source: str) -> Callable[[str], str | None]:
    return lambda url: cached_body(source, url)


def _flat_page(cache_dir: str, keep_dirs: int) -> Callable[[str], str | None]:
    """Pages cached as RAW_ROOT/<cache_dir>/<last keep_dirs path parts of the URL>."""

    def get(url: str) -> str | None:
        parts = [p for p in urlsplit(url).path.split("/") if p]
        if not parts:
            return None
        return _read(RAW_ROOT / cache_dir / Path(*parts[-keep_dirs:]))

    return get


# source extract -> (how to get a record's cached page, how to get its prose)
READERS: dict[str, tuple[Callable[[str], str | None], Callable[[str], str]]] = {
    "nhlr": (_register_page("nhlr"), register_description),
    "fflos": (_register_page("fflos"), register_description),
    "firelookout_com": (_flat_page("firelookout_com", 2), firelookout_com_prose),
    "eastern_us_lookouts": (_flat_page("eastern_us_lookouts", 1), weebly_content),
    "central_us_lookouts": (_flat_page("central_us_lookouts", 1), weebly_content),
}


def records(source: str) -> Iterator[dict]:
    path = SOURCES_DIR / f"{source}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for r in data.get("records") or []:
        if isinstance(r, dict) and isinstance(r.get("key"), str) and isinstance(r.get("url"), str):
            yield r


def mention_terms(text: str) -> list[str]:
    """The design names in one text, as short terms (each re-recognised by match_designs)."""
    terms: list[str] = []
    for did, span in designs.find_mentions(text):
        if did in designs.match_designs(span) and span not in terms:
            terms.append(span)
    return terms


def extract(sources: dict[str, tuple[Callable[[str], str | None], Callable[[str], str]]] = READERS) -> dict:
    mentions: dict[str, list[str]] = {}
    several: list[str] = []
    stats: dict[str, dict[str, int]] = {}
    for source, (page_of, prose_of) in sources.items():
        st = {"pages": 0, "read": 0, "with_mentions": 0}
        for r in records(source):
            st["pages"] += 1
            page = page_of(r["url"])
            if not page:
                continue
            st["read"] += 1
            prose = prose_of(page)
            terms = mention_terms(prose)
            if terms:
                st["with_mentions"] += 1
                mentions[r["key"]] = terms
                if designs.describes_several(prose):
                    several.append(r["key"])
        stats[source] = st
    return {
        "title": "Design names found in register descriptions and hobbyist pages",
        "note": "Short design names (facts) found by pipeline/extract_design_mentions.py in the prose of each source's cached page; the prose itself is not kept. Keys are source record keys.",
        "generated": dt.date.today().isoformat(),
        "sources": stats,
        "mentions": dict(sorted(mentions.items())),
        # Records whose prose names two or more designs and says the site had more than one
        # structure ("replaced", "original", "earlier"...): their designs are not paired.
        "several_structures": sorted(several),
    }


def main() -> None:
    if not RAW_ROOT.is_dir():
        raise SystemExit(f"No crawl cache at {RAW_ROOT}; set FIREFINDER_RAW_ROOT")
    out = extract()
    old = None
    if OUT.is_file():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            old = None
    if old and all(old.get(k) == out[k] for k in ("mentions", "sources", "several_structures")):
        print("design mentions unchanged")
        return
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for s, st in out["sources"].items():
        print(f"{s}: {st['read']} of {st['pages']} pages read, {st['with_mentions']} name a design")
    print(f"wrote {OUT.relative_to(REPO)} ({len(out['mentions'])} records)")


if __name__ == "__main__":
    main()
