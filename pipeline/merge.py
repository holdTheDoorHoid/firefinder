#!/usr/bin/env python3
"""Merge the source extracts into one canonical record per lookout site (DESIGN.md section 3.5).

Reads data/sources/<source>.json (section 3.2) and the existing canonical towers in
data/towers/<region>/<id>.json (section 3.3), and writes the towers back plus a review file,
data/merge_report.json.

The merge adds and refreshes; it never deletes:

  * A tower file, once written, keeps its id forever (ids are URLs and checklist keys).
  * A source record that matched a tower before is matched to it again by its key.
  * Fields named in a tower's "locked" list are never overwritten.
  * A tower whose source records have all disappeared is kept as it is.

Matching, in order (first hit wins):

  1. key       the record's key is already in some tower's sources[].key
  2. register  a shared register number. NHLR and FFLOS number their entries separately
               ("NHLR US 674" and "FFLOS US 674" are different lookouts), so the register
               name is part of the key. NRHP reference numbers count too.
  3. spatial   nearby towers, scored by normalised-name similarity, then distance
               (thresholds in MATCH_* below; see DESIGN.md 3.5)
  4. name      records with no coordinates: a unique same-name tower in the same state
  5. new       anything else in scope with coordinates starts a new tower

Two records from the same source never share a tower, except where that source is known to
list one lookout twice (DOUBLE_LISTED below) and the two records agree on name and place.

Field values come from the highest-precedence source that has one (PRECEDENCE below, mirrored
as a table in DESIGN.md 3.5). Disagreements on location (> 500 m), status and build year are
recorded in "conflicts", not silently resolved.

Usage:
    python3 pipeline/merge.py                  # merge into data/towers, write data/merge_report.json
    python3 pipeline/merge.py --dry-run        # report only, write no tower files
    python3 pipeline/merge.py --towers /tmp/t --report /tmp/r.json

Python 3.12, standard library only.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import difflib
import json
import math
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlsplit

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from state_bbox import STATE_BBOX, flag_coordinate  # noqa: E402

# Rough boxes for the territories, which state_bbox does not cover.
TERRITORY_BBOX = {"PR": (17.8, 18.6, -67.4, -65.2), "VI": (17.6, 18.5, -65.1, -64.5),
                  "GU": (13.2, 13.7, 144.6, 145.0), "AS": (-14.6, -11.0, -171.1, -168.1),
                  "MP": (14.0, 20.6, 144.8, 146.1), "DC": (38.7, 39.0, -77.2, -76.9)}


def inside_us(lat: float, lon: float) -> bool:
    return any(a <= lat <= b and c <= lon <= d for a, b, c, d in [*STATE_BBOX.values(), *TERRITORY_BBOX.values()])

# Files in data/sources that are not lists of lookouts.
SKIP_FILES = {"designs_reference.json", "ridb_excluded.json"}

# ---------------------------------------------------------------------------------------
# Source configuration
# ---------------------------------------------------------------------------------------

# Processing order for matching, and the order sources are listed on a tower. Register and
# master-list sources first, so they seed the towers the others attach to. Sources not named
# here (a future extract) are processed last, alphabetically, at the lowest precedence.
SOURCE_ORDER = [
    "nhlr", "fflos", "ffla", "ridb", "fire_lookouts_org", "firelookout_com", "idaho_fl",
    "pa_storymap", "andyarthur_ny", "cskt", "wikidata", "osm",
]

# Field precedence: the first source in the list that has a value wins. Mirrored in DESIGN.md
# 3.5; change both together.
PRECEDENCE: dict[str, list[str]] = {
    "name": ["nhlr", "fflos", "ridb", "ffla", "firelookout_com", "fire_lookouts_org",
             "andyarthur_ny", "pa_storymap", "cskt", "wikidata", "idaho_fl", "osm"],
    "location": ["nhlr", "fflos", "ffla", "fire_lookouts_org", "firelookout_com", "osm",
                 "wikidata", "ridb", "andyarthur_ny", "pa_storymap", "idaho_fl", "cskt"],
    "status": ["ffla", "nhlr", "fflos", "ridb", "fire_lookouts_org", "andyarthur_ny",
               "pa_storymap", "cskt", "firelookout_com", "idaho_fl", "osm", "wikidata"],
    "kind": ["ffla", "nhlr", "fflos", "ridb", "firelookout_com", "fire_lookouts_org",
             "pa_storymap", "andyarthur_ny", "cskt", "osm", "wikidata", "idaho_fl"],
    "county": ["nhlr", "fflos", "ffla", "firelookout_com", "pa_storymap", "cskt",
               "andyarthur_ny", "fire_lookouts_org", "wikidata"],
    "elevation_m": ["nhlr", "fflos", "firelookout_com", "fire_lookouts_org", "ridb",
                    "wikidata", "cskt", "osm"],
    "built": ["nhlr", "fflos", "firelookout_com", "fire_lookouts_org", "pa_storymap", "ridb",
              "wikidata", "cskt", "idaho_fl", "osm", "andyarthur_ny", "ffla"],
    "design": ["nhlr", "fflos", "firelookout_com", "fire_lookouts_org", "pa_storymap", "cskt"],
    "height_m": ["nhlr", "fflos", "firelookout_com", "fire_lookouts_org", "pa_storymap",
                 "cskt", "wikidata", "osm"],
    "agency": ["nhlr", "fflos", "ridb", "firelookout_com", "fire_lookouts_org", "pa_storymap",
               "andyarthur_ny", "cskt", "osm"],
    "ownership": ["cskt", "ridb", "nhlr", "fflos", "andyarthur_ny", "pa_storymap",
                  "fire_lookouts_org", "firelookout_com", "ffla", "osm"],
    "access": ["cskt", "osm"],
    "staffing": ["firelookout_com", "fire_lookouts_org", "cskt", "idaho_fl"],
    "rental": ["ridb"],
    "events": ["nhlr", "fflos", "firelookout_com", "fire_lookouts_org", "pa_storymap", "ridb",
               "wikidata", "cskt", "idaho_fl", "ffla", "osm", "andyarthur_ny"],
    "photos": ["nhlr", "fflos", "firelookout_com", "fire_lookouts_org", "pa_storymap",
               "wikidata", "andyarthur_ny", "idaho_fl", "cskt", "ridb", "osm", "ffla"],
}

# Sources whose positions share a lineage. For verification ("facts" needs two independent
# sources agreeing on location and status) a whole group counts once. NHLR/FFLOS and FFLA
# share lineage (the FFLA tables carry the register numbers); firelookout.com is in the
# group too because 3,173 of its 3,266 coordinates are byte-identical to an FFLA row.
LOCATION_LINEAGE = {"nhlr": "registers", "fflos": "registers", "ffla": "registers",
                    "firelookout_com": "registers"}

# Sources that list one lookout twice (a node and a way in OSM; a Facility and a Campground
# in RIDB; border lookouts on two state maps at firelookout.com; repeated table rows in FFLA;
# repeat posts at idahofirelookouts.com). Two records from one of these may share a tower if
# they are within this many metres and their names agree.
DOUBLE_LISTED = {"ffla": 50, "firelookout_com": 100, "idaho_fl": 100, "osm": 100,
                 "ridb": 300, "wikidata": 100}
# Of those, sources whose duplicates may be unnamed or generically named ("Fire Tower").
DOUBLE_LISTED_GENERIC = {"osm", "wikidata"}

# Sources with approximate positions: never used for location conflicts, and matched with a
# wider radius when the name agrees.
APPROXIMATE = {"cskt"}

# Spatial matching (metres). A candidate is accepted when:
#   names agree strongly (score >= 0.85)            within MATCH_STRONG_M (per source below)
#   names agree partly (0.5 <= score < 0.85),
#     or a name is missing/generic                  within MATCH_NEAR_M
#   names differ (score < 0.5)                      within MATCH_SAME_SPOT_M
# Across a state line only MATCH_NEAR_M with a strong name, or the same spot, is allowed.
MATCH_SAME_SPOT_M = 100
MATCH_NEAR_M = 400
MATCH_STRONG_M = 1500
STRONG_RADIUS_BY_SOURCE = {"idaho_fl": 3000, "ridb": 3000, "cskt": 15000}
NEAR_MISS_M = 10000
REGISTER_FAR_M = 5000
CONFLICT_LOCATION_M = 500
STRONG = 0.85
PARTIAL = 0.5

# Hobbyist and regional sites, with the words used for credits and link labels.
SOURCE_SITE = {
    "ffla": "Forest Fire Lookout Association (firelookout.org)",
    "nhlr": "National Historic Lookout Register (nhlr.org)",
    "fflos": "Former Fire Lookout Sites Register (firetower.org)",
    "ridb": "Recreation.gov",
    "osm": "OpenStreetMap",
    "wikidata": "Wikidata",
    "firelookout_com": "firelookout.com",
    "idaho_fl": "idahofirelookouts.com",
    "pa_storymap": "Fire Towers of Pennsylvania StoryMap (Shawn Lesitsky)",
    "andyarthur_ny": "andyarthur.org",
    "fire_lookouts_org": "fire-lookouts.org (Rich Camp)",
    "cskt": "Confederated Salish and Kootenai Tribes",
}

# Default photo licence per source, where the source states one (None = not stated).
PHOTO_LICENSE = {
    "nhlr": "All rights reserved",
    "fflos": "All rights reserved",
    "andyarthur_ny": "CC BY 3.0",
    "fire_lookouts_org": "Reuse allowed with credit",
    "ridb": "Public domain (US government)",
}

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}

# Out of scope (DESIGN.md 1: structures only).
HIDDEN_KIND_REASON = {
    "tree": "Tree platform: out of scope (structures only)",
    "camp": "Camp or tent site: out of scope (structures only)",
}
# FFLA "Type" values that are a bare lookout point, not a structure.
BARE_POINT_TYPES = {
    "firefinder", "map board", "map boards", "map table", "alidade", "obs pt", "obs. point",
    "open site", "rock cairn", "high point", "obs deck",
}
NEVER_BUILT_STATUS = {"proposed", "planned", "never built"}
NOT_A_LOOKOUT_SECTION = "sites determined not to have been used as wildland fire lookouts"

TOWER_KEYS = [
    "id", "name", "other_names", "country", "region", "county", "location", "elevation_m",
    "kind", "design", "height_m", "status", "registers", "agency", "ownership", "access",
    "staffing", "visit", "rental", "events", "photos", "links", "sources", "conflicts",
    "verification", "locked", "hidden", "hidden_reason", "updated",
]
FIELD_ORDER = [
    "name", "location", "county", "elevation_m", "kind", "design", "height_m", "status",
    "registers", "agency", "ownership", "access", "staffing", "rental", "events", "photos",
    "links",
]

# ---------------------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------------------

# Words that say "this is a lookout" rather than which one. Dropped before comparing names.
GENERIC_WORDS = {
    "lookout", "lookouts", "lo", "fire", "fires", "tower", "towers", "firetower",
    "firetowers", "observation", "obs", "station", "cabin", "house", "ground", "rental", "rec",
    "cupola", "cab", "historic", "site", "former", "the", "of", "and", "complex", "interp",
}
# Topographic words dropped for the "core" comparison (DESIGN: strip Peak/Mountain/Butte),
# mapped to a class so "Mt X" and "X Mountain" still compare as the same kind of feature.
TOPO_WORDS = {"mountain": "mountain", "mount": "mountain", "mountains": "mountain",
              "peak": "peak", "butte": "butte"}
ABBREVIATIONS = {
    "mtn": "mountain", "mtns": "mountains", "mnt": "mountain", "mt": "mount", "pk": "peak",
    "pt": "point", "st": "saint", "ft": "fort", "lk": "lake", "cr": "creek", "ck": "creek",
    "rdg": "ridge", "cyn": "canyon", "spgs": "springs", "hts": "heights", "jct": "junction",
    "n": "north", "s": "south", "e": "east", "w": "west", "firetower": "firetower",
}
# Pairs of words that mark two different places ("North X" is not "South X").
OPPOSITES = [("north", "south"), ("east", "west"), ("upper", "lower"), ("big", "little"),
             ("old", "new"), ("inner", "outer")]
PLACEHOLDER_NAMES = {"unnamed", "unknown", "no name", "none", "?"}
# Trailing words dropped when making a slug ("Dutchman Peak Lookout" -> dutchman-peak).
SLUG_TRAILING = {"lookout", "lookouts", "tower", "fire", "firetower", "lo", "station",
                 "observation", "site", "the"}
# Suffixes a display name may borrow from another source's spelling of the same name.
LOOKOUT_SUFFIXES = ["fire lookout tower", "lookout tower", "fire lookout", "fire tower",
                    "lookout", "firetower"]


def ascii_fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.replace("’", "'").replace("‘", "'").replace("–", "-").replace("—", "-")


_INVERTED_RE = re.compile(r"^(?P<base>[^,()]+?),\s*(?P<lead>mount|mt\.?|the|lake)\b\.?(?P<rest>.*)$", re.I)
_MOJIBAKE_RE = re.compile("[\u00c2-\u00f4][\u0080-\u00bf]")
# Parentheticals that are part of the name, not an alternate name: "(North)", "(#2)", "(62)".
_QUALIFIER_RE = re.compile(r"\((\s*(?:north|south|east|west|upper|lower|middle|#?\s*\d+|no\.?\s*\d+)\s*)\)", re.I)


def fix_mojibake(s: str) -> str:
    """Undo UTF-8 read as Latin-1 ("Brownâ\x80\x99s" -> "Brown’s"), seen in one extract."""
    if _MOJIBAKE_RE.search(s):
        try:
            return s.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return s
    return s


def clean_name(name: str | None) -> str | None:
    """Tidy a source's name for display: "Bigelow, Mount" -> "Mount Bigelow", collapse
    whitespace, title-case names written in capitals. Returns None for placeholders."""
    if name is None:
        return None
    s = re.sub(r"\s+", " ", fix_mojibake(str(name))).strip()
    if not s or s.lower().strip(" .") in PLACEHOLDER_NAMES:
        return None
    m = _INVERTED_RE.match(s)
    if m:
        lead = m.group("lead")
        lead = "Mount" if lead.lower() == "mount" else lead.rstrip(".") + ("." if lead.lower().startswith("mt") else "")
        s = re.sub(r"\s+", " ", f"{lead} {m.group('base').strip()} {m.group('rest').strip()}").strip()
    letters = [c for c in s if c.isalpha()]
    if letters and all(c.isupper() for c in letters) and len(letters) > 3:
        s = smart_title(s)
    return s


def smart_title(s: str) -> str:
    small = {"of", "the", "and", "a", "on", "at", "in"}
    out = []
    for i, word in enumerate(s.lower().split(" ")):
        if i and word in small:
            out.append(word)
            continue
        w = word[:1].upper() + word[1:]
        w = re.sub(r"^(Mc)([a-z])", lambda m: m.group(1) + m.group(2).upper(), w)
        w = re.sub(r"([-/(])([a-z])", lambda m: m.group(1) + m.group(2).upper(), w)
        out.append(w)
    return " ".join(out)


def clean_ridb_name(name: str | None) -> str | None:
    """RIDB facility names carry booking noise: "MCGUIRE MTN. LOOKOUT RENTAL",
    "Cone Peak Lookout - 4E12", "Bald Butte Lookout (Fremont-Winema National Forest, OR)"."""
    s = clean_name(name)
    if not s:
        return s
    s = re.sub(r"\s*\((?:[A-Z]{2}|[^)]*(?:National Forest|Forests?)[^)]*)\)\s*$", "", s)
    s = re.sub(r"\s+-\s+[0-9A-Z]{2,6}$", "", s)
    s = re.sub(r"\b(Rental|Rec|Interp Site|Observation Site)\b", "", s, flags=re.I)
    s = re.sub(r"\b(Mtn)\.?(?=\s|$)", "Mountain", s)
    s = re.sub(r"(?<=[A-Za-z]{4})\.(?=\s)", "", s)  # "Baldy. Lookout"; keeps "Mt."
    s = re.sub(r"\s+", " ", s).strip(" -")
    return s or clean_name(name)


def name_tokens(s: str) -> list[str]:
    s = ascii_fold(s).lower().replace("'", "")
    s = re.sub(r"\bl\.\s*o\.?", " lo ", s)
    s = re.sub(r"\bg\.\s*s\.?(?=\s|$)", " guard station ", s)
    s = re.sub(r"\br\.\s*s\.?(?=\s|$)", " ranger station ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return [ABBREVIATIONS.get(t, t) for t in s.split()]


def name_variants(name: str | None, aliases: list[str] | None = None) -> list[str]:
    """The ways a record names its lookout: the name without any parenthetical, the
    parenthetical itself when it is an alternate name ("Putnam (Liberty)"), each side of a
    slash ("Moore Creek/ Perley Creek"), and any aliases the source lists."""
    out: list[str] = []
    for raw in [name, *(aliases or [])]:
        c = clean_name(raw)
        if not c:
            continue
        c = _QUALIFIER_RE.sub(lambda m: " " + m.group(1).strip() + " ", c)
        main = re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", " ", c)).strip()
        if main:
            out.append(main)
        for paren in re.findall(r"\(([^)]*)\)", c):
            p = paren.strip()
            # "(Relocated Graves Mountain)": the structure's original name
            p = re.sub(r"^relocated\s+(?:from\s+)?(?:near\s+)?", "", p, flags=re.I)
            if p and not re.match(r"^(same as|see\b|railroad|military|unk|\?)", p, re.I):
                out.append(p)
        for part in re.split(r"\s*/\s*", main):
            if part and part != main:
                out.append(part)
    seen, uniq = set(), []
    for v in out:
        if v.lower() not in seen:
            seen.add(v.lower())
            uniq.append(v)
    return uniq


@dataclass(frozen=True)
class NameForm:
    full: str            # expanded, generic lookout words removed: "bald mountain"
    core: str            # also without Peak/Mountain/Butte: "bald"
    topo: tuple          # topographic classes removed from core: ("mountain",)

    @property
    def squash(self) -> str:
        return self.core.replace(" ", "")


def name_form(variant: str) -> NameForm:
    all_toks = name_tokens(variant)
    toks = [t for t in all_toks if t not in GENERIC_WORDS]
    if not [t for t in toks if t not in TOPO_WORDS]:
        # "Lookout Mountain", "Lookout Butte": the generic word is the name. Strip only the
        # trailing generic words ("Lookout Mountain Lookout" -> "lookout mountain").
        toks = list(all_toks)
        while toks and toks[-1] in GENERIC_WORDS:
            toks.pop()
    topo = tuple(sorted({TOPO_WORDS[t] for t in toks if t in TOPO_WORDS}))
    core = " ".join(t for t in toks if t not in TOPO_WORDS)
    return NameForm(" ".join(toks), core, topo)


def name_forms(name: str | None, aliases: list[str] | None = None) -> list[NameForm]:
    return [f for f in (name_form(v) for v in name_variants(name, aliases)) if f.core]


def _pair_score(a: NameForm, b: NameForm) -> float:
    if a.full == b.full:
        return 1.0
    ta, tb = set(a.core.split()), set(b.core.split())
    for x, y in OPPOSITES:
        if (x in ta and y in tb) or (y in ta and x in tb):
            return 0.2
    na, nb = {t for t in ta if t.isdigit()}, {t for t in tb if t.isdigit()}
    if na and nb and na != nb:
        return 0.2
    if a.core == b.core or a.squash == b.squash:
        return 0.95 if (not a.topo or not b.topo or a.topo == b.topo) else 0.85
    ratio = difflib.SequenceMatcher(None, a.squash, b.squash).ratio()
    score = 0.85 if ratio >= 0.9 else ratio * 0.9  # a one-letter slip in a long name is strong
    if ta < tb or tb < ta:
        score = max(score, 0.6)
    return round(score, 3)


def name_score(forms_a: list[NameForm], forms_b: list[NameForm]) -> float | None:
    """Similarity of two lookouts' names, 0..1, or None when either side has no usable name
    (unnamed, or only generic words such as "Fire Tower").

    1.0  same name ("Bald Mtn. L.O." / "Bald Mountain Lookout")
    0.95 same once Peak/Mountain/Butte are dropped ("Abbot Butte" / "Abbot")
    0.85 same core, different feature word ("Dominion Peak" / "Dominion Mountain")
    0.6  one name inside the other ("Bald" / "Bald Knob")
    0.2  opposites or different numbers ("Crescent Lake North" / "Crescent Lake South")
    else 0.9 x the character similarity of the cores
    """
    if not forms_a or not forms_b:
        return None
    return max(_pair_score(a, b) for a in forms_a for b in forms_b)


def slugify(text: str) -> str:
    toks = re.sub(r"[^a-z0-9]+", " ", ascii_fold(text).lower().replace("'", "")).split()
    if name_forms(text):  # a generic name ("Fire Tower") keeps all its words
        while len(toks) > 1 and toks[-1] in SLUG_TRAILING:
            toks.pop()
    slug = "-".join(toks)
    if len(slug) > 80:
        slug = slug[:80].rsplit("-", 1)[0]
    return slug or "lookout"


def has_lookout_word(name: str) -> bool:
    """Does the name already end in a word for the structure ("... Lookout", "... Tower")?"""
    toks = name_tokens(re.sub(r"\([^)]*\)", " ", name))
    return bool(toks) and toks[-1] in {"lookout", "lookouts", "lo", "tower", "towers", "firetower",
                                       "station", "cabin", "house", "cupola", "observatory", "site",
                                       "tree", "platform"}


# ---------------------------------------------------------------------------------------
# Registers
# ---------------------------------------------------------------------------------------

_US_NUM_RE = re.compile(r"^(?:US)?\s*#?\s*(\d+)$", re.I)
_ST_NUM_RE = re.compile(r"^([A-Z]{2})\s*#?\s*(\d+)$", re.I)


def normalize_register(reg: dict) -> dict | None:
    """Canonical register entry: {"register": "NHLR", "number": "US 592",
    "state_number": "OR 23", "url": ...}. Accepts "US 592", "US592", "US #592" and a bare
    "592" (fire-lookouts.org writes NHLR numbers that way). NRHP reference numbers keep
    their digits."""
    if not isinstance(reg, dict):
        return None
    register = str(reg.get("register") or "").strip().upper()
    number = re.sub(r"\s+", " ", str(reg.get("number") or "")).strip()
    state = re.sub(r"\s+", " ", str(reg.get("state_number") or "")).strip()
    if not register or not (number or state):
        return None
    out = {"register": register, "number": None, "state_number": None, "url": reg.get("url") or None}
    if register == "NRHP":
        digits = re.sub(r"\D", "", number)
        if not digits:
            return None
        out["number"] = digits.zfill(8)
        return out
    m = _US_NUM_RE.match(number)
    if m:
        out["number"] = f"US {int(m.group(1))}"
    else:
        sm = _ST_NUM_RE.match(number)
        if sm and not state:
            state = number
        elif number:
            out["number"] = number
    sm = _ST_NUM_RE.match(state)
    if sm:
        out["state_number"] = f"{sm.group(1).upper()} {int(sm.group(2))}"
    if not out["number"] and not out["state_number"]:
        return None
    return out


def register_keys(reg: dict) -> list[str]:
    """Index keys for a normalized register entry. The register name is part of the key:
    NHLR and FFLOS number their entries separately."""
    keys = []
    if reg.get("number"):
        n = reg["number"]
        if reg["register"] == "NRHP":
            n = str(int(n))
        keys.append(f"{reg['register']} {n}")
    if reg.get("state_number"):
        keys.append(f"{reg['register']} {reg['state_number']}")
    return keys


def register_url(reg: dict) -> str | None:
    if reg["register"] == "NRHP" and reg.get("number"):
        return f"https://npgallery.nps.gov/AssetDetail/NRIS/{reg['number']}"
    return None


# ---------------------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------------------

CELL_DEG = 0.05


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))


def cell_of(lat: float, lon: float) -> tuple[int, int]:
    return (math.floor(lat / CELL_DEG), math.floor(lon / CELL_DEG))


def cells_around(lat: float, lon: float, radius_m: float) -> list[tuple[int, int]]:
    cy, cx = cell_of(lat, lon)
    span_lat = math.ceil(radius_m / (CELL_DEG * 111_000)) or 1
    span_lon = math.ceil(radius_m / (CELL_DEG * 111_000 * max(0.2, math.cos(math.radians(lat))))) or 1
    return [(cy + dy, cx + dx) for dy in range(-span_lat, span_lat + 1) for dx in range(-span_lon, span_lon + 1)]


def round_coord(x: float) -> float:
    return round(float(x), 6)


# ---------------------------------------------------------------------------------------
# Working objects
# ---------------------------------------------------------------------------------------


def _num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


@dataclass(eq=False)
class Rec:
    source: str
    raw: dict
    order: int
    key: str = ""
    region: str | None = None
    lat: float | None = None
    lon: float | None = None
    display: str | None = None
    forms: list = field(default_factory=list)
    registers: list = field(default_factory=list)
    reg_keys: list = field(default_factory=list)
    match: str | None = None        # how it was matched: key/register/spatial/name/new
    match_note: str | None = None
    bad_coords: str | None = None   # why the source's coordinates were not used, if so

    @classmethod
    def build(cls, source: str, raw: dict, order: int) -> "Rec":
        r = cls(source, raw, order)
        r.key = str(raw.get("key") or "")
        r.region = (raw.get("region") or None) and str(raw["region"]).upper()
        if _num(raw.get("lat")) and _num(raw.get("lon")) and (raw["lat"], raw["lon"]) != (0, 0):
            lat, lon = float(raw["lat"]), float(raw["lon"])
            if inside_us(lat, lon):
                r.lat, r.lon = lat, lon
                if r.region and r.region in STATE_BBOX and flag_coordinate(r.region, lat, lon):
                    r.bad_coords = "outside_state"
            else:
                r.bad_coords = "outside_us"   # e.g. latitude copied from longitude
        extra = raw.get("extra") or {}
        aliases = []
        for k in ("aliases", "alt_name", "old_name"):
            v = extra.get(k)
            if isinstance(v, str):
                aliases.extend(x.strip() for x in v.split(";") if x.strip())
            elif isinstance(v, list):
                aliases.extend(str(x) for x in v if x)
        r.display = clean_ridb_name(raw.get("name")) if source == "ridb" else clean_name(raw.get("name"))
        r.forms = name_forms(raw.get("name"), aliases)
        regs = [normalize_register(g) for g in raw.get("registers") or []]
        r.registers = [g for g in regs if g]
        r.reg_keys = sorted({k for g in r.registers for k in register_keys(g)})
        return r

    @property
    def has_coords(self) -> bool:
        return self.lat is not None

    @property
    def extra(self) -> dict:
        return self.raw.get("extra") or {}

    @property
    def coordinate_problem(self) -> bool:
        """The source flags the row, or the point is outside the record's own state."""
        return bool(self.extra.get("coordinate_problem")) or self.bad_coords is not None

    def dist(self, other: "Rec") -> float | None:
        if self.lat is None or other.lat is None:
            return None
        return haversine_m(self.lat, self.lon, other.lat, other.lon)


