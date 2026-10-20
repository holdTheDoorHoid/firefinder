"""Two BC Geographic Warehouse layers -> two source extracts (2026-10-20).

BC's open map services (openmaps.gov.bc.ca, WFS; no robots.txt) hold two layers about fire lookouts:

* **bc_rec_sites**: `WHSE_FOREST_TENURE.FTEN_REC_SITE_POINTS_SVW` ("Recreation Sites Subset -
  Information Purposes Only"), filtered `PROJECT_NAME ILIKE '%lookout%' OR PROJECT_DESCRIPTION ILIKE
  '%fire lookout%'`: 23 sites, 21 of them lookouts (Lookout Lake and Swansea Mountain are not). Since
  2012 Recreation Sites and Trails BC has taken over abandoned lookouts as recreation sites, often with a
  club. Kept: the site's name and position (at the site), its REC number, the club that runs it, the
  road or trail access, and a closure notice when the site has one (quoted: a short government notice
  under the Open Government Licence). A build or removal year the description states exactly ("The
  present tower was built in 1974", "dismantled in the fall of 2007") becomes an event in our words.
  Each record's `county` is the regional district whose legal boundary holds it (the province's
  ABMS_REGIONAL_DISTRICTS_SP layer, Open Government Licence - British Columbia; see
  pipeline/fetch_cgndb_places.py), so a same-name lookout another source files in another district is
  not joined to it by name. Licence: Open Government Licence - British Columbia (the open.canada.ca record of the dataset, which
  the federal portal carries only for open-licensed BC data, 2026-10-20). Credit "Contains information
  licensed under the Open Government Licence - British Columbia."

* **bc_trim_lookouts**: `WHSE_BASEMAPPING.TRIM_EBM_LANDMARKSTRUCTURES`, `FEATURE_TYPE =
  'fireLookoutTower'` (FCODE BF10950120): 68 map symbols of a fire lookout tower on the province's
  1:20,000 base map (TRIM, mapped in the 1980s and 1990s), each the same 863 m2 footprint, with no name.
  Kept: the symbol's centre (5 decimals). A symbol gets a name only when it is the one symbol within
  1.5 km of the one same-name summit (CGNDB, high-ground generic terms, merge.CGNDB_HIGH_GROUND) of a
  BC lookout another source names without a position, and no lookout with a position stands within
  400 m of it (that lookout is the symbol's, and the merge joins them by position); `extra.named_by`
  records the record, the summit and the distance. A symbol left unnamed is "Unnamed lookout (BC base
  map)" (`extra.fallback_name`), after the sample check below showed the symbols mark fire lookouts.
  Licence: not confirmed. The layer's catalogue page is JavaScript only and its API is disallowed by
  the catalogue's robots.txt; the federal open-data portal, which carries BC's open-licensed datasets,
  has no record of it (404); the TRIM base map is otherwise sold by GeoBC. The positions are used as
  facts only, like the registers' (DESIGN.md 1, "Registry data"), credited and linked on every tower;
  the question is in the report for the owner.

Sample check of the TRIM symbols (2026-10-20, `--sample`): for each symbol, the nearest lookout another
source places. The ten nearest are Hamilton (8 m, Firelookout.ca), Jesmond (11 m, OpenStreetMap), Windy
Joe (12 m), Bluejoint (13 m), Begbie (15 m, the recreation site), Goat Peak (17 m), Old Glory (18 m),
Hicks Hill (22 m), Lavina (28 m) and Longworth (32 m): a symbol drawn on a lookout. 18 of the 68 lie within
400 m of a placed lookout; the rest are where no source places one. Two symbols share one spot (23100 and
31585, Windy Mountain: one record).

Cached responses: $FIREFINDER_RAW_ROOT/bc_geowarehouse/ (copied from the BC/Yukon survey's
data/raw/expansion/bc-yt/bcgw/, which made the two GetFeature calls on 2026-10-20; nothing re-fetched).

Output:  data/sources/bc_rec_sites.json, data/sources/bc_trim_lookouts.json
Re-run:  python3 pipeline/regional/bc_geowarehouse.py            (after canada_lookouts_weebly.py and
         firelookout_ca.py, whose records without a position it reads to name symbols)
         python3 pipeline/regional/bc_geowarehouse.py --sample   (print the sample check)
"""

from __future__ import annotations

import argparse
import datetime
import html as htmlmod
import json
import math
import pathlib
import re
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _common import RAW_ROOT, slugify, write_source_json  # noqa: E402
sys.path.insert(1, str(HERE.parent))
import ca_units  # noqa: E402
import fetch_peaks_cgndb  # noqa: E402
import merge  # noqa: E402

