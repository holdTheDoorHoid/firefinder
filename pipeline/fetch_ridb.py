#!/usr/bin/env python3
r"""Fetch fire-lookout facilities from the RIDB (recreation.gov) bulk export.

Writes:
  data/sources/ridb.json           -- source records, DESIGN.md Â§3.2/Â§3.3
  data/sources/ridb_excluded.json  -- candidates we looked at and rejected,
                                       each with a reason (name clashes like
                                       "Lookout Campground", "Cape Lookout
                                       National Seashore", trailheads, etc.)

Source: https://ridb.recreation.gov/downloads/RIDBFullExport_V1_JSON.zip
(~572 MB, no API key, updated daily). We never extract the zip to disk --
every member is read straight out of it with zipfile, and the zip itself is
deleted once we're done (see main()). The export is "stored" (no deflate),
so streaming members out of it is cheap.

How facilities link to other tables (worked out by inspecting the export on
2026-10-04; there is no public schema doc for the bulk export):
  - EntityActivities_API_v1.json ties an ActivityID to an EntityID, with an
    EntityType that mirrors FacilityTypeDescription ("Facility", "Campground",
    "Rec Area", ...). For Facility- and Campground-typed entities, EntityID
    IS the FacilityID -- there's a single Facilities table underneath.
  - FacilityAddresses_API_v1.json gives AddressStateCode (the region) and
    City per FacilityID. ~98% of our candidates have one; the rest fall back
    to a state point-in-polygon lookup (_common.get_state_lookup) against the
    facility's own coordinates.
  - Organizations_API_v1.json + a facility's own ParentOrgID gives the
    managing agency name directly (no join table needed for Facility-level
    records).
  - Campsites_API_v1.json has a CampsiteType of "LOOKOUT" for a small subset
    (20 facilities) -- used here only as a cross-check, not as a selection
    source (every one of them was already caught by the name match below).
  - CampsiteAttributes_API_v1.json (290 MB) and Media_API_v1.json (136 MB)
    are NOT read: neither carries anything-per-facility that the description
    text doesn't already give us for a lookout-sized facility set, and
    reading them would double the memory/time cost of the fetch for no
    reportable gain. See the fetcher's final report for what this costs us
    (mainly: nightly $ rate, which RIDB's static export rarely states anyway).

Selection (DESIGN.md Â§2 + the task): a facility is a candidate if EITHER
  (a) its ActivityID set (via EntityActivities) includes 30 ("FIRE LOOKOUTS/
      CABINS OVERNIGHT") or 100052 ("LOOKOUT TOWER"), OR
  (b) its FacilityName matches /lookout|fire\s*tower|\bl-?4\b/i,
restricted to FacilityTypeDescription in {"Facility", "Campground"} (that
excludes Rec Area-level rows, which aren't single structures, and "Ticket
Facility" rows like the Cape Lookout National Seashore tours).

In practice (a) alone is extremely noisy: activity 30 is reused across RIDB
for every rentable administrative cabin/guard station, so most of its ~219
facility/campground hits are ranger stations, generic campgrounds and area
index pages with no fire-lookout connection at all. So selection here is
really name-match-first. The records the name regex misses are added by hand
in EXTRA_INCLUDE (an explicit id list, a reason per id, checked against the
facility's own recreation.gov page): Spyglass Ground House (caught via its
Keywords field) and the lookout rentals the FFLA lists whose RIDB names carry
no "lookout". Every activity-tagged candidate that is neither a name match nor
in EXTRA_INCLUDE is logged to ridb_excluded.json with a reason -- see
ACTIVITY_ONLY_REJECTS and the loop at the end of main().
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _common as c

ZIP_URL = "https://ridb.recreation.gov/downloads/RIDBFullExport_V1_JSON.zip"
ZIP_PATH = c.raw_dir("ridb") / "RIDBFullExport_V1_JSON.zip"

REPO_ROOT = Path(__file__).parent.parent
OUT_PATH = REPO_ROOT / "data" / "sources" / "ridb.json"
EXCLUDED_PATH = REPO_ROOT / "data" / "sources" / "ridb_excluded.json"

NAME_RE = re.compile(r"lookout|fire\s*tower|\bl-?4\b", re.IGNORECASE)
LOOKOUT_ACTIVITY_IDS = {30, 100052}  # confirmed by name against Activities_API_v1.json
FACILITY_LIKE_TYPES = {"Facility", "Campground"}

# Candidates we found via the activity tag alone (not name/keyword) and
# manually decided are NOT fire lookout structures, with the reasoning.
# Keyed by FacilityID. Anything activity-tagged but not in this dict and not
# selected is still logged to ridb_excluded.json as "no lookout signal".
ACTIVITY_ONLY_REJECTS = {
    "233332": "Keywords mention 'Cape Lookout National Seashore' as a nearby place name "
               "(Great Island Cabin Camp); not a fire lookout structure itself.",
    "234451": "Indian Flats Cabin / Indian Flats Guard Station: a ranger cabin (built 1944, "
               "relocated 1969). Keywords include an alternate name 'Hogback Lookout Cabin' "
               "but the description describes a guard-duty residence, not a fire-watching "
               "structure or an on-site tower.",
    "262730": "Crack-In-The-Ground: a geological fissure / interpretive day-use site near "
               "Christmas Valley, OR. 'Lookout Tower' is one of several generic recreation "
               "keyword tags (with Camping, Trailhead, Hiking); the site itself is the "
               "fissure, not a tower.",
    "10161357": "Hopkins Mountain Fireman's Cabin (WV): description says the cabin and a "
                "separate 'Fire Tower site' were built together by the CCC in 1935. The "
                "rental is the fire watcher's residence, not the tower (whose site is implied "
                "gone); excluded as a support cabin, not the lookout structure.",
}

# Name/keyword matches that are confirmed NOT fire lookout structures, with reasons.
NAME_MATCH_REJECTS = {
    "10063832": "Cape Lookout National Seashore Duck Blind Lottery: Cape Lookout, NC is a "
                "geographic cape/lighthouse area; this facility is a hunting-blind lottery, "
                "unrelated to fire lookout towers.",
    "252276": "Cape Lookout National Seashore Tours: same geographic place name (Cape "
              "Lookout, NC), a boat-tour ticket product, not a fire lookout structure.",
    "122540": "Lookout Campground and Boat Launch - Willamette: a generic campground/boat "
              "launch on Blue River Reservoir named for its location; no fire lookout tower "
              "on site.",
    "234728": "Lookout Campground (CA/NV border): description is a generic 'secret hideaway' "
              "campground; no mention of a fire lookout structure.",
    "239000": "Blacktail Canyon-Point Lookout Road: a snowmobile road, not a structure.",
    "239703": "Stateline Lookout (Palisades Interstate Park, NJ): a scenic overlook/parking "
              "area, not a fire lookout tower.",
    "257413": "Lookout Mountain CDNST Trailhead: a trailhead parking area for the Continental "
              "Divide Trail, not a structure.",
    "258588": "Lookout Mountain Battlefield Visitor Center: a Civil War (Battle of Chattanooga) "
              "site; 'Lookout' here is the mountain's name, not a fire lookout tower.",
    "258821": "Lands End Lookout Visitor Center (San Francisco): a coastal scenic-viewpoint "
              "visitor center; not a fire lookout tower.",
    "265538": "Lookout Pass Ski and Recreation Area: a ski resort at Lookout Pass, ID/MT; not "
              "a fire lookout structure.",
    "270885": "Lookout Peak Trailhead (Sequoia NF / Kings Canyon): a trailhead to the peak, "
              "not the lookout structure (if any survives, it would be a separate facility).",
    "237824": "Red Hill Lookout Viewpoint: description says it is 'located next to the fire "
              "lookout tower' -- this facility IS the viewpoint, not the tower; using its "
              "coordinates would misplace the actual structure.",
}

# Facilities included BY HAND, whatever their name or activity tags say. Keyed by FacilityID, each
# with the reason, checked against the facility's own recreation.gov page. Two kinds of entry:
#   - a real lookout whose RIDB name has no "lookout"/"fire tower"/"L-4" in it, so NAME_RE misses
#     it (Spyglass, Post Creek, Mt. Baldy-Buckhorn Ridge, ...);
#   - a rental on a lookout's site that RIDB names as a cabin or guard station (Bishop Mountain,
#     Strawberry, Tamarack, Timber Butte) but that the Forest Fire Lookout Association lists as a
#     lookout rental (data/sources/ffla_rentals.json, 2026-10-08). RIDB gives the rental's own
#     coordinates, so the record joins the lookout already on the map; it does not start a tower.
# An id here must not also be in NAME_MATCH_REJECTS (select_include_ids would drop it silently) or
# ACTIVITY_ONLY_REJECTS (a contradiction); test_fetch_ridb checks both.
EXTRA_INCLUDE = {
    "10007160": "Spyglass Ground House (ID): a real lookout, caught via its Keywords field "
                "('Spyglass Lookout Ground House'); verified by hand.",
    "234404": "Post Creek Guard Station (Shasta-Trinity NF, CA): built 1934 by the CCC for use as "
              "a wildfire lookout; its own notices call it 'Post Creek Lookout', and the FFLA "
              "lists it as 'Post Creek Lookout'. A ground-level cabin, not a tower. Was rejected "
              "as activity-only because the name has no 'lookout'.",
    "234432": "Mt. Baldy-Buckhorn Ridge (Kootenai NF, MT): a 26-foot tower with a 144 sq ft cab, "
              "built 1957 on a site watched since 1910; the FFLA lists it as 'Mt. Baldy "
              "Lookout'. Was rejected as activity-only because the name has no 'lookout'.",
    "234304": "Bishop Mountain Cabin (Caribou-Targhee NF, ID): a 1938 CCC cabin that housed "
              "lookout workers until the early 1980s, with a historic lookout tower nearby "
              "(not rentable); the FFLA lists it as 'Bishop Mountain Lookout Cabin'.",
    "234281": "Gird Point (Bitterroot NF, MT): an L-4 cab on an 8-foot tower at 7,702 ft, "
              "restored from 2001; the FFLA lists it as 'Gird Point Lookout'. The name has no "
              "'lookout', so NAME_RE misses it.",
    "272173": "Strawberry Cabin (Helena-Lewis and Clark NF, MT): a 1941 log cabin on the top of "
              "Strawberry Butte, beside a 1940s metal lookout tower that is closed to the public; "
              "the FFLA lists it as 'Strawberry Lookout Cabin'.",
    "234138": "Tamarack Cabin (Umatilla NF, OR): a converted shed beside the 96-foot Aermotor "
              "tower (1933, replacing a 1925 tree platform) that is still standing; the FFLA "
              "lists it as 'Tamarack Lookout Cabin'.",
    "233133": "Timber Butte Cabin (Willamette NF, OR): the Timber Butte Lookout, a 2005 volunteer-"
              "built replica of an L-4 cab with a catwalk; the FFLA lists it as 'Timber Butte "
              "Replica Lookout'. The name has no 'lookout', so NAME_RE misses it.",
}


def select_include_ids(name_matched_ids, extra_include=None, name_match_rejects=None) -> set[str]:
    """The facilities that become lookout records: those whose name matches, plus the by-hand
    EXTRA_INCLUDE ones, minus the confirmed false positives in NAME_MATCH_REJECTS. (An
    ACTIVITY_ONLY_REJECTS id is never name-matched, so it only matters if it is also listed in
    EXTRA_INCLUDE, which the tests forbid.)"""
    extra = EXTRA_INCLUDE if extra_include is None else extra_include
    rejects = NAME_MATCH_REJECTS if name_match_rejects is None else name_match_rejects
    return (set(name_matched_ids) | set(extra)) - set(rejects)


def load_members(zf: zipfile.ZipFile, names: list[str]) -> dict:
    out = {}
    for name in names:
        with zf.open(name) as f:
            out[name] = json.load(f)["RECDATA"]
    return out


def ensure_zip() -> Path:
    if not ZIP_PATH.exists():
        print(f"Downloading {ZIP_URL} -> {ZIP_PATH} (~572 MB)...", file=sys.stderr)
        c.fetch_cached(ZIP_URL, ZIP_PATH, timeout=1800)
    return ZIP_PATH


# ---------------------------------------------------------------------------
# Text parsing for the rental object. Every pattern below pulls a literal
# substring out of the facility's own description -- nothing here invents a
# value. If nothing matches, the field stays null and the full text is still
# available in rental.description for a human to read.
# ---------------------------------------------------------------------------

WORD_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}

SEASON_RANGE_RE = re.compile(
    r"\b(?:is\s+)?(?:typically\s+|normally\s+|generally\s+|usually\s+)?"
    r"(?:open|available\s+(?:for|as)?\s*(?:rent|rental|renting|reservations?))\s+"
    r"(?:from\s+|for\s+)?"
    r"(?P<range>[A-Za-z][A-Za-z0-9,.\-– ]{2,60}?"
    r"(?:through|thru|to|[-–])\s*[A-Za-z0-9][A-Za-z0-9,.\- ]{1,40}?)"
    r"(?=[.;]|,\s+(?:however|depending|although)|\s+\()",
    re.IGNORECASE,
)
SEASON_YEARROUND_RE = re.compile(
    r"available\s+for\s+(?:rent|rental|reservations?)\s+year[- ]round", re.IGNORECASE
)

OCC_RE = re.compile(
    r"(?:sleep[s]?|accommodate[s]?)\s+(?:up\s+to\s+)?(?P<n>\w+)\s+(?:people|guests|person)",
    re.IGNORECASE,
)
OCC_DIGIT_RE = re.compile(r"\b(?P<n>\d{1,2})[- ](?:person|people|guest)", re.IGNORECASE)

PET_PATTERNS = [
    (re.compile(r"absolutely no pets|no pets (?:are )?allowed|pets (?:are )?not (?:permitted|allowed)", re.I), "Not allowed"),
    (re.compile(r"pets? (?:must be |are )?(?:kept )?(?:on (?:a )?leash|leashed)", re.I), "Allowed on leash"),
    (re.compile(r"service animals? only", re.I), "Service animals only"),
    (re.compile(r"pets? (?:are )?(?:welcome|allowed|permitted)", re.I), "Allowed"),
]

ELEV_RE = re.compile(
    r"(?:elevation of|altitude of|elevation:?)\s*([\d,]{3,6})\s*(?:feet|ft\.?|')", re.IGNORECASE
)
ELEV_AT_RE = re.compile(r"\bat\s+([\d,]{4,6})\s*feet\b", re.IGNORECASE)

BUILT_RE = re.compile(
    r"(?:was\s+)?(?:built|constructed|erected)\s+(?:in|during(?:\s+the\s+summer\s+of)?)\s+(\d{4})",
    re.IGNORECASE,
)
RENTAL_OPENED_RE = re.compile(
    r"opened\s+(?:to the public\s+)?for\s+(?:overnight\s+)?rental\s+in\s+(\d{4})", re.IGNORECASE
)

# (regex, canonical rule text) -- matched sentence is kept verbatim if short
# enough, else the canonical text is used. Order matters: first match wins
# per sentence category below.
RULE_DETECTORS = [
    (re.compile(r"pack out (?:their |all )?trash|must pack out", re.I), "Pack out all trash"),
    (re.compile(r"no water (?:or|and) electricity|no water, no electricity", re.I), "No water or electricity on site"),
    (re.compile(r"clean the cabin before (?:they )?(?:leav|check)", re.I), "Clean the cabin before leaving"),
    (re.compile(r"no open fires|campfires? (?:are )?not (?:permitted|allowed)", re.I), "No open fires / campfires not allowed"),
    (re.compile(r"generators? (?:are )?not (?:permitted|allowed)", re.I), "No generators"),
    (re.compile(r"no smoking", re.I), "No smoking"),
    (re.compile(r"quiet hours", re.I), "Quiet hours observed"),
    (re.compile(r"not (?:wheelchair|ADA) accessible", re.I), "Not ADA accessible"),
]

ACCESS_SENTENCE_RE = re.compile(
    r"(?:access(?:ed|ible)? (?:by|via)|accessed by|drive directly|high[- ]clearance|"
    r"four[- ]wheel drive|4wd|4-wheel drive|must (?:hike|ski|snowshoe|snowmobile)|"
    r"hiking, horseback|not plowed or maintained)",
    re.IGNORECASE,
)


def word_to_int(word: str) -> int | None:
    word = word.lower()
    if word.isdigit():
        return int(word)
    return WORD_NUM.get(word)


def parse_season(text: str) -> str | None:
    if SEASON_YEARROUND_RE.search(text):
        return "Year-round"
    m = SEASON_RANGE_RE.search(text)
    if m:
        return re.sub(r"\s+", " ", m.group("range")).strip().rstrip(",")
    return None


def parse_occupancy(text: str) -> int | None:
    m = OCC_RE.search(text)
    if m:
        n = word_to_int(m.group("n"))
        if n:
            return n
    m = OCC_DIGIT_RE.search(text)
    if m:
        return int(m.group("n"))
    return None


def parse_pets(text: str) -> str | None:
    for pat, label in PET_PATTERNS:
        if pat.search(text):
            return label
    return None


def parse_elevation_ft(text: str) -> float | None:
    m = ELEV_RE.search(text)
    if not m:
        m = ELEV_AT_RE.search(text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def parse_built_year(text: str) -> int | None:
    years = [int(y) for y in BUILT_RE.findall(text)]
    return years[-1] if years else None


def parse_rental_opened_year(text: str) -> int | None:
    m = RENTAL_OPENED_RE.search(text)
    return int(m.group(1)) if m else None


def parse_rules(sentences: list[str]) -> list[str]:
    rules: list[str] = []
    seen = set()
    for sent in sentences:
        for pat, label in RULE_DETECTORS:
            if pat.search(sent) and label not in seen:
                rules.append(label)
                seen.add(label)
                break
    return rules


def parse_access_note(sentences: list[str]) -> str | None:
    for sent in sentences:
        if ACCESS_SENTENCE_RE.search(sent):
            return sent.strip()
    return None


def infer_kind(name: str, text: str) -> str:
    low = (name + " " + text).lower()
    if "ground house" in low or "ground cab" in low or re.search(r"\bground\b.*\b(cab|house)\b", low):
        return "ground"
    if "two-story" in low or "two story" in low:
        return "two_story"
    if "three-story" in low or "three story" in low:
        return "three_story"
    if "platform" in low and "cab" not in low and "cabin" not in low:
        return "platform"
    return "tower"


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return re.sub(r"-+", "-", s)


def build_record(fac: dict, *, reservable_url: str | None, addr: dict | None,
                  agency: str | None, is_lookout_type_campsite: bool) -> dict:
    fid = fac["FacilityID"]
    name = (fac.get("FacilityName") or "").strip()
    desc_html = fac.get("FacilityDescription") or ""
    text = c.flatten_text(desc_html)
    plain_desc = c.html_to_text(desc_html)
    sentences = c.split_sentences(text)

    lat = fac.get("FacilityLatitude") or 0
    lon = fac.get("FacilityLongitude") or 0
    has_coords = bool(lat) and bool(lon)

    region = c.normalize_state(addr.get("AddressStateCode")) if addr else None
    if not region and has_coords:
        region = STATE_LOOKUP.state_for(lon, lat)

    elev_ft = parse_elevation_ft(text)
    elevation_m = c.ft_to_m(elev_ft) if elev_ft else None

    built_year = parse_built_year(text)
    events = []
    if built_year:
        events.append({"year": built_year, "event": "built", "note": None, "from": "ridb"})
    rental_opened = parse_rental_opened_year(text)
    if rental_opened:
        events.append({"year": rental_opened, "event": "rental_opened", "note": None, "from": "ridb"})

    reservable = bool(fac.get("Reservable"))
    rental = None
    if reservable:
        fee_desc = c.html_to_text(fac.get("FacilityUseFeeDescription"))
        rental = {
            "available": True,
            "provider": "recreation.gov",
            "url": reservable_url,
            "ridb_facility_id": fid,
            "season": parse_season(text),
            "max_occupancy": parse_occupancy(text),
            "pets": parse_pets(text),
            "fee": fee_desc,
            "rules": parse_rules(sentences),
            "access_note": parse_access_note(sentences),
            "description": plain_desc,
            "checked": c.today(),
        }

    extra = {"facility_type": fac.get("FacilityTypeDescription")}
    if elev_ft:
        extra["elevation_ft"] = elev_ft
    if is_lookout_type_campsite:
        extra["ridb_campsite_type"] = "LOOKOUT"
    if not reservable and plain_desc:
        # Non-reservable facilities still get the description preserved,
        # just not inside a rental object (DESIGN: rental is null here).
        extra["description"] = plain_desc

    links = []
    map_url = fac.get("FacilityMapURL")
    if map_url:
        links.append({"label": "Facility map", "url": map_url})

    record = {
        "key": f"ridb:{fid}",
        "url": reservable_url if reservable else None,
        "name": name,
        "country": "US",
        "region": region,
        "county": None,
        "lat": round(lat, 5) if has_coords else None,
        "lon": round(lon, 5) if has_coords else None,
        "elevation_m": elevation_m,
        "type_raw": None,
        "kind": infer_kind(name, text),
        "status_raw": None,
        "status": "standing" if fac.get("Enabled") else "unknown",
        "registers": [],
        "built": built_year,
        "agency": agency,
        "events": events,
        "photos": [],
        "links": links,
        "rental": rental,
        "extra": extra,
    }
    return record


STATE_LOOKUP = None  # set in main()


def main() -> None:
    global STATE_LOOKUP
    zip_path = ensure_zip()
    zip_size = zip_path.stat().st_size
    zip_mtime = zip_path.stat().st_mtime

    print("Reading RIDB export members (streamed from the zip, nothing extracted to disk)...",
          file=sys.stderr)
    with zipfile.ZipFile(zip_path) as zf:
        members = load_members(zf, [
            "Activities_API_v1.json",
            "EntityActivities_API_v1.json",
            "Facilities_API_v1.json",
            "FacilityAddresses_API_v1.json",
            "Organizations_API_v1.json",
            "Campsites_API_v1.json",
        ])

    activities = members["Activities_API_v1.json"]
    entity_activities = members["EntityActivities_API_v1.json"]
    facilities = members["Facilities_API_v1.json"]
    addresses = members["FacilityAddresses_API_v1.json"]
    organizations = members["Organizations_API_v1.json"]
    campsites = members["Campsites_API_v1.json"]

    # Sanity-check the activity IDs we hardcoded still mean what we think.
    act_names = {a["ActivityID"]: a["ActivityName"] for a in activities}
    for aid in LOOKOUT_ACTIVITY_IDS:
        found = act_names.get(aid)
        expected = {30: "FIRE LOOKOUTS/CABINS OVERNIGHT", 100052: "LOOKOUT TOWER"}[aid]
        if found != expected:
            print(f"WARNING: ActivityID {aid} is now {found!r}, expected {expected!r} -- "
                  f"RIDB may have renumbered activities.", file=sys.stderr)

    facilities_by_id = {f["FacilityID"]: f for f in facilities}
    addr_by_fac: dict[str, dict] = {}
    for a in addresses:
        addr_by_fac.setdefault(a["FacilityID"], a)  # first (Default) address wins
    org_by_id = {o["OrgID"]: o["OrgName"] for o in organizations}

    lookout_campsite_facility_ids = {
        s["FacilityID"] for s in campsites if (s.get("CampsiteType") or "").upper() == "LOOKOUT"
    }

    activity_tagged_ids = {
        r["EntityID"] for r in entity_activities
        if r.get("ActivityID") in LOOKOUT_ACTIVITY_IDS and r.get("EntityType") in FACILITY_LIKE_TYPES
    }

    def name_matches(fac: dict) -> bool:
        if fac.get("FacilityTypeDescription") not in FACILITY_LIKE_TYPES:
            return False
        return bool(NAME_RE.search(fac.get("FacilityName") or ""))

    name_matched_ids = {fid for fid, fac in facilities_by_id.items() if name_matches(fac)}

    extra_include_ids = set(EXTRA_INCLUDE)
    include_ids = select_include_ids(name_matched_ids)

    only_activity_ids = activity_tagged_ids - name_matched_ids - extra_include_ids

    print(f"Candidates: {len(name_matched_ids)} name-matched, "
          f"{len(extra_include_ids)} added by hand (EXTRA_INCLUDE), "
          f"{len(NAME_MATCH_REJECTS)} name-matched false positives excluded, "
          f"{len(only_activity_ids)} activity-only (not included; see ridb_excluded.json).",
          file=sys.stderr)
    for fid in sorted(extra_include_ids - set(facilities_by_id)):
        print(f"WARNING: EXTRA_INCLUDE facility {fid} is not in this export -- RIDB may have "
              f"renumbered or dropped it (see EXTRA_INCLUDE in pipeline/fetch_ridb.py).",
              file=sys.stderr)

    STATE_LOOKUP = c.get_state_lookup()

    records = []
    for fid in sorted(include_ids):
        fac = facilities_by_id.get(fid)
        if fac is None:
            continue
        agency = org_by_id.get(fac.get("ParentOrgID"))
        reservable_url = (f"https://www.recreation.gov/camping/campgrounds/{fid}"
                           if fac.get("Reservable") else None)
        rec = build_record(
            fac,
            reservable_url=reservable_url,
            addr=addr_by_fac.get(fid),
            agency=agency,
            is_lookout_type_campsite=fid in lookout_campsite_facility_ids,
        )
        records.append(rec)

    c.write_source_json(
        OUT_PATH,
        source="ridb",
        title="Recreation Information Database (RIDB) -- fire lookouts",
        url=ZIP_URL,
        license_text='Public domain (US government work). Data source: ridb.recreation.gov.',
        records=records,
    )

    # --- exclusions, with reasons ---
    excluded = []
    for fid, reason in NAME_MATCH_REJECTS.items():
        fac = facilities_by_id.get(fid)
        if fac:
            excluded.append({"key": f"ridb:{fid}", "name": fac.get("FacilityName"),
                              "facility_id": fid, "reason": reason})
    for fid, reason in ACTIVITY_ONLY_REJECTS.items():
        fac = facilities_by_id.get(fid)
        if fac:
            excluded.append({"key": f"ridb:{fid}", "name": fac.get("FacilityName"),
                              "facility_id": fid, "reason": reason})
    logged_ids = set(NAME_MATCH_REJECTS) | set(ACTIVITY_ONLY_REJECTS)
    for fid in sorted(only_activity_ids - logged_ids):
        fac = facilities_by_id.get(fid)
        if not fac:
            continue
        excluded.append({
            "key": f"ridb:{fid}",
            "name": fac.get("FacilityName"),
            "facility_id": fid,
            "reason": (
                f"Tagged with RIDB activity 'FIRE LOOKOUTS/CABINS OVERNIGHT' or 'LOOKOUT "
                f"TOWER', but the name/type gives no indication of a fire lookout structure "
                f"(FacilityTypeDescription: {fac.get('FacilityTypeDescription')!r}). That "
                f"activity tag is reused broadly in RIDB for ranger stations, guard cabins, "
                f"generic campgrounds and area-index pages."
            ),
        })

    excluded.sort(key=lambda r: r["key"])
    EXCLUDED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EXCLUDED_PATH.open("w") as f:
        json.dump({
            "source": "ridb",
            "retrieved": c.today(),
            "note": "Candidates considered for data/sources/ridb.json and rejected, with why.",
            "excluded": excluded,
        }, f, indent=2, ensure_ascii=False)
        f.write("\n")

    reservable_count = sum(1 for r in records if r["rental"] is not None)
    print(f"\nWrote {len(records)} records to {OUT_PATH} "
          f"({reservable_count} reservable, {len(records) - reservable_count} visit-only).",
          file=sys.stderr)
    print(f"Wrote {len(excluded)} exclusions to {EXCLUDED_PATH}.", file=sys.stderr)
    print(f"\nRIDB zip: {zip_size:,} bytes, last-modified {zip_mtime}.", file=sys.stderr)


if __name__ == "__main__":
    main()
