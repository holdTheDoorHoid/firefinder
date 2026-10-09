#!/usr/bin/env python3
"""Extract the USGS GNIS names that the approximate lookout positions need.

About 2,000 source records name a lookout and its county but give no coordinates. merge.py
places one approximately when the USGS Geographic Names Information System (GNIS) has exactly one
same-name high-ground feature (summit, ridge, gap, pillar, cliff, bench) in that county, and lists
the rest on the "Lookouts we can't place yet" page, with a town of that name as a hint (DESIGN.md
3.5, "Approximate locations").

The full GNIS Domestic Names file is about 1 million names (a 46 MB zip). This keeps only what the
merge needs, so the extract can be committed and the merge runs without the download:

  keys       per state, every name key looked up: the names of every source record that has no
             usable position (merge.gnis_lookout_keys), so the merge can tell "GNIS has no such
             name" from "not looked up yet"
  counties   per state, every county GNIS knows (to recognise a record's county)
  features   per state, [gnis_id, name, class, county, lat, lon] for every high-ground feature
             (merge.GNIS_HIGH_GROUND) and populated place (merge.GNIS_TOWN) whose name matches
             one of the keys, in any county

Re-run it after adding or re-fetching a source whose records lack coordinates; merge.py reports
records whose names were never looked up ("not_looked_up") until then.

GNIS is a U.S. Government work in the public domain; credit "USGS Geographic Names Information
System (GNIS)". The download is cached under $FIREFINDER_RAW_ROOT/gnis/ (shared with
pipeline/fetch_peaks.py) and fetched once, politely; --refresh fetches it again.

Usage:
    python3 pipeline/fetch_gnis_places.py            # write data/sources/gnis_places.json

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
import zipfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fetch_peaks  # noqa: E402  (download URL, user agent and state names)
import merge  # noqa: E402

REPO = HERE.parent
SOURCES = REPO / "data" / "sources"
OUT = SOURCES / merge.GNIS_FILE
RAW = Path(os.environ.get("FIREFINDER_RAW_ROOT") or "/home/hoid/Desktop/firefinder/data/raw") / "gnis"
CLASSES = merge.GNIS_HIGH_GROUND | merge.GNIS_TOWN


def wanted_keys(sources_dir: Path) -> dict[str, set[str]]:
    """{state: name keys} for every source record without a usable position."""
    with contextlib.redirect_stdout(io.StringIO()):
        _, records = merge.load_sources(sources_dir, log=lambda *a, **k: None)
    out: dict[str, set[str]] = defaultdict(set)
    for recs in records.values():
        for r in recs:
            if r.has_coords or not r.region:
                continue
            out[r.region].update(merge.gnis_keys_for(r))
    return out


def read_gnis(rows, wanted: dict[str, set[str]]) -> tuple[dict[str, list[list]], dict[str, set[str]]]:
    """The features to keep, by state, and every county name, by state, from GNIS rows (dicts with
    the Domestic Names columns)."""
    features: dict[str, dict[int, list]] = defaultdict(dict)
    counties: dict[str, set[str]] = defaultdict(set)
    for rec in rows:
        st = fetch_peaks.STATES.get((rec.get("state_name") or "").strip())
        county = (rec.get("county_name") or "").strip()
        if not st:
            continue
        if county:
            counties[st].add(county)
        if rec.get("feature_class") not in CLASSES or not county:
            continue
        key = merge.gnis_feature_key(rec.get("feature_name") or "")
        if not key or key not in wanted.get(st, ()):
            continue
        try:
            fid = int(rec["feature_id"])
            lat, lon = float(rec.get("prim_lat_dec") or 0), float(rec.get("prim_long_dec") or 0)
        except (KeyError, TypeError, ValueError):
            continue
        if lat == 0 and lon == 0:
            continue
        features[st][fid] = [fid, rec["feature_name"].strip(), rec["feature_class"], county, round(lat, 5), round(lon, 5)]
    return {st: [rows_[k] for k in sorted(rows_)] for st, rows_ in features.items()}, counties


def zip_rows(zpath: Path):
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            if not info.filename.lower().endswith(".txt"):
                continue
            with z.open(info) as raw:
                yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""), delimiter="|")


def write(out: Path, wanted: dict[str, set[str]], features: dict[str, list[list]], counties: dict[str, set[str]], retrieved: str) -> int:
    head = {
        "source": "gnis_places",
        "kind": "reference",
        "title": "USGS Geographic Names Information System (GNIS): lookout names",
        "url": "https://www.usgs.gov/tools/geographic-names-information-system-gnis",
        "download": fetch_peaks.URL,
        "retrieved": retrieved,
        "license": "Public domain (U.S. Government work)",
        "credit": "USGS Geographic Names Information System (GNIS)",
        "note": ("Not a list of lookouts. The GNIS high-ground features and populated places whose names match a lookout "
                 "record without coordinates, for approximate positions; see pipeline/fetch_gnis_places.py."),
        "classes": {"high_ground": sorted(merge.GNIS_HIGH_GROUND), "town": sorted(merge.GNIS_TOWN)},
        "format": {"features": ["gnis_id", "name", "class", "county", "lat", "lon"]},
        "count": sum(len(v) for v in features.values()),
    }
    lines = [json.dumps(head, ensure_ascii=False, indent=1)[:-2] + ","]
    lines.append(' "keys": ' + json.dumps({st: sorted(k) for st, k in sorted(wanted.items())}, ensure_ascii=False, separators=(",", ":")) + ",")
    lines.append(' "counties": ' + json.dumps({st: sorted(c) for st, c in sorted(counties.items())}, ensure_ascii=False, separators=(",", ":")) + ",")
    # One feature per line keeps diffs readable when GNIS or the lookout records change.
    body = []
    for st in sorted(features):
        rows = ",\n".join("   " + json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in features[st])
        body.append(f'  "{st}": [\n{rows}\n  ]')
    lines.append(' "features": {\n' + ",\n".join(body) + "\n }\n}\n")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return head["count"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true", help="download the GNIS file again")
    ap.add_argument("--zip", type=Path, default=RAW / "DomesticNames_AllStates_Text.zip")
    ap.add_argument("--sources", type=Path, default=SOURCES)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    wanted = wanted_keys(args.sources)
    zpath = fetch_peaks.download(args.zip, args.refresh)
    features, counties = read_gnis(zip_rows(zpath), wanted)
    retrieved = dt.date.fromtimestamp(zpath.stat().st_mtime).isoformat()
    n = write(args.out, wanted, features, counties, retrieved)
    print(f"Looked up {sum(len(v) for v in wanted.values())} names in {len(wanted)} states; "
          f"wrote {n} GNIS features to {args.out} ({args.out.stat().st_size / 1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
