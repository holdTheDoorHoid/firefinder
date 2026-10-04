#!/usr/bin/env python3
"""Fetch named summits from the USGS Geographic Names Information System (GNIS).

Writes data/sources/peaks_gnis.json: every feature of class "Summit" in the GNIS Domestic
Names national file that has coordinates, as [gnis_id, name, lat, lon, state] rows. The
panorama ("View from the cab") labels the ones a lookout can actually see;
pipeline/build_peaks.py cuts this file into 1-degree chunks for the website.

GNIS is the federal standard for US geographic names. It is a U.S. Government work in the
public domain; we credit "USGS Geographic Names Information System (GNIS)". The 2021-onwards
Domestic Names files carry no elevations, so heights shown on the site come from the terrain
tiles and are labelled as approximate.

Names flagged "(historical)" are left out: GNIS uses that for features that no longer exist
or names no longer in use.

The download (~46 MB zip) is cached under data/raw/gnis/ and reused; pass --refresh to fetch
it again. This file is not a list of lookouts: merge.py and build_site_data.py skip it.

Python 3.12, standard library only.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "sources" / "peaks_gnis.json"
RAW = Path("/home/hoid/Desktop/firefinder/data/raw/gnis")
URL = "https://prd-tnm.s3.amazonaws.com/StagedProducts/GeographicNames/DomesticNames/DomesticNames_AllStates_Text.zip"
USER_AGENT = "FirefinderBot/0.1 (+https://github.com/holdTheDoorHoid/firefinder)"

STATES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
    "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA",
    "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
    "Puerto Rico": "PR", "Guam": "GU", "Virgin Islands": "VI", "American Samoa": "AS",
    "Northern Mariana Islands": "MP",
}


def download(path: Path, refresh: bool) -> Path:
    if path.exists() and not refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {URL} ...", file=sys.stderr)
    req = urllib.request.Request(URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=300) as r, open(path.with_suffix(".part"), "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    path.with_suffix(".part").replace(path)
    return path


def summits_from_zip(zpath: Path) -> list[list]:
    """[gnis_id, name, lat, lon, state] for every usable Summit, sorted by GNIS id."""
    rows: dict[int, list] = {}
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            if not info.filename.lower().endswith(".txt"):
                continue
            with z.open(info) as raw:
                text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
                rows.update((r[0], r) for r in parse_rows(text))
    return [rows[k] for k in sorted(rows)]


def parse_rows(lines) -> list[list]:
    out = []
    for rec in csv.DictReader(lines, delimiter="|"):
        if rec.get("feature_class") != "Summit":
            continue
        name = (rec.get("feature_name") or "").strip()
        if not name or "(historical)" in name.lower():
            continue
        try:
            lat = float(rec.get("prim_lat_dec") or 0)
            lon = float(rec.get("prim_long_dec") or 0)
            fid = int(rec["feature_id"])
        except (TypeError, ValueError, KeyError):
            continue
        if lat == 0 and lon == 0:
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        state = STATES.get((rec.get("state_name") or "").strip(), (rec.get("state_name") or "").strip()[:2].upper() or None)
        out.append([fid, name, round(lat, 5), round(lon, 5), state])
    return out


def write(peaks: list[list], out: Path, retrieved: str) -> None:
    head = {
        "source": "gnis_summits",
        "kind": "reference",
        "title": "USGS Geographic Names Information System (GNIS): summits",
        "url": "https://www.usgs.gov/tools/geographic-names-information-system-gnis",
        "download": URL,
        "retrieved": retrieved,
        "license": "Public domain (U.S. Government work)",
        "credit": "USGS Geographic Names Information System (GNIS)",
        "note": "Not a list of lookouts. Named summits for labelling the panorama; see pipeline/fetch_peaks.py.",
        "format": ["gnis_id", "name", "lat", "lon", "state"],
        "count": len(peaks),
    }
    # One peak per line keeps diffs readable when GNIS changes.
    body = ",\n".join(json.dumps(p, ensure_ascii=False, separators=(",", ":")) for p in peaks)
    text = json.dumps(head, ensure_ascii=False, indent=1)[:-2] + ',\n "peaks": [\n' + body + "\n ]\n}\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true", help="download the GNIS file again")
    ap.add_argument("--zip", type=Path, default=RAW / "DomesticNames_AllStates_Text.zip")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    zpath = download(args.zip, args.refresh)
    peaks = summits_from_zip(zpath)
    retrieved = dt.date.fromtimestamp(zpath.stat().st_mtime).isoformat()
    write(peaks, args.out, retrieved)
    print(f"Wrote {len(peaks)} summits to {args.out} ({args.out.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
