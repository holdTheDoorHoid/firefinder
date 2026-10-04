"""Fetcher for the CSKT (Confederated Salish and Kootenai Tribes) Flathead
Reservation fire lookout page:
  https://fwrconline.csktnrd.org/Fire/FireOnTheLand/FireManagement/Lookouts/

Six lookouts (Ferry Basin, High Point, Jocko, Pistol Creek, Irvine, Basso),
each with a short prose paragraph giving location note, elevation, and a
build/design/staffing history. The page gives no coordinates at all.

Geocoding note: Nominatim (OSM's public geocoder) explicitly disallows
/search in its robots.txt, so this script does NOT call it -- that would
violate the project's own "honour robots.txt" rule (DESIGN.md Sec 2). The
coordinates below were instead researched by hand, once, through a regular
browser/manual lookup: for High Point, Jocko, Pistol Creek and Irvine, an
OSM feature exists with the same name as the lookout (recorded in
GEOCODE_RESULTS with its OSM type); for Ferry Basin and Basso, no named
feature could be found, so the point is dead-reckoned from the bearing and
distance the source text itself gives from the nearest named town (Moiese,
Dayton), using those towns' own OSM coordinates (also looked up by hand,
recorded in REFERENCE_TOWNS). Every record's extra.coord_method states
which of the two this is and how confident that makes the point -- treat
the dead-reckoned pair especially as approximate.

Tribal land: extra.ownership = "tribal", access.level-equivalent note is
left for the merge/canonical stage (DESIGN.md Sec 3.4); this source record
just carries the facts.

Output: data/sources/cskt.json

Re-run: python3 pipeline/regional/cskt.py
"""

from __future__ import annotations

import datetime
import math
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import fetch_text, ft_to_m, slugify, write_source_json  # noqa: E402

SOURCE = "cskt"
PAGE_URL = "https://fwrconline.csktnrd.org/Fire/FireOnTheLand/FireManagement/Lookouts/"

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

FACTS_RE = re.compile(
    r"^(?P<name>.+?)\s+Located\s+(?P<locnote>.+?)\s+in\s+(?P<county>[A-Za-z]+)\s+County,?"
    r"\s*(?:Montana)?\s*Elevation\s+(?P<elev>[\d.]+)\s+feet\s+(?P<prose>.+)$"
)
DESIGN_RE = re.compile(r"\b(L-4|L-5|L-6|R-6|D-6|Aermotor)\b")
HEIGHT_RE = re.compile(r"(?<![\dx])(\d{1,3})[-'’]\s*(?:foot|ft|treated timber tower|steel)", re.I)
BUILT_RE = re.compile(r"built\D{0,20}?(?:about |here about |here in |in )?(\d{4})", re.I)
GONE_BY_RE = re.compile(r"gone by (\d{4})", re.I)


