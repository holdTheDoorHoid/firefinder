#!/usr/bin/env python3
"""Construction kinds, materials and statuses: the deliberate mapping from every source's own
wording to Firefinder's vocabulary (DESIGN.md 3.4).

Every "Type" and "Status" value any source uses has an entry here, so a new value from a future
crawl is noticed (pipeline/test_structure.py fails, naming it) instead of quietly becoming
"unknown". The plain-language side of the vocabulary -- labels, the paragraph about each kind,
which group a kind belongs to, and whether a kind is hidden -- lives in
data/structure_kinds.json, so the owner can change the scope decision with one edit.

What this module decides, per source record:

  kind      from the record's type value (FFLA's Type column, firelookout.com's title word,
            Wikidata classes, ...), else from words in its description ("100-foot steel tower",
            "ground cabin"), else the fetcher's own reading (OSM tags, RIDB text).
  material  steel | wood | log | stone | concrete | masonry | mixed: from type values
            ("Stone Tower", "Log Crib", "Wooden Tower"), description words, and OSM's
            tower:construction / building:material tags. The tower-level fallback from the
            lookout's design (an L-4 cab is wood, an Aermotor tower steel) is design_material().
  status    from the record's status value, with years inside it ("Burned 2026") as events.
  roles     jobs a site did that are not a kind of building: "aws", the Second World War
            Aircraft Warning Service.

Description words are reduced to short canonical facts ("steel tower", "wood cab", "kind
ground"), never stored as prose. NHLR/FFLOS and firelookout.com pages are only in the crawl
cache, so their fetchers store the words in the extract (extra.structure_words); run
`python3 pipeline/structure.py --backfill` to refresh them from the cache without a re-crawl.

Python 3.12, standard library only.
"""

from __future__ import annotations

import argparse
import functools
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
VOCAB_FILE = DATA / "structure_kinds.json"

MATERIALS = ("steel", "wood", "log", "stone", "concrete", "masonry", "mixed")
# Kinds whose material is the tower's (its legs and frame), and kinds whose material is the
# building's walls. Sites with no structure have no material.
TOWER_KINDS = {"tower", "enclosed_tower", "platform"}
BUILDING_KINDS = {"ground", "two_story", "three_story", "rooftop", "mobile"}

# A table value meaning "this value is understood, but the fetcher's own reading of the record
# (OSM tags, Wikidata's dissolved date) decides".
KEEP = "keep"


# ---------------------------------------------------------------------------------------
# data/structure_kinds.json
# ---------------------------------------------------------------------------------------

@functools.lru_cache(maxsize=4)
def load_vocab(path: Path = VOCAB_FILE) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def kind_ids(path: Path = VOCAB_FILE) -> list[str]:
    return [k["id"] for k in load_vocab(path)["kinds"]]


def kind_group(path: Path = VOCAB_FILE) -> dict[str, str]:
    """{kind: group id}: "structure" or "no_structure"."""
    return {k["id"]: k["group"] for k in load_vocab(path)["kinds"]}


@functools.lru_cache(maxsize=4)
def no_structure_kinds(path: Path = VOCAB_FILE) -> frozenset[str]:
    """Camps, lookout trees and bare points: sites where nothing was built to stand in."""
    return frozenset(k for k, g in kind_group(path).items() if g == "no_structure")


def hidden_kind_reasons(path: Path = VOCAB_FILE) -> dict[str, str]:
    """{kind: reason} for the kinds the owner has chosen to hide (none, since 2026-10-08)."""
    return {k["id"]: k.get("hidden_reason") or f"{k['label']}: out of scope"
            for k in load_vocab(path)["kinds"] if k.get("hidden")}


def material_ids(path: Path = VOCAB_FILE) -> list[str]:
    return [m["id"] for m in load_vocab(path)["materials"]]


def role_ids(path: Path = VOCAB_FILE) -> list[str]:
    return [r["id"] for r in load_vocab(path)["roles"]]


# ---------------------------------------------------------------------------------------
# Type values
# ---------------------------------------------------------------------------------------

@dataclass(frozen=True)
class TypeInfo:
    kind: str | None            # vocabulary kind; None = the value says nothing about it; KEEP
    material: str | None = None
    role: str | None = None
    status: str | None = None   # a status written in the type column (FFLA "Gone")
    note: str | None = None     # why, for the odd ones (documentation only)


T = TypeInfo