@dataclass(eq=False)
class Tower:
    seq: int
    existing: dict | None = None
    path: Path | None = None
    id: str | None = None
    members: list = field(default_factory=list)
    old_forms: list = field(default_factory=list)
    old_point: tuple | None = None
    old_region: str | None = None

    @property
    def sources(self) -> set:
        return {m.source for m in self.members}

    def points(self) -> list[tuple[float, float]]:
        pts = [(m.lat, m.lon) for m in self.members if m.has_coords]
        if not pts and self.old_point:
            pts = [self.old_point]
        return pts

    def forms(self) -> list:
        out = list(self.old_forms)
        for m in self.members:
            out.extend(m.forms)
        return out

    def regions(self) -> set:
        regs = {m.region for m in self.members if m.region}
        if self.old_region:
            regs.add(self.old_region)
        return regs

    def min_dist(self, lat: float, lon: float) -> float | None:
        pts = self.points()
        if not pts:
            return None
        return min(haversine_m(lat, lon, a, b) for a, b in pts)


def is_relocated(rec: Rec) -> bool:
    text = f"{rec.raw.get('name') or ''} {rec.extra.get('section') or ''}".lower()
    return "relocated" in text or "replica" in text


def precedence(field_name: str, sources: list[str]) -> list[str]:
    order = list(PRECEDENCE.get(field_name, SOURCE_ORDER))
    extra = sorted(set(sources) - set(order))
    return order + extra


