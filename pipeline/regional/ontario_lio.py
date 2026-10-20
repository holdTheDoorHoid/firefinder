"""Fetcher for the Land Information Ontario (LIO) "Tower" layer: Ontario's fire towers (2026-10-20).

LIO's Tower layer (Ministry of Natural Resources) holds 3,080 towers of every kind; its subtype
"Fire Tower" is 95 points with good positions (each with its accuracy, mostly within 10 to 50 m).
42 carry an official name, 12 an identifier, 39 a comment ("Constructed in 1929", "Tower not used",
"MNR Fire Tower - no longer used"). There is no status field and the checks date from 1998-2000,
and the layer keeps towers the province removed later, so every record's status is unknown.

One request (survey docs/sources/expansion_on.md):
  https://ws.lioservices.lrc.gov.on.ca/arcgis2/rest/services/LIO_OPEN_DATA/LIO_Open10/MapServer/14/query
    ?where=CLASS_SUBTYPE='Fire Tower'&outFields=*&outSR=4326&f=geojson
cached under $FIREFINDER_RAW_ROOT/ontario_lio/fire_towers.geojson (the Ontario survey's copy of the
same answer, data/raw/expansion/on/lio_fire_towers.geojson, is used when present instead of asking
again). ws.lioservices has no robots.txt; one request, our User-Agent.

Licence: Open Government Licence - Ontario. Credit line (About page): "Contains information
licensed under the Open Government Licence – Ontario."

Names. An official name is used as given (capitals title-cased; "MNR Stetham Fire Tower" without the
ministry's initials). A tower with none takes its identifier when that is a name ("Sydere"), else
no name: the merge then names it from another source at the spot, and only failing that shows our
fallback ("Unnamed fire tower near Upsala" when the location note names a place, else "Fire tower
(LIO 301092334)"; extra.fallback_name). Positions LIO itself rates "Within 500 metres" or loaded
without an accuracy ("Data Load") are marked approximate.

Output: data/sources/ontario_lio.json
Re-run: python3 pipeline/regional/ontario_lio.py
"""

from __future__ import annotations

import datetime
import json
import pathlib
import re
import shutil
import sys
import urllib.parse

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _common import RAW_ROOT, fetch, write_source_json  # noqa: E402

SOURCE = "ontario_lio"
SERVICE = "https://ws.lioservices.lrc.gov.on.ca/arcgis2/rest/services/LIO_OPEN_DATA/LIO_Open10/MapServer/14"
QUERY_URL = SERVICE + "/query?" + urllib.parse.urlencode(
    {"where": "CLASS_SUBTYPE='Fire Tower'", "outFields": "*", "outSR": "4326", "f": "geojson"})
DATASET_URL = "https://geohub.lio.gov.on.ca/datasets/mnrf::tower"
CACHE = "fire_towers.geojson"
SURVEY_COPY = RAW_ROOT / "expansion" / "on" / "lio_fire_towers.geojson"
OUT = HERE.parent.parent / "data" / "sources" / f"{SOURCE}.json"
LICENSE = "Open Government Licence – Ontario (https://www.ontario.ca/page/open-government-licence-ontario)"
CREDIT = "Contains information licensed under the Open Government Licence – Ontario."

# Places the location notes of unnamed towers name (our reading, by OGF_ID).
NEAR = {
    67107577: "near McCreights Pond",
    70699531: "at Dividing Lake",
    550803154: "near the Frost Centre",
    500490746: "in Moses Township",
    151324467: "near Upsala",
    151324470: "in Haines Township",
    151324472: "in Aldina Township",
    151324473: "near Dog River",
    1300130578: "near Pashkokogan Lake",
    950318868: "in McKeown Township",
}
GENERIC = {"mnr", "old fire tower", "fire tower", "unknown1"}
ACCURACY_ROUGH = ("Within 500 metres", "Data Load")
CONSTRUCTED_RE = re.compile(r"\bconstructed in (1[89]\d\d|20[0-2]\d)\b", re.I)


