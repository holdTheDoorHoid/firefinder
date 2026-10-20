#!/usr/bin/env python3
"""Cut the summit gazetteers into small spatial chunks for the website.

Reads data/sources/peaks_gnis.json (USGS GNIS, pipeline/fetch_peaks.py: the US with Alaska and
Hawaii) and data/sources/peaks_cgndb.json (Canada's CGNDB, pipeline/fetch_peaks_cgndb.py, since
2026-10-20) and writes web/public/data/peaks/:

  index.json         {"cells": ["43_-123", ...], "count": N, "sources": [{title, credit, ...}], ...}
  <lat>_<lon>.json   the summits in the 1-degree cell whose south-west corner is (lat, lon),
                     as [[name, lat, lon, id], ...] with 4-decimal coordinates (~11 m); the id is a
                     GNIS feature id (a number) or a CGNDB name id (a string such as "FEGTX")

The panorama loads only the cells within its range (about 20 for 150 km). Run it after
pipeline/build_site_data.py, which owns web/public/data and would refuse a folder it did not
make; this script only replaces the peaks/ subfolder.

Python 3.12, standard library only.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "data" / "sources" / "peaks_gnis.json"
SRC_CA = REPO / "data" / "sources" / "peaks_cgndb.json"
OUT = REPO / "web" / "public" / "data" / "peaks"


def cell_of(lat: float, lon: float) -> str:
    return f"{math.floor(lat)}_{math.floor(lon)}"


def chunk(peaks: list[list]) -> dict[str, list[list]]:
    cells: dict[str, list[list]] = defaultdict(list)
    for fid, name, lat, lon, _state in peaks:
        cells[cell_of(lat, lon)].append([name, round(lat, 4), round(lon, 4), fid])
    for rows in cells.values():
        rows.sort(key=lambda r: (r[1], r[2], r[3]))
    return dict(cells)


def build(src: Path = SRC, out: Path = OUT, extra: list[Path] | None = None) -> dict:
    data = json.loads(src.read_text(encoding="utf-8"))
    peaks = list(data["peaks"])
    heads = [data]
    if extra is None:
        # the default build reads both gazetteers; a build from another file reads that file only
        extra = [SRC_CA] if src == SRC else []
    for path in extra:
        if path.exists():
            more = json.loads(path.read_text(encoding="utf-8"))
            peaks += more["peaks"]
            heads.append(more)
    cells = chunk(peaks)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for key, rows in cells.items():
        (out / f"{key}.json").write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    index = {
        "cells": sorted(cells),
        "count": len(peaks),
        "format": ["name", "lat", "lon", "gnis_id"],
        "title": data.get("title"),
        "credit": data.get("credit"),
        "license": data.get("license"),
        "retrieved": data.get("retrieved"),
        "sources": [{k: h.get(k) for k in ("source", "title", "credit", "license", "retrieved", "count")} for h in heads],
    }
    (out / "index.json").write_text(json.dumps(index, separators=(",", ":")), encoding="utf-8")
    return index


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", type=Path, default=SRC)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    if not args.src.exists():
        print(f"{args.src} is missing; run pipeline/fetch_peaks.py first. The panorama will show no peak names.")
        return 1
    index = build(args.src, args.out)
    size = sum(p.stat().st_size for p in args.out.iterdir())
    print(f"Wrote {index['count']} summits in {len(index['cells'])} chunks to {args.out} ({size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
