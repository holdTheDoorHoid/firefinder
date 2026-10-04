"""Fetcher for tnlandforms.us (Tom Dunigan's landforms/geocaching site), found
while searching for a Georgia state-forestry fire-tower list (the search
instead turned up this independent surveyor's own dataset, which turns out
to be the single richest candidate found for any of this task's gap states).
robots.txt gives no User-agent line, only a bare "Crawl-delay: 10" -- honoured
here as if it applied to every agent (DESIGN.md Sec 2's own 2 s minimum is a
floor, not a ceiling).

Three pages, three gap states:
  - https://tnlandforms.us/gatowers.html  -- Georgia, 427 towers
  - https://tnlandforms.us/nctowers.html  -- North Carolina, 227 towers
  - https://tnlandforms.us/towers/towers.gpx -- Tennessee, 275 waypoints

GA/NC are the same template: a <pre> block of CSV-like lines, one per tower,
with the coordinates given twice (redundantly) -- once in the visible text,
once in the href query string of the link wrapping it; the href is what gets
parsed, since it is well-formed regardless of the display text's rounding.
Column 5 means different things on the two pages (checked against every row,
2026-10-04): on the Georgia page it is always a bare number (elevation in
feet); on the North Carolina page it is never numeric -- usually an NGS PID
("FB3510"), sometimes a placeholder ("0 bm", "gw topo"). Both are handled by
inspecting the value itself rather than hard-coding per-state column
semantics, so a third state added in this format would parse correctly with
no code change. Column 6, only ever populated on the Georgia page, carries
register cross-references in free text ("nhlr gfc-610", "BLL-41100 gfc-605",
"Ron GA097-relocated") -- "gfc-NNN" and "BLL-NNNNN" are parsed into
registers[]; an "nhlr"/"fflos" flag (meaning "also on that register, no
number given here") is kept as extra.on_nhlr / extra.on_fflos; anything else
is kept verbatim in extra.notes_raw (it is the site's own short tag, not
narrative prose). GA/NC give no status at all -- every record here is
status "unknown" unless a sibling source says otherwise.

Tennessee's towers.gpx is cleaner still: real GPX waypoints with lat/lon,
<ele> in metres, a waypoint code, the tower name, and a <desc> of
"<County> [<NGS PID>] [<agency flag>] [<state #>] <status>" -- status is
given directly (standing/removed/moved/historical/sitting[sic]/station/
replaced/"?"), which this fetcher trusts for the two unambiguous words
(standing, and its one-off typo "sitting") and gone ("removed"); "moved" maps
to relocated; everything else (historical, station, replaced, "?") is too
ambiguous to assert either way and is kept only as status_raw.

Output: data/sources/tnlandforms.json

Re-run: python3 pipeline/regional/tnlandforms.py
"""

from __future__ import annotations

import datetime
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import ft_to_m, slugify, fetch_text, write_source_json  # noqa: E402

SOURCE = "tnlandforms"
BASE = "https://tnlandforms.us"
HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

# This site's own robots.txt asks for a 10 s crawl delay (no User-agent line,
# honoured for every agent); only 3 requests total are needed, so the extra
# wait costs under 30 s.
CRAWL_DELAY_S = 10.0

ROW_RE = re.compile(
    r"^([A-Z]+\d+),(.*?),<a href=google\.php\?lat=(-?[\d.]+)&lon=(-?[\d.]+)[^>]*>.*?</a>,(.*)$"
)
PID_RE = re.compile(r"^[A-Z]{2}\d{3,5}$")
GFC_RE = re.compile(r"\bgfc-(\d+)\b", re.I)
BLL_RE = re.compile(r"\bBLL-?(\d+)\b", re.I)

WPT_RE = re.compile(
    r'<wpt lat="(-?[\d.]+)" lon="(-?[\d.]+)">\s*<ele>(-?[\d.]+)</ele>\s*'
    r"<name>([^<]+)</name>\s*<cmt>([^<]*)</cmt>\s*<desc>([^<]*)</desc>",
)
TN_STATUS_MAP = {"standing": "standing", "sitting": "standing", "removed": "gone", "moved": "relocated"}


