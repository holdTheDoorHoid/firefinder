"""Fetcher for idahofirelookouts.com -- a young, actively-growing survey
site (newest posts within the last few months of this run).

The homepage/category teasers look sparse (one post shown per category),
but every category page ALSO embeds a map-widget JSON blob
(`data-items='[...]'`, a WP Google Maps / OSM "category map" shortcode)
listing EVERY post in that category with id, title, link, lat/lon
("address"/"latitude"/"longitude") and a short excerpt -- this is the real
per-lookout dataset, and it is large: 998 unique lookouts across the site's
6 regional categories (103-322 each) as of this run. Visiting all 998
individual post pages for their full prose would be a very large crawl;
this fetcher instead extracts everything the category pages' map-widget
JSON already gives for free (coordinates, name, thumbnail, and short status
facts regex'd out of the excerpt), which covers status/built/destroyed for
most entries without any extra requests.

No licence is stated for idahofirelookouts.com (unlike andyarthur.org or
fire-lookouts.org), so per DESIGN.md Sec 2/3.2 this is treated as a
facts-only source: the excerpt text itself is NOT copied into extra.
description, only facts parsed out of it (status, built year, destroyed/
abandoned year). Thumbnail photos ARE mirrored with credit, per the
project's separate, already-decided photo policy (DESIGN.md Sec 1).

Output: data/sources/idaho_fl.json

Re-run: python3 pipeline/regional/idaho_fl.py
"""

from __future__ import annotations

import datetime
import html as htmlmod
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import fetch_text, slugify, write_source_json  # noqa: E402

SOURCE = "idaho_fl"
BASE = "https://www.idahofirelookouts.com"
CATEGORIES = [
    ("northern-idaho", "Northern Idaho"),
    ("cda-region", "Coeur d'Alene"),
    ("st-joe-clearwater-region", "St. Joe -- Clearwater"),
    ("selway-region", "Selway"),
    ("west-central", "West Central"),
    ("southern-idaho", "Southern Idaho"),
]

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

DATA_ITEMS_RE = re.compile(r"data-items='(\[.*?\])'", re.S)
YEAR_RE = re.compile(r"\b(1[89]\d\d|20[0-2]\d)\b")
BUILT_RE = re.compile(r"[Bb]uilt in (\d{4})")
RUINS_RE = re.compile(r"ruins|not a single thing left|nothing left", re.I)
DESTROYED_RE = re.compile(r"destroyed|burn(?:ed|t)", re.I)
ABANDONED_RE = re.compile(r"abandoned|\bgone\b", re.I)
STAFFED_RE = re.compile(r"\bstaffed\b", re.I)
STILL_STANDING_RE = re.compile(r"\bstill\b", re.I)
SOLD_RE = re.compile(r"\bsold\b", re.I)

# The site reuses a handful of generic "no photo yet" images across
# hundreds of posts (571 of 998 entries as surveyed) rather than leaving
# the thumbnail blank. These aren't real tower photos, so they're excluded
# by filename rather than kept as if they were.
PLACEHOLDER_IMAGE_MARKERS = (
    "c3bf2b89-777c-4ecf-856e-468b337ac2cc",
    "c1cef656-e29a-4d8d-92e7-1c6017477912",
    "coming-soon",
)


def classify_excerpt(excerpt: str) -> dict:
    """Best-effort facts out of a short (often truncated) excerpt. Returns
    status plus an optional built/event year -- never stores the excerpt
    text itself (no reuse licence for this source)."""
    years = [int(y) for y in YEAR_RE.findall(excerpt)]
    built_m = BUILT_RE.search(excerpt)
    built_year = int(built_m.group(1)) if built_m else None

    events = []
    if built_year:
        events.append({"year": built_year, "event": "built", "note": None, "from": "idaho_fl"})

    if RUINS_RE.search(excerpt):
        status = "ruins"
    elif DESTROYED_RE.search(excerpt):
        status = "gone"
        event_years = [y for y in years if y != built_year]
        if event_years:
            events.append({"year": event_years[-1], "event": "destroyed", "note": None, "from": "idaho_fl"})
    elif ABANDONED_RE.search(excerpt):
        status = "gone"
        event_years = [y for y in years if y != built_year]
        if event_years:
            events.append({"year": event_years[-1], "event": "abandoned", "note": None, "from": "idaho_fl"})
    elif STAFFED_RE.search(excerpt):
        status = "standing"
    elif STILL_STANDING_RE.search(excerpt):
        status = "standing"
    elif SOLD_RE.search(excerpt):
        status = "unknown"  # sold off site; fate of the structure itself isn't stated
    else:
        status = "unknown"

    staffing = "staffed" if STAFFED_RE.search(excerpt) else None

    return {"status": status, "built_year": built_year, "events": events, "staffing": staffing}