def source_rank(field_name: str, source: str) -> int:
    order = PRECEDENCE.get(field_name, SOURCE_ORDER)
    return order.index(source) if source in order else len(order) + 1


def global_rank(source: str) -> tuple:
    return (SOURCE_ORDER.index(source), "") if source in SOURCE_ORDER else (len(SOURCE_ORDER), source)


# ---------------------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------------------


def load_sources(sources_dir: Path, log=print) -> tuple[dict[str, dict], dict[str, list[Rec]]]:
    headers: dict[str, dict] = {}
    records: dict[str, list[Rec]] = {}
    for path in sorted(sources_dir.glob("*.json")):
        if path.name in SKIP_FILES:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            log(f"WARNING: skipped {path.name}: {e}")
            continue
        if not isinstance(data, dict) or not isinstance(data.get("records"), list):
            continue
        sid = str(data.get("source") or path.stem)
        headers[sid] = {k: data.get(k) for k in ("title", "url", "retrieved", "license")}
        headers[sid]["file"] = path.name
        headers[sid]["records"] = len(data["records"])
        recs, seen = [], set()
        for i, raw in enumerate(data["records"]):
            if not isinstance(raw, dict) or not raw.get("key"):
                continue
            if raw["key"] in seen:
                log(f"WARNING: {sid}: duplicate key {raw['key']} skipped")
                continue
            seen.add(raw["key"])
            recs.append(Rec.build(sid, raw, i))
        recs.sort(key=lambda r: r.key)
        records[sid] = recs
    return headers, records


def load_towers(towers_dir: Path, log=print) -> list[tuple[Path, dict]]:
    out = []
    if not towers_dir.is_dir():
        return out
    for path in sorted(towers_dir.rglob("*.json")):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise SystemExit(f"Cannot read existing tower {path}: {e}. Fix it before merging.")
        if not isinstance(rec, dict) or not isinstance(rec.get("id"), str):
            raise SystemExit(f"Existing tower {path} has no id. Fix it before merging.")
        out.append((path, rec))
    return out


# ---------------------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------------------