def parse_pre_page(region: str, html: str, prefix: str, page_url: str) -> list[dict]:
    lines = [l for l in html.split("\n") if re.match(rf"^{prefix}\d+,", l)]
    records = []
    for line in lines:
        m = ROW_RE.match(line)
        if not m:
            print(f"  ! {region}: no match for row {line[:60]!r}", file=sys.stderr)
            continue
        code, name_raw, lat_s, lon_s, rest = m.groups()
        name = name_raw.strip() or None
        if not name:
            continue
        parts = rest.split(",")
        county = (parts[0].strip() or None) if parts else None
        field5 = parts[1].strip() if len(parts) > 1 else ""
        field6 = ",".join(parts[2:]).strip() if len(parts) > 2 else ""

        elevation_ft = None
        extra: dict = {}
        registers = []
        if field5.isdigit():
            elevation_ft = int(field5)
        elif PID_RE.match(field5):
            registers.append({"register": "NGS", "number": field5, "state_number": None})
        elif field5 and field5.lower() != "0 bm":
            extra["reference_note"] = field5

        if field6:
            gfc_m = GFC_RE.search(field6)
            if gfc_m:
                registers.append({"register": "GFC", "number": gfc_m.group(1), "state_number": None})
            bll_m = BLL_RE.search(field6)
            if bll_m:
                registers.append({"register": "BLL", "number": bll_m.group(1), "state_number": None})
            low = field6.lower()
            if "nhlr" in low:
                extra["on_nhlr"] = True
            if "fflos" in low:
                extra["on_fflos"] = True
            if not gfc_m and not bll_m and "nhlr" not in low and "fflos" not in low:
                extra["notes_raw"] = field6

        key = f"{SOURCE}:{region.lower()}:{code.lower()}"
        rec = {
            "key": key,
            "url": page_url,
            "name": name,
            "country": "US",
            "region": region,
            "county": county,
            "lat": round(float(lat_s), 5),
            "lon": round(float(lon_s), 5),
            "elevation_m": ft_to_m(elevation_ft) if elevation_ft else None,
            "type_raw": None,
            "kind": "tower",
            "status_raw": None,
            "status": "unknown",
            "registers": registers,
            "built": None,
            "agency": None,
            "events": [],
            "photos": [],
            "links": [{"label": "tnlandforms.us (Tom Dunigan)", "url": page_url}],
            "rental": None,
            "extra": {**extra, **({"elevation_ft": elevation_ft} if elevation_ft else {})},
        }
        records.append(rec)
    return records


def parse_tn_gpx(xml: str) -> list[dict]:
    records = []
    for lat_s, lon_s, ele_s, code, cmt, desc in WPT_RE.findall(xml):
        name = cmt.strip() or None
        if not name:
            continue
        tokens = desc.split()
        county = tokens[0].strip(",") if tokens else None
        rest_tokens = tokens[1:]
        pid = None
        state_num = None
        agency_flag = None
        status_word = None
        for t in rest_tokens:
            if PID_RE.match(t):
                pid = t
            elif re.fullmatch(r"\d+-\d+", t):
                state_num = t
            elif t.lower() in ("gsmnp", "cnf"):
                agency_flag = t.lower()
            else:
                status_word = t  # last non-matching token wins; typically the status word
        status = TN_STATUS_MAP.get((status_word or "").lower(), "unknown")

        registers = [{"register": "NGS", "number": pid, "state_number": None}] if pid else []
        extra = {}
        if state_num:
            extra["tn_tower_number"] = state_num
        if agency_flag == "gsmnp":
            extra["agency_hint"] = "Great Smoky Mountains National Park"
        elif agency_flag == "cnf":
            extra["agency_hint"] = "Cherokee National Forest"

        key = f"{SOURCE}:tn:{code.lower()}"
        rec = {
            "key": key,
            "url": f"{BASE}/towers/",
            "name": name,
            "country": "US",
            "region": "TN",
            "county": county,
            "lat": round(float(lat_s), 5),
            "lon": round(float(lon_s), 5),
            "elevation_m": round(float(ele_s), 1),
            "type_raw": None,
            "kind": "tower",
            "status_raw": status_word,
            "status": status,
            "registers": registers,
            "built": None,
            "agency": extra.get("agency_hint"),
            "events": [],
            "photos": [],
            "links": [{"label": "tnlandforms.us (Tom Dunigan) -- TN towers", "url": f"{BASE}/towers/"}],
            "rental": None,
            "extra": extra,
        }
        records.append(rec)
    return records


def main() -> None:
    retrieved = datetime.date.today().isoformat()
    records: list[dict] = []

    ga_url = f"{BASE}/gatowers.html"
    ga_html = fetch_text(ga_url, SOURCE, "ga-towers.html", encoding="utf-8")
    ga_recs = parse_pre_page("GA", ga_html, "GA", ga_url)
    print(f"  GA: {len(ga_recs)} towers", file=sys.stderr)
    records.extend(ga_recs)
    time.sleep(CRAWL_DELAY_S)

    nc_url = f"{BASE}/nctowers.html"
    nc_html = fetch_text(nc_url, SOURCE, "nc-towers.html", encoding="utf-8")
    nc_recs = parse_pre_page("NC", nc_html, "NCT", nc_url)
    print(f"  NC: {len(nc_recs)} towers", file=sys.stderr)
    records.extend(nc_recs)
    time.sleep(CRAWL_DELAY_S)

    tn_gpx = fetch_text(f"{BASE}/towers/towers.gpx", SOURCE, "tn-towers.gpx", encoding="utf-8")
    tn_recs = parse_tn_gpx(tn_gpx)
    print(f"  TN: {len(tn_recs)} towers", file=sys.stderr)
    records.extend(tn_recs)

    out_path = REPO_ROOT / "data" / "sources" / f"{SOURCE}.json"
    write_source_json(
        out_path,
        source=SOURCE,
        title="tnlandforms.us fire lookout towers (Tom Dunigan) -- GA, NC, TN",
        url=f"{BASE}/towers/",
        retrieved=retrieved,
        license_=(
            "No licence stated; facts only (coordinates, county, elevation, NGS/GFC/BLL "
            "register cross-references, status where given)."
        ),
        records=records,
    )
    print(f"wrote {len(records)} records -> {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