# FFLA's "Type" column, lower-cased, trailing "*" dropped. Every value seen in the state tables.
FFLA_TYPES: dict[str, TypeInfo] = {
    "tower": T("tower"),
    "tower?": T("tower", note="FFLA is unsure; a tower is its best guess"),
    "tower (unk)": T("tower"),
    "tower/ground": T("tower", note="a tower and a ground cab on one site; the tower is the lookout"),
    "obs tower": T("tower"),
    "obs. tower": T("tower"),
    "observation tower": T("tower"),
    "beacon tower": T("tower"),
    "security tower": T("tower", note="a security tower used as a lookout (Los Alamos, NM)"),
    "radio tower": T("tower", note="a radio tower used as a lookout"),
    "windmill tower": T("tower", note="a windmill tower used as a lookout"),
    "non-fire tower": T("tower", note="hidden by merge.hidden_for as not a fire lookout"),
    "stone tower": T("tower", "stone"),
    "stone obs tower": T("tower", "stone"),
    "log tower": T("tower", "log"),
    "wooden tower": T("tower", "wood"),
    # A cab raised on a crib of stacked logs: a short tower, built of logs.
    "log crib": T("tower", "log"),
    "log base": T("tower", "log"),
    "encl. tower": T("enclosed_tower"),
    "enclosed tower": T("enclosed_tower"),
    "platform": T("platform"),
    "platfrom": T("platform"),
    "platforms": T("platform"),
    "platform tower": T("platform"),
    "open tower": T("platform", note="a tower with an open top and no cab"),
    "obs deck": T("platform"),
    # A crow's nest was a small platform high on a pole or in a treetop. FFLA lists it apart
    # from "Tree", so it is counted as a platform (owner may regroup it with lookout trees).
    "crowsnest": T("platform"),
    "crows nest": T("platform"),
    "crow's nest": T("platform"),
    "ground": T("ground"),
    "shelter": T("ground", note="a small summit shelter the observer used"),
    "stone hut": T("ground", "stone"),
    "stone walls": T("ground", "stone", note="the stone walls of a summit lookout house"),
    "rock shelter": T("ground", "stone"),
    "tram house": T("ground", note="a mine tramway's terminal building used as a lookout (Alta Mine, CO)"),
    "map board (cabin)": T("ground", note="a map board kept in a cabin"),
    "stone": T(None, "stone", note="says the material, not the form"),
    "2-story cab": T("two_story"),
    "2 story cab": T("two_story"),
    "2-storycab": T("two_story"),
    "two-story cab": T("two_story"),
    "2-story": T("two_story"),
    "3-story cab": T("three_story"),
    "3 story cab": T("three_story"),
    "3-storycab": T("three_story"),
    "three-story cab": T("three_story"),
    "3-story": T("three_story"),
    "3-story stone": T("three_story", "stone"),
    # A cab on top of another building.
    "rooftop": T("rooftop"),
    "roof top": T("rooftop"),
    "rooftop cab": T("rooftop"),
    "rooftop tower": T("rooftop"),
    "hotel": T("rooftop", note="a lookout on a hotel (Mount Moosilauke, NH)"),
    "office building": T("rooftop"),
    "grain elevator": T("rooftop"),
    "clock tower": T("rooftop"),
    # Movable cabs.
    "trailer": T("mobile"),
    "bus/cupola": T("mobile", note="a bus with a cupola on the roof"),
    # The Aircraft Warning Service was a wartime job, not a kind of building.
    "aws": T(None, role="aws"),
    "aws tower": T("tower", role="aws"),
    # No structure.
    "tree": T("tree"),
    "tree platform": T("tree"),
    "tree cab": T("tree"),
    "camp": T("camp"),
    "firefinder": T("point"),
    "map board": T("point"),
    "map boards": T("point"),
    "map table": T("point"),
    "alidade": T("point"),
    "obs pt": T("point"),
    "obs. point": T("point"),
    "open site": T("point"),
    "rock cairn": T("point"),
    "high point": T("point"),
    # Nothing known.
    "unknown": T(None),
    "unk": T(None),
    "unconfirmed": T(None),
    "no info": T(None),
    "xxxx": T(None),  # placeholder rows in FFLA's California "Unknown/Undocumented" list
    # California's "Unknown/Undocumented" list (ca-un) has a few more words.
    # An emergency lookout was staffed only in bad fire weather, often with no building of its own.
    "emergency": T(None, note="an emergency lookout, staffed only in high fire danger"),
    "g.s.": T("ground", note="a guard station used as a lookout"),
    "house": T("ground"),
    "portable": T("mobile", note="a portable cab"),
    # A few Virginia rows carry the status in the Type column and leave Status empty.
    "gone": T(None, status="gone", note="the status, written in the Type column"),
}

# firelookout.com: the word at the end of the page title ("... Fire Lookout Tower").
FIRELOOKOUT_COM_TYPES: dict[str, TypeInfo] = {
    "tower": T("tower"),
    "cabin": T("ground"),
    "house": T("ground"),
    "cab": T("ground"),
    # Titles that end in a place name, not a structure word: no kind.
    "triple divide": T(None),
    "looking glass": T(None),
    "sonyok mtn.": T(None),
    "star mtn.": T(None),
    "bimetallic": T(None),
}

SIMPLE_TYPES: dict[str, dict[str, TypeInfo]] = {
    "ffla": FFLA_TYPES,
    "firelookout_com": FIRELOOKOUT_COM_TYPES,
    "fire_lookouts_org": {"tower": T("tower")},
    "pa_storymap": {"tower": T("tower")},
}

# Wikidata: "; "-joined labels of the item's classes. Each label must be known.
WIKIDATA_CLASSES: dict[str, str | None] = {
    "fire lookout tower": "tower",
    "observation tower": "tower",
    "lookout tree": "tree",
    "scenic viewpoint": None,
    "ranger station": None,
    "trailhead": None,
    "historic district": None,
    "military building": None,
    "cabana": None,
    "destroyed building or structure": None,
}

