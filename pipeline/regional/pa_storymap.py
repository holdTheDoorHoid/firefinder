"""Fetcher for the Pennsylvania Fire Towers ArcGIS StoryMap by Shawn Lesitsky.

https://www.arcgis.com/apps/instant/atlas/index.html?appid=... (the public
story) backs onto a plain JSON export:
  https://www.arcgis.com/sharing/rest/content/items/<item>/data?f=json

That JSON is an ArcGIS StoryMaps node graph: a "tour" node lists one "place"
per tower (id, featureId, title node, content node(s), media node); a
"tour-map" node holds each featureId's lat/long; "resources" maps image
node ids to resourceId filenames served from
.../items/<item>/resources/<resourceId>.

Each place's prose is a short, uniform sentence: "Built in YYYY by
<builder>. Located in <County> County in <agency/park/forest>. It has a
height of N feet and <current status note>." Facts are pulled out with
regexes; the prose itself is not stored in the committed JSON (DESIGN.md
Sec 2/3.2: facts only, no copied history prose).

Output: data/sources/pa_storymap.json

Re-run: python3 pipeline/regional/pa_storymap.py
"""

from __future__ import annotations

import datetime
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import fetch_text, ft_to_m, slugify, write_source_json  # noqa: E402

SOURCE = "pa_storymap"
ITEM_ID = "ed47c97ebe7246868ce8ef3e7139a0b4"
DATA_URL = f"https://www.arcgis.com/sharing/rest/content/items/{ITEM_ID}/data?f=json"
RESOURCE_URL_TMPL = f"https://www.arcgis.com/sharing/rest/content/items/{ITEM_ID}/resources/{{}}"
STORY_URL = "https://www.arcgis.com/apps/MapSeries/index.html?appid=" + ITEM_ID

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

BUILT_RE = re.compile(r"Built in (\d{4}) by (?:the )?([^.]+?)\.")
COUNTY_RE = re.compile(
    r"Located in ([A-Za-z]+(?:\s[A-Za-z]+)?)\s+Count(?:y|ies|ry)\s+(?:in|on)\s+(.+?)\."
    r"\s*It has a height",
    re.S,
)
HEIGHT_RE = re.compile(r"height of (\d+)(?:\.\d+)?\s*feet")
REPLACED_IN_RE = re.compile(r"replaced in (\d{4})")
ORIGINAL_FROM_RE = re.compile(r"(?:original|replaces a[^.]*?)[^.]*?(\d{4})\s*tower|tower from (\d{4})")
DESIGN_AKA = {"Aermotor Windmill Company": "Aermotor"}


def parse_facts(prose: str) -> dict:
    built_m = BUILT_RE.search(prose)
    built_year = int(built_m.group(1)) if built_m else None
    builder_raw = None
    if built_m:
        builder_raw = built_m.group(2).split(",")[0].strip()

    county_m = COUNTY_RE.search(prose)
    county = county_m.group(1).strip() if county_m else None
    agency_raw = county_m.group(2).strip() if county_m else None

    height_m = HEIGHT_RE.search(prose)
    height_ft = int(height_m.group(1)) if height_m else None

    events = []
    if built_year:
        events.append({"year": built_year, "event": "built", "note": None, "from": "pa_storymap"})
    rep_m = REPLACED_IN_RE.search(prose)
    if rep_m and int(rep_m.group(1)) != built_year:
        events.append({"year": int(rep_m.group(1)), "event": "replaced", "note": None, "from": "pa_storymap"})
    orig_m = ORIGINAL_FROM_RE.search(prose)
    if orig_m:
        y = int(orig_m.group(1) or orig_m.group(2))
        if y and y != built_year:
            events.append({"year": y, "event": "built", "note": "original structure, later replaced", "from": "pa_storymap"})

    design = DESIGN_AKA.get(builder_raw)

    return {
        "built_year": built_year,
        "builder_raw": builder_raw,
        "county": county,
        "agency_raw": agency_raw,
        "height_ft": height_ft,
        "design": design,
        "events": events,
    }


