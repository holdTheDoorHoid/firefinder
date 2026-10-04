"""Fetcher for fire-lookouts.org (Rich Camp's Sierra National Forest area
lookout pages), covering ~19 California lookouts on the Sequoia and Sierra
National Forests plus two CAL FIRE (CDF) cooperative towers.

Licence: the site's disclaim.htm states "Information presented on this
website is considered public information and may be distributed or copied
unless otherwise indicated on the site. Use of appropriate byline/photo/
image credit is requested." -- one of the two reuse-permitted regional
sources named in DESIGN.md Sec 2, so (per the brief) a short description is
kept in extra.description with extra.license set, unlike the facts-only
sources. The per-tower pages otherwise run 3-5 paragraphs of history and
FFLA year-by-year maintenance logs; only the first (most factual) paragraph
is kept as the short description -- the rest stays in the raw cache, not
the committed JSON.

Output: data/sources/fire_lookouts_org.json

Re-run: python3 pipeline/regional/fire_lookouts_org.py
"""

from __future__ import annotations

import datetime
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import fetch_text, ft_to_m, slugify, write_source_json  # noqa: E402

SOURCE = "fire_lookouts_org"
BASE = "https://www.fire-lookouts.org"
INDEX_URL = f"{BASE}/cali/cali.htm"
LICENSE_NOTE = ("Public information per the site's own disclaimer: \"may be distributed or "
                "copied unless otherwise indicated... byline/photo/image credit is requested.\"")
CREDIT = "fire-lookouts.org (Rich Camp)"

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

INDEX_LINK_RE = re.compile(r'<a href="\./([a-z_]+)/index\.htm">([^<]+)</a>', re.I)

GPS_RE = re.compile(r"GPS location is:?\s*([\d.]+)\s*&deg;?\s*N\s*[,/]\s*([\d.]+)\s*&deg;?\s*W", re.I)
NHLR_RE = re.compile(r"National Historic Lookout Register on\s*([\d/]+)\s*as Lookout No\.?\s*(\d+)", re.I)
ELEV_RE = re.compile(
    r"(?:elevation of|[Ss]itting at|located at|[Ee]levation[:\s]+)\s*([\d,]+)\s*feet(?:\s*in elevation)?",
    re.I,
)
DESIGN_RE = re.compile(r"\b(L-4|L-5|L-6|R-6|D-6|Aermotor)\b")
HEIGHT_RE = re.compile(r"(?<![\dx])(\d{1,3})[-'’]?\s*(?:foot|ft)\s+(?:H-braced|steel|wood(?:en)?|treated timber)?\s*tower", re.I)
BUILT_RE = re.compile(r"(?:[Cc]onstructed|built)\D{0,25}?(\d{4})")
GONE_KEYWORDS_RE = re.compile(r"razed|demolished|no longer stands|collapsed|torn down|was removed in", re.I)


def strip_tags(s: str) -> str:
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_detail(html: str) -> dict:
    gps_m = GPS_RE.search(html)
    lat = lon = None
    if gps_m:
        lat = float(gps_m.group(1))
        lon = -float(gps_m.group(2))  # page always gives west longitude as a positive number

    nhlr_m = NHLR_RE.search(html)
    registers = []
    nhlr_year = None
    if nhlr_m:
        date_str, number = nhlr_m.group(1), nhlr_m.group(2)
        registers.append({"register": "NHLR", "number": number, "state_number": None})
        parts = date_str.split("/")
        if len(parts) == 3:
            nhlr_year = int(parts[2])

    elev_m = ELEV_RE.search(html)
    elevation_ft = float(elev_m.group(1).replace(",", "")) if elev_m else None

    h2_m = re.search(r"<h2[^>]*>(.*?)</h2>", html, re.S)
    h3_m = re.search(r"<h3[^>]*>(.*?)</h3>", html, re.S)
    h2_text = strip_tags(h2_m.group(1)) if h2_m else ""
    h3_text = strip_tags(h3_m.group(1)) if h3_m else ""
    if "california department of forestry" in h2_text.lower():
        agency_raw = f"CAL FIRE (CDF) -- {h3_text}" if h3_text else "CAL FIRE (CDF)"
        ownership = "state"
    elif h3_text:
        agency_raw = h3_text
        ownership = "federal"
    else:
        agency_raw = None
        ownership = "unknown"

    # First substantive <p> in the main content table -- the factual
    # location/history paragraph. Later paragraphs (FFLA year-by-year
    # maintenance logs, anecdotes) are left out of the committed description.
    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html, re.S)
    description = None
    for p in paragraphs:
        text = strip_tags(p)
        if len(text) > 60 and "FFLA" not in text and "Volunteer" not in text[:20]:
            description = text
            break

    prose_for_facts = " ".join(strip_tags(p) for p in paragraphs)
    designs = DESIGN_RE.findall(prose_for_facts)
    design = designs[-1] if designs else None
    heights = [int(h) for h in HEIGHT_RE.findall(prose_for_facts)]
    height_ft = heights[-1] if heights else None
    built_years = [int(y) for y in BUILT_RE.findall(prose_for_facts)]
    built_year = built_years[-1] if built_years else None
    events = []
    if built_years:
        events.append({"year": built_years[-1], "event": "built", "note": None, "from": "fire_lookouts_org"})
        for y in built_years[:-1]:
            events.append({"year": y, "event": "built", "note": "original structure, later replaced", "from": "fire_lookouts_org"})
    if nhlr_year:
        events.append({"year": nhlr_year, "event": "nhlr_registered", "note": None, "from": "fire_lookouts_org"})

    low = prose_for_facts.lower()
    status = "gone" if GONE_KEYWORDS_RE.search(prose_for_facts) else "standing"
    staffing = None
    if "staffed with paid and volunteer" in low or "staffed full-time" in low or "staffed during fire season" in low:
        staffing = "staffed"
    elif "volunteer" in low and "staff" in low:
        staffing = "volunteer"
    elif "not staffed" in low or "non operational" in low or "not been used for fire detection" in low:
        staffing = "unstaffed"

    img_m = re.search(r'<img src="\./images/([^"]+)"', html)

    return {
        "lat": lat, "lon": lon,
        "registers": registers,
        "elevation_ft": elevation_ft,
        "agency_raw": agency_raw,
        "ownership": ownership,
        "description": description,
        "design": design,
        "height_ft": height_ft,
        "built_year": built_year,
        "events": events,
        "status": status,
        "staffing": staffing,
        "photo_filename": img_m.group(1) if img_m else None,
    }