# OpenStreetMap: "; "-joined tag summaries (pipeline/fetch_osm.type_raw_for). The fetcher reads
# the kind from the full tags (building:levels makes a two- or three-story building).
OSM_TYPE_PARTS = {"emergency=fire_lookout", "building=fire_lookout", "man_made=tower",
                  "man_made=tower;tower:type=observation", "unknown"}


def norm_type(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip().lower().rstrip("*").strip()


def type_info(source: str, type_raw: str) -> TypeInfo | None:
    """The deliberate reading of one type value, or None when nobody has mapped it yet."""
    key = norm_type(type_raw)
    if source in SIMPLE_TYPES:
        return SIMPLE_TYPES[source].get(key)
    if source == "osm":
        parts = [p.strip() for p in key.split("; ")]
        return T(KEEP) if parts and all(p in OSM_TYPE_PARTS for p in parts) else None
    if source == "wikidata":
        labels = [p.strip() for p in key.split(";") if p.strip()]
        if not labels or any(lb not in WIKIDATA_CLASSES for lb in labels):
            return None
        kinds = {WIKIDATA_CLASSES[lb] for lb in labels} - {None}
        return T("tree" if "tree" in kinds else "tower" if "tower" in kinds else None)
    return None


# ---------------------------------------------------------------------------------------
# Status values
# ---------------------------------------------------------------------------------------

@dataclass(frozen=True)
class StatusInfo:
    status: str | None          # vocabulary status; None = no claim; KEEP = the fetcher decides
    event: str | None = None    # with a year in the value: the event that year records
    note: str | None = None     # shown beside the status on the tower page
    flag: str | None = None     # private / never_built / non_fire (merge acts on these)


S = StatusInfo

FFLA_STATUS: dict[str, StatusInfo] = {
    "standing": S("standing"),
    # FFLA's legend: "Towers that retain their structure and support with the cab no longer in
    # place are denoted as 'Standing*'".
    "standing*": S("standing", note="The tower still stands, but its cab is gone (FFLA)."),
    "gone": S("gone"),
    "gone**": S("gone"),  # the "**" is not explained on FFLA's pages
    "removed": S("gone"),
    "abandoned": S("gone"),
    "ruins": S("ruins"),
    "standing (ruins)": S("ruins"),
    "collapsed": S("ruins"),
    "relocated": S("relocated"),
    "unknown": S(None),
    "??": S(None),
    "nb?": S(None, note="FFLA marks it as possibly never built."),
    "duplicate?": S(None),  # the name says which lookout it may duplicate: "(same as X?)"
    "undocumented": S(None, note="FFLA lists the site as undocumented."),
    # Temporarily taken down: High Rock, WA was flown off in 2020 for restoration and is being
    # rebuilt. No status claim; the note says it.
    "temp*": S(None, note="FFLA marks it as temporarily removed: the lookout may be away for restoration. Check before you go."),
    "private": S(None, flag="private"),
    "proposed": S(None, flag="never_built"),
    "planned": S(None, flag="never_built"),
    "never built": S(None, flag="never_built"),
    "non-fire": S(None, flag="non_fire"),
    "non-wildfire": S(None, flag="non_fire"),
}
# "Burned 2026", "Removed 2026", "New 2026": a status and the year of the change.
FFLA_STATUS_YEAR_RE = re.compile(r"^(new|burned|removed|standing|gone)\s+(\d{4})$")
FFLA_STATUS_YEAR: dict[str, StatusInfo] = {
    "new": S("standing", event="rebuilt"),  # a new structure on an old site
    "burned": S("gone", event="burned"),
    "removed": S("gone", event="removed"),
    "standing": S("standing"),
    "gone": S("gone"),
}

WEEBLY_STATUS: dict[str, StatusInfo] = {
    "removed": S("gone"), "dismantled": S("gone"), "demolished": S("gone"), "taken down": S("gone"),
    "torn down": S("gone"), "razed": S("gone"), "destroyed": S("gone"), "burned down": S("gone"),
    "still standing": S("standing"), "still stands": S("standing"),
    "collapsed": S("ruins"),
    # The western sites' standalone status words (regional/weebly_west.py).
    "burned": S("gone"), "burnt": S("gone"), "ruins": S("ruins"), "relocated": S("relocated"),
    "replica": S("replica"), "standing": S("standing"), "active": S("standing"),
}

SIMPLE_STATUS: dict[str, dict[str, StatusInfo]] = {
    "ffla": FFLA_STATUS,
    "eastern_us_lookouts": WEEBLY_STATUS,
    "central_us_lookouts": WEEBLY_STATUS,
    "west_us_lookouts": WEEBLY_STATUS,
    "firelookout_com": {
        "standing": S("standing"),
        # Listed on firelookout.com, but not on its map of standing lookouts.
        "not on standing map": S("gone"),
    },
    "michigan_fire_tower": {"standing": S("standing"), "down": S("gone"), "unknown": S(None)},
    "nj_forest_fire_towers": {
        "active service": S("standing"),
        # The table's one legend covers both, so it says neither (Batsto's still stands).
        "not in service or no longer standing": S(None),
    },
    "tnlandforms": {
        "standing": S("standing"), "sitting": S("standing"),
        "removed": S("gone"), "moved": S("relocated"),
        "historical": S(None), "station": S(None), "?": S(None), "replaced": S(None),
    },
    "wikipedia_lookout_lists": {
        "torn down.": S("gone"), "torn down": S("gone"),
        "torn down?": S(None, note="Sources suggest it is gone."),
        "still standing": S("standing"), "still standing.": S("standing"),
        "still standing/active use.": S("standing"), "still standing/inactive": S("standing"),
        "still standing* used on high wind days": S("standing"),
    },
}

# OSM lifecycle tags summarised in status_raw ("abandoned=yes; ruins=yes"). The fetcher reads
# the full tags; each key here is understood.
OSM_STATUS_KEYS = {"disused:emergency", "was:emergency", "was:operator", "disused:tourism", "ruins",
                   "abandoned", "abandoned:building", "demolished", "building:destroyed",
                   "destroyed:building"}
WIKIDATA_STATUS_RE = re.compile(r"^(?:P31 instance of 'destroyed building or structure'|"
                                r"P576 dissolved/abandoned/demolished date: .+)$")


def norm_status(s: str) -> str:
    """Lower-cased and tidied; a trailing "*" is kept ("Standing*" is not "Standing")."""
    s = s.replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", s).strip().lower()


def status_info(source: str, status_raw: str) -> tuple[StatusInfo, int | None] | None:
    """The deliberate reading of one status value and the year in it, or None if unmapped."""
    key = norm_status(status_raw)
    if source == "ffla":
        m = FFLA_STATUS_YEAR_RE.match(key)
        if m:
            return FFLA_STATUS_YEAR[m.group(1)], int(m.group(2))
    if source in SIMPLE_STATUS:
        info = SIMPLE_STATUS[source].get(key)
        return (info, None) if info is not None else None
    if source == "osm":
        keys = [p.split("=", 1)[0].strip() for p in key.split(";") if p.strip()]
        return (S(KEEP), None) if keys and all(k in OSM_STATUS_KEYS for k in keys) else None
    if source == "wikidata":
        return (S(KEEP), None) if WIKIDATA_STATUS_RE.match(status_raw.strip()) else None
    return None


# ---------------------------------------------------------------------------------------
# OSM material tags
# ---------------------------------------------------------------------------------------

# tower:construction describes the form ("lattice", "freestanding") more often than the
# material; only material values count.
OSM_TOWER_CONSTRUCTION: dict[str, str | None] = {
    "stone": "stone", "wood": "wood", "wooden": "wood", "concrete": "concrete",
    "lattice_steel": "steel", "steel": "steel", "brick": "masonry",
    "lattice": None, "freestanding": None, "building": None, "guyed_lattice": None,
    "guyed_tube": None, "ground": None, "tower": None, "clear_lake_fire_lookout": None,
}
OSM_BUILDING_MATERIAL: dict[str, str | None] = {
    "wood": "wood", "timber_framing": "wood", "log": "log", "steel": "steel", "metal": "steel",
    "stone": "stone", "brick": "masonry", "concrete": "concrete", "cement_block": "masonry",
}


def osm_material(extra: dict) -> tuple[str | None, list[str]]:
    """Material from OSM tags, and any tag values nobody has mapped yet."""
    unmapped: list[str] = []
    found: list[str] = []
    for key, table in (("tower_construction", OSM_TOWER_CONSTRUCTION), ("building_material", OSM_BUILDING_MATERIAL)):
        v = extra.get(key)
        if not isinstance(v, str) or not v.strip():
            continue
        for part in v.split(";"):
            p = part.strip().lower()
            if p not in table:
                unmapped.append(f"{key}={p}")
            elif table[p]:
                found.append(table[p])
    mats = set(found)
    return (mats.pop() if len(mats) == 1 else ("mixed" if mats else None)), unmapped


# ---------------------------------------------------------------------------------------
# Description words
# ---------------------------------------------------------------------------------------

# Adjective -> material. Longest first when matching ("concrete block" before "concrete").
MATERIAL_WORDS: dict[str, str] = {
    "steel": "steel", "iron": "steel", "galvanized": "steel", "galvanised": "steel", "metal": "steel",
    "wood": "wood", "wooden": "wood", "timber": "wood", "treated timber": "wood", "frame": "wood",
    "framed": "wood", "wood frame": "wood", "wood-frame": "wood", "pole": "wood", "lumber": "wood",
    "log": "log", "peeled log": "log", "peeled-log": "log", "hewn log": "log",
    "stone": "stone", "native stone": "stone", "fieldstone": "stone", "granite": "stone",
    "native rock": "stone",
    "concrete": "concrete", "reinforced concrete": "concrete", "poured concrete": "concrete",
    "masonry": "masonry", "brick": "masonry", "block": "masonry", "cinder block": "masonry",
    "concrete block": "masonry", "cinderblock": "masonry",
}
# Noun -> part of the lookout the material belongs to.
PART_WORDS: dict[str, str] = {
    "tower": "tower", "towers": "tower", "shaft": "tower", "legs": "tower",
    "cab": "cab", "cabs": "cab",
    "structure": "structure", "lookout": "structure",
    "building": "building", "house": "house", "cabin": "cabin",
    "base": "base", "foundation": "base",
    "platform": "platform",
}
PARTS = sorted(set(PART_WORDS.values()))
WORD_KINDS = ("tower", "ground", "two_story", "three_story", "platform", "tree", "rooftop", "mobile")
# The closed vocabulary of extra.structure_words.
STRUCTURE_WORDS = ({f"{m} {p}" for m in MATERIALS for p in PARTS} | {f"kind {k}" for k in WORD_KINDS}
                   | {"role aws"})


def _alt(words) -> str:
    return "|".join(re.escape(w).replace(r"\ ", r"[\s-]+").replace(r"\-", r"[\s-]+")
                    for w in sorted(words, key=len, reverse=True))


_MAT = _alt(MATERIAL_WORDS)
_PART = _alt(PART_WORDS)
_FEET = r"\d{1,3}(?:\.\d)?[\s-]*(?:foot|feet|ft\.?|['’])"
_FILL = (r"(?:[\s,-]+(?:" + _FEET + r"|\d+\s*['’]?\s*x\s*\d+\s*['’]?|tall|high|lattice|fire|lookout|"
         r"observation|open|enclosed|square|live[\s-]in|(?:three|four|3|4)[\s-]legged|story|sided|walled|"
         r"frame|framed|aermotor|ideco|model|[a-z]{1,2}[\s-]?\d{1,3}[a-z]?)){0,4}")
MAT_PART_RE = re.compile(rf"\b({_MAT}){_FILL}[\s-]+({_PART})\b", re.I)
MIXED_RE = re.compile(rf"\b({_MAT})\s+(?:and|&)\s+({_MAT}){_FILL}[\s-]+({_PART})\b", re.I)
BUILT_OF_RE = re.compile(rf"\b(?:built|made|constructed)\s+(?:entirely\s+)?(?:of|from)\s+({_MAT})(?:\s+(?:and|&)\s+({_MAT}))?\b", re.I)
# "rock" alone is too often part of a name ("Table Rock Lookout"); only these count.
ROCK_RE = re.compile(r"\brock[\s-]+(?:walls?|walled|masonry)\b|\bbuilt\s+of\s+rock\b", re.I)
KIND_RES: list[tuple[str, re.Pattern[str]]] = [
    ("ground", re.compile(r"\b(?<!story )(?<!story-)ground(?:[\s-]+level)?[\s-]+(?:house|cab|cabin|lookout)\b|\bat ground level\b", re.I)),
    ("two_story", re.compile(r"\b(?:two|2)[\s-]+stor(?:y|ey|ied)\b(?=[\s-]+(?:lookout|cab|cabin|house|building|structure|frame|wood|log|stone|cupola|ground))", re.I)),
    ("three_story", re.compile(r"\b(?:three|3)[\s-]+stor(?:y|ey|ied)\b(?=[\s-]+(?:lookout|cab|cabin|house|building|structure|frame|wood|log|stone))", re.I)),
    ("tower", re.compile(rf"\b{_FEET}[\s-]+(?:[a-z0-9-]+[\s-]+){{0,3}}?(?:tower|structure)\b", re.I)),
    ("platform", re.compile(r"\bopen[\s-]+platform\b|\bplatform[\s-]+tower\b", re.I)),
    # Lower case only: "S-Tree Lookout" and "Look-See Tree" are names.
    ("tree", re.compile(r"(?<![-\w])tree[\s-]+(?:platform|lookout|crow'?s[\s-]+nest)\b|\blookout[\s-]+tree\b")),
    # A cab on another building's roof; not "a rooftop observation platform" on a cab.
    ("rooftop", re.compile(r"\broof[\s-]?top[\s-]+(?:lookout|cab)\b|\bon\s+(?:the|its)\s+roof\s+of\b", re.I)),
    # The trailer as the lookout, not "trailer quarters" or the lowboy that moved a cab.
    ("mobile", re.compile(r"\b(?:lookout|cupola|pop-up(?:\s+cupola)?)[\s-]+trailer\b|\btrailer[\s-]+(?:with\b|cupola\b|lookout\b)|"
                          r"\b(?:mobile|portable)[\s-]+(?:lookout|cab|unit)\b|\b(?:a|this)\s+trailer\s+(?:was\s+)?(?:set\s+up|placed|used)\b", re.I)),
]
AWS_RE = re.compile(r"\baircraft[\s-]+warning\b", re.I)
# Clauses about a structure other than the lookout itself (an earlier one, the living quarters).
OTHER_RE = re.compile(
    r"\b(?:original(?:ly)?|earlier|previous(?:ly)?|former(?:ly)?|predecessor|preced\w*|first|"
    r"before|until|began|start(?:ed|ing)|established|may\s+have|also(?!\s+(?:known|called|named))|"
    r"(?:trailer|living)\s+quarters|housing\s+trailer|"
    r"old\s+(?:lookout|tower|cab|cabin|structure)|living\s+quarters|residence|garage|shed|barn|"
    r"outhouse|privy|cistern|warehouse|bunkhouse|guard\s+station|ranger\s+station|museum|"
    r"near(?:by)?|next\s+to|beside|watchman'?s|keeper'?s|"
    r"communications?\s+(?:tower|building|site)|radio\s+(?:tower|building|repeater))\b", re.I)
REPLACED_BY_RE = re.compile(r"\breplaced\s+(?:in\s+(?:about\s+)?\d{4}\s+)?(?:by|with)\b", re.I)
# "X was replaced in 1933", "X, replaced in 1950": X is the old one.
REPLACED_PASSIVE_RE = re.compile(r"(?:\b(?:was|were|been|being|is|and)|,)\s+(?:later\s+|eventually\s+|then\s+)?replaced\b", re.I)
REPLACED_RE = re.compile(r"\breplac\w*\b", re.I)
PRESENT_RE = re.compile(r"\b(?:present|current(?:ly)?|today|now|still|existing)\b", re.I)
PART_NOUN_RE = re.compile(r"\b(?:tower|cab|cabin|house|structure|building|platform)\b", re.I)


def _material(word: str) -> str | None:
    return MATERIAL_WORDS.get(re.sub(r"[\s-]+", " ", word.lower()))


def _clauses(text: str):
    """Sentences (and halves of "X replaced by Y" sentences) about the lookout itself."""
    for s in re.split(r"(?<=[.!?;])\s+", text):
        m = REPLACED_BY_RE.search(s)
        if m:
            s = s[m.end():]       # "... was replaced by a steel tower": the new one
        elif REPLACED_PASSIVE_RE.search(s):
            continue              # "a log cabin was built in 1923, replaced in 1933": an old one
        else:
            m = REPLACED_RE.search(s)
            if m:
                s = s[:m.start()]  # "this steel tower replaced the earlier one": the new one
        if s.strip() and not OTHER_RE.search(s):
            yield s


def _clause_words(s: str) -> list[str]:
    out: list[str] = []

    def add(w: str) -> None:
        if w not in out:
            out.append(w)

    mixed_spans = []
    for m in MIXED_RE.finditer(s):
        a, b = _material(m.group(1)), _material(m.group(2))
        if a and b and a != b:
            add(f"mixed {PART_WORDS[m.group(3).lower()]}")
            mixed_spans.append(m.span())
    for m in MAT_PART_RE.finditer(s):
        if any(a <= m.start() < b for a, b in mixed_spans):
            continue
        mat, part = _material(m.group(1)), PART_WORDS.get(m.group(2).lower())
        if mat and part:
            add(f"{mat} {part}")
    for m in BUILT_OF_RE.finditer(s):
        a = _material(m.group(1))
        b = _material(m.group(2)) if m.group(2) else None
        if a and b and a != b:
            add("mixed structure")
        elif a:
            add(f"{a} structure")
    if ROCK_RE.search(s):
        add("stone structure")
    for kind, rx in KIND_RES:
        if rx.search(s):
            add(f"kind {kind}")
    return out


def structure_words(text: str | None) -> list[str]:
    """Short canonical facts about the lookout's structure in a description: "steel tower",
    "wood cab", "concrete base", "kind ground", "role aws". Clauses about another structure (the
    original tower, the living quarters) are skipped. When a clause about the present lookout
    ("the present R-6 cab", "the current tower") names a structure, only that clause's materials
    count: the rest of the text is history."""
    if not isinstance(text, str) or not text.strip():
        return []
    every: list[str] = []
    present: list[str] = []
    present_names_structure = False
    for s in _clauses(text):
        ws = _clause_words(s)
        every += [w for w in ws if w not in every]
        if PRESENT_RE.search(s):
            present += [w for w in ws if w not in present]
            present_names_structure = present_names_structure or bool(PART_NOUN_RE.search(s))
    if present_names_structure:
        kinds = [w for w in present if w.startswith("kind ")] or [w for w in every if w.startswith("kind ")]
        every = kinds + [w for w in present if not w.startswith("kind ")]
    if AWS_RE.search(text):
        every.append("role aws")
    return every


def _main_materials(words: list[str], kind: str | None) -> set[str]:
    by_part: dict[str, set[str]] = defaultdict(set)
    for w in words:
        head, _, part = w.partition(" ")
        if head in MATERIALS and part:
            by_part[part].add(head)
    if kind in TOWER_KINDS:
        parts = ("tower", "structure", "platform")
    elif kind in BUILDING_KINDS:
        parts = ("structure", "building", "house", "cabin", "cab")
    else:
        parts = ("tower", "structure")
    return set().union(*(by_part.get(p, set()) for p in parts))


def words_material(words: list[str], kind: str | None) -> str | None:
    """The main structure's material from description words, given the lookout's kind: the
    tower's for a tower, the walls' for a building. None when they say nothing or disagree."""
    if kind in no_structure_kinds():
        return None  # nothing was built
    mats = _main_materials(words, kind)
    if mats == {"mixed"} or ("mixed" in mats and len(mats) == 2):
        return "mixed"
    return mats.pop() if len(mats) == 1 else None


def words_kind(words: list[str]) -> str | None:
    """The kind the words name, when they name exactly one."""
    kinds = {w[5:] for w in words if w.startswith("kind ")}
    if any(w.endswith(" tower") and not w.startswith("kind ") for w in words):
        kinds.add("tower")
    return kinds.pop() if len(kinds) == 1 else None


# ---------------------------------------------------------------------------------------
# Design fallback
# ---------------------------------------------------------------------------------------

# Used until data/designs.json gives each design its own "material". From that file's own
# "materials" text: L-4, L-6, D-6 and the R-6 cab are wood frame; the D-1 is peeled log; the
# steel makers are steel. L-5 (wood frame, but log in Region 1), the cupola houses (log or
# frame) and the California plans (wood, later steel) are mixed, so they give no material.
DESIGN_MATERIAL_FALLBACK: dict[str, str | None] = {
    "l4": "wood", "l5": None, "l6": "wood", "r6": "wood", "d6": "wood", "d1": "log",
    "cupola": None, "r5_lookouts": None,
    "aermotor": "steel", "ideco": "steel", "other_steel": "steel",
}
# Designs that are towers (their material is the tower's); the rest are cabs and houses.
TOWER_DESIGN_KINDS = {"steel_tower"}


def _design_is_tower(did: str, facts: dict) -> bool:
    """data/designs.json "part" == "tower" (the supporting structure; the rest are cabs, houses
    and whole lookouts); older files said "kind": "steel_tower"."""
    part = facts.get(did, {}).get("part")
    if part:
        return part == "tower"
    k = facts.get(did, {}).get("kind")
    return k in TOWER_DESIGN_KINDS if k else did in ("aermotor", "ideco", "other_steel")


def design_material(design_ids: list[str], kind: str | None, designs: list[dict] | None = None, region: str | None = None) -> tuple[str | None, str | None]:
    """(material, design id) from the lookout's recognised designs. A tower design (Aermotor)
    gives the tower's material; a cab design (L-4) gives it only for a building, since the cab
    says nothing about what the tower under it was made of. A design whose material depends on
    the state (the L-5: log in Montana and Idaho, frame elsewhere) says so in data/designs.json's
    "material_by_state", read with the lookout's `region`."""
    if kind in no_structure_kinds():
        return None, None
    facts = {d.get("id"): d for d in designs or [] if isinstance(d, dict)}

    def mat(did: str) -> str | None:
        by_state = facts.get(did, {}).get("material_by_state")
        m = by_state.get(region) if isinstance(by_state, dict) and region else None
        m = m or facts.get(did, {}).get("material")
        if isinstance(m, str) and m in MATERIALS:
            return m
        return DESIGN_MATERIAL_FALLBACK.get(did)

    def is_tower(did: str) -> bool:
        return _design_is_tower(did, facts)

    towers = [d for d in design_ids if is_tower(d) and mat(d)]
    cabs = [d for d in design_ids if not is_tower(d) and mat(d)]
    if kind in BUILDING_KINDS:
        pool = cabs
    elif kind in TOWER_KINDS:
        pool = towers
    else:
        pool = towers or ([] if any(not is_tower(d) for d in design_ids) else cabs)
    found = {mat(d) for d in pool}
    if len(found) == 1:
        return found.pop(), pool[0]
    return None, None


def design_is_tower(design_ids: list[str], designs: list[dict] | None = None) -> str | None:
    """A steel-tower design among them (an Aermotor is a tower whatever else is said)."""
    facts = {d.get("id"): d for d in designs or [] if isinstance(d, dict)}
    for did in design_ids:
        if _design_is_tower(did, facts):
            return did
    return None


# ---------------------------------------------------------------------------------------
# One source record
# ---------------------------------------------------------------------------------------

# Sources whose extract carries description text the merge can read words from directly.
DESCRIPTION_SOURCES = {"ridb", "fire_lookouts_org", "andyarthur_ny"}


def read_record(source: str, raw: dict) -> dict:
    """What one source record says about the structure and its state, read through the
    tables above:

      {"kind", "kind_from": "type"|"words"|"fetcher", "status", "status_note", "events",
       "material", "words", "roles", "flags", "unmapped": [(field, value), ...]}

    "material" is the record's explicit, kind-independent material (a type value, an OSM tag);
    description words wait for the tower's kind (words_material)."""
    extra = raw.get("extra") if isinstance(raw.get("extra"), dict) else {}
    out: dict = {"kind": raw.get("kind") or "unknown", "kind_from": "fetcher", "status": raw.get("status") or "unknown",
                 "status_note": None, "events": [], "material": None, "words": [], "roles": [], "flags": [],
                 "unmapped": []}

    type_raw = raw.get("type_raw")
    if isinstance(type_raw, str) and type_raw.strip():
        info = type_info(source, type_raw)
        if info is None:
            out["unmapped"].append(("type", type_raw))
        else:
            if info.kind != KEEP:
                out["kind"] = info.kind or "unknown"
                out["kind_from"] = "type"
            if info.material:
                out["material"] = info.material
            if info.role:
                out["roles"].append(info.role)
            if info.status and not (isinstance(raw.get("status_raw"), str) and raw["status_raw"].strip()):
                out["status"] = info.status

    status_raw = raw.get("status_raw")
    if isinstance(status_raw, str) and status_raw.strip():
        found = status_info(source, status_raw)
        if found is None:
            out["unmapped"].append(("status", status_raw))
        else:
            info, year = found
            if info.status != KEEP:
                out["status"] = info.status or "unknown"
            out["status_note"] = info.note
            if info.flag:
                out["flags"].append(info.flag)
            if info.event and year is not None:
                out["events"].append({"year": year, "event": info.event,
                                      "note": f"From {source.upper()} status column value {status_raw.strip()!r}",
                                      "from": source})

    words = [w for w in extra.get("structure_words") or [] if isinstance(w, str)]
    for w in words:
        if w not in STRUCTURE_WORDS:
            out["unmapped"].append(("structure_words", w))
    if source in DESCRIPTION_SOURCES:
        words += [w for w in structure_words(extra.get("description")) if w not in words]
    out["words"] = words
    if "role aws" in words and "aws" not in out["roles"]:
        out["roles"].append("aws")
    if out["kind"] in (None, "unknown"):
        k = words_kind(words)
        if k:
            out["kind"], out["kind_from"] = k, "words"

    if source == "osm":
        mat, bad = osm_material(extra)
        out["unmapped"] += [("osm_tag", b) for b in bad]
        out["material"] = out["material"] or mat
    return out


def apply(source: str, raw: dict) -> tuple[dict, dict]:
    """(raw with kind, status and status-year events replaced by the deliberate reading, the
    full reading). The source record itself is not changed."""
    info = read_record(source, raw)
    new = dict(raw)
    new["kind"] = info["kind"]
    new["status"] = info["status"]
    if info["events"]:
        have = {(e.get("event"), e.get("year")) for e in raw.get("events") or [] if isinstance(e, dict)}
        new["events"] = list(raw.get("events") or []) + [e for e in info["events"] if (e["event"], e["year"]) not in have]
    return new, info


# ---------------------------------------------------------------------------------------
# Guard: every value in data/sources has a deliberate mapping
# ---------------------------------------------------------------------------------------

SKIP_FILES = {"designs_reference.json", "ridb_excluded.json", "peaks_gnis.json", "commons_credits.json"}


def unmapped_values(sources_dir: Path = DATA / "sources") -> dict[str, dict[str, int]]:
    """{source: {"type: <value>": count, ...}} for every value nobody has mapped yet."""
    out: dict[str, dict[str, int]] = {}
    for path in sorted(Path(sources_dir).glob("*.json")):
        if path.name in SKIP_FILES:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("kind") == "reference" or not isinstance(data.get("records"), list):
            continue
        sid = str(data.get("source") or path.stem)
        for raw in data["records"]:
            if not isinstance(raw, dict):
                continue
            for field, value in read_record(sid, raw)["unmapped"]:
                bucket = out.setdefault(sid, {})
                k = f"{field}: {value}"
                bucket[k] = bucket.get(k, 0) + 1
    return out


# ---------------------------------------------------------------------------------------
# Backfill extra.structure_words from the crawl cache
# ---------------------------------------------------------------------------------------

def _backfill(sources: list[str]) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.path.insert(0, str(Path(__file__).resolve().parent / "regional"))
    from common import _cache_path  # noqa: E402
    for source in sources:
        path = DATA / "sources" / f"{source}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = missing = 0
        for raw in data["records"]:
            if source in ("nhlr", "fflos"):
                import fetch_registers  # noqa: E402
                p = _cache_path(source, raw["url"])
                text = fetch_registers.description_text(p.read_text(encoding="utf-8", errors="replace")) if p.exists() else None
            else:
                import firelookout_com  # noqa: E402
                text = firelookout_com.cached_prose(raw)
            if text is None:
                missing += 1
                continue
            words = structure_words(text)
            extra = raw.setdefault("extra", {})
            if words != (extra.get("structure_words") or []):
                changed += 1
                if words:
                    extra["structure_words"] = words
                else:
                    extra.pop("structure_words", None)
        # Written the way each fetcher writes it, so the diff is only the words.
        text_out = json.dumps(data, indent=2, ensure_ascii=False)
        path.write_text(text_out if source in ("nhlr", "fflos") else text_out + "\n", encoding="utf-8")
        print(f"{source}: {changed} records changed, {missing} with no cached page")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--backfill", nargs="*", metavar="SOURCE", default=None,
                    help="refresh extra.structure_words from the crawl cache (nhlr, fflos, firelookout_com)")
    ap.add_argument("--check", action="store_true", help="list type/status values with no mapping")
    args = ap.parse_args(argv)
    if args.backfill is not None:
        _backfill(args.backfill or ["nhlr", "fflos", "firelookout_com"])
    if args.check or args.backfill is None:
        bad = unmapped_values()
        for sid, vals in bad.items():
            for k, n in sorted(vals.items()):
                print(f"{sid}: {k} ({n})")
        if bad:
            return 1
        print("Every type and status value in data/sources has a mapping.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
