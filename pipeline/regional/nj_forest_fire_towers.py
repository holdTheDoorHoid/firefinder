"""Fetcher for Wikipedia's "List of New Jersey Forest Fire Service fire
towers" -- a far richer table than the Louisiana list (wikipedia_lists.py):
US# / NJ# register numbers, a Commons photo, tower name (with an alt name
in parentheses), elevation, tower height, NJFFS division/section coverage,
a location cell, county, and notes. Two tables share this schema: "Fire
towers in active service" (20 rows, all status standing -- the article's
own section heading, not a guess) and "Fire towers not in service or no
longer standing" (3 rows, status gone).

The US#/NJ# register numbers in this table are NHLR's own numbering --
checked 2026-10-04 against the sibling-fetched data/sources/nhlr.json,
whose NJ entries have byte-identical numbers (Apple Pie Hill = US 564,
Bass River = US 243, Bearfort = US 244, ...). So registers[] here is left
empty rather than re-asserting a number already carried by nhlr.json under
its own key; merge.py will match these records onto the same towers by
name/place regardless. What this source actually adds on top of NHLR:
  - tower height (NHLR/the FFLA table don't carry this; NJFFS does)
  - NJFFS division/section assignment (kept in extra.division)
  - a Wikimedia Commons photo for about half the towers, a different
    (openly licensed) source from NHLR's own "all rights reserved" photo
  - coordinates for towers that may not all be in NHLR yet

Coordinates come in two forms on this page: a few rows have a Parsoid
`{{coord}}` ("geo") span; most instead just have NJFFS's own plain-text
"N41°03.521' W074°15.330'" (degrees + decimal minutes, no seconds) typed
directly into the cell -- both are parsed, which is why every row here
ends up with coordinates (checked 2026-10-04: 23 of 23 rows).

Per DESIGN.md Sec 2/3.2 and this task's instruction, the Notes column
(short editorial asides) is read only to confirm it holds no extra fact
worth keeping, never copied.

Output: data/sources/nj_forest_fire_towers.json

Re-run: python3 pipeline/regional/nj_forest_fire_towers.py
"""

from __future__ import annotations

import datetime
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import ft_to_m, slugify, fetch_text, write_source_json  # noqa: E402

SOURCE = "nj_forest_fire_towers"
PAGE_TITLE = "List_of_New_Jersey_Forest_Fire_Service_fire_towers"
PAGE_URL = f"https://en.wikipedia.org/wiki/{PAGE_TITLE}"
HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

TABLE_RE = re.compile(r'<table class="wikitable"[^>]*>(.*?)</table>', re.S)
ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
GEO_RE = re.compile(r'class="geo">(-?[\d.]+); (-?[\d.]+)<')
DM_RE = re.compile(r"N\s*(\d+)\D{1,3}(\d+\.\d+)\D+W\s*(\d+)\D{1,3}(\d+\.\d+)")
IMG_RE = re.compile(r'resource="https://en\.wikipedia\.org/wiki/File:([^"]+)"')
FEET_RE = re.compile(r"([\d,]+)\s*feet")
METERS_RE = re.compile(r"\(([\d.]+)\s*m\)")
QUALIFIER_RE = re.compile(r"\((?:previously|also known as|or)\s+([^)]+)\)", re.I)

# Section tables in page order: (status, status_raw).
SECTIONS = [("standing", "Active service"), ("gone", "Not in service or no longer standing")]


