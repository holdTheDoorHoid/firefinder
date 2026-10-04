"""Fetcher for Andy Arthur's "Map and Coordinates List for NYS DEC Firetowers"
(andyarthur.org), which covers New York's surviving, hikeable DEC fire towers.

CC BY 3.0, credit "Andy Arthur, andyarthur.org" -- DESIGN.md Sec 2 names this
as one of the sources whose licence permits keeping a short description in
extra.description (with extra.license set), unlike the facts-only sources.
The page's own one-line trail notes ("Relatively short hike.", "Currently
closed to public use.") are short enough to qualify and are kept verbatim
with credit, rather than being discarded like prose from no-licence sources.

IMPORTANT -- Cloudflare: andyarthur.org sits behind a Cloudflare JS
challenge ("Just a moment...") that blocks both the bot UA and a plain
requests-style browser UA fetched via urllib; there is no HTTP-only way
through it with the standard library. The table was instead captured once
through an interactive browser session (which does pass the challenge) and
saved to the shared cache at
  data/raw/andyarthur_ny/p-138058-table.html
(just the <table> element's outerHTML, not the full page). This script
only ever reads that cache file -- see fetch_table_html() -- so it is
resumable in the ordinary sense (nothing to re-fetch) but NOT self-sufficient
from a clean checkout: if that cache file is ever missing, a human (or an
agent with real browser tool access) needs to re-capture it from
https://andyarthur.org/p/138058 and save the <table> element's outerHTML to
that path before re-running.

Output: data/sources/andyarthur_ny.json

Re-run: python3 pipeline/regional/andyarthur_ny.py
"""

from __future__ import annotations

import datetime
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import RAW_ROOT, slugify, write_source_json  # noqa: E402

SOURCE = "andyarthur_ny"
PAGE_URL = "https://andyarthur.org/p/138058"
CACHE_REL = "p-138058-table.html"

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.I | re.S)
CELL_RE = re.compile(r"<td>(.*?)</td>", re.I | re.S)
LINK_RE = re.compile(r'<a href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
COORD_RE = re.compile(r"(-?\d+\.\d+)\s*,?\s*<br\s*/?>\s*(-?\d+\.\d+)", re.I)


def strip_tags(html: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", html, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_table_html() -> str:
    path = RAW_ROOT / SOURCE / CACHE_REL
    if not path.exists():
        raise SystemExit(
            f"missing cache file {path} -- andyarthur.org is behind Cloudflare and "
            "can't be fetched with urllib (see module docstring). Re-capture the "
            f"<table> element's outerHTML from {PAGE_URL} with a real browser and "
            f"save it to this path, then re-run."
        )
    return path.read_text(encoding="utf-8")


def main() -> None:
    html = fetch_table_html()
    rows = ROW_RE.findall(html)

    records = []
    for row in rows:
        cells = CELL_RE.findall(row)
        if len(cells) != 4:
            continue
        name_cell, land_cell, notes_cell, coord_cell = cells
        if "<strong>" in name_cell:
            continue  # header row

        link_m = LINK_RE.search(name_cell)
        name = strip_tags(link_m.group(2)) if link_m else strip_tags(name_cell)
        page_link = link_m.group(1) if link_m else None

        land = strip_tags(land_cell) or None
        notes = strip_tags(notes_cell) or None

        coord_m = COORD_RE.search(coord_cell)
        if not coord_m:
            print(f"  ! no coordinates for {name!r}, skipping", file=sys.stderr)
            continue
        lat, lon = float(coord_m.group(1)), float(coord_m.group(2))

        links = [{"label": "andyarthur.org NYS DEC Firetowers list", "url": PAGE_URL}]
        if page_link:
            links.append({"label": "andyarthur.org tower page", "url": page_link})

        key = f"{SOURCE}:{slugify(name)}:{lat:.4f}:{lon:.4f}"
        rec = {
            "key": key,
            "url": page_link or PAGE_URL,
            "name": name,
            "country": "US",
            "region": "NY",
            "county": None,
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "elevation_m": None,
            "type_raw": None,
            "kind": "tower",
            "status_raw": None,
            "status": "standing",  # page covers NY DEC's current, hikeable fire towers
            "registers": [],
            "built": None,
            "agency": f"NY DEC -- {land}" if land else "NY DEC",
            "events": [],
            "photos": [],
            "links": links,
            "rental": None,
            "extra": {
                "ownership": "state",
                **({"description": notes} if notes else {}),
                **({"license": "CC BY 3.0, credit: Andy Arthur, andyarthur.org"} if notes else {}),
                **({"state_land_unit": land} if land else {}),
            },
        }
        records.append(rec)

    out_path = REPO_ROOT / "data" / "sources" / "andyarthur_ny.json"
    write_source_json(
        out_path,
        source=SOURCE,
        title="Map and Coordinates List for NYS DEC Firetowers (Andy Arthur)",
        url=PAGE_URL,
        retrieved=datetime.date.today().isoformat(),
        license_="CC BY 3.0, credit: Andy Arthur, andyarthur.org. Facts + short description text reused under that licence.",
        records=records,
    )
    print(f"wrote {len(records)} records -> {out_path}")


if __name__ == "__main__":
    main()