class Matcher:
    def __init__(self, log=print) -> None:
        self.log = log
        self.towers: list[Tower] = []
        self.by_key: dict[str, Tower] = {}
        self.by_register: dict[str, Tower] = {}
        self.register_clash: list[dict] = []
        self.grid: dict[tuple, set] = defaultdict(set)
        self.by_region: dict[str, set] = defaultdict(set)
        self.unplaced: list[Rec] = []
        self.deferred: list[Rec] = []
        self.review: list[dict] = []
        self.stats: Counter = Counter()

    # -- index maintenance --------------------------------------------------------------

    def new_tower(self, existing: dict | None = None, path: Path | None = None) -> Tower:
        t = Tower(seq=len(self.towers), existing=existing, path=path)
        if existing:
            t.id = existing["id"]
            names = [existing.get("name")] + list(existing.get("other_names") or [])
            t.old_forms = [f for n in names if isinstance(n, str) for f in name_forms(n)]
            loc = existing.get("location") or {}
            if _num(loc.get("lat")) and _num(loc.get("lon")):
                t.old_point = (float(loc["lat"]), float(loc["lon"]))
                self.grid[cell_of(*t.old_point)].add(t)
            if existing.get("region"):
                t.old_region = str(existing["region"]).upper()
                self.by_region[t.old_region].add(t)
            for s in existing.get("sources") or []:
                if isinstance(s, dict) and s.get("key"):
                    self.by_key.setdefault(str(s["key"]), t)
            for g in existing.get("registers") or []:
                ng = normalize_register(g)
                if ng:
                    for k in register_keys(ng):
                        self.by_register.setdefault(k, t)
        self.towers.append(t)
        return t

    def attach(self, rec: Rec, tower: Tower, how: str, note: str | None = None) -> None:
        rec.match, rec.match_note = how, note
        tower.members.append(rec)
        self.stats[f"matched_{how}"] += 1
        self.by_key[rec.key] = tower
        if rec.has_coords:
            self.grid[cell_of(rec.lat, rec.lon)].add(tower)
        if rec.region:
            self.by_region[rec.region].add(tower)
        for k in rec.reg_keys:
            holder = self.by_register.get(k)
            if holder is None:
                self.by_register[k] = tower
            elif holder is not tower:
                self.register_clash.append({"register": k, "towers": [holder.seq, tower.seq], "key": rec.key})

    def register_hits(self, r: Rec) -> set:
        """Towers sharing a register number with the record. US numbers decide; state numbers
        ("WI 49") are used only when no US number matches, since FFLA's state-number column
        is out of step with its US numbers in places."""
        us = {self.by_register[k] for k in r.reg_keys if " US " in k and k in self.by_register}
        if us:
            return us
        return {self.by_register[k] for k in r.reg_keys if k in self.by_register}

    # -- same-source rule ---------------------------------------------------------------

    @staticmethod
    def double_listed(a: Rec, b: Rec) -> bool:
        """May two records from one source describe the same lookout?"""
        limit = DOUBLE_LISTED.get(a.source)
        if limit is None or a.source != b.source:
            return False
        d = a.dist(b)
        if d is None or d > limit:
            return False
        score = name_score(a.forms, b.forms)
        if score is None:
            return a.source in DOUBLE_LISTED_GENERIC and d <= 50
        if score < STRONG:
            return False
        for reg in ("NHLR", "FFLOS"):
            ka = {k for k in a.reg_keys if k.startswith(reg + " US ")}
            kb = {k for k in b.reg_keys if k.startswith(reg + " US ")}
            if ka and kb and not (ka & kb):
                return False
        return True

    def can_join(self, rec: Rec, tower: Tower) -> bool:
        same = [m for m in tower.members if m.source == rec.source]
        return all(self.double_listed(rec, m) for m in same)

    # -- candidate scoring --------------------------------------------------------------

    def candidates(self, rec: Rec) -> list[tuple]:
        """(rank, distance, tower, score) for every tower this record may join."""
        strong_r = STRONG_RADIUS_BY_SOURCE.get(rec.source, MATCH_STRONG_M)
        seen: set = set()
        out = []
        for c in cells_around(rec.lat, rec.lon, max(strong_r, MATCH_NEAR_M)):
            for t in self.grid.get(c, ()):
                if t in seen:
                    continue
                seen.add(t)
                d = t.min_dist(rec.lat, rec.lon)
                if d is None:
                    continue
                score = name_score(rec.forms, t.forms())
                same_region = rec.region is None or not t.regions() or rec.region in t.regions()
                if same_region:
                    ok = (
                        (score is not None and score >= STRONG and d <= strong_r)
                        or ((score is None or score >= PARTIAL) and d <= MATCH_NEAR_M)
                        or d <= MATCH_SAME_SPOT_M
                    )
                else:
                    ok = (score is not None and score >= STRONG and d <= MATCH_NEAR_M) or d <= MATCH_SAME_SPOT_M
                if not ok:
                    continue
                eff = 0.7 if score is None else score
                # a structure record prefers a tower that is not a tree/camp row at the same spot
                kinds = {m.raw.get("kind") for m in t.members} - {None, "unknown"}
                penalty = 1 if (rec.raw.get("kind") not in (None, "unknown", "tree", "camp")
                                and kinds and kinds <= {"tree", "camp"}) else 0
                out.append((-eff, penalty, d, t, score, same_region))
        return out

    def place_without_coords(self) -> None:
        """Records with no coordinates, once every source is in: a register number, else a
        unique same-name tower in the same state (and county, when both give one)."""
        order = {s: i for i, s in enumerate(SOURCE_ORDER)}
        for r in sorted(self.deferred, key=lambda x: (order.get(x.source, len(order)), x.source, x.key)):
            hits = self.register_hits(r)
            if len(hits) == 1 and self.can_join(r, next(iter(hits))):
                self.attach(r, next(iter(hits)), "register")
                continue
            cands = []
            county = record_county(r)
            for t in self.by_region.get(r.region or "", ()):
                s = name_score(r.forms, t.forms())
                if s is None or s < 0.95:
                    continue
                tcounties = {c.lower() for c in (record_county(m) for m in t.members) if c}
                if county and tcounties and county.lower() not in tcounties:
                    continue
                if self.can_join(r, t):
                    cands.append(t)
            if len(cands) == 1:
                self.attach(r, cands[0], "name")
            else:
                section = str(r.extra.get("section") or "")
                if section.startswith("(Border"):
                    r.match_note = f"no coordinates; FFLA border pointer {section}"
                else:
                    r.match_note = "no coordinates; " + ("several same-name lookouts in the state" if cands else "no same-name lookout in the state")
                self.unplaced.append(r)
        self.deferred = []

    # -- per-source pass ----------------------------------------------------------------

    def match_source(self, source: str, recs: list[Rec]) -> None:
        pending: list[Rec] = []
        # 1. key
        for r in recs:
            t = self.by_key.get(r.key)
            if t is not None:
                self.attach(r, t, "key")
            else:
                pending.append(r)
        # 2. register
        rest = []
        for r in pending:
            hits = self.register_hits(r)
            if len(hits) == 1:
                t = next(iter(hits))
                if self.can_join(r, t):
                    note = None
                    d = t.min_dist(r.lat, r.lon) if r.has_coords and not r.coordinate_problem else None
                    if d is not None and d > REGISTER_FAR_M:
                        local = sorted((c for c in self.candidates(r) if c[3] is not t and self.can_join(r, c[3])),
                                       key=lambda c: (c[0], c[1], c[2], c[3].seq))
                        if is_relocated(r):
                            # a moved structure keeps its register number; its new site is its own entry
                            self.review.append({"type": "register_match_far_relocated", "key": r.key, "tower_seq": t.seq,
                                                "distance_m": round(d), "registers": r.reg_keys})
                            rest.append(r)
                            continue
                        if local:
                            self.review.append({"type": "register_match_far_skipped", "key": r.key, "tower_seq": t.seq,
                                                "distance_m": round(d), "registers": r.reg_keys,
                                                "nearby_tower_seq": local[0][3].seq})
                            rest.append(r)
                            continue
                        note = f"register match {round(d / 1000, 1)} km away"
                        self.review.append({"type": "register_match_far", "key": r.key, "tower_seq": t.seq,
                                            "distance_m": round(d), "registers": r.reg_keys})
                    self.attach(r, t, "register", note)
                    continue
            elif len(hits) > 1:
                self.review.append({"type": "register_ambiguous", "key": r.key, "registers": r.reg_keys,
                                    "tower_seqs": sorted(t.seq for t in hits)})
            rest.append(r)
        # 3. spatial: greedy one-to-one over all (record, tower) pairs, best name first.
        pairs = []
        for r in rest:
            if r.has_coords:
                for neg_eff, penalty, d, t, score, same_region in self.candidates(r):
                    pairs.append((neg_eff, penalty, d, r.key, t.seq, r, t, score, same_region))
        pairs.sort(key=lambda p: p[:5])
        done: set = set()
        for neg_eff, penalty, d, _, _, r, t, score, same_region in pairs:
            if r.key in done or not self.can_join(r, t):
                continue
            note = None
            if score is not None and score < PARTIAL:
                note = "same spot, different names"
                self.review.append({"type": "matched_different_names", "key": r.key, "tower_seq": t.seq,
                                    "distance_m": round(d), "score": score})
            if not same_region:
                note = (note + "; " if note else "") + "across a state line"
                self.stats["matched_cross_region"] += 1
            self.attach(r, t, "spatial", note)
            done.add(r.key)
        unmatched = [r for r in rest if r.key not in done]
        # 4. records with no coordinates wait for place_without_coords(), after every source
        leftover = []
        for r in unmatched:
            (leftover if r.has_coords else self.deferred).append(r)
        # 5. new towers, joining same-source double listings into one
        groups: list[list[Rec]] = []
        near: dict[tuple, list] = defaultdict(list)
        limit = DOUBLE_LISTED.get(source)
        for r in sorted(leftover, key=lambda x: x.key):
            home = None
            if limit is not None:
                for c in cells_around(r.lat, r.lon, limit):
                    for g in near.get(c, ()):
                        if all(self.double_listed(r, m) for m in g):
                            home = g
                            break
                    if home is not None:
                        break
            if home is None:
                home = []
                groups.append(home)
            home.append(r)
            near[cell_of(r.lat, r.lon)].append(home)
        for g in groups:
            t = self.new_tower()
            for i, r in enumerate(g):
                self.attach(r, t, "new" if i == 0 else "spatial", None if i == 0 else "listed twice by the source")


# ---------------------------------------------------------------------------------------
# Resolving a tower's fields
# ---------------------------------------------------------------------------------------


def status_group(s: str | None) -> str | None:
    if not s or s == "unknown":
        return None
    return {"ruins": "gone", "replica": "standing"}.get(s, s)


def record_status(rec: Rec) -> str | None:
    """The record's status claim, or None. An OSM feature imported from GNIS (it carries
    gnis:feature_id) marks where a lookout is or was, not that it stands: FFLA calls 70 of the
    215 such "standing" features gone, against 19 of 388 for hand-mapped ones."""
    st = rec.raw.get("status")
    if st in (None, "unknown"):
        return None
    if rec.source == "osm" and st == "standing" and rec.extra.get("gnis_feature_id"):
        return None
    if st == "standing" and re.search(r"\breplica\b", str(rec.raw.get("name") or ""), re.I):
        return "replica"  # FFLA: "Kellogg Peak (Replica)"
    return st


def record_built(rec: Rec) -> int | None:
    years = [e.get("year") for e in rec.raw.get("events") or []
             if isinstance(e, dict) and e.get("event") == "built" and isinstance(e.get("year"), int)]
    b = rec.raw.get("built")
    if isinstance(b, int) and not isinstance(b, bool):
        years.append(b)
    return min(years) if years else None


