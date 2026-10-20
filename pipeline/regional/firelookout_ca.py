"""Fetcher for firelookout.ca, the "Open Canada Fire Lookout Index" (2026-10-20).

The home page carries the whole index as one JavaScript array, `const rawTowers = [...]`: 206
lookouts with id, title, slug, lat, lng, address and region (Ontario, British Columbia and
Saskatchewan when first read). Each lookout has a record page, `/lookouts/?slug=<slug>` (the
"View Record" link the map popups build), with labelled facts: Region, Location / Address,
Coordinates, Elevation ("459 m (1506 ft)"), Tower Type ("Steel Tower"), Structure Height, Year Built,
a free-text note, "References & Credits" and photos.

robots.txt: the site has none (the path answers with the home page), so nothing is disallowed. We
fetch politely anyway: one request every 2 s, our honest User-Agent, every page cached once under
`$FIREFINDER_RAW_ROOT/firelookout_ca/` (206 pages, about seven minutes the first time).

Rights: the site publishes its historical records under CC BY-NC-SA 4.0. Firefinder takes **facts
only** (name, position, province and local unit, elevation, type, height, year built) with credit
and a link to each record, as for the FFLA and the registers. The free-text notes, the contributors'
words and photos are not copied.

Province and local unit come from `address`, read from the end: "..., Sudbury District,
Northeastern Ontario, Ontario, Canada" -> ON, "Sudbury District"; "Meadow Lake No. 588, SK S0M,
Canada" -> SK, "Meadow Lake No. 588". The unit is the address part that names a Canadian
census division or municipality in its own words (District, Regional District, County, Division
No., Municipal District, No. <n> rural municipality, Unorganized ...); nothing is appended to it.
When the address names no province (a bare plus code), the position decides (regions.py).

Output: data/sources/firelookout_ca.json
Re-run: python3 pipeline/regional/firelookout_ca.py            (reads the cache; fetches what is missing)
        python3 pipeline/regional/firelookout_ca.py --no-fetch (cache only; records without a page keep the index facts)
"""

from __future__ import annotations

import argparse
import datetime
import html as htmlmod
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(HERE.parent))  # after regional/, whose _common.py shadows the pipeline's
from _common import RAW_ROOT, FetchError, fetch, slugify, write_source_json  # noqa: E402
import regions  # noqa: E402

SOURCE = "firelookout_ca"
BASE = "https://firelookout.ca"
HOME_URL = f"{BASE}/"
REPO_ROOT = HERE.parent.parent
OUT = REPO_ROOT / "data" / "sources" / f"{SOURCE}.json"
# research/fetch_text.py cached the home page here first (sha1 of the URL); read it rather than
# fetching it again.
WEB_CACHE = RAW_ROOT / "web" / "8d0a1f2eb4fe0b34b7a23fbb4e19906b96769bf4.bin"
LICENSE = "CC BY-NC-SA 4.0 (firelookout.ca); facts only, with credit and a link"
CREDIT = "Firelookout.ca, Open Canada Fire Lookout Index (CC BY-NC-SA 4.0)"

RAW_TOWERS_RE = re.compile(r"const\s+rawTowers\s*=\s*(\[.*?\]);", re.S)


def record_url(slug: str) -> str:
    return f"{BASE}/lookouts/?slug={slug}"


def home_html(fetch_missing: bool = True) -> str:
    cached = RAW_ROOT / SOURCE / "index.html"
    if cached.exists():
        return cached.read_text(encoding="utf-8", errors="replace")
    if WEB_CACHE.exists():
        return WEB_CACHE.read_text(encoding="utf-8", errors="replace")
    if not fetch_missing:
        raise SystemExit("firelookout.ca home page is not cached; run without --no-fetch")
    return fetch(HOME_URL, SOURCE, "index.html").decode("utf-8", errors="replace")


def raw_towers(page: str) -> list[dict]:
    m = RAW_TOWERS_RE.search(page)
    if not m:
        raise SystemExit("firelookout.ca: no rawTowers array on the home page (layout changed?)")
    return json.loads(m.group(1))


