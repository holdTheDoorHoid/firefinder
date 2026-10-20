#!/usr/bin/env python3
"""Fetch named summits in Canada from the Canadian Geographical Names Database (CGNDB).

Writes data/sources/peaks_cgndb.json: one row per named summit, [cgndb_id, name, lat, lon,
region], the same shape as peaks_gnis.json (pipeline/fetch_peaks.py), so pipeline/build_peaks.py
cuts both into the panorama's 1-degree chunks. The panorama ("View from the cab") labels the
summits a lookout can see.

Source: Natural Resources Canada's GeoNames web service, the CGNDB's public query interface
(https://geogratis.gc.ca/services/geoname/en/geonames.csv?concise=MTN&province=<SGC>&num=1000&skip=<n>),
every name of concise class MTN ("Mountain": mountains, hills, peaks, ridges, ranges...) in each
province and territory, 1,000 rows a page. The bulk files on ftp.maps.canada.ca are not used:
that host's robots.txt disallows /pub. geogratis.gc.ca's robots.txt allows /services/. One
request every 2 s, our honest User-Agent, every page cached once under
$FIREFINDER_RAW_ROOT/cgndb/ (about 70 pages; --refresh fetches them again).

Kept: names whose generic term is a single summit (Mountain, Mount, Peak, Hill, Butte, Knoll,
Dome, Pinnacle, Summit, Cone, Tolt, Lookout...; SUMMIT_GENERICS below; the English service gives
French generics their English terms, so Quebec's "Mont" and "Colline" come through as Mount and
Hill). Left out:
ranges, ridges, highlands, plural groups ("Blue Mountains", "Mono Hills"), cliffs and slopes,
whose single point can be kilometres from any top. One name per feature: a feature with official
names in English and French (features of pan-Canadian significance) is labelled with its English
name; any other feature with its official name, in the language the province made official
(Quebec's are French).

Licence: Open Government Licence - Canada. Credit line (About page and the peaks index):
"Contains information licensed under the Open Government Licence - Canada". Not a list of
lookouts: merge.py and build_site_data.py skip it ("kind": "reference").

Python 3.12, standard library only.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "sources" / "peaks_cgndb.json"
RAW = Path(os.environ.get("FIREFINDER_RAW_ROOT") or "/home/hoid/Desktop/firefinder/data/raw") / "cgndb"
API = "https://geogratis.gc.ca/services/geoname/en/geonames.csv"
GENERIC_URL = "https://geogratis.gc.ca/services/geoname/en/codes/generic.json"
USER_AGENT = "FirefinderBot/0.1 (+https://github.com/holdTheDoorHoid/firefinder)"
PAGE = 1000
CREDIT = "Contains information licensed under the Open Government Licence – Canada"
LICENSE = "Open Government Licence – Canada (https://open.canada.ca/en/open-government-licence-canada)"

# Statistics Canada SGC codes the service uses for provinces and territories.
PROVINCE_SGC = {
    "10": "NL", "11": "PE", "12": "NS", "13": "NB", "24": "QC", "35": "ON", "46": "MB",
    "47": "SK", "48": "AB", "59": "BC", "60": "YT", "61": "NT", "62": "NU",
}

# Generic terms (the CGNDB's word for what kind of feature a name is) that name one summit. The
# service's code list gives each code an English term; French generics carry French terms.
SUMMIT_GENERICS = {
    "mountain", "mount", "peak", "hill", "butte", "knoll", "dome", "pinnacle", "summit", "spire",
    "crag", "cone", "hump", "tor", "tolt", "nunatak", "pingo", "tower", "lookout", "knob", "head", "monadnock",
    "mont", "montagne", "pic", "colline", "sommet", "dôme", "dome", "piton", "buse", "butte",
    "mamelon", "morne", "montagnette", "tête", "pain de sucre", "aiguille", "cap",
}
# "cap" in Quebec is often a headland on a hill, but also a cape on the shore: only kept when the
# CGNDB files it under concise MTN, which this fetch already requires.

_last = 0.0


def _get(url: str) -> bytes:
    global _last
    wait = _last + 2.0 - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read()
    finally:
        _last = time.monotonic()


def cached(path: Path, url: str, refresh: bool) -> bytes:
    if path.exists() and not refresh:
        return path.read_bytes()
    print(f"GET {url}", file=sys.stderr)
    body = _get(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(body)
    tmp.replace(path)
    return body


def generic_terms(refresh: bool) -> dict[str, str]:
    """{generic code: term} from the service's code list (cached)."""
    body = cached(RAW / "generic.json", GENERIC_URL, refresh)
    # The list carries raw control characters inside some descriptions.
    data = json.loads(body.decode("utf-8", "replace"), strict=False)
    defs = data.get("definitions", data) if isinstance(data, dict) else data
    return {str(d.get("code")): str(d.get("term") or "") for d in defs if isinstance(d, dict)}