def record_height(rec: Rec) -> float | None:
    ex = rec.extra
    if _num(ex.get("height_m")):
        return round(float(ex["height_m"]), 1)
    if _num(ex.get("height_ft")):
        return round(float(ex["height_ft"]) * 0.3048, 1)
    return None


FEDERAL_RE = re.compile(r"national forest|forest service|usfs|u\.s\.? forest|bureau of land management|\bblm\b|"
                        r"national park|fish (?:&|and) wildlife|national wildlife refuge|\bnwr\b", re.I)
TRIBAL_RE = re.compile(r"\btrib(?:e|es|al)\b|indian reservation|\bnation\b|confederated", re.I)
STATE_RE = re.compile(r"\bstate forest\b|\bstate park\b|\bny ?dec\b|\bdcnr\b", re.I)


def record_ownership(rec: Rec) -> str | None:
    own = rec.extra.get("ownership")
    if own in ("federal", "state", "tribal", "local", "private"):
        return own
    agency = rec.raw.get("agency") or ""
    if not agency:
        return None
    if rec.source == "ridb" and FEDERAL_RE.search(agency):
        return "federal"
    if rec.source in ("nhlr", "fflos", "ridb", "cskt"):
        if TRIBAL_RE.search(agency):
            return "tribal"
        if FEDERAL_RE.search(agency) and "/" not in agency:
            return "federal"
        if STATE_RE.search(agency):
            return "state"
    if rec.source == "firelookout_com" and agency.strip().lower() == "private":
        return "private"
    return None


def record_ownership_any(rec: Rec) -> str | None:
    # FFLA's status column says "Private" for a few towers: an explicit ownership statement.
    if rec.source == "ffla" and str(rec.raw.get("status_raw") or "").strip().lower() == "private":
        return "private"
    return record_ownership(rec)


def record_access(rec: Rec) -> dict | None:
    if rec.source == "cskt" or (rec.extra.get("permission") and rec.extra.get("ownership") == "tribal"):
        return {"level": "permission",
                "note": "On the Flathead Reservation. Ask the Confederated Salish and Kootenai Tribes before visiting."}
    if rec.source == "osm" and rec.extra.get("access"):
        # OSM's access tag describes the structure, often only the cab ("private" on a staffed
        # Forest Service lookout), not the land, so it does not set the level. Kept as a note.
        return {"level": "unknown", "note": f"OpenStreetMap tags the structure access={rec.extra['access']}."}
    return None


def record_county(rec: Rec) -> str | None:
    c = rec.raw.get("county")
    if not isinstance(c, str) or not c.strip():
        return None
    c = re.sub(r"\s+(County|Parish|Borough)$", "", c.strip(), flags=re.I)
    return c or None


def photo_entry(rec: Rec, p: dict) -> dict | None:
    if not isinstance(p, dict):
        return None
    url = p.get("url")
    source_url = p.get("source_url") or rec.raw.get("url")
    if rec.source == "wikidata" and isinstance(url, str) and "/wiki/File:" in url:
        source_url = url
        fname = url.split("/wiki/File:", 1)[1]
        url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{fname}?width=1280"
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return None
    site = SOURCE_SITE.get(rec.source, rec.source)
    credit = p.get("credit")
    if rec.source == "wikidata":
        credit = credit or "Wikimedia Commons contributors"
        if "commons" not in credit.lower():
            credit += ", via Wikimedia Commons"
    elif credit:
        short = site.split(" (")[0].lower()
        if short not in credit.lower() and rec.source not in ("pa_storymap",):
            credit = f"{credit}, via {site}"
    else:
        credit = site
    year = p.get("year") if isinstance(p.get("year"), int) else None
    return {
        "file": None,
        "thumb": None,
        "url": url,
        "source_url": source_url,
        "credit": credit,
        "license": p.get("license") or PHOTO_LICENSE.get(rec.source),
        "caption": p.get("caption") or None,
        "year": year,
    }


def _wiki_title(url: str) -> str:
    return unquote(url.rstrip("/").rsplit("/", 1)[-1]).replace("_", " ")


def record_links(rec: Rec) -> list[dict]:
    """Link to the record's own page, labelled for credit, plus the links the source gives."""
    out: list[dict] = []
    raw, src = rec.raw, rec.source
    url = raw.get("url")
    name = rec.display or "this lookout"
    state = STATE_NAMES.get(rec.region or "", rec.region or "")
    reg = rec.registers[0] if rec.registers else None
    if url:
        if src == "ffla":
            out.append({"label": f"FFLA {state} lookout list (firelookout.org)".replace("  ", " "), "url": url, "kind": "association"})
        elif src in ("nhlr", "fflos"):
            num = f" {reg['number']}" if reg and reg.get("number") else ""
            host = "nhlr.org" if src == "nhlr" else "firetower.org"
            out.append({"label": f"{src.upper()} register entry{num} ({host})", "url": url, "kind": "register"})
        elif src == "ridb":
            out.append({"label": "Recreation.gov listing", "url": url, "kind": "rental"})
        elif src == "osm":
            obj = url.rstrip("/").rsplit("/", 2)[-2:]
            out.append({"label": f"OpenStreetMap {' '.join(obj)}", "url": url, "kind": "osm"})
        elif src == "wikidata":
            out.append({"label": f"Wikidata item {url.rstrip('/').rsplit('/', 1)[-1]}", "url": url, "kind": "wikidata"})
        elif src == "firelookout_com":
            out.append({"label": f"{name} on firelookout.com (Rex Kamstra)", "url": url, "kind": "site"})
        elif src == "idaho_fl":
            out.append({"label": f"{name} on idahofirelookouts.com", "url": url, "kind": "site"})
        elif src == "fire_lookouts_org":
            out.append({"label": f"{name} on fire-lookouts.org (Rich Camp)", "url": url, "kind": "site"})
        elif src == "pa_storymap":
            out.append({"label": "Fire Towers of Pennsylvania StoryMap (Shawn Lesitsky)", "url": url, "kind": "site"})
        elif src == "andyarthur_ny":
            out.append({"label": f"{name} on andyarthur.org (Andy Arthur)", "url": url, "kind": "site"})
        elif src == "cskt":
            out.append({"label": "CSKT Fire on the Land: fire lookouts", "url": url, "kind": "agency"})
        else:
            out.append({"label": f"{name} ({SOURCE_SITE.get(src, src)})", "url": url, "kind": "site"})
    for link in raw.get("links") or []:
        if not isinstance(link, dict) or not isinstance(link.get("url"), str):
            continue
        lurl, label, kind = link["url"], str(link.get("label") or "").strip(), link.get("kind")
        low = label.lower()
        host = urlsplit(lurl).netloc.lower()
        if "wikipedia.org" in host:
            out.append({"label": f"Wikipedia: {_wiki_title(lurl)}", "url": lurl, "kind": "wikipedia"})
        elif "wikidata.org" in host:
            out.append({"label": f"Wikidata item {lurl.rstrip('/').rsplit('/', 1)[-1]}", "url": lurl, "kind": "wikidata"})
        elif "commons.wikimedia.org" in host:
            out.append({"label": "Wikimedia Commons", "url": lurl, "kind": "commons"})
        elif "nhlr.org" in host or ("register" in low and "nhlr" in low):
            num = next((g["number"] for g in rec.registers if g["register"] == "NHLR" and g.get("number")), None)
            out.append({"label": f"NHLR register entry{' ' + num if num else ''} (nhlr.org)", "url": lurl, "kind": "register"})
        elif "firetower.org" in host or ("register" in low and "fflos" in low):
            num = next((g["number"] for g in rec.registers if g["register"] == "FFLOS" and g.get("number")), None)
            out.append({"label": f"FFLOS register entry{' ' + num if num else ''} (firetower.org)", "url": lurl, "kind": "register"})
        elif kind == "category":
            continue  # a regional index page, not about this lookout
        elif src == "osm" and low == "website":
            out.append({"label": f"Website ({host.removeprefix('www.')})", "url": lurl, "kind": "website"})
        elif lurl == url:
            continue
        else:
            out.append({"label": label or host, "url": lurl, "kind": kind or ("agency" if src in ("ridb", "cskt") else "site")})
    return out


def link_norm(url: str) -> str:
    p = urlsplit(url.strip())
    host = p.netloc.lower().removeprefix("www.")
    path = p.path.rstrip("/") or "/"
    return f"{host}{path}?{p.query}" if p.query else f"{host}{path}"


LINK_KIND_ORDER = ["register", "rental", "association", "wikipedia", "site", "agency", "website",
                   "category", "commons", "wikidata", "osm"]


def pick(field_name: str, members: list[Rec], getter) -> tuple[object, Rec | None]:
    """First value from the members in the field's precedence order (ties by key)."""
    for m in sorted(members, key=lambda m: (source_rank(field_name, m.source), m.key)):
        v = getter(m)
        if v is not None:
            return v, m
    return None, None


def location_of(m: Rec):
    if not m.has_coords:
        return None
    return (m.lat, m.lon)


def lineage(source: str) -> str:
    return LOCATION_LINEAGE.get(source, source)


def corroborated(m: Rec, members: list[Rec]) -> bool:
    """Does a source of another lineage put the lookout within 500 m of this record?"""
    return any(o.has_coords and o.source not in APPROXIMATE and lineage(o.source) != lineage(m.source)
               and haversine_m(m.lat, m.lon, o.lat, o.lon) <= CONFLICT_LOCATION_M for o in members)


def location_pick(members: list[Rec]):
    """Location by precedence ("corroborated precedence"): the best source wins, unless its
    position is confirmed by no other lineage and lies over 500 m from a position that is.
    Then the best corroborated position wins (NHLR's Taylor Mountain, ID sits 253 km from
    its own county; FFLA's position there is confirmed by idahofirelookouts.com). Rows the
    source itself flags as outside its state are used only as a last resort."""
    good = [m for m in members if m.has_coords and not m.coordinate_problem]
    v, m = pick("location", good, location_of)
    if v is None:
        return pick("location", members, location_of)
    if not corroborated(m, good):
        backed = [o for o in good if corroborated(o, good)
                  and haversine_m(m.lat, m.lon, o.lat, o.lon) > CONFLICT_LOCATION_M]
        if backed:
            v, m = pick("location", backed, location_of)
    return v, m


def precision_of(m: Rec) -> str:
    if m.source in APPROXIMATE or m.coordinate_problem:
        return "approximate"
    if round(m.lat, 2) == m.lat and round(m.lon, 2) == m.lon:
        return "approximate"
    return "exact"


