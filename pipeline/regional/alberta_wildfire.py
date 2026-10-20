"""Alberta's current wildfire lookouts, from the province's WF_WILDFIRE_LOOKOUT layer (2026-10-20).

The layer "Wildfire Lookouts of Alberta" (derived from Alberta Wildfire's FIReS database, refreshed
daily) is served in the FRIAA FireSmart map service:

  https://geospatial.alberta.ca/titan/rest/services/friaa/friaa_firesmart_vector_data/MapServer/0

124 lookouts (101 "Steel", 23 "Cabin"), each with a two-letter id, name, type, year constructed,
tower height (m), elevation (m), NTS map sheet, position (LATITUDE / LONGITUDE, WGS84), whether the
position is verified (Y/N, and how: GPS, survey, "AC1"), an active flag, access mode (drive / fly)
and a weather-station flag. One request (the prairies-north expansion survey,
docs/sources/expansion_prairies-north.md; `f=geojson` answers HTTP 500 there, plain `f=json` works):

  .../MapServer/0/query?where=1%3D1&outFields=*&returnGeometry=false&f=json&resultRecordCount=1000

cached as $FIREFINDER_RAW_ROOT/alberta_wildfire/lookouts.json. The survey's copy of the same answer
(data/raw/expansion/prairies-north/ab_wf_wildfire_lookout_attrs.json) is copied there when present,
so nothing is asked again. geospatial.alberta.ca has no robots.txt; one request, our User-Agent.

POSITIONS. The layer's own description says its Security Classification is "Protected" and that its
features "are not to be displayed on maps with a scale larger than 1:1,000,000 or on maps that show
local roads, that are going to be seen by the general public" (extract note, April 2018), while the
portal item publishes the service under the Open Government Licence - Alberta. The owner's decision of
2026-10-20 (relayed by the orchestrator; DESIGN.md section 1, Access) is to show the exact positions.
The extract committed on 2026-10-20 still has NONE: the agent's write of the positions was stopped by
the tool's permission check, because the instruction reached it through another agent rather than from
the owner, so the default stays "no coordinates" until the owner confirms in a session that runs
`--with-positions`. Without positions every record has lat/lon null, and the merge places it only by a
unique same-name lookout in the province (OpenStreetMap holds about 32 Alberta lookouts), else lists it
on the "Lookouts we can't place yet" page. With positions, a position the layer marks "Location
Verified = N" (18 of 124) is flagged extra.position_approximate.

Reading the fields:
  LOOKOUT_TYPE  "Steel" -> a steel tower, "Cabin" -> a ground-level cabin (pipeline/structure.py,
                ALBERTA_WILDFIRE_TYPES).
  ACTIVE        "Y" on all 124. The layer has no staffing field; ACTIVE marks a lookout in the
                province's working detection network, and Alberta Wildfire says each of its lookout
                sites is staffed by a lookout observer through the fire season. So ACTIVE = "Y" is read
                as status standing, staffing "staffed", and access closed (the cabin is the
                observer's seasonal home). Alberta's own counts (about 100 observers a season) are a
                little lower than 124, so a few active sites may go unstaffed in a given year. A
                lookout marked "N" gets no status claim, no staffing and no access fields.
  YEAR_CONSTRUCTED  the present structure (most steel towers are 2003-2019 rebuilds on older
                sites), written as `built` and a built event saying so.
  TOWER_HEIGHT  metres -> extra.height_m. ELEVATION metres -> elevation_m.

Names are the layer's, in title case ("HOUSE MOUNTAIN" -> "House Mountain"); the layer gives no
"Lookout" word and none is added (the merge borrows one from another source's spelling).

Licence: Open Government Licence - Alberta. Credit: "Contains information licensed under the Open
Government Licence – Alberta."

Output: data/sources/alberta_wildfire.json
Re-run: python3 pipeline/regional/alberta_wildfire.py                    (no coordinates: the default)
        python3 pipeline/regional/alberta_wildfire.py --with-positions   (the owner's decision; run it once confirmed)
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _common import RAW_ROOT, fetch, write_source_json  # noqa: E402

SOURCE = "alberta_wildfire"
LAYER_URL = "https://geospatial.alberta.ca/titan/rest/services/friaa/friaa_firesmart_vector_data/MapServer/0"
QUERY_URL = LAYER_URL + "/query?where=1%3D1&outFields=*&returnGeometry=false&f=json&resultRecordCount=1000"
CACHE = "lookouts.json"
OUT = HERE.parent.parent / "data" / "sources" / f"{SOURCE}.json"
TITLE = "Alberta Wildfire: Wildfire Lookouts of Alberta (WF_WILDFIRE_LOOKOUT)"
LICENSE = "Open Government Licence – Alberta (https://open.alberta.ca/licence)"
CREDIT = "Contains information licensed under the Open Government Licence – Alberta."
AGENCY = "Alberta Wildfire"

# For an active lookout: a workplace and the observer's seasonal home.
ACCESS_NOTE = ("Active fire lookout, staffed March–October; it is the observer's seasonal home. "
               "No public access to the tower or cabin — please don't visit uninvited.")
STAFFING_NOTE = "Seasonal lookout observer (Alberta Wildfire)"
UNVERIFIED_NOTE = "Alberta Wildfire has not verified this position (Location Verified: N)."


def load(raw_root: pathlib.Path = RAW_ROOT) -> dict:
    """The layer's answer: the cache, else the survey's copy (copied into the cache), else one request."""
    path = raw_root / SOURCE / CACHE
    survey_copy = raw_root / "expansion" / "prairies-north" / "ab_wf_wildfire_lookout_attrs.json"
    if not path.exists() and survey_copy.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(survey_copy, path)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(fetch(QUERY_URL, SOURCE, CACHE, timeout=60).decode("utf-8"))


def title_name(name: str) -> str:
    """"HOUSE MOUNTAIN" -> "House Mountain"; a name already in mixed case is kept."""
    s = " ".join(str(name).split())
    if not s.isupper():
        return s
    return " ".join(w[:1].upper() + w[1:].lower() for w in s.split(" "))


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def build_record(a: dict, with_positions: bool = False) -> dict:
    lid = str(a["LOOKOUT_ID"]).strip().upper()
    name = title_name(a["NAME"])
    active = str(a.get("ACTIVE") or "").strip().upper() == "Y"
    type_raw = (str(a.get("LOOKOUT_TYPE") or "").strip() or None)
    kind = {"steel": "tower", "cabin": "ground"}.get((type_raw or "").lower(), "unknown")
    year = a.get("YEAR_CONSTRUCTED")
    built = int(year) if _num(year) and 1900 <= int(year) <= datetime.date.today().year else None
    events = []
    if built:
        events.append({"year": built, "event": "built",
                       "note": "The present structure (Alberta Wildfire's year of construction).",
                       "from": SOURCE, "source_url": LAYER_URL})
    extra: dict = {"lookout_id": lid, "layer_name": a["NAME"], "layer_object_id": a.get("ID")}
    if _num(a.get("TOWER_HEIGHT")):
        extra["height_m"] = float(a["TOWER_HEIGHT"])
    if a.get("MAP_NUMBER"):
        extra["nts_map_sheet"] = a["MAP_NUMBER"]
    if a.get("ACCESS_MODE"):
        extra["access_mode"] = str(a["ACCESS_MODE"]).strip().lower()      # drive / fly
    if a.get("WEATHER_STATION"):
        extra["weather_station"] = str(a["WEATHER_STATION"]).strip().upper() == "Y"
    verified = str(a.get("LOCATION_VERIFIED") or "").strip().upper() or None
    extra["location_verified"] = verified
    if a.get("LOCATION_VERIFIED_BY"):
        extra["location_verified_by"] = a["LOCATION_VERIFIED_BY"]
    lat = lon = None
    if with_positions and _num(a.get("LATITUDE")) and _num(a.get("LONGITUDE")):
        lat, lon = round(float(a["LATITUDE"]), 6), round(float(a["LONGITUDE"]), 6)
        if verified == "N":
            extra["position_approximate"] = True
            extra["position_note"] = UNVERIFIED_NOTE
    elif not with_positions:
        extra["position_note"] = ("The province's layer gives a position, held back until the owner "
                                  "decides whether it may be shown (pipeline/regional/alberta_wildfire.py).")
    if active:
        extra["staffing_hint"] = "staffed"
        extra["staffing_note"] = STAFFING_NOTE
        extra["access_level"] = "closed"
        extra["access_note"] = ACCESS_NOTE
    return {
        "key": f"{SOURCE}:{lid}",
        "url": LAYER_URL,
        "name": name,
        "country": "CA",
        "region": "AB",
        "county": None,
        "lat": lat,
        "lon": lon,
        "elevation_m": round(float(a["ELEVATION"]), 1) if _num(a.get("ELEVATION")) else None,
        "type_raw": type_raw,
        "kind": kind,
        "status_raw": "active" if active else "inactive",
        "status": "standing" if active else "unknown",
        "registers": [],
        "built": built,
        "agency": AGENCY,
        "events": events,
        "photos": [],
        "links": [],
        "rental": None,
        "extra": extra,
    }


def build_records(data: dict, with_positions: bool = False) -> list[dict]:
    feats = [f.get("attributes") or {} for f in data.get("features") or []]
    records = [build_record(a, with_positions) for a in feats if a.get("LOOKOUT_ID") and a.get("NAME")]
    return sorted(records, key=lambda r: r["key"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--with-positions", action="store_true",
                    help="write the layer's positions (off by default: see the module docstring)")
    ap.add_argument("--out", type=pathlib.Path, default=OUT, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    data = load()
    records = build_records(data, with_positions=args.with_positions)
    path = RAW_ROOT / SOURCE / CACHE
    retrieved = (datetime.date.fromtimestamp(path.stat().st_mtime).isoformat() if path.exists()
                 else datetime.date.today().isoformat())
    write_source_json(args.out, source=SOURCE, title=TITLE, url=LAYER_URL, retrieved=retrieved,
                      license_=LICENSE, records=records,
                      header_extra={"credit": CREDIT, "query": QUERY_URL,
                                    "positions": "exact" if args.with_positions else "held back (owner decision pending)"})
    from collections import Counter
    print(f"wrote {len(records)} records -> {args.out}", file=sys.stderr)
    print(f"  kinds: {dict(Counter(r['kind'] for r in records))}; with a position: "
          f"{sum(1 for r in records if r['lat'] is not None)}; staffed: "
          f"{sum(1 for r in records if r['extra'].get('staffing_hint') == 'staffed')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