REPO = HERE.parent.parent
SOURCES = REPO / "data" / "sources"
RAW = RAW_ROOT / "bc_geowarehouse"
SURVEY = RAW_ROOT / "expansion" / "bc-yt" / "bcgw"
WFS = "https://openmaps.gov.bc.ca/geo/pub/ows?service=WFS&version=2.0.0&request=GetFeature&outputFormat=application/json&srsName=EPSG:4326"
REC_URL = WFS + ("&typeName=pub:WHSE_FOREST_TENURE.FTEN_REC_SITE_POINTS_SVW&cql_filter=PROJECT_NAME%20ILIKE%20%27%25lookout%25%27"
                 "%20OR%20PROJECT_DESCRIPTION%20ILIKE%20%27%25fire%20lookout%25%27")
TRIM_URL = WFS + "&typeName=pub:WHSE_BASEMAPPING.TRIM_EBM_LANDMARKSTRUCTURES&cql_filter=FEATURE_TYPE%20ILIKE%20%27%25look%25%27"
REC_DATASET = "https://open.canada.ca/data/en/dataset/bc37b35d-8d00-45ab-9ab2-57cae75637ad"
TRIM_DATASET = "https://catalogue.data.gov.bc.ca/dataset/d1fc9c40-c3ba-4ae4-ae5a-838ad3c43289"
REC_PAGE = "https://www.sitesandtrailsbc.ca/resource/{rec}"

# Rec sites the filter finds that are not lookouts.
NOT_LOOKOUTS = {
    "REC3066": "Lookout Lake: a lakeside campsite named for the lake",
    "REC2002": "Swansea Mountain: hiking and cycling trails; the description names no lookout",
}
NAME_RADIUS_M = 1500      # a symbol this close to the lookout's same-name summit can be its lookout
TAKEN_RADIUS_M = 400      # a symbol this close to a lookout with a position is that lookout's


