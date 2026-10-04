"""Fetcher for per-state Wikipedia "List of fire lookout towers in <state>"
articles that carry a coordinate-bearing wikitable -- as opposed to
Wikipedia's bare link-list "List of fire lookout towers" (checked
2026-10-04: its per-state sections are just names + nearest town + NRHP
status, with coordinates only on each tower's own article; crawling those
individually would mostly duplicate what Wikidata's P649/P18 extract
already carries for NRHP-listed towers, so that page is not fetched here).

Louisiana is -- as far as a web search for this article-naming pattern
turned up on 2026-10-04 -- the only state with a *dedicated* list article in
this format: https://en.wikipedia.org/wiki/List_of_fire_lookout_towers_in_Louisiana
Name / Parish / Nearest town / Coordinates / Status / Notes, self-flagged
"incomplete" as of March 2023. PAGES below is a list so a second one can be
added later with no code change.

Wikipedia serves Parsoid HTML at /wiki/<title> (no API call needed, which
matters here: /w/api.php and /api/rest_v1/ are both disallowed for a generic
bot UA by robots.txt, but plain /wiki/<title> pages are not). Coordinates
come from the `<span class="geo">lat; lon</span>` Parsoid emits for every
{{coord}} template -- exact and easy, no DMS parsing needed.

Per DESIGN.md Sec 2/3.2 and this task's explicit instruction, only facts are
kept (name, parish/county, nearest town, coordinates, status). Wikipedia's
own prose -- here, the "Notes" column, which is short editorial commentary
("Cannot verify on aerial imagery, removed from USGS maps in 2015.") -- is
CC BY-SA and reuse-with-attribution would be licence-permitted, but the task
says explicitly not to copy Wikipedia prose, so the Notes column is read
only far enough to confirm it is prose (never stored).

Output: data/sources/wikipedia_lookout_lists.json

Re-run: python3 pipeline/regional/wikipedia_lists.py
"""

from __future__ import annotations

import datetime
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import fetch_text, slugify, write_source_json  # noqa: E402

SOURCE = "wikipedia_lookout_lists"
HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

PAGES = [
    {"region": "LA", "title": "List_of_fire_lookout_towers_in_Louisiana"},
]

TABLE_RE = re.compile(r'<table class="wikitable[^"]*"[^>]*>(.*?)</table>', re.S)
ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
GEO_RE = re.compile(r'class="geo">(-?[\d.]+); (-?[\d.]+)<')
LINK_RE = re.compile(r'<a\s+[^>]*href="([^"]+)"', re.I)


def strip_tags(cell_html: str) -> str:
    cell_html = re.sub(r"<style.*?</style>", "", cell_html, flags=re.S)
    cell_html = re.sub(r"<sup\b.*?</sup>", "", cell_html, flags=re.S)  # footnote markers [4]
    text = re.sub(r"<[^>]+>", "", cell_html)
    return re.sub(r"\s+", " ", text).strip()


def parse_status(raw: str) -> str:
    low = raw.lower()
    if low.startswith("still standing"):
        return "standing"
    if low.startswith("torn down"):
        return "gone"
    return "unknown"


def main() -> None:
    retrieved = datetime.date.today().isoformat()
    records = []
    for page in PAGES:
        url = f"https://en.wikipedia.org/wiki/{page['title']}"
        html = fetch_text(url, SOURCE, f"{page['title']}.html", encoding="utf-8")
        table_m = TABLE_RE.search(html)
        if not table_m:
            print(f"  ! {page['title']}: no wikitable found, skipping", file=sys.stderr)
            continue
        rows = ROW_RE.findall(table_m.group(1))
        header = [strip_tags(c).lower() for c in CELL_RE.findall(rows[0])] if rows else []
        try:
            name_i = header.index("name")
            parish_i = header.index("parish")
            town_i = next(i for i, h in enumerate(header) if "nearest" in h)
            coord_i = header.index("coordinates")
            status_i = header.index("status")
        except (ValueError, StopIteration):
            print(f"  ! {page['title']}: unexpected header {header!r}, skipping", file=sys.stderr)
            continue

        for row in rows[1:]:
            cells = CELL_RE.findall(row)
            if len(cells) <= max(name_i, parish_i, town_i, coord_i, status_i):
                continue
            name = strip_tags(cells[name_i])
            if not name:
                continue
            county = strip_tags(cells[parish_i]) or None
            nearest_town = strip_tags(cells[town_i]) or None
            geo_m = GEO_RE.search(cells[coord_i])
            lat = float(geo_m.group(1)) if geo_m else None
            lon = float(geo_m.group(2)) if geo_m else None
            status_raw = strip_tags(cells[status_i]) or None
            status = parse_status(status_raw) if status_raw else "unknown"

            name_cell_no_sup = re.sub(r"<sup\b.*?</sup>", "", cells[name_i], flags=re.S)
            link_m = LINK_RE.search(name_cell_no_sup)
            page_url = link_m.group(1) if link_m else url
            if page_url.startswith("./"):
                page_url = "https://en.wikipedia.org/wiki/" + page_url[2:]

            key = f"{SOURCE}:{page['region'].lower()}:{slugify(name)}"
            extra = {}
            if lat is None:
                extra["location_text"] = ", ".join(x for x in [nearest_town, county and f"{county} Parish"] if x) or None

            rec = {
                "key": key,
                "url": page_url,
                "name": name,
                "country": "US",
                "region": page["region"],
                "county": county,
                "lat": round(lat, 5) if lat is not None else None,
                "lon": round(lon, 5) if lon is not None else None,
                "elevation_m": None,
                "type_raw": None,
                "kind": "tower",
                "status_raw": status_raw,
                "status": status,
                "registers": [],
                "built": None,
                "agency": None,
                "events": [],
                "photos": [],
                "links": [{"label": "Wikipedia: List of fire lookout towers in Louisiana", "url": url}],
                "rental": None,
                "extra": extra,
            }
            records.append(rec)
        print(f"  {page['title']}: {len(rows) - 1} rows -> records so far {len(records)}", file=sys.stderr)

    out_path = REPO_ROOT / "data" / "sources" / f"{SOURCE}.json"
    write_source_json(
        out_path,
        source=SOURCE,
        title="Wikipedia: per-state fire lookout tower lists with coordinates",
        url="https://en.wikipedia.org/wiki/List_of_fire_lookout_towers_in_Louisiana",
        retrieved=retrieved,
        license_=(
            "CC BY-SA 4.0 (Wikipedia). Facts only (parish/county, nearest town, coordinates, "
            "status); the article's own prose/notes are not reproduced, per this project's policy."
        ),
        records=records,
    )
    print(f"wrote {len(records)} records -> {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
