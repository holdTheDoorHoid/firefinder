"""Fetcher for michiganfiretower.com, a young Michigan-only WordPress site
(credit line "FFLA.org | Michigan DNR | USDA"; posts dated 2025, with three
leftover "test-tower" posts the fetcher drops). Each tower is a custom post
type ("fire_tower"), discovered from its own sitemap -- but the WordPress
REST API (/wp-json/wp/v2/fire_tower) exposes only title/slug/link, no
content or custom fields, so each page is still fetched and read as HTML.

Reconnaissance (2026-10-04): the sitemap lists 11 fire_tower posts, 3 of
them named "testing-tower"/"test-tower-2"/"test-tower-5" (the site author's
own placeholders -- dropped here, not a real site). Of the remaining 8, the
template is a small fixed fact table:
  Tower Name / Alias / County / Forest / Removed / Status / Latitude /
  Longitude / Nad Pos. N / Nad Pos. W / PID(s) / T. Cabin
with an optional "Chronology" table (Date / Event) below it. Not every field
is present on every page (Barbeau has no coordinates at all; most have no
Alias/Forest/Removed). "Status" is one of Standing / Down / Unknown.
"PID(s)" is an NGS geodetic-mark PID when the site found one (same NGS
survey-mark linkage seen on the weebly lookout sites), "None", or a free
sentence like "No PIDs exist for this tower. Need to confirm location." --
only a value matching the PID pattern is kept.

Every page also embeds the same one site-logo image
(wp-content/uploads/2025/08/michigan-fire-towers2.png) and nothing else;
there are no genuine per-tower photos on this source as of this run.

Output: data/sources/michigan_fire_tower.json

Re-run: python3 pipeline/regional/michigan_fire_tower.py
"""

from __future__ import annotations

import datetime
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import fetch_text, slugify, write_source_json  # noqa: E402

SOURCE = "michigan_fire_tower"
BASE = "https://michiganfiretower.com"
HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

SITEMAP_URL = f"{BASE}/wp-sitemap-posts-fire_tower-1.xml"
TEST_SLUG_RE = re.compile(r"/(testing-tower|test-tower-\d+)/$", re.I)
PID_RE = re.compile(r"^[A-Z]{2}\d{3,5}$")

CHRON_ROW_RE = re.compile(r"<tr[^>]*>\s*<td[^>]*>([^<]*)</td>\s*<td[^>]*>([^<]*)</td>\s*</tr>", re.I)


def own_body(html: str) -> str:
    body = html[html.find("<body") :]
    body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
    body = re.sub(r"<style.*?</style>", "", body, flags=re.S)
    return body


def parse_fields(body: str) -> dict:
    """The fact table alternates "<strong>Label:</strong> value" (or similar
    markup) across adjacent cells/lines; pull every (label, value) text-node
    pair out directly rather than assuming a fixed table shape, since the
    theme wraps each row differently depending on whether the field repeats
    an icon span or not."""
    text_nodes = [re.sub(r"\s+", " ", t).strip() for t in re.findall(r">([^<>]{1,300})<", body)]
    text_nodes = [t for t in text_nodes if t]
    fields: dict[str, str] = {}
    labels = {"Tower Name:", "Alias:", "County:", "Forest:", "Removed:", "Status:",
              "Latitude:", "Longitude:", "PID(s):", "T. Cabin:"}
    for i, node in enumerate(text_nodes):
        if node in labels and i + 1 < len(text_nodes):
            fields[node[:-1]] = text_nodes[i + 1]
    return fields


def parse_chronology(body: str) -> list[tuple[str, str]]:
    idx = body.find(">Chronology<")
    if idx == -1:
        return []
    table_m = re.search(r"<table[^>]*>(.*?)</table>", body[idx:], re.S)
    if not table_m:
        return []
    rows = CHRON_ROW_RE.findall(table_m.group(1))
    out = []
    for date_html, event_html in rows:
        date = re.sub(r"\s+", " ", date_html).strip()
        event = re.sub(r"\s+", " ", event_html).strip()
        if date.lower() == "date" and event.lower() == "event":
            continue  # header row
        if date or event:
            out.append((date, event))
    return out


def map_status(raw: str | None) -> str:
    if not raw:
        return "unknown"
    low = raw.strip().lower()
    if low == "standing":
        return "standing"
    if low == "down":
        return "gone"
    return "unknown"