def province_rows(sgc: str, refresh: bool) -> list[dict]:
    rows: list[dict] = []
    skip = 0
    while True:
        url = f"{API}?concise=MTN&province={sgc}&num={PAGE}&skip={skip}"
        body = cached(RAW / f"mtn_{sgc}_{skip:06d}.csv", url, refresh)
        page = list(csv.DictReader(io.StringIO(body.decode("utf-8-sig", "replace"))))
        rows.extend(page)
        if len(page) < PAGE:
            return rows
        skip += PAGE


def is_summit(term: str) -> bool:
    t = term.strip().lower()
    return t in SUMMIT_GENERICS


def pick_names(rows: list[dict], terms: dict[str, str]) -> list[list]:
    """[cgndb_id, name, lat, lon, region], one per feature, sorted by id."""
    by_feature: dict[str, list[dict]] = {}
    for r in rows:
        if (r.get("concise.code") or "") != "MTN":
            continue
        if not is_summit(terms.get(r.get("generic.code") or "", "")):
            continue
        if (r.get("status.code") or "") != "official":
            continue
        try:
            lat, lon = float(r["latitude"]), float(r["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (40 <= lat <= 84 and -142 <= lon <= -52):
            continue
        by_feature.setdefault(r.get("feature.id") or r["id"], []).append(r)
    out = []
    for fid, names in by_feature.items():
        names.sort(key=lambda r: (0 if r.get("language.code") == "eng" else 1, r["id"]))
        r = names[0]
        region = PROVINCE_SGC.get(r.get("province.code") or "")
        out.append([r["id"], r["name"].strip(), round(float(r["latitude"]), 5), round(float(r["longitude"]), 5), region])
    out.sort(key=lambda p: p[0])
    return out


def write(peaks: list[list], out: Path, retrieved: str) -> None:
    head = {
        "source": "cgndb_summits",
        "kind": "reference",
        "title": "Canadian Geographical Names Database (CGNDB): summits",
        "url": "https://natural-resources.canada.ca/earth-sciences/geography/geographical-names-board-canada/about-canadian-geographical-names-database",
        "download": f"{API}?concise=MTN&province=<SGC>",
        "retrieved": retrieved,
        "license": LICENSE,
        "credit": CREDIT,
        "note": "Not a list of lookouts. Named summits in Canada for labelling the panorama; see pipeline/fetch_peaks_cgndb.py.",
        "format": ["cgndb_id", "name", "lat", "lon", "region"],
        "count": len(peaks),
    }
    body = ",\n".join(json.dumps(p, ensure_ascii=False, separators=(",", ":")) for p in peaks)
    text = json.dumps(head, ensure_ascii=False, indent=1)[:-2] + ',\n "peaks": [\n' + body + "\n ]\n}\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true", help="fetch every page again")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    terms = generic_terms(args.refresh)
    rows: list[dict] = []
    for sgc in PROVINCE_SGC:
        rows.extend(province_rows(sgc, args.refresh))
    peaks = pick_names(rows, terms)
    newest = max(p.stat().st_mtime for p in RAW.glob("mtn_*.csv"))
    write(peaks, args.out, dt.date.fromtimestamp(newest).isoformat())
    from collections import Counter
    print(f"Read {len(rows)} MTN names; wrote {len(peaks)} summits to {args.out} "
          f"({args.out.stat().st_size / 1e6:.1f} MB): {dict(sorted(Counter(p[4] for p in peaks).items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