def strip_tags(html: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", html, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def destination_point(lat1: float, lon1: float, bearing_deg: float, distance_mi: float) -> tuple[float, float]:
    """Dead-reckon a destination point on a spherical Earth, standard
    bearing/distance navigation formula."""
    R = 6371.0
    d_r = (distance_mi * 1.609344) / R
    lat1r, lon1r, brng = math.radians(lat1), math.radians(lon1), math.radians(bearing_deg)
    lat2r = math.asin(math.sin(lat1r) * math.cos(d_r) + math.cos(lat1r) * math.sin(d_r) * math.cos(brng))
    lon2r = lon1r + math.atan2(
        math.sin(brng) * math.sin(d_r) * math.cos(lat1r),
        math.cos(d_r) - math.sin(lat1r) * math.sin(lat2r),
    )
    return math.degrees(lat2r), math.degrees(lon2r)


# Towns the source text itself uses as bearing/distance references,
# looked up by hand once (OSM Nominatim web UI, not the disallowed /search
# API -- see module docstring).
REFERENCE_TOWNS = {
    "Moiese, Montana": (47.37152, -114.26386),   # OSM node 150974778 (hamlet)
    "Dayton, Montana": (47.86280, -114.28268),   # OSM relation 142657 (locality)
}

# Per-lookout coordinate + how it was obtained, looked up by hand once.
# "osm" entries matched a named OSM feature sharing the lookout's name;
# "dead_reckon" entries have no such feature and are computed below from
# the bearing/distance the source prose gives from a REFERENCE_TOWNS entry.
GEOCODE_RESULTS = {
    "Ferry Basin": {
        "dead_reckon": {"from_town": "Moiese, Montana", "bearing": 225, "distance_mi": 6},
        "method": "estimated: 6 mi SW of Moiese, MT (bearing/distance from source text, dead-reckoned); "
                   "no named OSM feature found -- nearest hint is an OSM track cluster named "
                   "'Ferry Crossing Basin' a few km NE of this point",
    },
    "High Point": {
        "osm": (47.32038, -114.20351),  # OSM way "High Point Trail" (Sanders Co., inside CSKT/National Bison Range)
        "method": "OSM way 'High Point Trail', same name as the lookout, inside the CSKT National Bison "
                   "Range -- matches the source's 'Located on the National Bison Range' note",
    },
    "Jocko": {
        "osm": (47.14160, -113.82873),  # OSM node, man_made=tower, name="Jocko Lookout"
        "method": "OSM man_made=tower node named 'Jocko Lookout'",
    },
    "Pistol Creek": {
        "osm": (47.30080, -114.13613),  # OSM node, place=hamlet, name="Pistol Creek"
        "method": "OSM place node named 'Pistol Creek'; exact tower pad not separately mapped",
    },
    "Irvine": {
        "osm": (47.75494, -114.45818),  # OSM node, man_made=tower, name="Irvine Lookout Tower"
        "method": "OSM man_made=tower node named 'Irvine Lookout Tower'",
    },
    "Basso": {
        "dead_reckon": {"from_town": "Dayton, Montana", "bearing": 270, "distance_mi": 23.5},
        "method": "estimated: 23.5 mi W of Dayton, MT (bearing/distance from source text, dead-reckoned); "
                   "no named OSM feature found",
    },
}


def geocode(name: str) -> tuple[float | None, float | None, str]:
    plan = GEOCODE_RESULTS[name]
    if "osm" in plan:
        lat, lon = plan["osm"]
        return lat, lon, plan["method"]
    dr = plan["dead_reckon"]
    ref_lat, ref_lon = REFERENCE_TOWNS[dr["from_town"]]
    lat, lon = destination_point(ref_lat, ref_lon, dr["bearing"], dr["distance_mi"])
    return round(lat, 5), round(lon, 5), plan["method"]


def parse_lookouts(html: str) -> list[dict]:
    p_blocks = re.findall(r'<p class="text-left[^>]*>(.*?)</p>', html, re.S)
    seen_text = set()
    out = []
    for p in p_blocks:
        text = strip_tags(p)
        if text in seen_text or "Located" not in text or "Elevation" not in text:
            continue
        seen_text.add(text)
        m = FACTS_RE.match(text)
        if not m:
            print(f"  ! unparsed lookout block: {text[:80]}...", file=sys.stderr)
            continue
        out.append(m.groupdict())
    return out


def main() -> None:
    html = fetch_text(PAGE_URL, SOURCE, "lookouts.html")
    facts_list = parse_lookouts(html)

    records = []
    for facts in facts_list:
        name = facts["name"].strip()
        county = facts["county"].strip()
        elevation_ft = float(facts["elev"])
        prose = facts["prose"].strip()

        designs = DESIGN_RE.findall(prose)
        design = designs[-1] if designs else None
        heights = [int(h) for h in HEIGHT_RE.findall(prose)]
        height_ft = heights[-1] if heights else None
        built_m = BUILT_RE.search(prose)
        built_year = int(built_m.group(1)) if built_m else None

        low = prose.lower()
        gone_m = GONE_BY_RE.search(prose)
        if gone_m:
            status = "gone"
        elif "no longer in use" in low:
            status = "unknown"  # text doesn't say the structure was removed, just unused
        else:
            status = "standing"

        staffing = None
        if "staffed every summer" in low:
            staffing = "staffed"
        elif "only staffed during emergencies" in low or "staffed during emergencies" in low:
            staffing = "emergency"
        elif "staffed during the summer" in low:
            staffing = "staffed"
        elif "no longer in use" in low:
            staffing = "unstaffed"

        events = []
        if built_year:
            events.append({"year": built_year, "event": "built", "note": None, "from": "cskt"})
        if gone_m:
            events.append({"year": int(gone_m.group(1)), "event": "removed", "note": None, "from": "cskt"})

        lat, lon, coord_method = geocode(name)

        key = f"{SOURCE}:{slugify(name)}"
        rec = {
            "key": key,
            "url": PAGE_URL,
            "name": name,
            "country": "US",
            "region": "MT",
            "county": county,
            "lat": lat,
            "lon": lon,
            "elevation_m": ft_to_m(elevation_ft),
            "type_raw": None,
            "kind": "tower",
            "status_raw": None,
            "status": status,
            "registers": [],
            "built": built_year,
            "agency": "Confederated Salish and Kootenai Tribes (Flathead Reservation)",
            "events": events,
            "photos": [],  # thumbnails on the page are tiny decorative crops, not credited originals; skipped
            "links": [{"label": "CSKT Fire on the Land -- Fire Lookouts", "url": PAGE_URL}],
            "rental": None,
            "extra": {
                "ownership": "tribal",
                "permission": "Flathead Reservation land; visiting these sites may require tribal permission -- confirm with CSKT before any visit guidance is published",
                "elevation_ft": elevation_ft,
                "coord_method": coord_method,
                **({"design": design} if design else {}),
                **({"height_ft": height_ft} if height_ft else {}),
                **({"staffing_hint": staffing} if staffing else {}),
            },
        }
        records.append(rec)

    out_path = REPO_ROOT / "data" / "sources" / "cskt.json"
    write_source_json(
        out_path,
        source=SOURCE,
        title="Fire Lookouts on the Flathead Reservation (CSKT Fire on the Land)",
        url=PAGE_URL,
        retrieved=datetime.date.today().isoformat(),
        license_="No licence stated; facts only. Coordinates are geocoded (OSM Nominatim) or dead-reckoned -- see extra.coord_method per record.",
        records=records,
    )
    print(f"wrote {len(records)} records -> {out_path}")


if __name__ == "__main__":
    main()
