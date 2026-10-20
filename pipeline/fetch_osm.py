#!/usr/bin/env python3
"""Fetch fire lookout structures from OpenStreetMap via the Overpass API.

Writes data/sources/osm.json (DESIGN.md Â§3.2): the United States (QUERY) and, since 2026-10-20,
Canada, Alaska and Hawaii (QUERY_CA_AK_HI), two cached Overpass answers read together.

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

Canada, Alaska and Hawaii (2026-10-20, the owner's decision to add them): one more combined
query, with the French names Quebec and New Brunswick use (tour a feu, tour d'observation,
vigie) and the disused:/was: lifecycle forms of the fire-lookout tags. The US area above already
holds Alaska and Hawaii and returned no element there; this one did not either (86 elements, all
in Canada). The region of each Canadian element is the province whose Natural Earth admin-1
polygon holds it (regions.Admin1Lookup, public domain, cached once under
$FIREFINDER_RAW_ROOT/natural_earth/), or its addr:province tag.

Canadian observation towers: in Canada "lookout" and "tour d'observation" also name scenic and
wildlife towers (Tay Marsh Lookout Tower, "Tour d'observation - canards et cervides"). An element
with no fire-lookout tag and no fire word in its name (fire, firetower, feu) is kept but marked
extra.unconfirmed_lookout: merge.py hides it unless another source (firelookout.ca) describes
the same tower, which then shows it.

Hawaii: the Second World War coastal-artillery fire-control stations (base-end stations on the
ridges above Oahu's batteries) are not fire lookouts; an element in Hawaii tagged military or
named for fire control, a base end or a battery is marked extra.not_fire_lookout (hidden).

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
import regions

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
CACHE_PATH = c.raw_dir("osm") / "overpass_result.json"
CACHE_PATH_CA_AK_HI = c.raw_dir("osm") / "overpass_ca_ak_hi.json"

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

QUERY_CA_AK_HI = """
[out:json][timeout:180];
area["ISO3166-1"="CA"][admin_level=2]->.ca;
area["ISO3166-2"="US-AK"]->.ak;
area["ISO3166-2"="US-HI"]->.hi;
(.ca; .ak; .hi;)->.a;
(
  nwr["emergency"="fire_lookout"](area.a);
  nwr["building"="fire_lookout"](area.a);
  nwr["disused:emergency"="fire_lookout"](area.a);
  nwr["was:emergency"="fire_lookout"](area.a);
  nwr["man_made"="tower"]["tower:type"="observation"]["name"~"lookout|fire.?tower|tour (a|à) feu|tour d.observation|vigie",i](area.a);
);
out center tags;
""".strip()

# Words in a Canadian name that say "fire lookout" (English and French).
FIRE_NAME_RE = re.compile(r"\bfire\b|firetower|fire\s*lookout|\bfeu\b", re.I)
FIRE_TAGS = {("emergency", "fire_lookout"), ("building", "fire_lookout"),
             ("disused:emergency", "fire_lookout"), ("was:emergency", "fire_lookout")}
# Hawaii's coastal-artillery fire-control stations (not fire lookouts).
HI_FIRE_CONTROL_RE = re.compile(r"\bfire[\s-]+control\b|\bbase[\s-]+end\b|\bbattery\b|\bcoast(?:al)?\s+artillery\b", re.I)

GONE_KEYS = {"demolished", "destroyed:building", "building:destroyed"}
RUINS_PREFIXES = ("abandoned:",)
RUINS_KEYS = {"abandoned", "ruins"}


def ensure_result(path: Path = CACHE_PATH, query: str = QUERY) -> dict:
    if not path.exists():
        print(f"Querying Overpass API ({OVERPASS_URL})...", file=sys.stderr)
        body = query.encode()
        raw = c.http_get(OVERPASS_URL, data=body, timeout=200,
                          headers={"Content-Type": "text/plain"})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return json.loads(path.read_text())


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


def has_fire_evidence(tags: dict) -> bool:
    """A fire-lookout tag, or a fire word in the name."""
    return (any(tags.get(k) == v for k, v in FIRE_TAGS)
            or bool(FIRE_NAME_RE.search(tags.get("name") or "")))


def build_record(elem: dict, state_lookup: c.StateLookup, admin1=None) -> dict:
    """One source record. Elements of the Canada/Alaska/Hawaii query pass `admin1` (a
    regions.Admin1Lookup); the US query's keep the Census state lookup they always had."""
    tags = elem.get("tags", {})
    etype = elem["type"]
    eid = elem["id"]
    if etype == "node":
        lat, lon = elem["lat"], elem["lon"]
    else:
        center = elem["center"]
        lat, lon = center["lat"], center["lon"]

    country = "US"
    if admin1 is None:
        region = c.normalize_state(tags.get("addr:state"))
        if not region:
            region = state_lookup.state_for(lon, lat)
    else:
        region = admin1.nearest_region(lat, lon)
        tagged = regions.parse_region(tags.get("addr:province") or tags.get("addr:state") or "")
        if region is None and tagged:
            region = tagged
        country = regions.country_of(region) or ("CA" if regions.country_at(lat, lon) == "CA" else "US")

    status, status_raw = infer_status(tags)
    elevation_m = parse_float(tags.get("ele"))
    height_m = parse_float(tags.get("height"))
    built = parse_built_year(tags.get("start_date"))

    extra = {"osm_tags": dict(sorted(tags.items()))}
    if country == "CA" and not has_fire_evidence(tags):
        extra["unconfirmed_lookout"] = ("Not confirmed as a fire lookout (an observation tower OpenStreetMap "
                                        "does not tag or name as one)")
    if region == "HI" and (tags.get("military") or HI_FIRE_CONTROL_RE.search(tags.get("name") or "")):
        extra["not_fire_lookout"] = "Not a fire lookout (a Second World War coastal-artillery fire-control station)"
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
        "country": country,
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
    seen = set()
    unnamed = 0
    for elem in elements:
        if not elem.get("tags", {}).get("name"):
            unnamed += 1
        records.append(build_record(elem, state_lookup))
        seen.add((elem["type"], elem["id"]))
    # Canada, Alaska and Hawaii: the second cached answer (module docstring).
    more = ensure_result(CACHE_PATH_CA_AK_HI, QUERY_CA_AK_HI)["elements"]
    admin1 = regions.admin1_lookup(c.RAW_ROOT)
    for elem in more:
        if (elem["type"], elem["id"]) in seen:
            continue
        if not elem.get("tags", {}).get("name"):
            unnamed += 1
        records.append(build_record(elem, state_lookup, admin1))

    c.write_source_json(
        OUT_PATH,
        source="osm",
        title="OpenStreetMap -- fire lookout structures (United States and Canada)",
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