def display_name(members: list[Rec]) -> tuple[str | None, Rec | None]:
    named = [m for m in members if m.display and m.forms]
    v, m = pick("name", named, lambda m: m.display)
    if v is None:
        v, m = pick("name", [m for m in members if m.display], lambda m: m.display)
    if v is None:
        return None, None
    # Borrow "Lookout"/"Fire Tower" from another source's spelling of the same name, but never
    # invent a suffix no source uses.
    if not has_lookout_word(v):
        base = " ".join(name_tokens(v))
        for other in sorted(members, key=lambda x: (source_rank("name", x.source), x.key)):
            if not other.display or other is m:
                continue
            otoks = " ".join(name_tokens(re.sub(r"\([^)]*\)", " ", other.display)))
            for suffix in LOOKOUT_SUFFIXES:
                if otoks == f"{base} {suffix}":
                    return f"{v} {smart_title(suffix) if suffix != 'firetower' else 'Firetower'}", m
    return v, m


def loose_key(name: str) -> str:
    toks = [t for t in name_tokens(name) if t not in GENERIC_WORDS or t in ("ground", "house", "cabin")]
    return " ".join(toks)


def resolve(tower: Tower, today: str, headers: dict) -> dict:
    """Compute the canonical record for a tower from its member source records."""
    ex = tower.existing or {}
    rec: dict = copy.deepcopy(ex) if ex else {}
    locked = set(ex.get("locked") or []) if isinstance(ex.get("locked"), list) else set()
    members = sorted(tower.members, key=lambda m: (global_rank(m.source), m.key))
    contributed: dict[str, set] = defaultdict(set)

    def set_field(name: str, value, src: Rec | None = None, *, keep_existing_if_none: bool = True) -> None:
        if name in locked:
            return
        if value is None and keep_existing_if_none and name in rec:
            return
        rec[name] = value
        if src is not None and value is not None:
            contributed[src.key].add(name)

    # Name and other names
    name, name_src = display_name(members)
    if name is None and "name" not in rec:
        name = "Unnamed lookout"
    set_field("name", name, name_src)
    if "other_names" not in locked:
        current = rec.get("name") or ""
        seen = {loose_key(current)}
        others = []
        old = [n for n in (ex.get("other_names") or []) if isinstance(n, str)]
        cand = []
        for m in sorted(members, key=lambda m: (source_rank("name", m.source), m.key)):
            if m.display:
                cand.append(m.display)
            for k in ("aliases", "alt_name", "old_name"):
                v = m.extra.get(k)
                if isinstance(v, str):
                    cand.extend(x.strip() for x in v.split(";"))
                elif isinstance(v, list):
                    cand.extend(str(x) for x in v)
        for n in cand + old:
            n = clean_name(n)
            if not n or not name_forms(n):
                continue
            k = loose_key(n)
            if k in seen or any(difflib.SequenceMatcher(None, k, o).ratio() >= 0.93 for o in seen):
                continue  # same name, or a one-letter typo of one ("Lookouut")
            seen.add(k)
            others.append(n)
        rec["other_names"] = others

    rec["country"] = rec.get("country") or "US"

    # Location and region
    loc, loc_src = location_pick(members)
    if loc is not None and "location" not in locked:
        rec["location"] = {"lat": round_coord(loc[0]), "lon": round_coord(loc[1]),
                           "precision": precision_of(loc_src), "from": loc_src.source}
        contributed[loc_src.key].add("location")
    if "region" not in locked:
        region_src = loc_src or next((m for m in members if m.region), None)
        if region_src and region_src.region:
            rec["region"] = region_src.region
        elif tower.old_region:
            rec["region"] = tower.old_region

    v, s = pick("county", members, record_county)
    set_field("county", v, s)
    v, s = pick("elevation_m", members, lambda m: round(float(m.raw["elevation_m"]), 1) if _num(m.raw.get("elevation_m")) else None)
    set_field("elevation_m", v, s)
    v, s = pick("kind", members, lambda m: m.raw.get("kind") if m.raw.get("kind") not in (None, "unknown") else None)
    if v is None and "kind" not in rec:
        v = "unknown"
    set_field("kind", v, s)
    v, s = pick("design", members, lambda m: (m.extra.get("design") or None) if isinstance(m.extra.get("design"), str) else None)
    set_field("design", v, s)
    v, s = pick("height_m", members, record_height)
    set_field("height_m", v, s)
    status, status_src = pick("status", members, record_status)
    if status is None and "status" not in rec:
        status = "unknown"
    set_field("status", status, status_src)

    # Registers: union, with the register's own page as the url where we have it.
    if "registers" not in locked:
        merged: dict[tuple, dict] = {}
        order: list[tuple] = []
        authority = {m.source.upper(): {g.get("number") for g in m.registers if g["register"] == m.source.upper()}
                     for m in members if m.source in ("nhlr", "fflos")}
        reg_disagree: dict[str, list] = defaultdict(list)
        for m in sorted(members, key=lambda m: (global_rank(m.source), m.key)):
            for g in m.registers:
                own = authority.get(g["register"])
                if own and m.source.upper() != g["register"] and g.get("number") and g.get("number") not in own:
                    # the register's own page wins over another source's copy of its number
                    reg_disagree[g["register"]].append({"source": m.source, "value": g["number"]})
                    continue
                k = (g["register"], g.get("number") or g.get("state_number"))
                cur = merged.get(k)
                if cur is None:
                    cur = {"register": g["register"], "number": g.get("number"), "state_number": g.get("state_number"), "url": None}
                    merged[k] = cur
                    order.append(k)
                cur["state_number"] = cur["state_number"] or g.get("state_number")
                url = None
                if m.source in ("nhlr", "fflos") and m.source.upper() == g["register"]:
                    url = m.raw.get("url")
                if not url:
                    for link in m.raw.get("links") or []:
                        if isinstance(link, dict) and link.get("kind") == "register" and g["register"].lower() in str(link.get("label", "")).lower():
                            url = link.get("url")
                            break
                url = url or g.get("url") or register_url(g)
                if url and (not cur["url"] or (m.source in ("nhlr", "fflos"))):
                    cur["url"] = url
                contributed[m.key].add("registers")
        reg_rank = {"NHLR": 0, "FFLOS": 1, "NRHP": 2}
        regs = [merged[k] for k in order]
        regs.sort(key=lambda g: (reg_rank.get(g["register"], 9), g["register"], g.get("number") or ""))
        if regs or "registers" not in rec:
            rec["registers"] = regs
        tower_reg_conflicts = [
            {"field": "registers",
             "values": [{"source": reg.lower(), "value": n} for n in sorted(n for n in authority[reg] if n)] + vals,
             "distance_m": None,
             "note": f"Another source gives a different {reg} number; the register's own entry is used."}
            for reg, vals in sorted(reg_disagree.items())
        ]
    else:
        tower_reg_conflicts = []

    v, s = pick("agency", members, lambda m: (m.raw.get("agency") or "").strip() or None)
    set_field("agency", v, s)
    v, s = pick("ownership", members, record_ownership_any)
    if v is None and "ownership" not in rec:
        v = "unknown"
    set_field("ownership", v, s)

    if "access" not in locked:
        acc, acc_src = pick("access", members, record_access)
        if acc is None and rec.get("ownership") == "tribal":
            acc = {"level": "permission", "note": "On tribal land. Ask the tribe before visiting."}
            acc_src = s
        if acc is not None:
            rec["access"] = acc
            if acc_src is not None:
                contributed[acc_src.key].add("access")
        elif not isinstance(rec.get("access"), dict):
            rec["access"] = {"level": "unknown", "note": None}

    if "staffing" not in locked:
        st, st_src = pick("staffing", members, lambda m: m.extra.get("staffing_hint") if m.extra.get("staffing_hint") in ("staffed", "emergency", "volunteer", "unstaffed") else None)
        if st is not None:
            rec["staffing"] = {"status": st, "as_of": None}
            contributed[st_src.key].add("staffing")
        elif not isinstance(rec.get("staffing"), dict):
            rec["staffing"] = {"status": "unknown", "as_of": None}
    if not isinstance(rec.get("visit"), dict):
        rec["visit"] = {"climbable": None, "drive_up": None, "trail_note": None}

    # Rental: RIDB only.
    if "rental" not in locked:
        ridb = [m for m in members if m.source == "ridb"]
        rentals = [m for m in ridb if isinstance(m.raw.get("rental"), dict)]
        rentals.sort(key=lambda m: (m.raw["rental"].get("available") is not True, m.key))
        if rentals:
            rec["rental"] = copy.deepcopy(rentals[0].raw["rental"])
            rec["rental"].setdefault("checked", headers.get("ridb", {}).get("retrieved"))
            contributed[rentals[0].key].add("rental")
        elif ridb and isinstance(rec.get("rental"), dict) and rec["rental"].get("provider") == "recreation.gov":
            rec["rental"]["available"] = False
        else:
            rec.setdefault("rental", None)

    # Events: one source's build dates (the "built" winner), everything else unioned.
    built, built_src = pick("built", members, record_built)
    if "events" not in locked:
        events: list[dict] = []
        seen_ev: set = set()
        if built_src is not None:
            bevs = [e for e in built_src.raw.get("events") or [] if isinstance(e, dict) and e.get("event") == "built" and isinstance(e.get("year"), int)]
            if not any(e["year"] == built for e in bevs):
                bevs.insert(0, {"year": built, "event": "built", "note": None, "from": built_src.source})
            for e in bevs:
                k = ("built", e["year"])
                if k not in seen_ev:
                    seen_ev.add(k)
                    events.append({"year": e["year"], "event": "built", "note": e.get("note"), "from": e.get("from") or built_src.source})
            contributed[built_src.key].add("events")
        for m in sorted(members, key=lambda m: (source_rank("events", m.source), m.key)):
            for e in m.raw.get("events") or []:
                if not isinstance(e, dict) or not e.get("event") or e.get("event") == "built":
                    continue
                k = (e["event"], e.get("year"))
                if k in seen_ev:
                    continue
                seen_ev.add(k)
                events.append({"year": e.get("year"), "event": e["event"], "note": e.get("note"), "from": e.get("from") or m.source})
                contributed[m.key].add("events")
        if events or "events" not in rec:
            old_other = [e for e in rec.get("events") or [] if isinstance(e, dict) and (e.get("event"), e.get("year")) not in seen_ev and e.get("from") not in {m.source for m in members}]
            events.extend(old_other)
            events.sort(key=lambda e: (e.get("year") if isinstance(e.get("year"), int) else 9999, e["event"]))
            rec["events"] = events

    # Photos: union, de-duplicated by URL.
    if "photos" not in locked:
        photos, seen_urls = [], set()
        for m in sorted(members, key=lambda m: (source_rank("photos", m.source), m.key)):
            for p in m.raw.get("photos") or []:
                pe = photo_entry(m, p)
                if pe and pe["url"] not in seen_urls:
                    seen_urls.add(pe["url"])
                    photos.append(pe)
                    contributed[m.key].add("photos")
        old = [p for p in rec.get("photos") or [] if isinstance(p, dict) and (p.get("file") or p.get("url")) and p.get("url") not in seen_urls]
        # keep mirrored copies made by the photo step: carry file/thumb over by URL
        old_by_url = {p.get("url"): p for p in rec.get("photos") or [] if isinstance(p, dict)}
        for p in photos:
            prev = old_by_url.get(p["url"])
            if prev:
                p["file"], p["thumb"] = prev.get("file"), prev.get("thumb")
        rec["photos"] = photos + old

    # Links: every source page, then the links each source gives.
    if "links" not in locked:
        links, seen_links = [], set()
        for m in sorted(members, key=lambda m: (global_rank(m.source), m.key)):
            for link in record_links(m):
                n = link_norm(link["url"])
                if n in seen_links:
                    continue
                seen_links.add(n)
                links.append(link)
                contributed[m.key].add("links")
        for link in rec.get("links") or []:
            if isinstance(link, dict) and isinstance(link.get("url"), str) and link_norm(link["url"]) not in seen_links:
                seen_links.add(link_norm(link["url"]))
                links.append(link)
        links.sort(key=lambda l: LINK_KIND_ORDER.index(l["kind"]) if l.get("kind") in LINK_KIND_ORDER else len(LINK_KIND_ORDER))
        rec["links"] = links

    # A listing for a lookout another source records as gone (Flag Point, OR: "Burned 2026"):
    # keep RIDB's details, but do not offer it as bookable.
    r_ = rec.get("rental")
    if "rental" not in locked and isinstance(r_, dict) and r_.get("available") and rec.get("status") in ("gone", "ruins"):
        r_["available"] = False
        src_name = SOURCE_SITE.get(status_src.source, status_src.source).split(" (")[0] if status_src else "a source"
        r_["status_note"] = (f"Recreation.gov still lists it, but {src_name} records the lookout as "
                             f"{rec['status']}{' (' + status_src.raw['status_raw'] + ')' if status_src and status_src.raw.get('status_raw') else ''}.")

    # Conflicts
    if "conflicts" not in locked:
        rec["conflicts"] = conflicts_for(rec, members, loc_src, status_src, built_src, built) + tower_reg_conflicts

    # Hidden (out of scope)
    if "hidden" not in locked:
        hidden, reason = hidden_for(rec, members)
        rec["hidden"], rec["hidden_reason"] = hidden, reason
    rec.setdefault("hidden", False)
    rec.setdefault("hidden_reason", None)

    # Verification
    if "verification" not in locked:
        cur = ex.get("verification")
        if cur in ("researched", "verified"):
            rec["verification"] = cur
        else:
            rec["verification"] = verification_for(rec, members)

    # Sources
    if "sources" not in locked:
        refs = []
        present = {m.source for m in members}
        for m in sorted(members, key=lambda m: (global_rank(m.source), m.key)):
            fields = [f for f in FIELD_ORDER if f in contributed[m.key]]
            refs.append({"source": m.source, "key": m.key, "fields": fields})
        member_keys = {m.key for m in members}
        for s_ in ex.get("sources") or []:
            if isinstance(s_, dict) and s_.get("key") not in member_keys and s_.get("source") not in present:
                stale = dict(s_)
                stale["fields"] = []
                stale.setdefault("missing_since", today)
                refs.append(stale)
        rec["sources"] = refs

    rec.setdefault("locked", [])
    for k, default in (("county", None), ("elevation_m", None), ("design", None), ("height_m", None),
                       ("agency", None), ("registers", []), ("events", []), ("photos", []),
                       ("links", []), ("conflicts", []), ("rental", None), ("other_names", []),
                       ("verification", "unverified"), ("ownership", "unknown")):
        rec.setdefault(k, default)
    return rec


