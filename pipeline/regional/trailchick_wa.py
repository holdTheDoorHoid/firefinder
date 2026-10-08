"""Fetcher for TrailChick's "Washington State Fire Lookouts" field guide
(trailchick.com/wa-state-fire-lookouts/), linked from FFLA's links page as "Trail Chick (WA)".

The guide is a photographic survey of 93 Washington lookouts the author has visited (89 standing; four
titled " - RIP" are gone: Slate Peak, Ned Hill, Aeneas Mountain and Diamond Peak Patrol, recorded
here as gone). The
index page carries all 93 as a JSON array in its script (`const LOOKOUTS = [...]`: title, slug, county,
land manager, wilderness, mountain range, lookout type, elevation, drivable), and each lookout has its
own page, /wa-state-fire-lookouts/<slug>/, whose fact block gives "Location : lat, lon", "Summit
Elevation", "Lookout Type", "Site Established" and "Current Structure Built". Coordinates are the
author's own (she has stood at each one), so unlike most hobby sites this is a good independent position.

Facts only: the descriptive text is not copied. The guide's card photo for each lookout is listed (the merge
credits it to the guide; the project mirrors photos from hobby sites with credit and a takedown note: DESIGN.md Sec 1). The site has no robots.txt (404) and no
stated licence. One request per 2 s, cached under data/raw/trailchick_wa/.

Not read: the "Former Lookout Sites of Washington" posts (about 14, trip reports, no fact block) and the
staffed / overnight-stay lists (subsets of the 93).

Output: data/sources/trailchick_wa.json
Re-run: python3 pipeline/regional/trailchick_wa.py
"""

from __future__ import annotations

import datetime
import html as htmlmod
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import FetchError, fetch_text, ft_to_m, slugify, write_source_json  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from structure import structure_words  # noqa: E402  (pipeline/structure.py: the closed vocabulary of facts)

SOURCE = "trailchick_wa"
BASE = "https://www.trailchick.com"
INDEX_URL = f"{BASE}/wa-state-fire-lookouts/"
HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

LOOKOUTS_RE = re.compile(r"const LOOKOUTS = (\[.*?\]);\s*\n", re.S)
LABELS = ["Location", "Summit Elevation", "Lookout Type", "Site Established", "Current Structure Built",
          "Date Visited", "Original Structure Built", "Structure Built", "Hike Length", "Elevation Gain",
          "Roundtrip", "Driveable", "Trailhead"]
DESIGN_RE = re.compile(r"\b(L-4|L-5|L-6|R-6|D-6|Aermotor(?:\s+\w+-?\d+)?|CL-\d+|BC-\d+|IS-\d+|Forest Service plan)\b", re.I)
SIZE_RE = re.compile(r"(\d+)\s*['′]?\s*x\s*(\d+)\s*['′]?")
HEIGHT_RE = re.compile(r"(\d{2,3})\s*['′]\s*(?:tall|high|tower)?", re.I)
YEAR_RE = re.compile(r"\b(1[89]\d\d|20[0-2]\d)\b")


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ")).strip()


