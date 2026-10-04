#!/usr/bin/env python3
"""Fetch US fire lookout towers from Wikidata via SPARQL.

Writes data/sources/wikidata.json (DESIGN.md Â§3.2).

Selection: instance of Q748998 ("fire lookout tower") or any transitive
subclass of it (wdt:P31/wdt:P279*), with P17 (country) = Q30 (United
States). That subclass walk also catches Wikidata's "lookout tree" class
(12 items in the 2026-10-04 pull) -- those are legitimately subclassed
under fire lookout tower in Wikidata's own ontology, so the query is right
to include them, but DESIGN.md Â§1 puts tree platforms out of scope for
Firefinder itself. We keep them here (kind="tree") and let merge.py /
human curation hide them, per Â§3.2's "kept in source extracts, hidden: true
with a reason" rule -- a source extract is not the place to drop data the
query legitimately found.

One SPARQL query gets everything, including items with NO coordinates
(via OPTIONAL on P625), specifically so we can report how many exist
without ever writing them to the output -- DESIGN only wants mappable
records, and "how many did we skip" is exactly the kind of fact a
reviewer without Wikidata access can't otherwise check.

A correctness note worth keeping: P2048 (height) and P2044 (elevation
above sea level) are NOT reliably in metres on Wikidata -- checking units
on this pull found height and elevation entered in *feet* (unit Q3710)
for the large majority of items, metres (Q11573) for a handful, and
nothing else. wdt:P2048/wdt:P2044 (the "simple" value) silently drops the
unit, so this fetcher goes through p:/psv:/wikibase:quantityUnit to get
the amount AND unit explicitly and converts by hand -- grabbing the simple
value and assuming metres would have been wrong for ~95% of these.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _common as c

SPARQL_URL = "https://query.wikidata.org/sparql"
CACHE_PATH = c.raw_dir("wikidata") / "sparql_result.json"

REPO_ROOT = Path(__file__).parent.parent
OUT_PATH = REPO_ROOT / "data" / "sources" / "wikidata.json"

QUERY = """
SELECT ?item ?itemLabel
  (SAMPLE(?coord) AS ?coord)
  (GROUP_CONCAT(DISTINCT ?alias; separator="|") AS ?aliases)
  (GROUP_CONCAT(DISTINCT ?image; separator="|") AS ?images)
  (GROUP_CONCAT(DISTINCT ?nrhp; separator="|") AS ?nrhps)
  (SAMPLE(?inception) AS ?inception)
  (SAMPLE(?dissolved) AS ?dissolved)
  (SAMPLE(?heightAmount) AS ?heightAmount)
  (SAMPLE(?heightUnit) AS ?heightUnit)
  (SAMPLE(?elevAmount) AS ?elevAmount)
  (SAMPLE(?elevUnit) AS ?elevUnit)
  (GROUP_CONCAT(DISTINCT ?locationLabel; separator="|") AS ?locations)
  (GROUP_CONCAT(DISTINCT ?stateIso; separator="|") AS ?stateIsos)
  (GROUP_CONCAT(DISTINCT ?classLabel; separator="|") AS ?classLabels)
  (SAMPLE(?article) AS ?article)