def cached(name: str) -> pathlib.Path:
    dest = RAW / name
    if not dest.exists():
        src = SURVEY / name
        if not src.exists():
            raise SystemExit(f"{dest} is missing (and no survey copy at {src}); fetch {REC_URL if 'rec' in name else TRIM_URL}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    return dest


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    return merge.haversine_m(lat1, lon1, lat2, lon2)


# ---------------------------------------------------------------------------------------------
# Recreation sites
# ---------------------------------------------------------------------------------------------

BUILT_YEAR_RE = re.compile(r"\b(?:present tower|tower|building|lookout)\s+(?:was\s+)?(?:built|constructed)\s+in\s+((?:19|20)\d\d)\b", re.I)
REMOVED_YEAR_RE = re.compile(r"\bdismantled\s+in\s+(?:the\s+(?:fall|spring|summer|winter)\s+of\s+)?((?:19|20)\d\d)\b", re.I)


def plain(text: str | None) -> str:
    t = htmlmod.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", t).strip()


def rec_name(name: str) -> str:
    n = plain(name)
    if n.isupper() or re.match(r"^[A-Z ]{4,}\(", n):
        n = re.sub(r"\b([A-Z])([A-Z']+)\b", lambda m: m.group(1) + m.group(2).lower(), n)
    return n


_DISTRICTS = None


def district_at(lat: float | None, lon: float | None) -> str | None:
    """The regional district (as the province names it, "Regional District of Central Kootenay") whose
    legal boundary holds the point: pipeline/fetch_cgndb_places.BcDistricts, the polygons cached once
    under $FIREFINDER_RAW_ROOT/ca_units/. None without a point or the polygons."""
    global _DISTRICTS
    if lat is None or lon is None:
        return None
    if _DISTRICTS is None:
        try:
            import fetch_cgndb_places
            _DISTRICTS = fetch_cgndb_places.BcDistricts()
        except Exception:  # noqa: BLE001
            _DISTRICTS = False
    if not _DISTRICTS:
        return None
    short = _DISTRICTS.district_at(lat, lon)
    return _DISTRICTS.official.get(short) if short else None


def rec_records(path: pathlib.Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for f in data.get("features") or []:
        p = f.get("properties") or {}
        rec = p.get("FOREST_FILE_ID")
        if not rec or rec in NOT_LOOKOUTS:
            continue
        lon, lat = (f.get("geometry") or {}).get("coordinates") or (None, None)
        desc = plain(p.get("PROJECT_DESCRIPTION"))
        closure = plain(p.get("CLOSURE_DESCRIPTION"))
        events = []
        for rx, ev, note in ((BUILT_YEAR_RE, "built", "The site's description dates the present lookout building to this year."),
                             (REMOVED_YEAR_RE, "removed", "The site's description says the lookout was taken down this year.")):
            years = sorted({int(y) for y in rx.findall(desc)})
            if len(years) == 1 and not re.search(r"\b(?:about|around|circa|early|late)\s+" + str(years[0]), desc, re.I):
                events.append({"year": years[0], "event": ev, "note": note, "from": "bc_rec_sites",
                               "source_url": REC_PAGE.format(rec=rec)})
        access = []
        for i in (1, 2, 3):
            a, sub = p.get(f"ACCESS_DESC{i}"), p.get(f"SUB_ACCESS_DESC{i}")
            if a:
                a = a.split(" (")[0].lower()
                access.append(f"{a} ({sub.lower()})" if sub else a)
        club = (p.get("OPERATOR_CLIENT_NAME") or "").strip()
        agency = "Recreation Sites and Trails BC" + (f", with {rec_name(club.title())}" if club else "")
        note = f"A Recreation Sites and Trails BC site ({rec})."
        if access:
            note += " Access: " + "; ".join(access) + "."
        extra: dict = {"rec_site_id": rec, "maintenance": p.get("MAINTAIN_STD_DESC"),
                       "established": (p.get("PROJECT_ESTABLISHED_DATE") or "")[:10] or None}
        if closure:
            extra["access_level"] = "closed"
            extra["access_note"] = f"Recreation Sites and Trails BC lists the site as closed: “{closure[:220]}”"
        else:
            extra["access_level"] = "public"
            extra["access_note"] = note
        if "fee for overnight" in desc.lower():
            extra["overnight_fee"] = True
        name = rec_name(p.get("PROJECT_NAME") or "")
        m = re.match(r"^(.+?)\s*\((.+)\)$", name)      # "Owen Hill (Owen Lookout Cabin)"
        if m:
            name, extra["aliases"] = m.group(2), [m.group(1)]
        out.append({
            "key": f"bc_rec_sites:bc:{rec.lower()}", "url": REC_PAGE.format(rec=rec), "name": name,
            "country": "CA", "region": "BC", "county": district_at(lat, lon),
            "lat": round(float(lat), 6) if lat is not None else None, "lon": round(float(lon), 6) if lon is not None else None,
            "elevation_m": None, "type_raw": None, "kind": "unknown", "status_raw": None, "status": "unknown",
            "registers": [], "built": next((e["year"] for e in events if e["event"] == "built"), None),
            "agency": agency, "events": events, "photos": [],
            "links": [{"label": f"Recreation Sites and Trails BC: {name} ({rec})", "url": REC_PAGE.format(rec=rec), "kind": "agency"}],
            "rental": None, "extra": {k: v for k, v in extra.items() if v not in (None, "")},
        })
    return sorted(out, key=lambda r: r["key"])


# ---------------------------------------------------------------------------------------------
# TRIM symbols
# ---------------------------------------------------------------------------------------------

def centroid(geom: dict) -> tuple[float, float]:
    """Area centroid of a (multi)polygon's outer rings, (lat, lon)."""
    polys = geom["coordinates"] if geom.get("type") == "MultiPolygon" else [geom["coordinates"]]
    x0, y0 = polys[0][0][0]           # measured from the first vertex, so the products stay small
    a_sum = x_sum = y_sum = 0.0
    for poly in polys:
        ring = [(x - x0, y - y0) for x, y in poly[0]]
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
            c = x1 * y2 - x2 * y1
            a_sum += c
            x_sum += (x1 + x2) * c
            y_sum += (y1 + y2) * c
    if abs(a_sum) < 1e-15:
        xs = [x for poly in polys for x, _ in poly[0]]
        ys = [y for poly in polys for _, y in poly[0]]
        return sum(ys) / len(ys), sum(xs) / len(xs)
    return y0 + y_sum / (3 * a_sum), x0 + x_sum / (3 * a_sum)


def trim_symbols(path: pathlib.Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for f in data.get("features") or []:
        p = f.get("properties") or {}
        if p.get("FEATURE_TYPE") != "fireLookoutTower":
            continue
        lat, lon = centroid(f["geometry"])
        out.append({"objectid": int(p["OBJECTID"]), "lat": round(lat, 5), "lon": round(lon, 5), "fcode": p.get("FCODE")})
    out.sort(key=lambda s: s["objectid"])
    # The same symbol drawn twice (on two map sheets: 23100 and 31585 sit on one spot): one record, the
    # lower object id, the other kept in extra.same_symbol.
    kept: list[dict] = []
    for s in out:
        twin = next((k for k in kept if haversine_m(k["lat"], k["lon"], s["lat"], s["lon"]) <= 50), None)
        if twin is None:
            kept.append(s)
        else:
            twin.setdefault("same_symbol", []).append(s["objectid"])
    return kept


def load_extract(name: str) -> list[dict]:
    path = SOURCES / f"{name}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("records") or []


def positioned_bc(rec_sites: list[dict]) -> list[tuple[str, str, float, float]]:
    """(source, name, lat, lon) for every BC lookout record with a position, from the sources that
    place BC lookouts."""
    out = []
    for src in ("nhlr", "fflos", "firelookout_ca", "osm", "wikidata", "canada_lookouts_weebly"):
        for r in load_extract(src):
            if r.get("region") == "BC" and isinstance(r.get("lat"), (int, float)) and isinstance(r.get("lon"), (int, float)):
                out.append((src, r.get("name") or "(unnamed)", float(r["lat"]), float(r["lon"])))
    out += [("bc_rec_sites", r["name"], r["lat"], r["lon"]) for r in rec_sites if r["lat"] is not None]
    return out


def core_key(text: str | None) -> str | None:
    """A name without its feature and lookout words: "Sinkut Mountain" and "Sinkut" -> "sinkut",
    "Mount Lolo" -> "lolo". Numbered or directional names keep those words ("Mount Hunter (Lower)")."""
    toks = [t for t in merge._gnis_tokens(text or "") if t not in merge.GNIS_LOOKOUT_WORDS
            and t not in merge.GNIS_FEATURE_WORDS and t not in merge.GNIS_LEADING_WORDS]
    return "".join(toks) or None


def bc_summits() -> dict[str, list[tuple]]:
    """{core name key: [(cgndb id, name, generic, lat, lon)]} for BC's official high-ground names. The
    symbol itself is the second piece of evidence, so a lookout the source names "Sinkut" may claim the
    one "Sinkut Mountain" (the approximate-pin rule of the merge, with no such symbol, needs the
    same name)."""
    terms = fetch_peaks_cgndb.generic_terms(False)
    out: dict[str, list[tuple]] = {}
    for r in fetch_peaks_cgndb.province_rows("59", False):
        if r.get("concise.code") != "MTN" or r.get("status.code") != "official":
            continue
        generic = (terms.get(r.get("generic.code") or "") or "").strip()
        if generic.lower() not in merge.CGNDB_HIGH_GROUND:
            continue
        key = core_key(r.get("name"))
        try:
            lat, lon = float(r["latitude"]), float(r["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        if key:
            out.setdefault(key, []).append((r["id"], r["name"], generic, lat, lon))
    return out


def name_symbols(symbols: list[dict], rec_sites: list[dict], log=print) -> dict[int, dict]:
    """{objectid: {"name", "named_by"}}: the symbols a name-only BC lookout record can claim (see the
    module docstring)."""
    positioned = positioned_bc(rec_sites)
    summits = bc_summits()
    try:
        import fetch_cgndb_places
        districts = fetch_cgndb_places.BcDistricts()
    except Exception:  # noqa: BLE001  (no polygons: units are not checked, only whole-province uniqueness)
        districts = None
    claims: dict[int, list[dict]] = {}
    for src in ("canada_lookouts_weebly", "firelookout_ca"):
        for r in load_extract(src):
            if r.get("region") != "BC" or r.get("lat") is not None:
                continue
            aliases = (r.get("extra") or {}).get("aliases") or []
            names = [r.get("name")] + (aliases if isinstance(aliases, list) else [])
            keys = {k for n in names if (k := core_key(n))}
            feats = {f[0]: f for k in keys for f in summits.get(k, [])}
            unit = ca_units.bc_current_districts(r.get("county")) if r.get("county") else []
            if unit and districts is not None:
                feats = {i: f for i, f in feats.items() if districts.district_at(f[3], f[4]) in unit}
            if len(feats) != 1:
                continue
            fid, fname, generic, flat, flon = next(iter(feats.values()))
            near = [(haversine_m(flat, flon, s["lat"], s["lon"]), s) for s in symbols]
            near = sorted([x for x in near if x[0] <= NAME_RADIUS_M], key=lambda x: x[0])
            if len(near) != 1:
                continue
            d, sym = near[0]
            if any(haversine_m(sym["lat"], sym["lon"], la, lo) <= TAKEN_RADIUS_M for _, _, la, lo in positioned):
                continue
            claims.setdefault(sym["objectid"], []).append({
                "name": r["name"], "aliases": aliases if isinstance(aliases, list) else [],
                "named_by": {"source": src, "key": r["key"], "summit": {"cgndb_id": fid, "name": fname, "generic": generic},
                             "summit_to_symbol_m": round(d)}})
    out = {}
    for oid, cl in claims.items():
        names = {merge.loose_key(c["name"]) for c in cl}
        if len(names) == 1:
            out[oid] = cl[0]
            if len(cl) > 1:
                out[oid]["named_by"]["also"] = [c["named_by"]["key"] for c in cl[1:]]
        else:
            log(f"  symbol {oid}: claimed by several lookouts {[c['name'] for c in cl]}; left unnamed")
    return out


def trim_records(symbols: list[dict], names: dict[int, dict]) -> list[dict]:
    out = []
    for s in symbols:
        nm = names.get(s["objectid"])
        extra: dict = {"trim_objectid": s["objectid"], "fcode": s["fcode"]}
        if s.get("same_symbol"):
            extra["same_symbol"] = s["same_symbol"]
        if nm:
            extra["named_by"] = nm["named_by"]
            if nm["aliases"]:
                extra["aliases"] = nm["aliases"]
        else:
            extra["fallback_name"] = "Unnamed lookout (BC base map)"
        out.append({
            "key": f"bc_trim_lookouts:bc:{s['objectid']}", "url": TRIM_DATASET, "name": nm["name"] if nm else None,
            "country": "CA", "region": "BC", "county": district_at(s["lat"], s["lon"]), "lat": s["lat"], "lon": s["lon"], "elevation_m": None,
            "type_raw": None, "kind": "tower", "status_raw": None, "status": "unknown", "registers": [], "built": None,
            "agency": None, "events": [], "photos": [],
            "links": [{"label": f"BC base map (TRIM): fire lookout tower symbol {s['objectid']}", "url": TRIM_DATASET, "kind": "agency"}],
            "rental": None, "extra": extra,
        })
    return out


def sample(symbols: list[dict], rec_sites: list[dict], n: int = 10) -> list[tuple]:
    """For each symbol the nearest lookout another source places: [(distance, objectid, source, name)]."""
    positioned = positioned_bc(rec_sites)
    rows = []
    for s in symbols:
        best = min(((haversine_m(s["lat"], s["lon"], la, lo), src, nm) for src, nm, la, lo in positioned), default=None)
        if best:
            rows.append((round(best[0]), s["objectid"], best[1], best[2]))
    return sorted(rows)[:n] if n else sorted(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sample", action="store_true", help="print the sample check and exit")
    args = ap.parse_args(argv)
    rec_path, trim_path = cached("rec_site_points_lookout.json"), cached("trim_ebm_fireLookoutTower.json")
    recs = rec_records(rec_path)
    symbols = trim_symbols(trim_path)
    if args.sample:
        rows = sample(symbols, recs, 0)
        for d, oid, src, nm in rows:
            print(f"{d:>7} m  symbol {oid}  {src}: {nm}")
        within = sum(1 for d, *_ in rows if d <= 400)
        print(f"{within} of {len(symbols)} symbols lie within 400 m of a lookout another source places")
        return 0
    names = name_symbols(symbols, recs, lambda *a: print(*a, file=sys.stderr))
    trims = trim_records(symbols, names)
    when = datetime.date.fromtimestamp(rec_path.stat().st_mtime).isoformat()
    write_source_json(SOURCES / "bc_rec_sites.json", source="bc_rec_sites",
                      title="Recreation Sites and Trails BC: lookout recreation sites (BC Geographic Warehouse)",
                      url=REC_DATASET, retrieved=when,
                      license_="Open Government Licence - British Columbia", records=recs,
                      header_extra={"credit": "Contains information licensed under the Open Government Licence - British Columbia.",
                                    "download": REC_URL})
    write_source_json(SOURCES / "bc_trim_lookouts.json", source="bc_trim_lookouts",
                      title="BC base map (TRIM Enhanced Base Map): fire lookout tower symbols",
                      url=TRIM_DATASET, retrieved=datetime.date.fromtimestamp(trim_path.stat().st_mtime).isoformat(),
                      license_=("Licence not confirmed (the catalogue page is JavaScript only and its API is disallowed by "
                                "robots.txt; not in the federal open-data portal). Positions used as facts only, credited "
                                "and linked, like the registers'."),
                      records=trims,
                      header_extra={"credit": "Government of British Columbia, TRIM Enhanced Base Map (BC Geographic Warehouse)",
                                    "download": TRIM_URL})
    print(f"wrote {len(recs)} recreation sites and {len(trims)} base-map symbols ({len(names)} named: "
          f"{sorted(n['name'] for n in names.values())})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