def fact_block(page_html: str) -> dict[str, str]:
    """{label: value} from the fact lines that follow the title ("Location : 48.95, -121.64" ...)."""
    text = clean(re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", page_html))
    start = text.find("Location :")
    if start < 0:
        start = text.find("Location:")
    if start < 0:
        return {}
    text = text[start:start + 1500]
    pat = r"(" + "|".join(re.escape(l) for l in LABELS) + r")\s*:\s*"
    parts = re.split(pat, text)
    out: dict[str, str] = {}
    # parts = [before, label, value, label, value, ...]
    for i in range(1, len(parts) - 1, 2):
        out.setdefault(parts[i], parts[i + 1].strip())
    return out


def parse_lookout(item: dict, facts: dict[str, str]) -> dict:
    lat = lon = None
    m = re.match(r"\s*(-?\d{1,3}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)", facts.get("Location", ""))
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
        if lon > 0:
            lon = -lon
        if not (45.0 <= lat <= 49.2 and -125.0 <= lon <= -116.5):
            lat = lon = None
    elev_ft = None
    em = re.search(r"(\d[\d,]*)", facts.get("Summit Elevation", "") or item.get("elevation", ""))
    if em:
        elev_ft = int(em.group(1).replace(",", ""))
    type_raw = facts.get("Lookout Type") or ", ".join(item.get("lookout_type") or []) or None
    design = None
    dm = DESIGN_RE.search(type_raw or "") or DESIGN_RE.search(" ".join(item.get("lookout_type") or []))
    if dm:
        design = dm.group(1)
    height_ft = None
    hm = HEIGHT_RE.search(type_raw or "")
    if hm and not SIZE_RE.search(type_raw or ""):
        height_ft = int(hm.group(1))
    built = est = None
    bm = YEAR_RE.search(facts.get("Current Structure Built", "") or "")
    if bm:
        built = int(bm.group(1))
    sm = YEAR_RE.search(facts.get("Site Established", "") or "")
    if sm:
        est = int(sm.group(1))
    return {"lat": lat, "lon": lon, "elev_ft": elev_ft, "type_raw": type_raw, "design": design,
            "height_ft": height_ft, "built": built, "established": est}


RIP_RE = re.compile(r"\s*[-\u2013]\s*RIP\s*$", re.I)
CAB_SUFFIX_RE = re.compile(r"\s+L-\d\s+Cab\s*$", re.I)
# Aliases for the names the guide shortens or extends (the second words are on the signs, not on maps).
ALIASES = {"Diamond Peak Patrol": ["Diamond Peak"]}


def clean_title(title: str) -> tuple[str, bool]:
    """(name, rip): the guide marks lookouts that are gone with a " - RIP" suffix on the title and
    adds " L-4 Cab" to one name (Whitmore Mountain, a cab with no tower)."""
    rip = bool(RIP_RE.search(title))
    name = CAB_SUFFIX_RE.sub("", RIP_RE.sub("", title)).strip()
    return name, rip


def kind_of(type_raw: str | None) -> str:
    """A rough kind from the guide's lookout-type line; 'unknown' where a bare "cab" could be a
    ground house or a tower cab. Only matters for a lookout no other source has."""
    t = (type_raw or "").lower()
    if re.search(r"ground\s*house|groundhouse|log cabin|custom designed cabin", t):
        return "ground"
    if "tree cab" in t:
        return "tree"
    if "tower" in t:
        return "tower"
    if "platform" in t or t.startswith("crows nest"):
        return "platform"
    return "unknown"


def ownership_of(land: str | None) -> str:
    low = (land or "").lower()
    if any(w in low for w in ("national forest", "national park", "national recreation", "blm", "bureau of land")):
        return "federal"
    if "state" in low or "dnr" in low or "department of natural resources" in low:
        return "state"
    if "reservation" in low or "tribal" in low:
        return "tribal"
    if "private" in low:
        return "private"
    return "unknown"


def main() -> None:
    retrieved = datetime.date.today().isoformat()
    index_html = fetch_text(INDEX_URL, SOURCE, "index.html", encoding="utf-8")
    m = LOOKOUTS_RE.search(index_html)
    if not m:
        sys.exit("trailchick_wa: could not find the LOOKOUTS array on the guide page (site changed?)")
    items = json.loads(m.group(1))
    print(f"{len(items)} lookouts in the guide", file=sys.stderr)
    records = []
    for item in items:
        slug = item["slug"]
        url = f"{INDEX_URL}{slug}/"
        try:
            page = fetch_text(url, SOURCE, f"{slugify(slug)}.html", encoding="utf-8")
            facts = fact_block(page)
        except FetchError as e:
            print(f"  ! {item['title']!r} ({url}): {e}", file=sys.stderr)
            facts = {}
        f = parse_lookout(item, facts)
        name, rip = clean_title(item["title"])
        events = []
        if f["built"]:
            events.append({"year": f["built"], "event": "built", "note": "Current structure", "from": SOURCE})
        extra = {"elevation_ft": f["elev_ft"], "driveable": item.get("driveable"),
                 "type_text": f["type_raw"], "structure_words": structure_words(f["type_raw"]),
                 "mountain_ranges": item.get("mountain_ranges") or None,
                 "wilderness": item.get("wilderness") or None}
        if f["design"]:
            extra["design"] = f["design"]
        if f["height_ft"]:
            extra["height_ft"] = f["height_ft"]
        if f["established"]:
            extra["site_established"] = f["established"]
        if ALIASES.get(name):
            extra["aliases"] = ALIASES[name]
        own = ownership_of(item.get("land"))
        if own != "unknown":
            extra["ownership"] = own
        records.append({
            "key": f"{SOURCE}:wa:{slugify(slug)}", "url": url, "name": name, "country": "US",
            "region": "WA", "county": item.get("county") or None,
            "lat": round(f["lat"], 5) if f["lat"] is not None else None,
            "lon": round(f["lon"], 5) if f["lon"] is not None else None,
            "elevation_m": ft_to_m(f["elev_ft"]) if f["elev_ft"] else None,
            "type_raw": None, "kind": kind_of(f["type_raw"]),
            "status_raw": None, "status": "gone" if rip else "standing",
            "registers": [], "built": f["built"], "agency": item.get("land") or None, "events": events,
            "photos": ([{"url": item["image"], "credit": None, "caption": None, "year": None}] if item.get("image") else []),
            "links": [{"label": f"{item['title']} in the TrailChick Washington lookout guide", "url": url,
                       "kind": "site"}],
            "rental": None, "extra": {k: v for k, v in extra.items() if v not in (None, [])},
        })
    n_coord = sum(1 for r in records if r["lat"] is not None)
    print(f"{len(records)} records, {n_coord} with coordinates", file=sys.stderr)
    out = REPO_ROOT / "data" / "sources" / f"{SOURCE}.json"
    write_source_json(
        out, source=SOURCE, title="TrailChick: Washington State Fire Lookouts",
        url=INDEX_URL, retrieved=retrieved,
        license_=("No licence stated; facts only (county, land manager, coordinates, elevation, lookout "
                  "type, years built). The guide's text is not reproduced; its card photos are listed with credit "
                  "to TrailChick, for the project's photo mirroring."),
        records=records,
    )
    print(f"wrote {len(records)} records -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