def main() -> None:
    all_records = []
    seen_links: set[str] = set()
    for slug, label in CATEGORIES:
        url = f"{BASE}/category/{slug}/"
        html = fetch_text(url, SOURCE, f"category-{slug}.html")
        m = DATA_ITEMS_RE.search(html)
        if not m:
            print(f"  ! no map data found for category {slug}", file=sys.stderr)
            continue
        items = json.loads(htmlmod.unescape(m.group(1)))

        for it in items:
            link = it["link"]
            if link in seen_links:
                continue  # a lookout can be cross-listed under more than one category
            seen_links.add(link)

            lat, lon = float(it["latitude"]), float(it["longitude"])
            name = htmlmod.unescape(it["title"]).strip()
            excerpt = re.sub(r"<[^>]+>", "", it.get("excerpt", "")).strip()
            facts = classify_excerpt(excerpt)

            thumb_m = re.search(r'src=\\?"([^"\\]+)\\?"', it.get("thumbnail", "")) or re.search(
                r'src="([^"]+)"', it.get("thumbnail", "")
            )
            photos = []
            if thumb_m and not any(marker in thumb_m.group(1) for marker in PLACEHOLDER_IMAGE_MARKERS):
                photos.append({
                    "url": thumb_m.group(1),
                    "credit": "idahofirelookouts.com",
                    "caption": name,
                    "year": None,
                })

            # Use the post's own URL slug, not a fresh slugify(name), as
            # the key's name component: a handful of lookouts are posted
            # twice under names that are identical once slugified (e.g.
            # "Sheep Hill Lookout" / "Sheep Hill Lookout" at the same
            # coordinates, posted as /sheep-hill-lookout/ and
            # /sheep-hill-lookout-2/) -- the site's own "-2" suffix is the
            # only thing that tells the two posts apart.
            url_slug = link.rstrip("/").rsplit("/", 1)[-1]
            key = f"{SOURCE}:{url_slug}:{lat:.4f}:{lon:.4f}"
            rec = {
                "key": key,
                "url": link,
                "name": name,
                "country": "US",
                "region": "ID",
                "county": None,
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "elevation_m": None,
                "type_raw": None,
                "kind": "unknown",
                "status_raw": None,
                "status": facts["status"],
                "registers": [],
                "built": facts["built_year"],
                "agency": None,
                "events": facts["events"],
                "photos": photos,
                "links": [{"label": "idahofirelookouts.com", "url": link},
                          {"label": "idahofirelookouts.com category", "url": url, "kind": "category"}],
                "rental": None,
                "extra": {
                    "category_label": label,
                    **({"staffing_hint": facts["staffing"]} if facts["staffing"] else {}),
                },
            }
            all_records.append(rec)

    out_path = REPO_ROOT / "data" / "sources" / "idaho_fl.json"
    write_source_json(
        out_path,
        source=SOURCE,
        title="Idaho Fire Lookouts (idahofirelookouts.com)",
        url=BASE + "/",
        retrieved=datetime.date.today().isoformat(),
        license_="No licence stated; facts only (coordinates, status/built/destroyed year parsed from each entry's short excerpt). Thumbnail photos mirrored with credit per the project's photo policy.",
        records=all_records,
    )
    print(f"wrote {len(all_records)} records -> {out_path}")

    status_counts: dict[str, int] = {}
    for r in all_records:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
    print("status breakdown:", status_counts)


if __name__ == "__main__":
    main()