def conflicts_for(rec: dict, members: list[Rec], loc_src: Rec | None, status_src: Rec | None,
                  built_src: Rec | None, built: int | None) -> list[dict]:
    out = []
    # Location: anything over 500 m from the position we show. Approximate sources excluded.
    if loc_src is not None and "location" in rec:
        lat, lon = rec["location"]["lat"], rec["location"]["lon"]
        far = []
        for m in sorted(members, key=lambda m: (source_rank("location", m.source), m.key)):
            if m is loc_src or not m.has_coords or m.source in APPROXIMATE:
                continue
            d = haversine_m(lat, lon, m.lat, m.lon)
            if d > CONFLICT_LOCATION_M:
                far.append((m, d))
        if far:
            values = [{"source": loc_src.source, "value": {"lat": round_coord(lat), "lon": round_coord(lon)}}]
            seen = {(loc_src.source, round(lat, 4), round(lon, 4))}
            for m, d in far:
                k = (m.source, round(m.lat, 4), round(m.lon, 4))
                if k not in seen:
                    seen.add(k)
                    values.append({"source": m.source, "value": {"lat": round_coord(m.lat), "lon": round_coord(m.lon)}})
            dmax = max(d for _, d in far)
            notes = []
            if any(set(m.reg_keys) & set(loc_src.reg_keys) for m, _ in far):
                notes.append("They share a register number.")
            odd = [m for m in [loc_src] + [m for m, _ in far] if m.coordinate_problem]
            if odd:
                notes.append(f"{SOURCE_SITE.get(odd[0].source, odd[0].source).split(' (')[0]}'s position is outside its own state.")
            out.append({"field": "location", "values": values, "distance_m": int(round(dmax)),
                        "note": " ".join(notes) or None})
    # Status: different statuses (gone and ruins count as the same here).
    if status_src is not None:
        by_source: dict[str, tuple] = {}
        for m in sorted(members, key=lambda m: (source_rank("status", m.source), m.key)):
            st = record_status(m)
            if st is None or m.source in by_source:
                continue
            by_source[m.source] = (st, m)
        groups = {status_group(v[0]) for v in by_source.values()}
        if len(groups) > 1:
            values = [{"source": src, "value": st} for src, (st, _) in by_source.items()]
            notes = []
            for src, (st, m) in by_source.items():
                if src == "firelookout_com" and m.raw.get("status_raw") == "Not on standing map":
                    notes.append("firelookout.com lists it, but not on its map of standing lookouts.")
                if src == "idaho_fl":
                    notes.append("idahofirelookouts.com's status is read from a short summary.")
                if src == "nhlr" and st == "standing":
                    notes.append("NHLR lists lookouts that were standing when registered.")
            out.append({"field": "status", "values": values, "distance_m": None, "note": " ".join(notes) or None})
    # Build year
    if built_src is not None:
        by_source = {}
        for m in sorted(members, key=lambda m: (source_rank("built", m.source), m.key)):
            b = record_built(m)
            if b is not None and m.source not in by_source:
                by_source[m.source] = b
        if len(set(by_source.values())) > 1:
            values = [{"source": src, "value": b} for src, b in by_source.items()]
            out.append({"field": "built", "values": values, "distance_m": None, "note": None})
    # Kind, only where it decides whether the lookout is shown.
    kinds = {}
    for m in sorted(members, key=lambda m: (source_rank("kind", m.source), m.key)):
        k = m.raw.get("kind")
        if k not in (None, "unknown") and m.source not in kinds:
            kinds[m.source] = k
    hidden_kinds = {k for k in kinds.values() if k in HIDDEN_KIND_REASON}
    if hidden_kinds and set(kinds.values()) - set(HIDDEN_KIND_REASON):
        out.append({"field": "kind", "values": [{"source": s, "value": k} for s, k in kinds.items()],
                    "distance_m": None, "note": "Sources disagree on whether this was a structure or a tree/camp site."})
    return out


def hidden_for(rec: dict, members: list[Rec]) -> tuple[bool, str | None]:
    kind = rec.get("kind")
    if kind in HIDDEN_KIND_REASON:
        return True, HIDDEN_KIND_REASON[kind]
    structural = any(m.raw.get("kind") not in (None, "unknown", "tree", "camp") for m in members if m.source != "ffla")
    ffla = [m for m in members if m.source == "ffla"]
    registered = any(m.source in ("nhlr", "fflos") for m in members)
    for m in ffla:
        st = str(m.raw.get("status_raw") or "").strip().lower()
        if st in NEVER_BUILT_STATUS and not registered and not structural:
            return True, f"Never built (FFLA lists it as \"{m.raw.get('status_raw')}\")"
        section = str(m.extra.get("section") or "").lower()
        if section.startswith(NOT_A_LOOKOUT_SECTION) and not registered:
            return True, "Not a fire lookout (FFLA: determined not to have been used as a wildland fire lookout)"
    if kind == "unknown" and ffla and not structural and not registered:
        types = {str(m.raw.get("type_raw") or "").strip().lower() for m in ffla}
        if types and types <= BARE_POINT_TYPES:
            return True, "Lookout point with no structure: out of scope (structures only)"
    return False, None


def verification_for(rec: dict, members: list[Rec]) -> str:
    """"facts" when two independent sources (lineage groups) agree on location (within
    500 m of the shown position) and status; otherwise "unverified"."""
    loc = rec.get("location") or {}
    if not _num(loc.get("lat")):
        return "unverified"
    want = status_group(rec.get("status"))
    if want is None:
        return "unverified"
    groups = set()
    for m in members:
        if not m.has_coords or m.source in APPROXIMATE:
            continue
        if status_group(record_status(m)) != want:
            continue
        if haversine_m(loc["lat"], loc["lon"], m.lat, m.lon) > CONFLICT_LOCATION_M:
            continue
        groups.add(LOCATION_LINEAGE.get(m.source, m.source))
    return "facts" if len(groups) >= 2 else "unverified"


# ---------------------------------------------------------------------------------------
# Ids and output
# ---------------------------------------------------------------------------------------


def assign_ids(towers: list[tuple[Tower, dict]], taken: set[str]) -> None:
    """Give new towers ids, deterministically: sorted by (state, slug, position, first key),
    "-2", "-3"... for clashes. Existing ids are never changed or reused."""
    new = [(t, r) for t, r in towers if t.id is None]

    def sort_key(item):
        t, r = item
        loc = r.get("location") or {}
        return (r.get("region") or "", slugify(r["name"]), -(loc.get("lat") or 0), loc.get("lon") or 0,
                min((m.key for m in t.members), default=""))

    for t, r in sorted(new, key=sort_key):
        base = f"us-{(r.get('region') or 'xx').lower()}-{slugify(r['name'])}"
        cand, n = base, 1
        while cand in taken:
            n += 1
            cand = f"{base}-{n}"
        taken.add(cand)
        t.id = cand