def main() -> None:
    index_html = fetch_text(INDEX_URL, SOURCE, "cali.htm")
    entries = []
    for slug, label in INDEX_LINK_RE.findall(index_html):
        if slug == "sitecredit":  # the "?? Place Holder" dummy entry
            continue
        entries.append((slug, strip_tags(label)))

    records = []
    for slug, label in entries:
        name, _, forest_label = label.partition(",")
        name = name.strip().strip('"“”')  # cali.htm has a stray leading quote on one entry (Delilah)
        tower_url = f"{BASE}/cali/{slug}/index.htm"
        html = fetch_text(tower_url, SOURCE, f"cali/{slug}/index.htm")
        d = parse_detail(html)

        if d["lat"] is None or d["lon"] is None:
            print(f"  ! no GPS coordinates for {name!r}, skipping", file=sys.stderr)
            continue

        photos = []
        if d["photo_filename"]:
            photos.append({
                "url": f"{BASE}/cali/{slug}/images/{d['photo_filename']}",
                "credit": CREDIT,
                "caption": name,
                "year": None,
            })

        key = f"{SOURCE}:{slug}:{d['lat']:.4f}:{d['lon']:.4f}"
        rec = {
            "key": key,
            "url": tower_url,
            "name": name,
            "country": "US",
            "region": "CA",
            "county": None,
            "lat": round(d["lat"], 5),
            "lon": round(d["lon"], 5),
            "elevation_m": ft_to_m(d["elevation_ft"]),
            "type_raw": "tower",
            "kind": "tower",
            "status_raw": None,
            "status": d["status"],
            "registers": d["registers"],
            "built": d["built_year"],
            "agency": d["agency_raw"],
            "events": d["events"],
            "photos": photos,
            "links": [{"label": "fire-lookouts.org", "url": tower_url}],
            "rental": None,
            "extra": {
                "ownership": d["ownership"],
                **({"elevation_ft": d["elevation_ft"]} if d["elevation_ft"] else {}),
                **({"design": d["design"]} if d["design"] else {}),
                **({"height_ft": d["height_ft"]} if d["height_ft"] else {}),
                **({"staffing_hint": d["staffing"]} if d["staffing"] else {}),
                **({"description": d["description"], "license": LICENSE_NOTE + " Credit: " + CREDIT}
                   if d["description"] else {}),
            },
        }
        records.append(rec)

    out_path = REPO_ROOT / "data" / "sources" / "fire_lookouts_org.json"
    write_source_json(
        out_path,
        source=SOURCE,
        title="California Fire Lookouts of the Sierra National Forest and Other Areas (fire-lookouts.org)",
        url=INDEX_URL,
        retrieved=datetime.date.today().isoformat(),
        license_="Public information per the site's disclaimer, credit requested. Facts + a short description reused under that permission -- see extra.license per record.",
        records=records,
    )
    print(f"wrote {len(records)} records -> {out_path}")


if __name__ == "__main__":
    main()