def agency_to_ownership(agency: str | None) -> str:
    if not agency:
        return "unknown"
    low = agency.lower()
    if "national forest" in low:
        return "federal"
    return "unknown"


def main() -> None:
    retrieved = datetime.date.today().isoformat()
    sitemap_xml = fetch_text(SITEMAP_URL, SOURCE, "sitemap-fire-tower.xml", encoding="utf-8")
    urls = re.findall(r"<loc>([^<]+)</loc>", sitemap_xml)

    records = []
    skipped_test = 0
    for url in urls:
        if TEST_SLUG_RE.search(url):
            skipped_test += 1
            continue
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        html = fetch_text(url, SOURCE, f"{slugify(slug)}.html", encoding="utf-8")
        body = own_body(html)
        fields = parse_fields(body)

        name = fields.get("Tower Name") or None
        if not name:
            print(f"  ! {url}: no Tower Name field found, skipping", file=sys.stderr)
            continue
        alias = fields.get("Alias") or None
        county = fields.get("County") or None
        agency_raw = fields.get("Forest") or None
        status = map_status(fields.get("Status"))
        status_raw = fields.get("Status") or None

        lat_raw, lon_raw = fields.get("Latitude"), fields.get("Longitude")
        try:
            lat = float(lat_raw) if lat_raw else None
            lon = float(lon_raw) if lon_raw else None
        except ValueError:
            lat = lon = None

        pid_raw = fields.get("PID(s)")
        pid = pid_raw if pid_raw and PID_RE.match(pid_raw.strip()) else None

        removed_raw = fields.get("Removed")
        events = []
        if removed_raw and re.fullmatch(r"\d{4}", removed_raw.strip()):
            events.append({"year": int(removed_raw), "event": "removed", "note": None, "from": SOURCE})

        chronology = parse_chronology(body)
        for date_text, event_text in chronology:
            year_m = re.search(r"\b(1[89]\d\d|20\d\d)\b", date_text) or re.search(r"\b(1[89]\d\d|20\d\d)\b", event_text)
            if not year_m:
                continue
            year = int(year_m.group(1))
            low = event_text.lower()
            if "torn down" in low or "removed" in low or "demolish" in low:
                ev = "removed"
            elif "built" in low or "erected" in low or "constructed" in low:
                ev = "built"
            elif "burn" in low:
                ev = "burned"
            else:
                ev = "removed" if status == "gone" else "built"
            if not any(e["year"] == year and e["event"] == ev for e in events):
                events.append({"year": year, "event": ev, "note": event_text, "from": SOURCE})

        registers = [{"register": "NGS", "number": pid, "state_number": None}] if pid else []

        key = f"{SOURCE}:mi:{slugify(name)}"
        extra = {}
        if lat is None:
            extra["location_text"] = ", ".join(x for x in [county and f"{county} County", agency_raw] if x) or None
        ownership = agency_to_ownership(agency_raw)
        if ownership != "unknown":
            extra["ownership"] = ownership

        rec = {
            "key": key,
            "url": url,
            "name": name,
            "country": "US",
            "region": "MI",
            "county": county,
            "lat": round(lat, 5) if lat is not None else None,
            "lon": round(lon, 5) if lon is not None else None,
            "elevation_m": None,
            "type_raw": None,
            "kind": "tower",
            "status_raw": status_raw,
            "status": status,
            "registers": registers,
            "built": None,
            "agency": agency_raw,
            "events": events,
            "photos": [],
            "links": [{"label": "michiganfiretower.com", "url": url}],
            "rental": None,
            "extra": {**extra, **({"alias": alias} if alias else {})},
        }
        records.append(rec)

    print(f"skipped {skipped_test} test placeholder posts", file=sys.stderr)

    out_path = REPO_ROOT / "data" / "sources" / f"{SOURCE}.json"
    write_source_json(
        out_path,
        source=SOURCE,
        title="Michigan Fire Towers (michiganfiretower.com)",
        url=f"{BASE}/",
        retrieved=retrieved,
        license_=(
            "No licence stated (site credits FFLA.org, Michigan DNR, USDA as its own sources); "
            "facts only (county, coordinates, status, NGS PID, removal year). No per-tower photos "
            "found on this source as of this run -- every page embeds the same site logo image."
        ),
        records=records,
    )
    print(f"wrote {len(records)} records -> {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