def load() -> dict:
    path = RAW_ROOT / SOURCE / CACHE
    if not path.exists() and SURVEY_COPY.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SURVEY_COPY, path)
    return json.loads(fetch(QUERY_URL, SOURCE, CACHE, timeout=60).decode("utf-8"))


def tidy(name: str | None) -> str | None:
    if not name:
        return None
    s = re.sub(r"\s+", " ", name).strip()
    s = re.sub(r"^MNR\s+", "", s)
    if not s or s.lower() in GENERIC:
        return None
    if s.isupper() and len(s) > 3:
        s = s.title()
    return s


def year_of_ms(ms) -> int | None:
    if not isinstance(ms, (int, float)):
        return None
    return (datetime.datetime(1970, 1, 1) + datetime.timedelta(milliseconds=ms)).year


def build_record(feat: dict) -> dict:
    p = feat["properties"]
    fid = int(p["OGF_ID"])
    lon, lat = feat["geometry"]["coordinates"][:2]
    ident = (p.get("TOWER_IDENT") or "").strip()
    name = tidy(p.get("OFFICIAL_NAME"))
    if name is None and re.fullmatch(r"[A-Za-z][A-Za-z' -]+", ident) and ident.lower() not in GENERIC:
        name = f"{ident.title()} Fire Tower"
    extra: dict = {"ogf_id": fid}
    if name is None:
        extra["fallback_name"] = f"Unnamed fire tower {NEAR[fid]}" if fid in NEAR else f"Fire tower (LIO {fid})"
    if ident:
        extra["tower_ident"] = ident
    acc = (p.get("LOCATION_ACCURACY") or "").replace("^", "").strip()
    extra["location_accuracy"] = acc or None
    if any(a in acc for a in ACCURACY_ROUGH):
        extra["position_approximate"] = True
    if p.get("VERIFICATION_STATUS_FLG"):
        extra["lio_verification"] = p["VERIFICATION_STATUS_FLG"]
    events = []
    text = " ".join(str(p.get(k) or "") for k in ("GENERAL_COMMENTS", "COMMENTS"))
    m = CONSTRUCTED_RE.search(text)
    built = int(m.group(1)) if m else year_of_ms(p.get("TOWER_CONSTRUCTION_DATE"))
    if built:
        events.append({"year": built, "event": "built", "note": None, "from": SOURCE})
    elev_ft = p.get("GROUND_ELEV_ASL_NUM")
    elevation = round(float(elev_ft) * 0.3048, 1) if isinstance(elev_ft, (int, float)) else None
    if elevation is not None:
        extra["elevation_ft"] = elev_ft
    return {
        "key": f"{SOURCE}:{fid}",
        "url": DATASET_URL,
        "name": name,
        "country": "CA",
        "region": "ON",
        "county": None,
        "lat": round(float(lat), 6),
        "lon": round(float(lon), 6),
        "elevation_m": elevation,
        "type_raw": None,
        "kind": "tower",
        "status_raw": None,
        "status": "unknown",
        "registers": [],
        "built": built,
        "agency": None,
        "events": events,
        "photos": [],
        "links": [],
        "rental": None,
        "extra": extra,
    }


def main() -> int:
    data = load()
    feats = [f for f in data.get("features") or [] if (f.get("properties") or {}).get("CLASS_SUBTYPE") == "Fire Tower"]
    records = sorted((build_record(f) for f in feats), key=lambda r: r["key"])
    path = RAW_ROOT / SOURCE / CACHE
    retrieved = datetime.date.fromtimestamp(path.stat().st_mtime).isoformat()
    write_source_json(OUT, source=SOURCE, title="Land Information Ontario: Tower layer (fire towers)",
                      url=DATASET_URL, retrieved=retrieved, license_=LICENSE, records=records,
                      header_extra={"credit": CREDIT, "query": QUERY_URL})
    named = sum(1 for r in records if r["name"])
    print(f"wrote {len(records)} records ({named} named) -> {OUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