def clean_cell(html: str) -> str:
    html = re.sub(r"<style.*?</style>", "", html, flags=re.S)
    html = re.sub(r"<sup\b.*?</sup>", "", html, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&amp;", "&").replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_coords(cell_html: str) -> tuple[float | None, float | None]:
    geo_m = GEO_RE.search(cell_html)
    if geo_m:
        return float(geo_m.group(1)), float(geo_m.group(2))
    dm_m = DM_RE.search(clean_cell(cell_html))
    if dm_m:
        lat_deg, lat_min, lon_deg, lon_min = (float(x) for x in dm_m.groups())
        lat = lat_deg + lat_min / 60
        lon = -(lon_deg + lon_min / 60)
        return round(lat, 5), round(lon, 5)
    return None, None


def parse_feet(text: str) -> int | None:
    m = FEET_RE.search(text)
    if not m:
        return None
    return int(m.group(1).replace(",", ""))


def parse_meters(text: str) -> float | None:
    m = METERS_RE.search(text)
    return float(m.group(1)) if m else None


def main() -> None:
    retrieved = datetime.date.today().isoformat()
    html = fetch_text(PAGE_URL, SOURCE, "page.html", encoding="utf-8")
    tables = TABLE_RE.findall(html)

    records = []
    for (status, status_raw), table in zip(SECTIONS, tables):
        rows = ROW_RE.findall(table)
        for row in rows[1:]:
            cells = CELL_RE.findall(row)
            if len(cells) < 9:
                continue
            us_num = clean_cell(cells[0]) or None
            nj_num = clean_cell(cells[1]) or None
            name_raw = clean_cell(cells[3])
            if not name_raw:
                continue
            qual_m = QUALIFIER_RE.search(name_raw)
            qualifier = qual_m.group(1).strip() if qual_m else None
            name = QUALIFIER_RE.sub("", name_raw).strip()

            elev_text = clean_cell(cells[4])
            elev_m = parse_meters(elev_text) or (ft_to_m(parse_feet(elev_text)) if parse_feet(elev_text) else None)
            elev_ft = parse_feet(elev_text)

            height_text = clean_cell(cells[5])
            height_m = parse_meters(height_text) or (ft_to_m(parse_feet(height_text)) if parse_feet(height_text) else None)
            height_ft = parse_feet(height_text)

            division = clean_cell(cells[6]) or None
            location_cell_html = cells[7]
            location_text = clean_cell(location_cell_html)
            county = clean_cell(cells[8]) or None
            lat, lon = parse_coords(location_cell_html)

            img_m = IMG_RE.search(row)
            photos = []
            if img_m:
                filename = img_m.group(1)
                photos.append({
                    "url": f"https://commons.wikimedia.org/wiki/Special:FilePath/{filename}",
                    "credit": "Wikimedia Commons, via Wikipedia",
                    "caption": name,
                    "year": None,
                })

            key = f"{SOURCE}:nj:{slugify(name)}"
            extra = {}
            if lat is None:
                extra["location_text"] = location_text or None
            if division:
                extra["division"] = division
            if elev_ft:
                extra["elevation_ft"] = elev_ft
            if height_ft:
                extra["height_ft"] = height_ft

            rec = {
                "key": key,
                "url": PAGE_URL,
                "name": name,
                "country": "US",
                "region": "NJ",
                "county": county,
                "lat": round(lat, 5) if lat is not None else None,
                "lon": round(lon, 5) if lon is not None else None,
                "elevation_m": round(elev_m, 2) if elev_m is not None else None,
                "type_raw": None,
                "kind": "tower",
                "status_raw": status_raw,
                "status": status,
                "registers": [],
                "built": None,
                "agency": "New Jersey Forest Fire Service",
                "events": [],
                "photos": photos,
                "links": [{"label": "Wikipedia: List of New Jersey Forest Fire Service fire towers", "url": PAGE_URL}],
                "rental": None,
                "extra": {
                    **extra,
                    "ownership": "state",
                    **({"height_m": round(height_m, 2)} if height_m is not None else {}),
                    **({"other_name": qualifier} if qualifier else {}),
                    **({"nhlr_us_number": us_num, "nhlr_nj_number": nj_num} if us_num else {}),
                },
            }
            records.append(rec)

    out_path = REPO_ROOT / "data" / "sources" / f"{SOURCE}.json"
    write_source_json(
        out_path,
        source=SOURCE,
        title="Wikipedia: List of New Jersey Forest Fire Service fire towers",
        url=PAGE_URL,
        retrieved=retrieved,
        license_=(
            "CC BY-SA 4.0 (Wikipedia). Facts only (register numbers, elevation, height, "
            "division, coordinates); article prose/notes not reproduced. Photos are Wikimedia "
            "Commons files, each with its own licence on its file page."
        ),
        records=records,
    )
    print(f"wrote {len(records)} records -> {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
