#!/usr/bin/env python3
"""Write a synthetic set of tower records for load-testing the site (not real data).

    python3 pipeline/make_synthetic_towers.py --count 9000 --out /tmp/synthetic-towers
    python3 pipeline/build_site_data.py --towers /tmp/synthetic-towers --out web/public/data

Records are copies of the fixtures with made-up names and ids, scattered over the lower 48
states with roughly the real mix (about a quarter standing). Every record is marked
"fixture": true, so the site shows its "Sample data" banner. Standard library only.
"""

from __future__ import annotations

import argparse
import copy
import json
import random
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "web" / "fixtures" / "towers"

# Rough bounding boxes (lon_min, lat_min, lon_max, lat_max) and weights: lookouts cluster in the West.
STATES = {
    "WA": ((-124.5, 45.6, -117.0, 49.0), 9), "OR": ((-124.4, 42.0, -116.5, 46.2), 9),
    "ID": ((-117.2, 42.0, -111.1, 49.0), 8), "MT": ((-116.0, 44.4, -104.1, 49.0), 7),
    "CA": ((-124.2, 32.6, -114.2, 42.0), 9), "AZ": ((-114.8, 31.4, -109.1, 37.0), 4),
    "NM": ((-109.0, 31.4, -103.1, 37.0), 3), "CO": ((-109.0, 37.0, -102.1, 41.0), 3),
    "WY": ((-111.0, 41.0, -104.1, 45.0), 2), "UT": ((-114.0, 37.0, -109.1, 42.0), 2),
    "PA": ((-80.5, 39.8, -74.8, 42.2), 4), "NY": ((-79.7, 40.6, -73.3, 45.0), 3),
    "NC": ((-84.3, 34.0, -75.5, 36.6), 3), "GA": ((-85.6, 30.4, -81.0, 35.0), 3),
    "MN": ((-97.2, 43.5, -89.5, 49.0), 3), "WI": ((-92.9, 42.5, -86.8, 47.1), 3),
    "MI": ((-90.4, 41.7, -82.4, 48.2), 3), "ME": ((-71.1, 43.1, -66.9, 47.4), 2),
    "AL": ((-88.5, 30.2, -84.9, 35.0), 3), "TX": ((-106.6, 25.8, -93.5, 36.5), 2),
    "MO": ((-95.8, 36.0, -89.1, 40.6), 2), "VA": ((-83.7, 36.5, -75.2, 39.5), 2),
}
FIRST = ["Bald", "Baldy", "Sugarloaf", "Granite", "Pine", "Cedar", "Eagle", "Bear", "Elk", "Signal",
         "Table", "Buck", "Red", "Black", "Grouse", "Hogback", "Indian", "Lone", "Twin", "Thunder",
         "Spruce", "Hemlock", "Wolf", "Deer", "Coyote", "Badger", "Antelope", "Juniper", "Aspen", "Copper"]
SECOND = ["Mountain", "Peak", "Butte", "Point", "Ridge", "Knob", "Hill", "Dome", "Top", "Rock"]
STATUS = ["standing"] * 26 + ["gone"] * 64 + ["ruins"] * 4 + ["relocated"] * 2 + ["replica"] * 1 + ["unknown"] * 3


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--count", type=int, default=9000)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    templates = [json.loads(p.read_text()) for p in sorted(FIXTURES.rglob("*.json"))]
    templates = [t for t in templates if not t.get("hidden")]
    states, weights = zip(*[(s, w) for s, (_, w) in STATES.items()])
    for n in range(args.count):
        rec = copy.deepcopy(rng.choice(templates))
        st = rng.choices(states, weights)[0]
        (x0, y0, x1, y1), _ = STATES[st]
        name = f"{rng.choice(FIRST)} {rng.choice(SECOND)}"
        rec.update(
            id=f"us-{st.lower()}-synthetic-{n}",
            name=f"{name} Lookout",
            region=st,
            status=rng.choice(STATUS),
            fixture=True,
            other_names=[],
            conflicts=[],
        )
        rec["location"] = {"lat": round(rng.uniform(y0, y1), 5), "lon": round(rng.uniform(x0, x1), 5), "precision": "approximate", "from": "ffla"}
        if rec["status"] not in ("standing",):
            rec["rental"] = None
        folder = args.out / st.lower()
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{rec['id']}.json").write_text(json.dumps(rec), encoding="utf-8")
    print(f"Wrote {args.count} synthetic towers to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