def page_path(slug: str) -> str:
    return f"lookouts/{slugify(slug)}.html"


def tower_page(slug: str, fetch_missing: bool = True) -> str | None:
    path = RAW_ROOT / SOURCE / page_path(slug)
    if path.exists():
        return path.read_text(encoding="utf-8", errors="replace")
    if not fetch_missing:
        return None
    try:
        return fetch(record_url(slug), SOURCE, page_path(slug), timeout=30).decode("utf-8", errors="replace")
    except FetchError as e:
        print(f"  {slug}: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------------------------
# Reading a record page
# ---------------------------------------------------------------------------------------------

ROW_RE = re.compile(r"<th>(.*?)</th>\s*<td>(.*?)</td>", re.S)
NOTE_RE = re.compile(r'<div class="content-box">(.*?)</div>', re.S)


def clean(text: str) -> str:
    text = htmlmod.unescape(re.sub(r"<[^>]+>", " ", text)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def page_facts(page: str | None) -> dict[str, str]:
    """{"Elevation": "459 m (1506 ft)", "Tower Type": "Steel Tower", ...} from the record's table;
    "N/A" and empty values are left out."""
    if not page:
        return {}
    out = {}
    for th, td in ROW_RE.findall(page):
        k, v = clean(th), clean(td)
        if k and v and v.upper() not in ("N/A", "NA", "-", "\u2014"):
            out[k] = v
    return out


def page_note(page: str | None) -> str:
    """The record's free-text note. Read only for the closed-vocabulary words below; never copied."""
    m = NOTE_RE.search(page or "")
    return clean(m.group(1)) if m else ""


ELEV_RE = re.compile(r"^(-?\d+(?:\.\d+)?)\s*m\b")
YEAR_RE = re.compile(r"^(1[89]\d\d|20[0-2]\d)$")
STEEL_NOTE_RE = re.compile(r"^(?:heavy(?: gauge)? |light )?steel\b", re.I)


def elevation_m(text: str | None) -> float | None:
    m = ELEV_RE.match(text or "")
    return float(m.group(1)) if m else None


# ---------------------------------------------------------------------------------------------
# Province and local unit from the address
# ---------------------------------------------------------------------------------------------

POSTAL_RE = re.compile(r"^(?P<prov>[A-Za-z .\u00c0-\u017f-]+?)?\s*[A-Z]\d[A-Z](?:\s*\d[A-Z]\d)?$")
# The site's own regions: a province, or a part of Ontario.
SITE_REGIONS = {
    "Northeastern Ontario": "ON", "Central Ontario": "ON", "Eastern Ontario": "ON",
    "Northwestern Ontario": "ON", "Southwestern Ontario": "ON",
}
# Parts of an address that name a region of a province, not a local unit.
NOT_UNITS = {"northeastern ontario", "central ontario", "eastern ontario", "northwestern ontario",
             "southwestern ontario", "abitibi-temiscamingue", "canada"}
# Ontario's territorial districts (census divisions), for "South Nipissing District" (an
# unorganized area's name mistaken for a district) and "District Municipality of Muskoka".
ON_DISTRICTS = {"Algoma", "Cochrane", "Kenora", "Manitoulin", "Muskoka", "Nipissing", "Parry Sound",
                "Rainy River", "Sudbury", "Thunder Bay", "Timiskaming"}
# Ontario single-tier census divisions an address may name without a unit word.
ON_SINGLE_TIER = {"Greater Sudbury", "Kawartha Lakes"}
# British Columbia's regional districts (its census divisions), by the short name addresses use,
# with their official names.
BC_REGIONAL_DISTRICTS = {
    "bulkley-nechako": "Regional District of Bulkley-Nechako",
    "cariboo": "Cariboo Regional District",
    "central kootenay": "Regional District of Central Kootenay",
    "central okanagan": "Regional District of Central Okanagan",
    "columbia-shuswap": "Columbia Shuswap Regional District",
    "columbia shuswap": "Columbia Shuswap Regional District",
    "east kootenay": "Regional District of East Kootenay",
    "fraser valley": "Fraser Valley Regional District",
    "fraser-fort george": "Regional District of Fraser-Fort George",
    "kitimat-stikine": "Regional District of Kitimat-Stikine",
    "kootenay boundary": "Regional District of Kootenay Boundary",
    "north okanagan": "Regional District of North Okanagan",
    "okanagan-similkameen": "Regional District of Okanagan-Similkameen",
    "peace river": "Peace River Regional District",
    "squamish-lillooet": "Squamish-Lillooet Regional District",
    "sunshine coast": "Sunshine Coast Regional District",
    "thompson-nicola": "Thompson-Nicola Regional District",
}


def _province_of_part(part: str) -> str | None:
    p = part.strip()
    m = POSTAL_RE.match(p)
    if m:
        p = (m.group("prov") or "").strip()
        if not p:
            return None
    return regions.parse_region(p, "CA")


def _bc_district(part: str) -> str | None:
    p = re.sub(r"\s+", " ", part.strip())
    m = re.match(r"^(?:Regional District of (.+)|(.+?) Regional District)$", p)
    key = (m.group(1) or m.group(2)) if m else p
    key = re.sub(r"\s+[A-H]$", "", key.strip())  # "Cariboo D", "Fraser-Fort George G": an electoral area
    return BC_REGIONAL_DISTRICTS.get(key.lower())


def local_unit(parts: list[str], province: str | None) -> str | None:
    """The census division (or rural municipality) an address names, in its own words."""
    units = []
    for part in parts:
        p = re.sub(r"\s+", " ", part).strip()
        low = regions.fold(p)
        if not p or low in NOT_UNITS or _province_of_part(p) or POSTAL_RE.match(p):
            continue
        if province == "BC":
            rd = _bc_district(p)
            if rd:
                units.append((0, rd))
            continue
        if province == "SK":
            m = re.match(r"^(?:Unorganized\s+)?(Division No\. ?\d+)$", p)
            if m:
                units.append((1, m.group(1)))
            elif re.match(r"^.+ No\. ?\d+$", p):
                units.append((0, p))    # a rural municipality: "Torch River No. 488"
            continue
        if province == "ON":
            m = re.match(r"^District Municipality of (.+)$", p)
            if m:
                units.append((1, f"{m.group(1)} District"))
                continue
            m = re.match(r"^(?:(?:North|South|East|West|Centre|North East)\s+)?(.+) District$", p)
            if m and m.group(1) in ON_DISTRICTS:
                units.append((0, f"{m.group(1)} District"))
                continue
            if re.match(r"^.+ County$", p) or p in ON_SINGLE_TIER:
                units.append((0, p))
            continue
        if re.match(r"^.+ (?:County|District|Regional District|Regional County Municipality)$", p):
            units.append((0, p))
    if not units:
        return None
    units.sort(key=lambda u: u[0])
    return units[0][1]


def read_address(address: str | None, site_region: str | None) -> tuple[str | None, str | None]:
    """(province code, local unit) from the address, read from the end. The site's own region
    ("Ontario", "Northeastern Ontario") decides the province; when the address names another
    (Maria Fire Tower: Ontario, with a reverse-geocoded Quebec address), its local unit is not
    used, since it belongs to the other province."""
    parts = [p.strip() for p in (address or "").split(",") if p.strip()]
    addr_prov = None
    for p in reversed(parts):
        addr_prov = _province_of_part(p)
        if addr_prov:
            break
    site_prov = SITE_REGIONS.get(site_region or "") or regions.parse_region(site_region or "", "CA")
    province = site_prov or addr_prov
    if addr_prov and site_prov and addr_prov != site_prov:
        return province, None
    return province, local_unit(parts, province)


# ---------------------------------------------------------------------------------------------
# Curated facts
# ---------------------------------------------------------------------------------------------
# Read once (2026-10-20) from each record's note and written here in our own words, by the site's
# record id. Only facts: a status, a dated event, a structure word, an access level. The notes
# themselves (CC BY-NC-SA) are not copied. Status values are the closed set mapped in
# pipeline/structure.py (FIRELOOKOUT_CA_STATUS).


def ev(year, event, note):
    return {"year": year, "event": event, "note": note, "from": SOURCE}


CURATED: dict[int, dict] = {
    41037: {"status": "gone", "events": [ev(1969, "destroyed", "Destroyed by a tornado.")]},             # Joan
    36636: {"status": "gone"},                                                                          # Thessalon: footings only
    36561: {"status": "standing, cab gone"},                                                            # Catfish Lake
    35810: {"status": "standing, cab gone"},                                                            # Lecours
    35807: {"status": "gone", "events": [ev(1979, "removed", "Dismantled.")]},                         # Bamoos
    35801: {"status": "standing"},                                                                      # Max Lake (visited 2025)
    41012: {"status": "gone", "events": [ev(1974, "staffed_last", "No longer staffed from 1974; later sold for scrap.")]},  # Richards
    41010: {"events": [ev(1962, "built", "Tower and observer's cabin built.")]},                       # Osler
    40823: {"status": "standing"},                                                                      # Sugar Mountain (restored)
    13994: {"events": [ev(1921, "built", "Built by the Dominion Forestry Branch.")],
            "words": ["stone house", "kind ground"]},                                                  # Joss Mountain
    13990: {"status": "standing"},                                                                      # Idaho Peak (locked)
    13971: {"access": "private", "ownership": "private"},                                               # Hamilton
    13964: {"status": "standing"},                                                                      # Greenstone (refurbished shelter)
    13026: {"events": [ev(1921, "built", "A stone cabin built by the Dominion Forestry Branch.")],
            "words": ["stone house", "kind ground"]},                                                  # Eagle Pass
    12642: {"words": ["steel tower"]},                                                                  # Bull (steel tower replaced a wooden one)
    12055: {"status": "gone", "events": [ev(2017, "burned", "Burned.")]},                              # Alex Graham
    11987: {"events": [ev(1957, "modified", "New cupola.")]},                                          # English Cabin
    11839: {"status": "likely gone"},                                                                   # Clear Lake, SK
    11831: {"status": "standing"},                                                                      # Buffalo Hills (seen on imagery)
    11796: {"status": "standing", "words": ["wood house", "kind ground"]},                            # Windy Joe
    11781: {"status": "gone", "events": [ev(2011, "removed", "Removed.")]},                            # Hazelwood
    11779: {"status": "gone", "events": [ev(1965, "destroyed", "Blown down in a windstorm.")]},        # Kwagama Mountain
    11759: {"status": "standing, cab gone"},                                                            # Pinery
    11756: {"status": "standing"},                                                                      # Tisdale
    11753: {"status": "standing, cab gone"},                                                            # Victoria
    11748: {"status": "standing, cab gone"},                                                            # Beaverhouse-Quetico
    11744: {"status": "standing"},                                                                      # Widdifield (now a communications tower)
    11741: {"status": "replica"},                                                                       # Elliot Lake
    11730: {"status": "standing, cab gone",
            "events": [ev(2011, "other", "The cab burned; the steel frame still stands.")]},            # Big Crow Lake
    11700: {"status": "standing, cab gone"},                                                            # Black Creek
    11685: {"status": "standing"},                                                                      # McDougal-Thorne
    11492: {"status": "standing"},                                                                      # Coulson
    11483: {"status": "standing",
            "events": [ev(None, "relocated", "Moved here after it closed, for a historical display.")]},  # Bonhuer
    11482: {"status": "likely gone"},                                                                   # Pickle Lake
    11474: {"status": "standing"},                                                                      # Upper Shakwa Lake
    11417: {"status": "standing"},                                                                      # Mount Collins (2011)
    11354: {"status": "standing"},                                                                      # Wylie (in use)
    11351: {"status": "standing"},                                                                      # Malone (in use)
    9936: {"status": "standing",
           "events": [ev(1930, "built", "An 80 ft tower; the 100 ft tower standing now replaced it.")]},  # Ishpatina
    9931: {"status": "standing"},                                                                       # Lyman
    9921: {"status": "standing"},                                                                       # Saunders Lake
    9896: {"status": "standing"},                                                                       # Bruce County (moved here)
    9892: {"status": "standing, cab gone",
           "events": [ev(2011, "other", "Lightning burned the cab; the steel tower still stands.")]},    # Freswick
    9872: {"status": "replaced by an observation tower",
           "events": [ev(1922, "built", None), ev(1961, "staffed_last", "Used as a fire lookout until 1961."),
                      ev(1967, "replaced", "A 30 m observation tower for visitors was built on the site.")]},  # Dorset
    9853: {"status": "standing", "events": [ev(1998, "restored", "Restored and reopened to visitors.")]},  # Temagami
    24360: {"status": "standing"},                                                                      # Antrim (communications tower)
    41027: {"status": "standing"},                                                                      # Rabbit Hill (camera detection, 2026)
    41011: {"events": [ev(1932, "relocated", "Moved here from Kitty Lake, its first site (1922).")]},  # Preston
    41024: {"words": ["steel tower"]},                                                                  # Rye
}
# Not fire lookouts, though the index lists them.
NOT_FIRE = {
    35798: "Not a fire lookout (Firelookout.ca lists the Thunder Cape Bird Observatory's tower)",
}
# Positions the site itself calls a guess, approximate, unverified, or a nearby village's.
POSITION_GUESS = {41038, 41031, 41030, 41025, 11757, 11752, 11777, 9988, 9919, 11685, 41017, 41022}
# Positions the site says are unknown.
POSITION_UNKNOWN = {11839: "Firelookout.ca says the location is not known."}
# A point shared by three or more lookouts of different names is a district office the index
# geocoded, not a tower (Lindsay, Tweed and Pembroke in 2026-10): such records are kept without a
# position. Two names close together are left alone: they may be one tower under two names
# (Big Crow Lake and Freswick, 169 m apart, both burned in 2011), which the merge report lists.
SHARED_POINT_M = 500
SHARED_POINT_NAMES = 3


def _dist_m(a: dict, b: dict) -> float:
    import math
    p = math.radians
    x = (math.sin(p(b["lat"] - a["lat"]) / 2) ** 2
         + math.cos(p(a["lat"])) * math.cos(p(b["lat"])) * math.sin(p(b["lng"] - a["lng"]) / 2) ** 2)
    return 2 * 6371000 * math.asin(math.sqrt(x))


def shared_points(towers: list[dict]) -> set[int]:
    """Ids of records in a cluster (points within SHARED_POINT_M of each other, chained) that
    holds SHARED_POINT_NAMES or more different names."""
    def core(t):
        return re.sub(r"\s+", " ", re.sub(r"\b(fire|tower|lookout)\b", "", t["title"].lower())).strip()
    parent = list(range(len(towers)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i, a in enumerate(towers):
        for j in range(i + 1, len(towers)):
            if _dist_m(a, towers[j]) <= SHARED_POINT_M:
                parent[find(i)] = find(j)
    groups: dict[int, list[dict]] = {}
    for i, t in enumerate(towers):
        groups.setdefault(find(i), []).append(t)
    out = set()
    for members in groups.values():
        if len({core(t) for t in members}) >= SHARED_POINT_NAMES:
            out.update(int(t["id"]) for t in members)
    return out


# ---------------------------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------------------------


def build_record(t: dict, page: str | None, shared: set[int]) -> dict:
    tid = int(t["id"])
    name = htmlmod.unescape(t["title"]).strip()
    facts = page_facts(page)
    note = page_note(page)
    address = facts.get("Location / Address") or t.get("address")
    province, unit = read_address(address, t.get("region"))
    if province is None:
        # A bare plus code: the index's region decides, else nothing (validate.py would reject it).
        province = regions.parse_region(t.get("region") or "", "CA")
    extra: dict = {"firelookout_ca_id": tid, "site_region": t.get("region"), "address": address}
    lat, lon = float(t["lat"]), float(t["lng"])
    if tid in POSITION_UNKNOWN:
        extra["position_note"] = POSITION_UNKNOWN[tid]
        lat = lon = None
    elif tid in shared:
        extra["position_note"] = ("Firelookout.ca gives the same point for several lookouts (a district "
                                  "office, not a tower), so it is not used.")
        lat = lon = None
    elif tid in POSITION_GUESS:
        extra["position_approximate"] = True
        extra["position_note"] = "Firelookout.ca marks this position as a guess or not verified."
    cur = CURATED.get(tid, {})
    type_raw = facts.get("Tower Type")
    words = list(cur.get("words") or [])
    if (STEEL_NOTE_RE.match(note) or (type_raw or "").lower() == "steel tower") and "steel tower" not in words:
        words.append("steel tower")
    if words:
        extra["structure_words"] = words
    if type_raw and re.search(r"\b(?:D-6|Aermotor|LL-25)\b", type_raw, re.I):
        extra["design"] = type_raw
    if tid in NOT_FIRE:
        extra["not_fire_lookout"] = NOT_FIRE[tid]
    events = list(cur.get("events") or [])
    year = facts.get("Year Built")
    built = int(year) if year and YEAR_RE.match(year) else None
    if built and not any(e["event"] == "built" for e in events):
        events.insert(0, ev(built, "built", None))
    elif built is None:
        built = next((e["year"] for e in events if e["event"] == "built"), None)
    status_raw = cur.get("status")
    url = record_url(t["slug"])
    rec = {
        "key": f"{SOURCE}:{tid}",
        "url": url,
        "name": name,
        "country": "CA",
        "region": province,
        "county": unit,
        "lat": round(lat, 6) if lat is not None else None,
        "lon": round(lon, 6) if lon is not None else None,
        "elevation_m": elevation_m(facts.get("Elevation")),
        "type_raw": type_raw,
        "kind": "tower" if (type_raw or "").lower() == "steel tower" else "unknown",
        "status_raw": status_raw,
        "status": "unknown",
        "registers": [],
        "built": built,
        "agency": None,
        "events": events,
        "photos": [],
        "links": [],
        "rental": None,
        "extra": extra,
    }
    if cur.get("access"):
        extra["access_level"] = cur["access"]
        extra["access_note"] = "Firelookout.ca: private property, no public access."
    if cur.get("ownership"):
        extra["ownership"] = cur["ownership"]
    return rec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-fetch", action="store_true", help="read the cache only")
    ap.add_argument("--fetch-only", action="store_true", help="fill the page cache and stop")
    args = ap.parse_args(argv)
    towers = raw_towers(home_html(not args.no_fetch))
    pages = {}
    for i, t in enumerate(towers, 1):
        pages[t["id"]] = tower_page(t["slug"], not args.no_fetch)
        if i % 25 == 0:
            print(f"  {i}/{len(towers)} pages", file=sys.stderr, flush=True)
    if args.fetch_only:
        return 0
    shared = shared_points(towers)
    records = [build_record(t, pages[t["id"]], shared) for t in towers]
    records.sort(key=lambda r: r["key"])
    newest = max((p.stat().st_mtime for p in (RAW_ROOT / SOURCE / "lookouts").glob("*.html")), default=None)
    retrieved = datetime.date.fromtimestamp(newest).isoformat() if newest else datetime.date.today().isoformat()
    write_source_json(OUT, source=SOURCE, title="Firelookout.ca, Open Canada Fire Lookout Index",
                      url=HOME_URL, retrieved=retrieved, license_=LICENSE, records=records,
                      header_extra={"credit": CREDIT})
    from collections import Counter
    print(f"wrote {len(records)} records -> {OUT}", file=sys.stderr)
    print(f"  by province: {dict(sorted(Counter(r['region'] for r in records).items()))}", file=sys.stderr)
    print(f"  without a position: {sum(1 for r in records if r['lat'] is None)}; "
          f"guessed: {sum(1 for r in records if r['extra'].get('position_approximate'))}; "
          f"with a local unit: {sum(1 for r in records if r['county'])}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