def ordered(rec: dict) -> dict:
    out = {k: rec[k] for k in TOWER_KEYS if k in rec}
    for k in rec:
        if k not in out:
            out[k] = rec[k]
    return out


def dump(rec: dict) -> str:
    return json.dumps(rec, indent=2, ensure_ascii=False) + "\n"


def without_updated(rec: dict) -> dict:
    return {k: v for k, v in rec.items() if k != "updated"}


# ---------------------------------------------------------------------------------------
# Review: near misses and report
# ---------------------------------------------------------------------------------------


def near_misses(towers: list[tuple[Tower, dict]]) -> list[dict]:
    """Pairs of separate towers that might be one lookout: same name within 10 km, or close
    together with different names. Pairs that share a source are skipped (that source lists
    them as two lookouts)."""
    grid: dict[tuple, list] = defaultdict(list)
    items = []
    for t, r in towers:
        loc = r.get("location") or {}
        if not _num(loc.get("lat")):
            continue
        items.append((t, r))
        grid[cell_of(loc["lat"], loc["lon"])].append((t, r))
    out = []
    for t, r in items:
        lat, lon = r["location"]["lat"], r["location"]["lon"]
        for c in cells_around(lat, lon, NEAR_MISS_M):
            for u, q in grid.get(c, ()):
                if u.id <= t.id or r.get("region") != q.get("region"):
                    continue
                if t.sources & u.sources:
                    continue
                d = haversine_m(lat, lon, q["location"]["lat"], q["location"]["lon"])
                if d > NEAR_MISS_M:
                    continue
                s = name_score(t.forms(), u.forms())
                if s is not None and s >= STRONG:
                    kind = "same_name_apart"
                elif d <= MATCH_NEAR_M:
                    kind = "close_different_names"
                else:
                    continue
                out.append({
                    "type": kind, "distance_m": int(round(d)), "name_score": s,
                    "a": {"id": t.id, "name": r["name"], "status": r.get("status"), "sources": sorted(t.sources), "hidden": r.get("hidden")},
                    "b": {"id": u.id, "name": q["name"], "status": q.get("status"), "sources": sorted(u.sources), "hidden": q.get("hidden")},
                })
    out.sort(key=lambda x: (x["type"], x["a"]["id"], x["b"]["id"]))
    return out


def run(sources_dir: Path, towers_dir: Path, report_path: Path | None, today: str,
        dry_run: bool = False, log=print) -> dict:
    headers, records = load_sources(sources_dir, log)
    existing = load_towers(towers_dir, log)
    m = Matcher(log)
    paths: dict[int, Path] = {}
    for path, rec in existing:
        t = m.new_tower(rec, path)
        paths[t.seq] = path
    taken = {t.id for t in m.towers if t.id}
    if len(taken) != len(existing):
        raise SystemExit("Existing towers have duplicate ids; fix them before merging.")

    order = [s for s in SOURCE_ORDER if s in records] + sorted(set(records) - set(SOURCE_ORDER))
    for sid in order:
        m.match_source(sid, records[sid])
    m.place_without_coords()

    resolved: list[tuple[Tower, dict]] = []
    for t in m.towers:
        if not t.members and t.existing is None:
            continue
        if not t.members:
            resolved.append((t, copy.deepcopy(t.existing)))
            continue
        resolved.append((t, resolve(t, today, headers)))
    assign_ids(resolved, taken)

    written = unchanged = 0
    for t, r in resolved:
        r["id"] = t.id
        if t.existing is not None and without_updated(ordered(r)) == without_updated(ordered(t.existing)):
            r["updated"] = t.existing.get("updated") or today
            unchanged += 1
        else:
            r["updated"] = today
            written += 1
            if not dry_run:
                path = t.path or towers_dir / t.id.split("-")[1] / f"{t.id}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(dump(ordered(r)), encoding="utf-8")

    report = build_report(m, resolved, headers, today, written, unchanged)
    if report_path and not dry_run:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def build_report(m: Matcher, resolved: list[tuple[Tower, dict]], headers: dict, today: str,
                 written: int, unchanged: int) -> dict:
    visible = [r for _, r in resolved if not r.get("hidden")]
    hidden = [r for _, r in resolved if r.get("hidden")]
    seq_to_id = {t.seq: t.id for t, _ in resolved}
    n_sources = Counter(min(len({s.get("source") for s in r.get("sources") or []}), 5) for _, r in resolved)
    multi = sum(1 for t, _ in resolved if len(t.sources) >= 2)
    conflict_counts = Counter(c["field"] for _, r in resolved for c in r.get("conflicts") or [])
    conflict_pairs: dict[str, Counter] = defaultdict(Counter)
    for _, r in resolved:
        for c in r.get("conflicts") or []:
            srcs = "+".join(sorted({v["source"] for v in c.get("values") or []}))
            conflict_pairs[c["field"]][srcs] += 1
    examples: dict[str, list] = defaultdict(list)
    for _, r in sorted(resolved, key=lambda x: x[1]["id"]):
        for c in r.get("conflicts") or []:
            if len(examples[c["field"]]) < 15:
                examples[c["field"]].append({"id": r["id"], "name": r["name"], "values": c.get("values"), "distance_m": c.get("distance_m")})
    distance_buckets = Counter()
    for _, r in resolved:
        for c in r.get("conflicts") or []:
            if c["field"] == "location":
                d = c.get("distance_m") or 0
                distance_buckets["0.5-1 km" if d < 1000 else "1-5 km" if d < 5000 else "5-25 km" if d < 25000 else ">25 km"] += 1
    nm = near_misses(resolved)
    review = []
    for item in m.review:
        item = dict(item)
        if "tower_seq" in item:
            item["tower"] = seq_to_id.get(item.pop("tower_seq"))
        if "nearby_tower_seq" in item:
            item["nearby_tower"] = seq_to_id.get(item.pop("nearby_tower_seq"))
        if "tower_seqs" in item:
            item["towers"] = [seq_to_id.get(s) for s in item.pop("tower_seqs")]
        review.append(item)
    for t, r in resolved:
        if isinstance(r.get("rental"), dict) and r["rental"].get("status_note"):
            review.append({"type": "rental_on_gone_lookout", "tower": r["id"], "note": r["rental"]["status_note"]})
    rental_hints = []
    for t, r in resolved:
        if r.get("rental"):
            continue
        for mem in t.members:
            if mem.source in ("nhlr", "fflos") and isinstance(mem.raw.get("rental"), dict) and mem.raw["rental"].get("available"):
                rental_hints.append({"id": r["id"], "name": r["name"], "key": mem.key})
    match_by_source: dict[str, Counter] = defaultdict(Counter)
    for t, _ in resolved:
        for mem in t.members:
            match_by_source[mem.source][mem.match] += 1
    for rec in m.unplaced:
        match_by_source[rec.source]["unplaced"] += 1

    def counts(rs: list[dict], key: str) -> dict:
        return dict(sorted(Counter(r.get(key) for r in rs).items(), key=lambda kv: (-kv[1], str(kv[0]))))

    return {
        "merged": today,
        "inputs": {sid: {"records": h.get("records"), "retrieved": h.get("retrieved"), "file": h.get("file")} for sid, h in sorted(headers.items())},
        "files": {"written": written, "unchanged": unchanged},
        "counts": {
            "towers": len(resolved),
            "visible": len(visible),
            "hidden": len(hidden),
            "hidden_by_reason": counts(hidden, "hidden_reason"),
            "visible_by_status": counts(visible, "status"),
            "visible_by_kind": counts(visible, "kind"),
            "visible_by_region": dict(sorted(Counter(r.get("region") for r in visible).items())),
            "visible_by_verification": counts(visible, "verification"),
            "multi_source_towers": multi,
            "towers_by_number_of_sources": {("5+" if k == 5 else str(k)): v for k, v in sorted(n_sources.items())},
            "rentable": sum(1 for r in visible if isinstance(r.get("rental"), dict) and r["rental"].get("available") is not False),
            "registered": sum(1 for r in visible if r.get("registers")),
        },
        "matching": {
            "note": "How each source record found its tower on this run. 'key' means it was matched "
                    "on an earlier run and found again by its key; delete data/towers to see a fresh run's methods.",
            "by_source": {s: dict(sorted(c.items())) for s, c in sorted(match_by_source.items())},
            "cross_region_matches": m.stats.get("matched_cross_region", 0),
            "register_clashes": len(m.register_clash),
        },
        "conflicts": {
            "by_field": dict(conflict_counts.most_common()),
            "by_field_and_sources": {f: dict(c.most_common(12)) for f, c in sorted(conflict_pairs.items())},
            "location_distance": dict(sorted(distance_buckets.items())),
            "examples": dict(sorted(examples.items())),
        },
        "near_misses": {
            "count": len(nm),
            "by_type": dict(Counter(x["type"] for x in nm)),
            "pairs": nm,
        },
        "review": review,
        "unplaced": [{"key": r.key, "name": r.display, "region": r.region, "reason": r.match_note} for r in m.unplaced],
        "coordinates_not_used": [{"key": mem.key, "name": mem.display, "region": mem.region,
                                  "lat": mem.raw.get("lat"), "lon": mem.raw.get("lon")}
                                 for t, _ in resolved for mem in t.members if mem.bad_coords == "outside_us"]
                                + [{"key": r.key, "name": r.display, "region": r.region, "lat": r.raw.get("lat"), "lon": r.raw.get("lon")}
                                   for r in m.unplaced if r.bad_coords == "outside_us"],
        "coordinates_outside_own_state": sum(1 for t, _ in resolved for mem in t.members if mem.bad_coords == "outside_state"),
        "rental_hints_without_ridb": rental_hints,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sources", type=Path, default=DATA / "sources")
    ap.add_argument("--towers", type=Path, default=DATA / "towers")
    ap.add_argument("--report", type=Path, default=DATA / "merge_report.json")
    ap.add_argument("--today", default=dt.date.today().isoformat(), help="date stamped on changed records (YYYY-MM-DD)")
    ap.add_argument("--dry-run", action="store_true", help="match and report, but write nothing")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    log = (lambda *a, **k: None) if args.quiet else print
    rep = run(args.sources, args.towers, args.report, args.today, args.dry_run, log)
    c = rep["counts"]
    log(f"{c['towers']} towers ({c['visible']} visible, {c['hidden']} hidden); "
        f"{c['multi_source_towers']} from 2+ sources; {rep['files']['written']} written, "
        f"{rep['files']['unchanged']} unchanged; {rep['near_misses']['count']} near misses; "
        f"{len(rep['unplaced'])} records without a place")
    if args.dry_run:
        log("dry run: nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
