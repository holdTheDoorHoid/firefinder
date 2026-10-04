#!/usr/bin/env python3
"""Fetch fire lookout structures from OpenStreetMap via the Overpass API.

Writes data/sources/osm.json (DESIGN.md Â§3.2).

Query (DESIGN.md Â§2): across the US (the "United States of America" admin_level=2
area in OSM, which includes Alaska, Hawaii and the inhabited territories as
members of the same relation) --
  - emergency=fire_lookout (nodes + ways)
  - building=fire_lookout (nodes + ways)
  - man_made=tower + tower:type=observation, name matching lookout/fire tower
    (filtered server-side with a case-insensitive regex, so we don't pull
    every observation tower in the country just to throw most of them away)

This is ONE combined Overpass query (not three), specifically to be gentle
with a shared public server: one request gets every element we need, with
"out center" so ways come back with a usable point (their centroid) without
a second request for geometry.

Status hints: OSM has no single "is this gone" tag, so we read the lifecycle
tags that actually show up on fire lookouts in practice (checked against the
2026-10-04 pull): `ruins=*` or `abandoned(:*)=*` -> "ruins"; `demolished=*` or
`building=collapsed` -> "gone". `disused:emergency=fire_lookout` and
`was:emergency=fire_lookout` are extremely common on well-known STANDING
lookouts (Mount Pilchuck, Three Fingers, Winchester Mountain, Slate Peak...)
-- they mean the fire-watching *role* ended, not that the structure is gone,
so they do NOT downgrade status on their own; they're recorded in
extra.osm_tags for anyone who wants that nuance.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _common as c

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
CACHE_PATH = c.raw_dir("osm") / "overpass_result.json"

REPO_ROOT = Path(__file__).parent.parent
OUT_PATH = REPO_ROOT / "data" / "sources" / "osm.json"

QUERY = """
[out:json][timeout:180];
area["ISO3166-1"="US"][admin_level=2]->.us;
(
  node["emergency"="fire_lookout"](area.us);
  way["emergency"="fire_lookout"](area.us);
  node["building"="fire_lookout"](area.us);
  way["building"="fire_lookout"](area.us);
  node["man_made"="tower"]["tower:type"="observation"]["name"~"lookout|fire.?tower",i](area.us);
  way["man_made"="tower"]["tower:type"="observation"]["name"~"lookout|fire.?tower",i](area.us);
);
out center tags;
""".strip()

GONE_KEYS = {"demolished", "destroyed:building", "building:destroyed"}
RUINS_PREFIXES = ("abandoned:",)
RUINS_KEYS = {"abandoned", "ruins"}


def ensure_result() -> dict:
    if not CACHE_PATH.exists():
        print(f"Querying Overpass API ({OVERPASS_URL})...", file=sys.stderr)
        body = QUERY.encode()
        raw = c.http_get(OVERPASS_URL, data=body, timeout=200,
                          headers={"Content-Type": "text/plain"})
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_bytes(raw)
    return json.loads(CACHE_PATH.read_text())


def infer_status(tags: dict) -> tuple[str, str | None]:
    hints = []
    for k, v in tags.items():
        if k in GONE_KEYS or k in RUINS_KEYS or k.startswith(RUINS_PREFIXES):
            hints.append(f"{k}={v}")
        elif k.startswith("disused:") or k.startswith("was:"):
            hints.append(f"{k}={v}")
    raw = "; ".join(sorted(hints)) if hints else None

    if "demolished" in tags or tags.get("building") == "collapsed" or \
       "destroyed:building" in tags or "building:destroyed" in tags:
        return "gone", raw
    if "ruins" in tags or "abandoned" in tags or any(k.startswith("abandoned:") for k in tags):
        return "ruins", raw
    return "standing", raw


def infer_kind(tags: dict) -> str:
    levels = tags.get("building:levels")
    if tags.get("man_made") == "tower":
        return "tower"
    if tags.get("building") == "fire_lookout" or tags.get("emergency") == "fire_lookout":
        if levels == "2":
            return "two_story"
        if levels == "3":
            return "three_story"
        return "ground"
    return "unknown"


def type_raw_for(tags: dict) -> str:
    parts = []
    if tags.get("emergency") == "fire_lookout":
        parts.append("emergency=fire_lookout")
    if tags.get("building") == "fire_lookout":
        parts.append("building=fire_lookout")
    if tags.get("man_made") == "tower":
        tt = tags.get("tower:type", "")
        parts.append(f"man_made=tower;tower:type={tt}" if tt else "man_made=tower")
    return "; ".join(parts) if parts else "unknown"


def parse_float(value: str | None) -> float | None:
    if not value:
        return None
    m = re.match(r"-?\d+(\.\d+)?", value.strip())
    return float(m.group(0)) if m else None


def parse_built_year(start_date: str | None) -> int | None:
    if not start_date:
        return None
    m = re.match(r"(\d{4})", start_date.strip())
    return int(m.group(1)) if m else None


def build_links(tags: dict) -> list[dict]:
    links = []
    if tags.get("website"):
        links.append({"label": "Website", "url": tags["website"]})
    if tags.get("wikipedia"):
        wp = tags["wikipedia"]
        if ":" in wp:
            lang, title = wp.split(":", 1)
            links.append({
                "label": "Wikipedia",
                "url": f"https://{lang}.wikipedia.org/wiki/{title.strip().replace(' ', '_')}",
            })
    if tags.get("wikidata"):
        links.append({"label": "Wikidata", "url": f"https://www.wikidata.org/wiki/{tags['wikidata']}"})
    if tags.get("wikimedia_commons"):
        wc = tags["wikimedia_commons"].replace(" ", "_")
        links.append({"label": "Wikimedia Commons", "url": f"https://commons.wikimedia.org/wiki/{wc}"})
    ref_url = tags.get("ref:nhlr:url")
    if ref_url:
        links.append({"label": "NHLR register entry", "url": ref_url})
    return links


def build_registers(tags: dict) -> list[dict]:
    regs = []
    if tags.get("ref:nhlr"):
        regs.append({
            "register": "NHLR",
            "number": tags["ref:nhlr"],
            "state_number": tags.get("ref:nhlr:state"),
            "url": tags.get("ref:nhlr:url"),
        })
    if tags.get("ref:nrhp"):
        regs.append({"register": "NRHP", "number": tags["ref:nrhp"], "state_number": None, "url": None})
    return regs


EXTRA_PASSTHROUGH = (
    "height", "access", "historic", "tourism", "fee", "tower:construction",
    "building:material", "operator:type", "heritage", "heritage:operator",
    "alt_name", "old_name", "gnis:feature_id", "source", "note",
)


def build_record(elem: dict, state_lookup: c.StateLookup) -> dict:
    tags = elem.get("tags", {})
    etype = elem["type"]
    eid = elem["id"]
    if etype == "node":
        lat, lon = elem["lat"], elem["lon"]
    else:
        center = elem["center"]
        lat, lon = center["lat"], center["lon"]

    region = c.normalize_state(tags.get("addr:state"))
    if not region:
        region = state_lookup.state_for(lon, lat)

    status, status_raw = infer_status(tags)
    elevation_m = parse_float(tags.get("ele"))
    height_m = parse_float(tags.get("height"))
    built = parse_built_year(tags.get("start_date"))

    extra = {"osm_tags": dict(sorted(tags.items()))}
    if height_m is not None:
        extra["height_m"] = height_m
    for k in EXTRA_PASSTHROUGH:
        if k in tags and k not in ("height",):
            extra[k.replace(":", "_")] = tags[k]

    events = []
    if built:
        events.append({"year": built, "event": "built", "note": None, "from": "osm"})

    return {
        "key": f"osm:{etype}/{eid}",
        "url": f"https://www.openstreetmap.org/{etype}/{eid}",
        "name": tags.get("name"),
        "country": "US",
        "region": region,
        "county": None,
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "elevation_m": elevation_m,
        "type_raw": type_raw_for(tags),
        "kind": infer_kind(tags),
        "status_raw": status_raw,
        "status": status,
        "registers": build_registers(tags),
        "built": built,
        "agency": tags.get("operator"),
        "events": events,
        "photos": [],
        "links": build_links(tags),
        "rental": None,
        "extra": extra,
    }


def main() -> None:
    result = ensure_result()
    elements = result["elements"]
    state_lookup = c.get_state_lookup()

    records = []
    unnamed = 0
    for elem in elements:
        if not elem.get("tags", {}).get("name"):
            unnamed += 1
        records.append(build_record(elem, state_lookup))

    c.write_source_json(
        OUT_PATH,
        source="osm",
        title="OpenStreetMap -- fire lookout structures",
        url="https://overpass-api.de/api/interpreter",
        license_text="ODbL 1.0. (c) OpenStreetMap contributors.",
        records=records,
    )

    from collections import Counter
    by_status = Counter(r["status"] for r in records)
    by_kind = Counter(r["kind"] for r in records)
    no_region = sum(1 for r in records if not r["region"])

    print(f"Wrote {len(records)} records to {OUT_PATH}", file=sys.stderr)
    print(f"  {unnamed} unnamed (emergency=/building=fire_lookout without a name tag)",
          file=sys.stderr)
    print(f"  status: {dict(by_status)}", file=sys.stderr)
    print(f"  kind:   {dict(by_kind)}", file=sys.stderr)
    print(f"  no region resolved: {no_region}", file=sys.stderr)


if __name__ == "__main__":
    main()
