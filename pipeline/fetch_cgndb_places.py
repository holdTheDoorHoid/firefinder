#!/usr/bin/env python3
"""Extract the Canadian Geographical Names Database (CGNDB) names that approximate lookout positions
in Canada need: the second gazetteer of DESIGN.md 3.5, "Approximate locations" (2026-10-20).

The owner's rule for the US (2026-10-08), applied to Canada the same way: a lookout a source names with
its local unit but no position is shown, with a dashed marker and an "Approximate location" note, on
the one same-name high-ground feature the gazetteer has in that unit. Canada's local units: a BC
regional district, an Ontario district or county, a New Brunswick, Nova Scotia or Prince Edward Island
county, a Quebec regional county municipality (MRC). Where the source gives no local unit (most
Canadian lookout lists file a lookout under a forest, an association or a fire district instead), the
feature must be the only one of its name in the whole province or territory, and the page says so.

Where the unit of a feature comes from:
  NB, NS, PE, ON  the CGNDB's own `location` field, which for these provinces is the county or
                  district ("Northumberland", "Renfrew", "Thunder Bay"; "Kings; Westmorland" for a
                  feature on a county line: both)
  QC              the same field's second part, the MRC ("Saint-Donat; Matawinie" -> Matawinie)
  BC              the regional district whose polygon holds the feature (the CGNDB writes BC's old
                  land districts there instead): the province's ABMS_REGIONAL_DISTRICTS_SP layer
                  (Regional Districts - Legally Defined Administrative Areas of BC, openmaps.gov.bc.ca
                  WFS, Open Government Licence - British Columbia), downloaded once and cached under
                  $FIREFINDER_RAW_ROOT/ca_units/bc_regional_districts.json
  AB, SK, MB, NL, YT, NT, NU
                  none: the field holds land survey references or electoral districts, not the units
                  sources name. A lookout there is placed only by the whole-province rule; a lookout a
                  source files under a unit there is not placed (its unit cannot be checked).
Statistics Canada's census-division boundary files would cover every province, but their host
answers our crawler with a Cloudflare challenge (2026-10-20); not worked around.

High ground (the CGNDB's generic terms, as its English service writes them; the French generic each
stands for in Quebec in brackets): single summits -- Mount [mont], Mountain [montagne], Hill [colline,
morne], Peak [pic], Butte [butte], Summit [sommet], Dome [dôme], Cone, Knob, Knoll [mamelon], Pinnacle
[piton], Spire [aiguille], Tower, Tolt, Head [tête], Hump, Tor, Crag, Nunatak, Monadnock, and the
lookout words Lookout, Lookoff and Viewpoint; ridges -- Ridge [crête], Spur, Shoulder; cliffs -- Bluff,
Cliff [falaise], Rock [rocher], Ledge. Left out: ranges and groups (Range, Mountains, Hills, Peaks,
Highlands...), long or low landforms (Esker, Dune, Moraine, Drumlins, Slope, Bank), and Cape [cap], a
point of land into water. Only official names; a feature with names in two languages is one feature.

Only concise class MTN ("Mountain") is read, from the pages pipeline/fetch_peaks_cgndb.py already
cached ($FIREFINDER_RAW_ROOT/cgndb/mtn_<SGC>_<skip>.csv, NRCan's GeoNames service). The extract keeps
only what the merge needs:
  keys      per province, every name key looked up (merge.gnis_lookout_keys of every Canadian record
            with no usable position)
  units     per province, the units the gazetteer can place in (to tell a misspelt unit from one
            with no hill of the name)
  features  per province, [cgndb_id, name, generic, [units], lat, lon] for every high-ground
            feature whose name matches a key

Licence: Open Government Licence - Canada; credit "Contains information licensed under the Open
Government Licence - Canada". BC's regional districts: Open Government Licence - British Columbia.

Usage:  python3 pipeline/fetch_cgndb_places.py      (writes data/sources/cgndb_places.json)
Re-run it after adding or re-fetching a Canadian source whose records lack coordinates.

Python 3.12, standard library only.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import datetime as dt
import io
import json
import os
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ca_units  # noqa: E402
import fetch_peaks_cgndb  # noqa: E402  (the cached MTN pages and the generic-term list)
import merge  # noqa: E402

REPO = HERE.parent
SOURCES = REPO / "data" / "sources"
OUT = SOURCES / "cgndb_places.json"
RAW_ROOT = Path(os.environ.get("FIREFINDER_RAW_ROOT") or "/home/hoid/Desktop/firefinder/data/raw")
BC_DISTRICTS_FILE = RAW_ROOT / "ca_units" / "bc_regional_districts.json"
BC_DISTRICTS_URL = ("https://openmaps.gov.bc.ca/geo/pub/ows?service=WFS&version=2.0.0&request=GetFeature"
                    "&typeName=pub:WHSE_LEGAL_ADMIN_BOUNDARIES.ABMS_REGIONAL_DISTRICTS_SP"
                    "&outputFormat=application/json&srsName=EPSG:4326")
USER_AGENT = "FirefinderBot/0.1 (+https://github.com/holdTheDoorHoid/firefinder)"

# The CGNDB's generic terms (English service) that are high ground a lookout could stand on, and the
# plain word a page uses for each ("the one hill of that name"). merge.CGNDB_HIGH_GROUND reads this.
HIGH_GROUND = merge.CGNDB_HIGH_GROUND
# Provinces whose features carry a usable unit, and how.
LOCATION_UNIT_PROVINCES = {"NB", "NS", "PE", "ON"}


def wanted_keys(sources_dir: Path) -> dict[str, set[str]]:
    """{province: name keys} for every Canadian source record without a usable position."""
    with contextlib.redirect_stdout(io.StringIO()):
        _, records = merge.load_sources(sources_dir, log=lambda *a, **k: None)
    out: dict[str, set[str]] = defaultdict(set)
    for recs in records.values():
        for r in recs:
            if r.has_coords or not r.region or r.country != "CA":
                continue
            out[r.region].update(merge.gnis_keys_for(r))
    return out


class BcDistricts:
    """Point in BC regional district (the province's legal boundaries, cached once)."""

    def __init__(self, path: Path = BC_DISTRICTS_FILE) -> None:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(BC_DISTRICTS_URL, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=300) as r:
                body = r.read()
            tmp = path.with_suffix(".part")
            tmp.write_bytes(body)
            tmp.replace(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.items = []
        self.official: dict[str, str] = {}      # short name -> the name the province writes
        for f in data.get("features") or []:
            name = (f.get("properties") or {}).get("ADMIN_AREA_NAME") or ""
            short = next(iter(ca_units.bc_current_districts(name.replace("(Unincorporated)", ""))), None)
            if short:
                self.official[short] = name.strip()
            g = f.get("geometry") or {}
            polys = g.get("coordinates") if g.get("type") == "MultiPolygon" else [g.get("coordinates")]
            boxes = []
            for poly in polys or []:
                xs = [x for ring in poly for x, _ in ring]
                ys = [y for ring in poly for _, y in ring]
                boxes.append((min(xs), min(ys), max(xs), max(ys)))
            if short:
                self.items.append((short, polys, boxes))
        self.retrieved = dt.date.fromtimestamp(path.stat().st_mtime).isoformat()

    def district_at(self, lat: float, lon: float) -> str | None:
        from regions import Admin1Lookup
        for name, polys, boxes in self.items:
            for poly, (x0, y0, x1, y1) in zip(polys, boxes):
                if x0 <= lon <= x1 and y0 <= lat <= y1 and Admin1Lookup._inside(lon, lat, poly):
                    return name
        return None

    def names(self) -> list[str]:
        return sorted({n for n, _, _ in self.items})


def feature_units(region: str, row: dict, bc: BcDistricts | None, lat: float, lon: float) -> list[str]:
    loc = (row.get("location") or "").strip()
    if region in LOCATION_UNIT_PROVINCES:
        return [p.strip() for p in loc.split(";") if p.strip()]
    if region == "QC":
        parts = [p.strip() for p in loc.split(";") if p.strip()]
        return parts[-1:] if len(parts) >= 2 else []
    if region == "BC" and bc is not None:
        d = bc.district_at(lat, lon)
        return [d] if d else []
    return []


def read_features(rows: list[dict], terms: dict[str, str], wanted: dict[str, set[str]],
                  bc: BcDistricts | None) -> tuple[dict[str, list[list]], dict[str, set[str]]]:
    """The high-ground features to keep, by province, and every unit seen, by province."""
    by_feature: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if (r.get("concise.code") or "") != "MTN" or (r.get("status.code") or "") != "official":
            continue
        generic = (terms.get(r.get("generic.code") or "") or "").strip()
        if generic.lower() not in HIGH_GROUND:
            continue
        by_feature[r.get("feature.id") or r["id"]].append(r)
    features: dict[str, dict[str, list]] = defaultdict(dict)
    units: dict[str, set[str]] = defaultdict(set)
    for fid, names in by_feature.items():
        for r in names:
            region = fetch_peaks_cgndb.PROVINCE_SGC.get(r.get("province.code") or "")
            if not region:
                continue
            key = merge.gnis_feature_key(r.get("name") or "")
            if not key or key not in wanted.get(region, ()):
                continue
            try:
                lat, lon = float(r["latitude"]), float(r["longitude"])
            except (KeyError, TypeError, ValueError):
                continue
            us = feature_units(region, r, bc, lat, lon)
            generic = terms.get(r.get("generic.code") or "", "").strip()
            features[region][r["id"]] = [r["id"], r["name"].strip(), generic, us, round(lat, 5), round(lon, 5)]
    # every unit the gazetteer can place in, from all features (not only the kept ones)
    for r in rows:
        region = fetch_peaks_cgndb.PROVINCE_SGC.get(r.get("province.code") or "")
        if region in LOCATION_UNIT_PROVINCES or region == "QC":
            try:
                lat, lon = float(r["latitude"]), float(r["longitude"])
            except (KeyError, TypeError, ValueError):
                continue
            units[region].update(feature_units(region, r, None, lat, lon))
    if bc is not None:
        units["BC"].update(bc.names())
    return {reg: [rows_[k] for k in sorted(rows_)] for reg, rows_ in features.items()}, units


def write(out: Path, wanted, features, units, retrieved: str, bc_retrieved: str | None) -> int:
    head = {
        "source": "cgndb_places",
        "kind": "reference",
        "title": "Canadian Geographical Names Database (CGNDB): lookout names",
        "url": "https://natural-resources.canada.ca/earth-sciences/geography/geographical-names-board-canada/about-canadian-geographical-names-database",
        "download": "https://geogratis.gc.ca/services/geoname/en/geonames.csv?concise=MTN&province=<SGC>",
        "retrieved": retrieved,
        "license": "Open Government Licence - Canada; BC regional districts: Open Government Licence - British Columbia",
        "credit": "Contains information licensed under the Open Government Licence - Canada",
        "units_from": {
            "NB, NS, PE, ON": "the CGNDB location field (county or district)",
            "QC": "the CGNDB location field's MRC",
            "BC": f"regional district polygons, openmaps.gov.bc.ca ABMS_REGIONAL_DISTRICTS_SP ({bc_retrieved})",
            "others": "none: placed only when the name is unique in the whole province or territory",
        },
        "note": ("Not a list of lookouts. The CGNDB high-ground features whose names match a Canadian lookout record "
                 "without coordinates, for approximate positions; see pipeline/fetch_cgndb_places.py."),
        "generics": sorted(HIGH_GROUND),
        "format": {"features": ["cgndb_id", "name", "generic", "units", "lat", "lon"]},
        "count": sum(len(v) for v in features.values()),
    }
    lines = [json.dumps(head, ensure_ascii=False, indent=1)[:-2] + ","]
    lines.append(' "keys": ' + json.dumps({k: sorted(v) for k, v in sorted(wanted.items())}, ensure_ascii=False, separators=(",", ":")) + ",")
    lines.append(' "units": ' + json.dumps({k: sorted(v) for k, v in sorted(units.items())}, ensure_ascii=False, separators=(",", ":")) + ",")
    body = []
    for reg in sorted(features):
        rows = ",\n".join("   " + json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in features[reg])
        body.append(f'  "{reg}": [\n{rows}\n  ]')
    lines.append(' "features": {\n' + ",\n".join(body) + "\n }\n}\n")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return head["count"]


def load_rows() -> tuple[list[dict], dict[str, str], str]:
    """Every cached MTN row (no network: pipeline/fetch_peaks_cgndb.py fills the cache)."""
    terms = fetch_peaks_cgndb.generic_terms(False)
    rows: list[dict] = []
    for sgc in fetch_peaks_cgndb.PROVINCE_SGC:
        rows.extend(fetch_peaks_cgndb.province_rows(sgc, False))
    newest = max(p.stat().st_mtime for p in fetch_peaks_cgndb.RAW.glob("mtn_*.csv"))
    return rows, terms, dt.date.fromtimestamp(newest).isoformat()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sources", type=Path, default=SOURCES)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    wanted = wanted_keys(args.sources)
    rows, terms, retrieved = load_rows()
    bc = BcDistricts()
    features, units = read_features(rows, terms, wanted, bc)
    n = write(args.out, wanted, features, units, retrieved, bc.retrieved)
    print(f"Looked up {sum(len(v) for v in wanted.values())} names in {len(wanted)} provinces and territories; "
          f"wrote {n} CGNDB features to {args.out}: {dict(sorted((k, len(v)) for k, v in features.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