WHERE {
  ?item wdt:P31/wdt:P279* wd:Q748998 .
  ?item wdt:P17 wd:Q30 .
  OPTIONAL { ?item wdt:P625 ?coord . }
  OPTIONAL { ?item rdfs:label ?itemLabel . FILTER(LANG(?itemLabel)="en") }
  OPTIONAL { ?item skos:altLabel ?alias . FILTER(LANG(?alias)="en") }
  OPTIONAL { ?item wdt:P18 ?image . }
  OPTIONAL { ?item wdt:P649 ?nrhp . }
  OPTIONAL { ?item wdt:P571 ?inception . }
  OPTIONAL { ?item wdt:P576 ?dissolved . }
  OPTIONAL {
    ?item p:P2048 ?heightNode .
    ?heightNode ps:P2048 ?heightSimple .
    ?heightNode psv:P2048 ?heightValueNode .
    ?heightValueNode wikibase:quantityAmount ?heightAmount .
    ?heightValueNode wikibase:quantityUnit ?heightUnit .
  }
  OPTIONAL {
    ?item p:P2044 ?elevNode .
    ?elevNode ps:P2044 ?elevSimple .
    ?elevNode psv:P2044 ?elevValueNode .
    ?elevValueNode wikibase:quantityAmount ?elevAmount .
    ?elevValueNode wikibase:quantityUnit ?elevUnit .
  }
  OPTIONAL { ?item wdt:P131 ?location . ?location rdfs:label ?locationLabel . FILTER(LANG(?locationLabel)="en") }
  OPTIONAL {
    ?item wdt:P131+ ?stateItem .
    ?stateItem wdt:P31 wd:Q35657 .
    ?stateItem wdt:P300 ?stateIso .
  }
  OPTIONAL { ?item wdt:P31 ?class . ?class rdfs:label ?classLabel . FILTER(LANG(?classLabel)="en") }
  OPTIONAL { ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> ; schema:inLanguage "en" . }
}
GROUP BY ?item ?itemLabel
""".strip()

# Wikidata QIDs for units of measure actually seen on these items (checked
# 2026-10-04: foot and metre only). Anything else is left unconverted
# rather than guessed.
UNIT_TO_M = {
    "http://www.wikidata.org/entity/Q3710": 0.3048,   # foot
    "http://www.wikidata.org/entity/Q11573": 1.0,     # metre
}
UNIT_IS_FOOT = {"http://www.wikidata.org/entity/Q3710"}

COORD_RE = re.compile(r"Point\(([-\d.]+)\s+([-\d.]+)\)")
COUNTY_SUFFIX_RE = re.compile(r"\s+(County|Parish|Borough|Census Area)$")


def ensure_result() -> dict:
    if not CACHE_PATH.exists():
        print(f"Querying Wikidata SPARQL ({SPARQL_URL})...", file=sys.stderr)
        body = urllib.parse.urlencode({"query": QUERY}).encode()
        raw = c.http_get(SPARQL_URL, data=body, timeout=180, headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/sparql-results+json",
        })
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_bytes(raw)
    return json.loads(CACHE_PATH.read_text())


def val(row: dict, key: str) -> str | None:
    v = row.get(key, {}).get("value")
    return v if v else None


def split_list(row: dict, key: str) -> list[str]:
    v = val(row, key)
    return [x for x in v.split("|") if x] if v else []


def convert_amount(amount: str | None, unit: str | None) -> tuple[float | None, float | None, bool]:
    """Returns (metres, original_value_in_its_own_unit, was_feet)."""
    if amount is None:
        return None, None, False
    amount_f = float(amount)
    if unit in UNIT_TO_M:
        return round(amount_f * UNIT_TO_M[unit], 2), amount_f, unit in UNIT_IS_FOOT
    return None, amount_f, False  # unknown unit: don't guess the conversion


def parse_year(dt: str | None) -> int | None:
    if not dt:
        return None
    m = re.match(r"-?(\d{1,4})", dt)
    return int(m.group(1)) if m else None


def filename_from_special_filepath(url: str) -> str | None:
    # e.g. http://commons.wikimedia.org/wiki/Special:FilePath/Feldtmann%20Fire%20Tower.jpg
    if "Special:FilePath/" not in url:
        return None
    frag = url.split("Special:FilePath/", 1)[1]
    return urllib.parse.unquote(frag)


def build_photos(image_urls: list[str]) -> list[dict]:
    photos = []
    for u in image_urls:
        fname = filename_from_special_filepath(u)
        if not fname:
            continue
        quoted = urllib.parse.quote(fname)
        page_name = fname.replace(" ", "_")
        photos.append({
            "url": f"https://commons.wikimedia.org/wiki/File:{page_name}",
            "credit": "Wikimedia Commons contributors",
            "caption": None,
            "year": None,
            "thumb_url": f"https://commons.wikimedia.org/wiki/Special:FilePath/{quoted}?width=400",
        })
    return photos


def infer_kind(class_labels: list[str]) -> str:
    labels = " ".join(class_labels).lower()
    if "lookout tree" in labels:
        return "tree"
    if "observation tower" in labels or "fire lookout tower" in labels:
        return "tower"
    return "tower"  # default: Q748998 itself IS "fire lookout tower"


def infer_status(dissolved: str | None, class_labels: list[str]) -> tuple[str, str | None]:
    labels = " ".join(class_labels).lower()
    if dissolved:
        year = parse_year(dissolved)
        return "gone", f"P576 dissolved/abandoned/demolished date: {year or dissolved}"
    if "destroyed building or structure" in labels:
        return "gone", "P31 instance of 'destroyed building or structure'"
    return "unknown", None


def build_record(row: dict, state_lookup: c.StateLookup) -> dict | None:
    qid = row["item"]["value"].rsplit("/", 1)[-1]
    coord = val(row, "coord")
    m = COORD_RE.match(coord) if coord else None
    if not m:
        return None
    lon, lat = float(m.group(1)), float(m.group(2))

    name = val(row, "itemLabel") or qid
    aliases = split_list(row, "aliases")
    class_labels = split_list(row, "classLabels")

    state_isos = split_list(row, "stateIsos")
    region = None
    if state_isos:
        region = c.normalize_state(state_isos[0].replace("US-", ""))
    if not region:
        region = state_lookup.state_for(lon, lat)

    counties = split_list(row, "locations")
    county = None
    if counties:
        county = COUNTY_SUFFIX_RE.sub("", counties[0])

    elev_m, elev_raw, elev_was_ft = convert_amount(val(row, "elevAmount"), val(row, "elevUnit"))
    height_m, height_raw, height_was_ft = convert_amount(val(row, "heightAmount"), val(row, "heightUnit"))

    built = parse_year(val(row, "inception"))
    dissolved_raw = val(row, "dissolved")
    status, status_raw = infer_status(dissolved_raw, class_labels)

    events = []
    if built:
        events.append({"year": built, "event": "built", "note": None, "from": "wikidata"})
    if dissolved_raw:
        events.append({
            "year": parse_year(dissolved_raw), "event": "destroyed",
            "note": "Wikidata P576 (dissolved/abandoned/demolished date); which of the three isn't specified.",
            "from": "wikidata",
        })

    nrhp_numbers = split_list(row, "nrhps")
    registers = [{"register": "NRHP", "number": n, "state_number": None, "url": None} for n in nrhp_numbers]

    links = [{"label": "Wikidata", "url": f"https://www.wikidata.org/wiki/{qid}"}]
    article = val(row, "article")
    if article:
        links.append({"label": "Wikipedia", "url": article})

    extra = {"wikidata_qid": qid}
    if aliases:
        extra["aliases"] = aliases
    if class_labels:
        extra["wikidata_classes"] = class_labels
    if elev_raw is not None:
        if elev_was_ft:
            extra["elevation_ft"] = elev_raw
        elif elev_m is None:
            extra["elevation_raw_unit_unrecognized"] = elev_raw
    if height_raw is not None:
        extra["height_m"] = height_m
        if height_was_ft:
            extra["height_ft"] = height_raw
        elif height_m is None:
            extra["height_raw_unit_unrecognized"] = height_raw

    return {
        "key": f"wikidata:{qid}",
        "url": f"https://www.wikidata.org/wiki/{qid}",
        "name": name,
        "country": "US",
        "region": region,
        "county": county,
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "elevation_m": elev_m,
        "type_raw": "; ".join(class_labels) if class_labels else None,
        "kind": infer_kind(class_labels),
        "status_raw": status_raw,
        "status": status,
        "registers": registers,
        "built": built,
        "agency": None,
        "events": events,
        "photos": build_photos(split_list(row, "images")),
        "links": links,
        "rental": None,
        "extra": extra,
    }


def main() -> None:
    result = ensure_result()
    rows = result["results"]["bindings"]
    state_lookup = c.get_state_lookup()

    with_coord = [r for r in rows if "coord" in r]
    no_coord = len(rows) - len(with_coord)

    records = []
    for row in with_coord:
        rec = build_record(row, state_lookup)
        if rec:
            records.append(rec)

    c.write_source_json(
        OUT_PATH,
        source="wikidata",
        title="Wikidata -- US fire lookout towers (Q748998 and subclasses)",
        url=SPARQL_URL,
        license_text="CC0 1.0 (Wikidata). Images keep their own Commons licence/credit.",
        records=records,
    )

    from collections import Counter
    by_status = Counter(r["status"] for r in records)
    by_kind = Counter(r["kind"] for r in records)
    no_region = sum(1 for r in records if not r["region"])

    print(f"Total Q748998-or-subclass items in the US: {len(rows)}", file=sys.stderr)
    print(f"  with coordinates (P625): {len(with_coord)} -- written to {OUT_PATH}", file=sys.stderr)
    print(f"  WITHOUT coordinates (skipped): {no_coord}", file=sys.stderr)
    print(f"  status: {dict(by_status)}", file=sys.stderr)
    print(f"  kind:   {dict(by_kind)}", file=sys.stderr)
    print(f"  no region resolved: {no_region}", file=sys.stderr)


if __name__ == "__main__":
    main()