def agency_to_ownership(agency_raw: str | None) -> str:
    if not agency_raw:
        return "unknown"
    low = agency_raw.lower()
    if "state forest" in low or "state park" in low or "state game lands" in low:
        return "state"
    if "national forest" in low:
        return "federal"
    return "unknown"


def main() -> None:
    raw = fetch_text(DATA_URL, SOURCE, "data.json")
    doc = json.loads(raw)
    nodes = doc["nodes"]

    tour = next(v for v in nodes.values() if v.get("type") == "tour")
    tour_map = next(v for v in nodes.values() if v.get("type") == "tour-map")
    geometries = tour_map["data"]["geometries"]

    records = []
    for place in tour["data"]["places"]:
        feature = geometries.get(place["featureId"])
        if not feature or not feature.get("nodes"):
            continue
        point = feature["nodes"][0]
        lat, lon = point["lat"], point["long"]

        title_node = nodes.get(place.get("title", ""), {})
        name = title_node.get("data", {}).get("text", "").strip()
        if not name:
            continue

        content_texts = [
            nodes[c]["data"]["text"]
            for c in place.get("contents", [])
            if c in nodes and nodes[c].get("data", {}).get("text")
        ]
        prose = " ".join(t.strip() for t in content_texts)
        facts = parse_facts(prose)

        photos = []
        media_id = place.get("media")
        media_node = nodes.get(media_id, {}) if media_id else {}
        image_ids = media_node.get("children", []) if media_node.get("type") == "carousel" else (
            [media_id] if media_node.get("type") == "image" else []
        )
        for img_node_id in image_ids:
            img_node = nodes.get(img_node_id, {})
            if img_node.get("type") != "image":
                continue
            resource_id = img_node.get("data", {}).get("image")
            resource = doc["resources"].get(resource_id, {})
            filename = resource.get("data", {}).get("resourceId")
            if not filename:
                continue
            photos.append({
                "url": RESOURCE_URL_TMPL.format(filename),
                "credit": "Shawn Lesitsky -- PA Fire Towers StoryMap (Esri ArcGIS StoryMaps)",
                "caption": name,
                "year": None,
            })

        key = f"pa_storymap:{slugify(name)}:{lat:.4f}:{lon:.4f}"
        agency_raw = facts["agency_raw"]

        rec = {
            "key": key,
            "url": STORY_URL,
            "name": name,
            "country": "US",
            "region": "PA",
            "county": facts["county"],
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "elevation_m": None,
            "type_raw": "tower",
            "kind": "tower",
            "status_raw": None,
            "status": "standing",  # every place in this story is a present-day, visitable tower
            "registers": [],
            "built": facts["built_year"],
            "agency": agency_raw,
            "events": facts["events"],
            "photos": photos,
            "links": [{"label": "PA Fire Towers StoryMap", "url": STORY_URL}],
            "rental": None,
            "extra": {
                **({"builder": facts["builder_raw"]} if facts["builder_raw"] else {}),
                **({"height_ft": facts["height_ft"]} if facts["height_ft"] else {}),
                **({"design": facts["design"]} if facts["design"] else {}),
                **({"ownership": agency_to_ownership(agency_raw)} if agency_raw else {}),
            },
        }
        records.append(rec)

    out_path = REPO_ROOT / "data" / "sources" / "pa_storymap.json"
    write_source_json(
        out_path,
        source=SOURCE,
        title="Fire Towers of Pennsylvania (ArcGIS StoryMap, Shawn Lesitsky)",
        url=STORY_URL,
        retrieved=datetime.date.today().isoformat(),
        license_="No licence stated; facts only (county, agency, built year, height, builder).",
        records=records,
    )
    print(f"wrote {len(records)} records -> {out_path}")


if __name__ == "__main__":
    main()
