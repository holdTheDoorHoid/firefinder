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
import functools
import hashlib
import json
import math
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from state_bbox import STATE_BBOX, flag_coordinate  # noqa: E402
from photo_credit import extract_photo_credit  # noqa: E402
import designs as design_names  # noqa: E402
import structure  # noqa: E402

# Rough boxes for the territories, which state_bbox does not cover.
TERRITORY_BBOX = {"PR": (17.8, 18.6, -67.4, -65.2), "VI": (17.6, 18.5, -65.1, -64.5),
                  "GU": (13.2, 13.7, 144.6, 145.0), "AS": (-14.6, -11.0, -171.1, -168.1),
                  "MP": (14.0, 20.6, 144.8, 146.1), "DC": (38.7, 39.0, -77.2, -76.9)}


def inside_us(lat: float, lon: float) -> bool:
    return any(a <= lat <= b and c <= lon <= d for a, b, c, d in [*STATE_BBOX.values(), *TERRITORY_BBOX.values()])

# Files in data/sources that are not lists of lookouts.
SKIP_FILES = {"designs_reference.json", "ridb_excluded.json", "peaks_gnis.json"}

# ---------------------------------------------------------------------------------------
# Source configuration
# ---------------------------------------------------------------------------------------

# Processing order for matching, and the order sources are listed on a tower. Register and
# master-list sources first, so they seed the towers the others attach to. Sources not named
# here (a future extract) are processed last, alphabetically, at the lowest precedence.
SOURCE_ORDER = [
    "nhlr", "fflos", "ffla", "ridb", "ffla_rentals", "fire_lookouts_org", "tnlandforms",
    "nj_forest_fire_towers", "firelookout_com", "idaho_fl", "michigan_fire_tower",
    "pa_storymap", "andyarthur_ny", "wikipedia_lookout_lists", "cskt", "eastern_us_lookouts",
    "central_us_lookouts", "wikidata", "osm",
]

# Field precedence: the first source in the list that has a value wins. Mirrored in DESIGN.md
# 3.5; change both together.
#
# 2026-10-04 (gapstates): six sources added for the FFLA gap states -- tnlandforms.us (Tom
# Dunigan's GA/NC/TN tower pages: no licence stated but unusually well-structured and verified
# -- its TN GPX's NGS PIDs and GA page's GFC numbers both cross-checked against other
# registers -- ranked with fire-lookouts.org), nj_forest_fire_towers (Wikipedia's NJFFS tower
# table: structured, cited, its US#/NJ# register numbers verified byte-identical to nhlr.json's
# NJ entries, so ranked just under that tier), wikipedia_lookout_lists (the Louisiana wikitable:
# licensed, cited, ranked with the other licensed regional extracts), michigan_fire_tower (a
# small young single-author site, ranked with idahofirelookouts.com), and eastern_us_lookouts /
# central_us_lookouts (the two weebly "FOREST LOOKOUTS" hobby sites: no licence stated, heavy
# free text, most entries have no coordinates -- ranked lowest among named sources, just above
# OSM/Wikidata). Each is only added to a field's precedence list when the fetcher actually
# populates that field; see pipeline/regional/weebly_lookouts.py, nj_forest_fire_towers.py,
# wikipedia_lists.py, michigan_fire_tower.py, tnlandforms.py for what each one supplies.
PRECEDENCE: dict[str, list[str]] = {
    "name": ["nhlr", "fflos", "ridb", "ffla", "firelookout_com", "fire_lookouts_org",
             "tnlandforms", "nj_forest_fire_towers", "andyarthur_ny", "wikipedia_lookout_lists",
             "pa_storymap", "cskt", "eastern_us_lookouts", "central_us_lookouts", "wikidata",
             "idaho_fl", "michigan_fire_tower", "osm"],
    "location": ["nhlr", "fflos", "ffla", "fire_lookouts_org", "tnlandforms",
                 "nj_forest_fire_towers", "firelookout_com", "osm", "eastern_us_lookouts",
                 "central_us_lookouts", "wikidata", "ridb", "andyarthur_ny",
                 "wikipedia_lookout_lists", "pa_storymap", "idaho_fl", "michigan_fire_tower",
                 "cskt"],
    "status": ["ffla", "nhlr", "fflos", "ridb", "fire_lookouts_org", "tnlandforms",
               "nj_forest_fire_towers", "andyarthur_ny", "wikipedia_lookout_lists", "pa_storymap",
               "cskt", "firelookout_com", "idaho_fl", "michigan_fire_tower", "osm",
               "eastern_us_lookouts", "central_us_lookouts", "wikidata"],
    "kind": ["ffla", "nhlr", "fflos", "ridb", "firelookout_com", "fire_lookouts_org",
             "tnlandforms", "nj_forest_fire_towers", "pa_storymap", "andyarthur_ny",
             "wikipedia_lookout_lists", "cskt", "osm", "eastern_us_lookouts",
             "central_us_lookouts", "wikidata", "idaho_fl", "michigan_fire_tower"],
    "county": ["nhlr", "fflos", "ffla", "firelookout_com", "pa_storymap", "cskt",
               "andyarthur_ny", "wikipedia_lookout_lists", "fire_lookouts_org", "tnlandforms",
               "nj_forest_fire_towers", "eastern_us_lookouts", "central_us_lookouts", "wikidata",
               "michigan_fire_tower"],
    "elevation_m": ["nhlr", "fflos", "firelookout_com", "fire_lookouts_org", "tnlandforms",
                    "nj_forest_fire_towers", "ridb", "wikidata", "cskt", "osm"],
    "built": ["nhlr", "fflos", "firelookout_com", "fire_lookouts_org", "pa_storymap", "ridb",
              "wikidata", "cskt", "idaho_fl", "osm", "andyarthur_ny", "ffla"],
    "design": ["nhlr", "fflos", "firelookout_com", "fire_lookouts_org", "pa_storymap", "cskt",
               "eastern_us_lookouts", "central_us_lookouts"],
    # Explicit words only (a type value, a description, an OSM tag); the design comes after.
    "material": ["ffla", "nhlr", "fflos", "firelookout_com", "fire_lookouts_org", "ridb", "osm",
                 "andyarthur_ny"],
    "height_m": ["nhlr", "fflos", "firelookout_com", "fire_lookouts_org", "nj_forest_fire_towers",
                 "pa_storymap", "cskt", "eastern_us_lookouts", "central_us_lookouts", "wikidata",
                 "osm"],
    "agency": ["nhlr", "fflos", "ridb", "firelookout_com", "fire_lookouts_org", "tnlandforms",
               "nj_forest_fire_towers", "pa_storymap", "andyarthur_ny", "cskt",
               "eastern_us_lookouts", "central_us_lookouts", "osm", "michigan_fire_tower"],
    "ownership": ["cskt", "ridb", "nhlr", "fflos", "andyarthur_ny", "pa_storymap",
                  "fire_lookouts_org", "nj_forest_fire_towers", "firelookout_com", "ffla",
                  "eastern_us_lookouts", "central_us_lookouts", "osm", "michigan_fire_tower"],
    "access": ["cskt", "osm"],
    "staffing": ["firelookout_com", "fire_lookouts_org", "cskt", "idaho_fl"],
    "rental": ["ridb", "ffla_rentals"],
    "events": ["nhlr", "fflos", "firelookout_com", "fire_lookouts_org", "pa_storymap", "ridb",
               "wikidata", "cskt", "idaho_fl", "michigan_fire_tower", "ffla", "osm",
               "andyarthur_ny"],
    "photos": ["nhlr", "fflos", "firelookout_com", "fire_lookouts_org", "nj_forest_fire_towers",
               "pa_storymap", "eastern_us_lookouts", "central_us_lookouts", "wikidata",
               "andyarthur_ny", "idaho_fl", "cskt", "ridb", "osm", "ffla"],
}

# Sources whose positions share a lineage. For verification ("facts" needs two independent
# sources agreeing on location and status) a whole group counts once. NHLR/FFLOS and FFLA
# share lineage (the FFLA tables carry the register numbers); firelookout.com is in the
# group too because 3,173 of its 3,266 coordinates are byte-identical to an FFLA row.
LOCATION_LINEAGE = {"nhlr": "registers", "fflos": "registers", "ffla": "registers",
                    "firelookout_com": "registers"}

# Association project sources (DESIGN.md 3.7): lookout associations' own year-by-year reports of
# the work they did on particular lookouts (FFLA chapters, "Friends of" groups, the Catskill Fire
# Tower Project...), one module in pipeline/regional/ each, all in the one record shape of
# pipeline/regional/_projects.py. Adding an association is one entry here: the source id
# (the "source" of its data/sources/<id>.json, which must carry "family": "association_projects").
# register_associations() then puts it in the match order, at the foot of the facts precedence
# lists below (the registers and lists outrank it), in the registers' location lineage (its
# positions are copied from those lists, so they never count as independent confirmation), and
# gives its page a labelled "association" link on the tower. Its events join the tower's timeline
# with the report that gives them as their source.
ASSOCIATION_FAMILY = "association_projects"
ASSOCIATION_SOURCES: list[str] = [
    "nwmt_projects",
    # the West and the Rockies (agent chapters-west)
    "sand_mountain", "mountaineers_everett", "snoqualmie_lookouts", "buck_rock", "anffla", "scmf_lookouts",
    "ffla_sdrc", "ffla_monterey", "hi_mountain", "mvffla", "historicorps_west", "siskiyou_mountain_club",
    "green_mountain_wa", "ffla_ca_south", "ffla_west_reports",
    # the East, the South and the Midwest (agent chapters-east), one source per line
    "nysffla_projects",
    "st_regis_friends",
    "hurricane_friends",
    "mt_arab_friends",
    "azure_mountain_friends",
    "bald_mountain_friends",
    "bramley_friends",
    "kent_conservation_foundation",
    "stillwater_friends",
    "smokies_friends",
    "ffla_east_reports",
]
# Fields an association supplies (the rest -- registers, rental, photos, access -- it does not).
ASSOCIATION_FIELDS = ("name", "location", "status", "kind", "county", "elevation_m", "built", "design",
                      "height_m", "agency", "ownership", "staffing", "events")


def register_associations(sources: list[str]) -> None:
    """Put association project sources into SOURCE_ORDER (before Wikidata and OSM), the end of
    each ASSOCIATION_FIELDS precedence list, and the registers' location lineage. Idempotent."""
    for sid in sources:
        if sid not in SOURCE_ORDER:
            at = SOURCE_ORDER.index("wikidata") if "wikidata" in SOURCE_ORDER else len(SOURCE_ORDER)
            SOURCE_ORDER.insert(at, sid)
        for f in ASSOCIATION_FIELDS:
            if f in PRECEDENCE and sid not in PRECEDENCE[f]:
                PRECEDENCE[f].append(sid)
        LOCATION_LINEAGE[sid] = "registers"


register_associations(ASSOCIATION_SOURCES)

# Sources that list one lookout twice (a node and a way in OSM; a Facility and a Campground
# in RIDB; border lookouts on two state maps at firelookout.com; repeated table rows in FFLA;
# repeat posts at idahofirelookouts.com). Two records from one of these may share a tower if
# they are within this many metres and their names agree.
DOUBLE_LISTED = {"ffla": 50, "firelookout_com": 100, "idaho_fl": 100, "osm": 100,
                 "ridb": 300, "wikidata": 100}
# Of those, sources whose duplicates may be unnamed or generically named ("Fire Tower").
DOUBLE_LISTED_GENERIC = {"osm", "wikidata"}
# FFLA lists a lookout on a state line under "(Border - see X)" in each state, with positions that
# can differ by a few hundred metres (DE and MD's "Interstate": 270 m).
BORDER_DOUBLE_LISTED_M = 400

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
# A same-spot match (<= MATCH_SAME_SPOT_M) whose name is *clearly* different (score < PARTIAL)
# from every member of the near tower may still be a plain coordinate error in the source: the
# record really belongs to a different tower it strongly (score >= STRONG) and uniquely names,
# somewhere else in the region. Sized to recreation.gov's "Lookout Butte Lookout" facility,
# whose pin sits 45 m from Black Butte, ID but whose listing is genuinely Lookout Butte's, 64 km
# away -- "say within 60 km" undershoots that real case, so this gives headroom without reaching
# across a whole region. See candidates() and merge_report.json's "reassigned_same_spot" review.
#
# Restricted to the sources DESIGN.md already singles out as having "rougher" pins (idahofl and
# RIDB share a 3 km STRONG_RADIUS_BY_SOURCE for the same reason). Everywhere else, a same-spot
# match with a different name is usually a real alternate name (Pequawket = Kearsarge North,
# or GA/NC/SC towers the eastern/central weebly sites know by a different local name than
# tnlandforms/NHLR do -- confirmed in the committed data by already-shared `other_names`), and a
# same-named tower 10s of km away is coincidence (common names recur: "Buck Peak", "Sugarloaf",
# "ADAMS"). Trying this against the whole dataset from scratch (no `by_key` memory) misattached
# several such coincidences and every "<X> (now at <Y>)" relocated-structure record (the near
# tower's different name there is explained by the move, not a coordinate bug) before this
# restriction and the relocation check in _reassign_same_spot() were added.
REASSIGN_SOURCES = {"ridb", "idaho_fl"}
REASSIGN_RADIUS_M = 75_000
NEAR_MISS_M = 10000
REGISTER_FAR_M = 5000
BUILT_CONFLICT_YEARS = 2
CONFLICT_LOCATION_M = 500
STRONG = 0.85
PARTIAL = 0.5

# The FFLA rentals list (source ffla_rentals) gives a name, a state and a booking link but no
# position, so its entries are placed by Matcher.match_rentals(): the recreation.gov facility
# number in the link, else a name match in the state. This table pins the ones those cannot
# settle, by the rental's key. The value is a tower id (permanent) or the key of any source
# record that tower holds. Each entry says why.
FFLA_RENTAL_OVERRIDES: dict[str, str] = {
    # Booked through Airbnb, "Managed by private owner" (2026-10). The standing lookout on private
    # land at Fernwood, Idaho was built on Stranger Mountain near Chewelah, WA in 1959 and moved to
    # Crystal Ridge/Peak in 1983 (the Airbnb listing says so); FFLA's table calls it "Crystal Ridge
    # (Relocated Stranger Mtn, WA)". The name "Crystal Peak" alone names an older, gone site 1.5 km
    # away (us-id-crystal-peak), so the name match cannot choose.
    "ffla_rentals:id:crystal-peak-relocated-lookout": "us-id-stranger-mountain-at-crystal-ridge",
    # The 1930s-style replica FFLA lists as "Timber Butte (Replica)", Lane County, OR; the rental is
    # "Timber Butte Replica" (recreation.gov 233133). The word "Replica" in the rental's name keeps
    # it from scoring as the same name as the tower's "Timber Butte". Given by the FFLA record's key
    # because that tower may be new in the run that places the rental (it has no id yet).
    "ffla_rentals:or:timber-butte-replica-lookout": "ffla:or:timber-butte-replica:43.9253:-122.5716",
    # Airbnb listing "Lorena Butte Lookout Tower" at Goldendale, WA, private land (Lefever Holbrook
    # Ranch). NHLR 1549 / FFLA "Lefever (Relocated Lorena Butte)" is the standing lookout there; the
    # old Lorena Butte site (us-wa-pierson-ridge, "Lorena Butte" alias) is the gone one.
    "ffla_rentals:wa:lorena-butte-relocated-lookout": "us-wa-lorena-butte-at-lefever",
    # Washington State Parks rents "Mount Spokane Quartz Mountain Fire Lookout" (the parks.wa.gov
    # link). Three towers answer to Quartz Mountain in WA; this one is the Mount Spokane vista-house
    # lookout moved to Quartz Mountain in Spokane County (NHLR 1558), the standing one. The other
    # two (Colville NF, Wenatchee NF) are gone sites.
    "ffla_rentals:wa:quartz-mountain-lookout": "us-wa-mount-spokane-at-quartz-mountain",
}

# Records that spatial matching cannot be trusted to place, pinned to a tower by the record's
# key. The value is a tower id (permanent) or the key of any source record that tower holds
# (stable across a from-scratch run, where the tower has no id yet). Used by Matcher.match_source()
# after the key memory and before the register and spatial steps. Each entry says why.
RECORD_JOINS: dict[str, str] = {
    # The recreation.gov rental "POST CREEK GUARD STATION" (234404) is the lookout NHLR registers as
    # "Post Creek Fireman-Lookout House" (the FFLA lists it as "Post Creek Lookout"): a 1934 CCC
    # cabin built for fire watching. The names share no words past "Post Creek" and RIDB's pin is
    # 779 m from the registered position, outside the 400 m a partial name match may span, so
    # without this it would start a second, permanent tower for the same building.
    "ridb:234404": "nhlr:US 1363",
    # "MT. BALDY-BUCKHORN RIDGE" (234432) is the Baldy Mountain Lookout in the Kootenai NF (NHLR
    # 1512, FFLA "Mt. Baldy Lookout"). Its pin is 370 m from the registered one, inside the 400 m
    # partial-name limit by 30 m; pinned so a small shift in RIDB's coordinates cannot start a
    # duplicate tower.
    "ridb:234432": "nhlr:US 1512",
}

# Hobbyist and regional sites, with the words used for credits and link labels.
SOURCE_SITE = {
    "ffla": "Forest Fire Lookout Association (firelookout.org)",
    "ffla_rentals": "Forest Fire Lookout Association: lookout rentals (firelookout.org)",
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
    "eastern_us_lookouts": "easternuslookouts.weebly.com",
    "central_us_lookouts": "centraluslookouts.weebly.com",
    "wikipedia_lookout_lists": "Wikipedia",
    "nj_forest_fire_towers": "Wikipedia (List of New Jersey Forest Fire Service fire towers)",
    "michigan_fire_tower": "michiganfiretower.com",
    "tnlandforms": "tnlandforms.us (Tom Dunigan)",
}

# Default photo licence per source, where the source states one (None = not stated).
PHOTO_LICENSE = {
    "nhlr": "All rights reserved",
    "fflos": "All rights reserved",
    "andyarthur_ny": "CC BY 3.0",
    "fire_lookouts_org": "Reuse allowed with credit",
    "ridb": "Public domain (US government)",
    "wikipedia_lookout_lists": "CC BY-SA 4.0",
    "nj_forest_fire_towers": "See Wikimedia Commons file page (varies per photo)",
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

# Kinds the owner has chosen to hide, from data/structure_kinds.json ("hidden": true). Since
# 2026-10-08 none is: camps, lookout trees and bare points are shown as sites with no structure.
HIDDEN_KIND_REASON = structure.hidden_kind_reasons()
# Camps, lookout trees and bare lookout points: nothing was built to stand in.
NO_STRUCTURE = structure.no_structure_kinds()


def _design_facts() -> list[dict]:
    """data/designs.json's designs: each one's part (cab, house, tower or whole lookout) and its
    "material" (structure.design_material)."""
    try:
        return json.loads((DATA / "designs.json").read_text(encoding="utf-8")).get("designs") or []
    except (OSError, json.JSONDecodeError, AttributeError):
        return []


DESIGN_FACTS = _design_facts()


def _design_mentions() -> dict[str, list[str]]:
    """data/design_mentions.json (pipeline/extract_design_mentions.py): design names found in
    the register and hobbyist prose the extracts do not keep, by source record key. Records whose
    prose tells of more than one structure ("replaced an Aermotor tower") are left out: their
    designs may not be today's, so they say nothing about what the lookout is built of."""
    try:
        data = json.loads((DATA / "design_mentions.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    several = set(data.get("several_structures") or [])
    return {k: v for k, v in (data.get("mentions") or {}).items() if k not in several and isinstance(v, list)}


DESIGN_MENTIONS = _design_mentions()
# Human decisions on single records, by source key. Each entry hides the tower holding that
# record (reason shown), however the sources describe it.
HIDE_KEYS = {
    "osm:node/358671897": "Not confirmed as a fire lookout",  # "East Lookout Tower", Guam (2026-10-04)
}
NEVER_BUILT_STATUS = {"proposed", "planned", "never built"}
NOT_A_LOOKOUT_SECTION = "sites determined not to have been used as wildland fire lookouts"
# FFLA's separate "Unknown/Undocumented" list (ca-un): emergency, planned and never-built sites
# from one survey, which FFLA keeps out of its lookout lists until evidence turns up.
UNDOCUMENTED_SECTION = "unknown/undocumented"

TOWER_KEYS = [
    "id", "name", "summary", "other_names", "country", "region", "county", "location", "elevation_m",
    "kind", "material", "material_from", "roles", "design", "height_m", "status", "status_note", "registers",
    "agency", "ownership", "access", "staffing", "visit", "rental", "events", "photos", "links", "sources",
    "conflicts", "research", "verification", "locked", "hidden", "hidden_reason", "updated",
]
FIELD_ORDER = [
    "name", "location", "county", "elevation_m", "kind", "material", "roles", "design", "height_m", "status",
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
    if letters and all(c.isupper() for c in letters) and len(letters) > 3 and " " in s:
        s = smart_title(s)  # "BALD KNOB LOOKOUT"; a lone acronym ("CBFIC") stays
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


_ANNOTATION_WORDS = re.compile(r"\b(relocated|replica|parts from)\b", re.I)
_ANNOTATION_RE = re.compile(r"\s*\((?P<body>[^()]*\b(?:relocated|replica|parts from)\b[^()]*)\)", re.I)
STATE_BY_NAME = {v.lower(): k for k, v in STATE_NAMES.items()}
_BORDER_POINTER_RE = re.compile(r"^\(border\s*[-\u2013\u2014]\s*see\s+([A-Za-z ]+)\)", re.I)


def _state_code(text: str) -> str | None:
    t = text.strip().strip(".").lower()
    if t.upper() in STATE_NAMES:
        return t.upper()
    return STATE_BY_NAME.get(t)


def expand_place(text: str) -> str:
    """"Huckleberry Mtn" -> "Huckleberry Mountain" for display."""
    text = re.sub(r"\bMtn\b\.?", "Mountain", text)
    text = re.sub(r"\bPk\b\.?", "Peak", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_annotation(name: str | None) -> tuple[str | None, dict | None]:
    """Split a name carrying a structure-history note into the plain name and the note.

    FFLA writes moved and copied lookouts as "<where it is now> (<note>)":
      "State Fair (Relocated Padlock Hill)"         kind relocated, origin Padlock Hill
      "Crystal Ridge (Relocated Stranger Mtn, WA)"  origin Stranger Mountain, in WA
      "Kathio State Park (Relocated from near Isle)", "Trout Mountain (Relocated from Alabama)"
      "Kellogg Peak (Replica)", "Missoula Aerial Fire Depot (Hornet Peak Replica)"
      "Mackenzie Center (Replica – from State Fair)"   a replica that was moved
      "Wilson Hill WMA #1 (Parts from Whites Hill)"  built with another tower's parts
    NHLR does the same in a few names ("OFS Cool Springs Fire Tower (Relocated Spears)").
    """
    if not name:
        return name, None
    m = _ANNOTATION_RE.search(name)
    if not m:
        return name, None
    site = re.sub(r"\s+", " ", (name[:m.start()] + " " + name[m.end():])).strip(" -\u2013")
    body = m.group("body").strip()
    ann: dict = {"kind": None, "origin": None, "origin_region": None, "near": False,
                 "same_place": False, "unknown_origin": False, "replica_of": None, "note": None, "raw": body}
    low = body.lower()
    rest: str | None = None
    if "parts from" in low:
        ann["kind"] = "parts"
        rest = re.split(r"parts from", body, flags=re.I)[1]
    elif "replica" in low:
        ann["kind"] = "replica"
        before, after = re.split(r"\breplica\b", body, maxsplit=1, flags=re.I)
        ann["replica_of"] = expand_place(before.strip(" -\u2013")) or None
        after = after.strip(" -\u2013")
        fm = re.match(r"^from\s+(.+)$", after, re.I)
        if fm:
            rest = fm.group(1)
        elif after:
            ann["note"] = after
    else:
        ann["kind"] = "relocated"
        rest = re.split(r"relocated", body, maxsplit=1, flags=re.I)[1]
    if rest is not None:
        rest = rest.strip(" -\u2013")
        rest = re.sub(r"^from\s+", "", rest, flags=re.I)
        if re.match(r"^near\s+", rest, re.I):
            ann["near"] = True
            rest = re.sub(r"^near\s+", "", rest, flags=re.I)
        # "Deer Town – non-fire", "Jefferson – Loc 1"; but "Salyer NWR – HQ" is one name
        nm = re.match(r"^(.*?)\s+[\u2013-]\s+(non-fire|loc\s*\d+)$", rest, re.I)
        if nm:
            rest, ann["note"] = nm.group(1).strip(), nm.group(2).strip()
        if re.fullmatch(r"(on\s+)?(the\s+)?same\s+(mountain|site|hill|peak)", rest, re.I):
            ann["same_place"] = True
            return site or name, ann
        if rest.lower() in ("unknown", "an unknown site", "?"):
            ann["unknown_origin"] = True
            return site or name, ann
        whole_state = _state_code(rest)
        if whole_state:
            ann["origin_region"] = whole_state
        elif "," in rest:
            place, _, st = rest.rpartition(",")
            code = _state_code(st)
            if code:
                ann["origin_region"] = code
                rest = place.strip()
            ann["origin"] = expand_place(rest) or None
        elif rest:
            ann["origin"] = expand_place(rest)
    return site or name, ann


# Parenthetical notes about a lookout's state, not part of its name. Each becomes a status,
# an access level, a note or a reason to hide (parse_status_note).
_GONE_WORDS = r"demolished|removed|destroyed|razed|torn down|burned(?: down)?(?: \d{4})?|burnt|gone|site only"
STATUS_NOTES = [
    # (pattern for the whole parenthetical, what it means)
    (re.compile(rf"^(?:{_GONE_WORDS})$", re.I), {"status": "gone"}),
    (re.compile(r"^(?:collapsed|ruins?)$", re.I), {"status": "ruins"}),
    (re.compile(r"^(?:likely|probably|possibly|maybe)\s+(?:gone|removed|demolished|destroyed)$|^(?:gone|removed)\s*\?$", re.I),
     {"status": "unknown", "note": "Sources suggest it is gone."}),
    (re.compile(r"^non-?fire(?:\s+(?:tower|lookout))?$", re.I),
     {"hidden_reason": "Not a fire lookout ({src} lists it as a non-fire tower)"}),
    (re.compile(r"^private$", re.I), {"access": "private", "note": "{src} marks it private."}),
    (re.compile(r"^closed$", re.I), {"access": "closed", "note": "{src} marks it closed."}),
    (re.compile(r"^(?:status\s+)?unknown$", re.I), {"note": "{src} marks this entry \u201cunknown\u201d: details are uncertain."}),
    (re.compile(r"^same as (?P<other>.+?)\s*\?$", re.I), {"note": "{src} asks whether this is the same lookout as {other}."}),
]
_PAREN_RE = re.compile(r"\s*\(([^()]*)\)")


def parse_status_note(name: str | None) -> tuple[str | None, dict | None]:
    """Take a state note out of a name: "Buffalo Lookout Tower (Demolished)" -> status gone;
    "Muzette Lookout Tower (likely gone)" -> status unknown and a note; "Slide Mountain
    (Non-fire Tower)" -> hidden; "Orchard Point (unknown)" and "Big Stony (same as Stony
    Creek?)" -> a note. Alternate names and qualifiers ("(Loc 2)", "(Liberty)") stay."""
    if not name:
        return name, None
    for m in _PAREN_RE.finditer(name):
        body = m.group(1).strip()
        for pattern, meaning in STATUS_NOTES:
            pm = pattern.match(body)
            if pm:
                info = {"raw": body, "original": name, **meaning}
                if pm.groupdict().get("other"):
                    info["other"] = pm.group("other")
                plain = re.sub(r"\s+", " ", name[:m.start()] + " " + name[m.end():]).strip()
                return plain or name, info
    return name, None


def status_note_text(info: dict, source: str) -> dict:
    """Fill the source's short name into a status note's texts."""
    src = SHORT_NAME.get(source, source)
    return {k: (v.format(src=src, other=info.get("other", "")) if isinstance(v, str) and k in ("note", "hidden_reason") else v)
            for k, v in info.items()}


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
            # "(Relocated X)", "(Replica)", "(Parts from X)" describe the structure's history,
            # not another name for this place: see parse_annotation()
            if p and not re.match(r"^(same as|see\b|railroad|military|unk|\?)", p, re.I) and not _ANNOTATION_WORDS.search(p):
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


SLUG_KEEP_BEFORE_TRAILING = {"big", "little", "old", "new", "high", "low", "the", "north", "south", "east", "west"}


def slugify(text: str) -> str:
    def tokens(t: str) -> list[str]:
        t = re.sub(r"\bnon-fire\b", "nonfire", ascii_fold(t).lower())
        return re.sub(r"[^a-z0-9]+", " ", t.replace("'", "")).split()

    def trim(toks: list[str]) -> list[str]:
        toks = list(toks)
        while len(toks) > 1 and toks[-1] in SLUG_TRAILING:
            if len(toks) == 2 and toks[0] in SLUG_KEEP_BEFORE_TRAILING:
                break  # "Big Tower" stays big-tower
            toks.pop()
        return toks

    base, paren, rest = text.partition("(")
    if name_forms(text):  # a generic name ("Fire Tower") keeps all its words
        toks = trim(trim(tokens(base)) + tokens(rest)) if paren and name_forms(base) else trim(tokens(text))
    else:
        toks = tokens(text)
    slug = "-".join(toks)
    if len(slug) > 80:
        slug = slug[:80].rsplit("-", 1)[0]
    return slug or "lookout"


def id_slug(name: str) -> str:
    """Slug for an id. Alternate names and qualifiers in parentheses stay, since they tell
    same-named lookouts apart ("Barnum (Loc 2)", "High Knob (JNF)"); a structure-history note
    never reaches here (see history_naming). "Lookout" before a parenthetical goes too:
    "Pilot Peak Lookout (Payette National Forest)" -> pilot-peak-payette-national-forest."""
    return slugify(name)


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
    annotation: dict | None = None  # structure history from the name: see parse_annotation()
    status_info: dict | None = None # state note from the name: see parse_status_note()
    structure: dict = field(default_factory=dict)  # kind/status/material reading: structure.read_record()

    @classmethod
    def build(cls, source: str, raw: dict, order: int) -> "Rec":
        # Kind and status through the deliberate tables in structure.py, not the fetcher's own map.
        raw, reading = structure.apply(source, raw)
        r = cls(source, raw, order)
        r.structure = reading
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
        plain, r.annotation = parse_annotation(clean_name(raw.get("name")))
        plain, info = parse_status_note(plain)
        r.status_info = status_note_text(info, source) if info else None
        r.display = clean_ridb_name(raw.get("name")) if source == "ridb" else plain
        r.forms = name_forms(plain, aliases)
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
    history: Rec | None = None          # the member whose name carries a structure-history note
    origin: "Tower | None" = None       # the tower at the site this structure came from
    origin_alternatives: list = field(default_factory=list)
    slug_text: str | None = None        # what the id is made from, when not the plain name
    source_status: tuple = (None, None)  # (status, source) as the sources gave it, before research
    source_kind: tuple = (None, None)

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


def is_border_row(rec: Rec) -> bool:
    """An FFLA row under "(Border - see Montana)": a lookout on a state line, listed in both states."""
    return bool(_BORDER_POINTER_RE.match(str(rec.extra.get("section") or "")))


def is_relocated(rec: Rec) -> bool:
    if rec.annotation and rec.annotation["kind"] in ("relocated", "replica", "parts"):
        return True
    return "relocated" in str(rec.extra.get("section") or "").lower()


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
        if (data.get("family") == ASSOCIATION_FAMILY) != (sid in ASSOCIATION_SOURCES):
            log(f"WARNING: {path.name}: " + (f"carries family {ASSOCIATION_FAMILY!r} but {sid!r} is not in ASSOCIATION_SOURCES (merge.py): add it"
                                             if data.get("family") == ASSOCIATION_FAMILY else
                                             f"{sid!r} is in ASSOCIATION_SOURCES but the extract has no \"family\": \"{ASSOCIATION_FAMILY}\""))
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
        self._reassign_logged: set[str] = set()  # dedupe: candidates() can run >1x per record

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
        if a.source == "ffla" and a.region != b.region and (is_border_row(a) or is_border_row(b)):
            limit = BORDER_DOUBLE_LISTED_M   # a border lookout in both states' lists, positions a few hundred metres apart
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
        if rec.source == "ffla_rentals":
            return True     # one lookout can have several booking pages (two cabins, two sites)
        same = [m for m in tower.members if m.source == rec.source]
        if rec.source == "ffla" and not rec.has_coords and is_border_row(rec):
            # a "(Border - see Montana)" pointer is the other state's row again, not a second lookout
            return all(m.region != rec.region or self.double_listed(rec, m) for m in same)
        return all(self.double_listed(rec, m) for m in same)

    # -- candidate scoring --------------------------------------------------------------

    def candidates(self, rec: Rec) -> list[tuple]:
        """(rank, distance, tower, score) for every tower this record may join."""
        strong_r = STRONG_RADIUS_BY_SOURCE.get(rec.source, MATCH_STRONG_M)
        seen: set = set()
        out = []
        same_spot_bad_name: list[tuple[float, "Tower"]] = []
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
                # a structure record prefers a tower that is not a camp/tree/point row at the same spot
                kinds = {m.raw.get("kind") for m in t.members} - {None, "unknown"}
                penalty = 1 if (rec.raw.get("kind") not in (None, "unknown", *NO_STRUCTURE)
                                and kinds and kinds <= NO_STRUCTURE) else 0
                out.append((-eff, penalty, d, t, score, same_region))
                if d <= MATCH_SAME_SPOT_M and score is not None and score < PARTIAL:
                    same_spot_bad_name.append((d, t))

        if same_spot_bad_name and rec.region and rec.source in REASSIGN_SOURCES:
            out.extend(self._reassign_same_spot(rec, same_spot_bad_name, seen))
        return out

    def _reassign_same_spot(self, rec: Rec, near: list[tuple[float, "Tower"]], seen: set) -> list[tuple]:
        """A record sits within MATCH_SAME_SPOT_M of a tower whose name clearly does not match
        it (a source's own coordinate error, not a relocated structure -- see parse_annotation()
        for that case). If exactly one other tower in the region strongly and uniquely matches
        the record's name within REASSIGN_RADIUS_M, candidates() also offers that tower; its
        higher name score sorts it ahead of the near-but-wrong one in the caller's greedy match,
        so it wins. Ambiguous (more than one strong match) is logged but not acted on. A near
        tower that is itself a relocated/replica/parts-from structure's current site is left
        alone: its different name there is explained by the move (DESIGN.md "Moved, copied and
        rebuilt structures"), not evidence of a coordinate error."""
        if any(mem.annotation and mem.annotation["kind"] in ("relocated", "replica", "parts")
               for _, t in near for mem in t.members):
            return []
        strong = []
        for c in cells_around(rec.lat, rec.lon, REASSIGN_RADIUS_M):
            for t in self.grid.get(c, ()):
                if t in seen:
                    continue
                seen.add(t)
                if rec.region not in t.regions():
                    continue
                d = t.min_dist(rec.lat, rec.lon)
                if d is None or d > REASSIGN_RADIUS_M:
                    continue
                score = name_score(rec.forms, t.forms())
                if score is not None and score >= STRONG:
                    strong.append((d, t, score))
        if not strong:
            return []
        nearest_d, nearest_t = min(near, key=lambda x: x[0])
        already_logged = rec.key in self._reassign_logged
        self._reassign_logged.add(rec.key)
        if len(strong) > 1:
            if not already_logged:
                self.review.append({
                    "type": "reassign_same_spot_ambiguous", "key": rec.key,
                    "nearby_tower_seq": nearest_t.seq,
                    "tower_seqs": sorted(t.seq for _, t, _ in strong),
                    "note": "Within 100 m of a differently-named tower, but more than one other "
                            "tower in the region strongly matches its name; left attached to the "
                            "near tower for a human to check.",
                })
            return []
        d, t, score = strong[0]
        if not already_logged:
            self.review.append({
                "type": "reassigned_same_spot", "key": rec.key,
                "nearby_tower_seq": nearest_t.seq, "near_distance_m": round(nearest_d),
                "tower_seq": t.seq, "distance_m": round(d), "score": score,
                "note": f"{rec.display!r} sits within 100 m of a differently-named tower but its "
                        f"name strongly matches a tower {round(d / 1000, 1)} km away; attached "
                        f"there instead of the near one.",
            })
        kinds = {m.raw.get("kind") for m in t.members} - {None, "unknown"}
        penalty = 1 if (rec.raw.get("kind") not in (None, "unknown", *NO_STRUCTURE)
                        and kinds and kinds <= NO_STRUCTURE) else 0
        return [(-score, penalty, d, t, score, True)]

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
            # An FFLA "(Border - see Montana)" pointer has no position because the other state's
            # list gives it: look for the lookout in both states, whatever the county.
            border = _BORDER_POINTER_RE.match(str(r.extra.get("section") or ""))
            border_region = STATE_BY_NAME.get(border.group(1).strip().lower()) if border else None
            regions = [r.region or ""] + ([border_region] if border_region else [])
            seen_towers: set = set()
            for region in regions:
                for t in self.by_region.get(region, ()):
                    if t in seen_towers:
                        continue
                    seen_towers.add(t)
                    s = name_score(r.forms, t.forms())
                    if s is None or s < 0.95:
                        continue
                    tcounties = {c.lower() for c in (record_county(m) for m in t.members) if c}
                    if county and tcounties and county.lower() not in tcounties and not border_region:
                        continue
                    if self.can_join(r, t):
                        cands.append(t)
            if len(cands) == 1:
                self.attach(r, cands[0], "name", "FFLA border pointer" if border_region else None)
            else:
                section = str(r.extra.get("section") or "")
                if section.startswith("(Border"):
                    r.match_note = f"no coordinates; FFLA border pointer {section}"
                else:
                    r.match_note = "no coordinates; " + ("several same-name lookouts in the state" if cands else "no same-name lookout in the state")
                self.unplaced.append(r)
        self.deferred = []

    def match_rentals(self, recs: list[Rec]) -> None:
        """Place the FFLA rentals list (no coordinates) on towers, after every other source.

        In order: FFLA_RENTAL_OVERRIDES; the key matched on an earlier run; the recreation.gov
        facility number in the booking link (a tower holding that ridb record); the entry's
        name against the towers of its state. A name match must be a unique one: among towers
        that name the place (score >= 0.95) the ones recreation.gov already rents win, then
        the ones not known to be gone; a nearly-the-same name (>= 0.85) is accepted only when
        it is the one tower in the state that is already rentable, and is listed for review.
        Anything left is listed as unplaced, with the candidates, for an override."""
        by_id = {t.id: t for t in self.towers if t.id}
        for r in sorted(recs, key=lambda x: x.key):
            target = FFLA_RENTAL_OVERRIDES.get(r.key)
            if target is not None:
                t = self.by_key.get(target) or by_id.get(target)
                if t is None:
                    self.review.append({"type": "ffla_rental_override_unknown_tower", "key": r.key, "target": target})
                elif self.can_join(r, t):
                    self.attach(r, t, "override", f"FFLA_RENTAL_OVERRIDES -> {target}")
                    continue
            t = self.by_key.get(r.key)
            if t is not None:
                self.attach(r, t, "key")
                continue
            fid = (r.raw.get("rental") or {}).get("ridb_facility_id")
            t = self.by_key.get(f"ridb:{fid}") if fid else None
            if t is not None and self.can_join(r, t):
                self.attach(r, t, "facility", f"recreation.gov facility {fid}")
                continue
            pool = []
            for t in self.by_region.get(r.region or "", ()):
                if not t.members and t.existing is None:
                    continue
                s_ = name_score(r.forms, t.forms())
                if s_ is not None and s_ >= STRONG and self.can_join(r, t):
                    pool.append((s_, t))

            def rentable(t: Tower) -> bool:   # recreation.gov rents it now
                return any(m.source == "ridb" and isinstance(m.raw.get("rental"), dict) and m.raw["rental"].get("available")
                           for m in t.members)

            def gone(t: Tower) -> bool:       # every source that takes a position on it says it is gone
                sts = {record_status(m) for m in t.members} - {None}
                return bool(sts) and sts <= {"gone", "ruins", "relocated"}

            strong = [t for s_, t in pool if s_ >= 0.95]
            chosen, note = None, None
            # narrow the strong candidates step by step, keeping a narrower set only if it is not empty
            cands = strong
            for keep in (rentable, lambda t: not gone(t)):
                narrower = [t for t in cands if keep(t)]
                if len(cands) > 1 and narrower:
                    cands = narrower
            if len(cands) == 1:
                chosen = cands[0]
            elif not strong:
                loose = [t for s_, t in pool if rentable(t)]
                if len(loose) == 1:
                    chosen, note = loose[0], "name nearly matches"
                    self.review.append({"type": "ffla_rental_loose_name_match", "key": r.key, "tower_seq": chosen.seq})
            if chosen is not None:
                self.attach(r, chosen, "name", note)
            elif r.has_coords:
                # a rental the extract itself positions (see SITE_POSITIONS in regional/ffla_rentals.py):
                # the tower already at that spot, else a tower of its own
                near = [c for c in self.candidates(r) if self.can_join(r, c[3])]
                if near:
                    self.attach(r, min(near, key=lambda c: (c[0], c[1], c[2], c[3].seq))[3], "spatial")
                else:
                    self.attach(r, self.new_tower(), "new")
            else:
                r.match_note = ("several lookouts of that name in the state" if len(cands) > 1
                                else "no lookout of that name in the state")
                self.unplaced.append(r)
                self.review.append({"type": "ffla_rental_unplaced", "key": r.key, "name": r.display, "region": r.region,
                                    "tower_seqs": sorted(t.seq for t in cands)})

    def find_origins(self) -> None:
        """For towers whose name says the structure came from elsewhere ("State Fair
        (Relocated Padlock Hill)"), find the tower at the original site: a strong name match in
        the origin's state, not itself a moved structure. Several candidates: prefer one whose
        sources say the lookout is gone, then the nearest; the others go to the report."""
        order = PRECEDENCE["name"]
        for t in self.towers:
            noted = [m for m in t.members if m.annotation and m.annotation["kind"] in ("relocated", "replica", "parts")]
            if not noted:
                continue
            noted.sort(key=lambda m: (order.index(m.source) if m.source in order else len(order), m.key))
            t.history = noted[0]
            ann = t.history.annotation
            site_forms = name_forms(t.history.display)
            if ann.get("origin") and not ann.get("same_place"):
                s_ = name_score(name_forms(ann["origin"]), site_forms)
                if s_ is not None and s_ >= 0.95 and not ann.get("origin_region"):
                    ann["same_place"] = True  # "Ascutney, Mount (Relocated Mount Ascutney)"
            if ann.get("same_place"):
                oforms = name_forms(ann.get("origin") or t.history.display)
            elif not ann.get("origin") or ann.get("near"):
                continue
            else:
                oforms = name_forms(ann["origin"])
            region = ann.get("origin_region") or t.history.region
            cands = []
            for u in self.by_region.get(region or "", ()):
                if u is t or not u.members:
                    continue
                if any(m.annotation and m.annotation["kind"] in ("relocated", "parts", "replica") for m in u.members):
                    continue
                score = name_score(oforms, u.forms())
                if score is None or score < STRONG:
                    continue
                gone = any(record_status(m) in ("gone", "ruins", "relocated") for m in u.members)
                d = u.min_dist(t.history.lat, t.history.lon) if t.history.has_coords else None
                cands.append((0 if gone else 1, d if d is not None else 1e12, u.seq, u))
            cands.sort(key=lambda c: c[:3])
            if cands:
                t.origin = cands[0][3]
                t.origin_alternatives = [c[3] for c in cands[1:]]

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
        # 1b. pinned by RECORD_JOINS
        if any(r.key in RECORD_JOINS for r in pending):
            by_id = {t.id: t for t in self.towers if t.id}
            unpinned = []
            for r in pending:
                target = RECORD_JOINS.get(r.key)
                t = (self.by_key.get(target) or by_id.get(target)) if target else None
                if target and t is None:
                    self.review.append({"type": "record_join_unknown_tower", "key": r.key, "target": target})
                if t is not None and self.can_join(r, t):
                    self.attach(r, t, "override", f"RECORD_JOINS -> {target}")
                else:
                    unpinned.append(r)
            pending = unpinned
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
    return {"ruins": "gone", "replica": "standing", "relocated": "gone"}.get(s, s)


def record_status(rec: Rec) -> str | None:
    """The record's status claim, or None. An OSM feature imported from GNIS (it carries
    gnis:feature_id) marks where a lookout is or was, not that it stands: FFLA calls 70 of the
    215 such "standing" features gone, against 19 of 388 for hand-mapped ones."""
    if rec.status_info and "status" in rec.status_info:
        st = rec.status_info["status"]  # "(Demolished)" -> gone; "(likely gone)" -> no claim
        return None if st == "unknown" else st
    st = rec.raw.get("status")
    if st in (None, "unknown"):
        return None
    if rec.source == "osm" and st == "standing" and rec.extra.get("gnis_feature_id"):
        return None
    kind = (rec.annotation or {}).get("kind")
    if st == "standing" and kind == "replica":
        return "replica"  # FFLA: "Kellogg Peak (Replica)"
    return st


def record_built(rec: Rec) -> int | None:
    years = [e.get("year") for e in rec.raw.get("events") or []
             if isinstance(e, dict) and e.get("event") == "built" and isinstance(e.get("year"), int)]
    b = rec.raw.get("built")
    if isinstance(b, int) and not isinstance(b, bool):
        years.append(b)
    return min(years) if years else None


def record_material(rec: Rec, kind: str | None) -> str | None:
    """The material a record names for the lookout's main structure (a type value such as
    "Stone Tower", an OSM tag, or description words read for this kind of structure)."""
    if kind in NO_STRUCTURE:
        return None
    reading = rec.structure or {}
    return reading.get("material") or structure.words_material(reading.get("words") or [], kind)


def tower_design_ids(members: list[Rec], design: str | None, design_src: Rec | None) -> tuple[list[str], dict]:
    """Recognised designs (pipeline/designs.py) in the tower's design, its sources' type and
    design wording and the design names found in their prose (DESIGN_MENTIONS), and the record
    each was first found in."""
    cands: list[tuple[str, Rec | None]] = [(design, design_src)] if isinstance(design, str) and design.strip() else []
    for m in sorted(members, key=lambda m: (global_rank(m.source), m.key)):
        for w in (m.raw.get("type_raw"), m.extra.get("design"), *DESIGN_MENTIONS.get(m.key, [])):
            if isinstance(w, str) and w.strip():
                cands.append((w, m))
    ids: list[str] = []
    found: dict[str, Rec | None] = {}
    for text, m in cands:
        for did in design_names.match_designs(text):
            if did not in found:
                ids.append(did)
                found[did] = m
    return ids, found


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
    if rec.status_info and rec.status_info.get("access"):
        return {"level": rec.status_info["access"], "note": rec.status_info.get("note")}
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


# ---------------------------------------------------------------------------------------
# Mirrored photos (pipeline/mirror_photos.py, DESIGN.md "Photos")
# ---------------------------------------------------------------------------------------


def load_photo_manifest(path: Path) -> dict:
    """data/photos_manifest.json: source url -> {file, thumb, w, h, bytes, status, reason},
    written by pipeline/mirror_photos.py. Missing or unreadable is treated as empty, so merge
    still works before any photo has been mirrored."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def apply_photo_manifest(photos: list[dict], manifest: dict) -> list[dict]:
    """Fill file/thumb/w/h from the mirror manifest. A photo the mirror step could not use
    (download failed, or too small once decoded to be a real photo) is dropped rather than
    kept as a dead link: the interim "View photo at <site>" card (web/src/render/tower.ts) is
    for a photo not yet attempted, not one already known not to work."""
    if not manifest:
        return photos
    out = []
    for p in photos:
        entry = manifest.get(p.get("url"))
        if entry:
            status = entry.get("status")
            if status in ("failed", "skipped"):
                continue
            if status == "ok":
                p = dict(p)
                p["file"] = entry.get("file")
                p["thumb"] = entry.get("thumb")
                if entry.get("w") is not None:
                    p["w"] = entry.get("w")
                if entry.get("h") is not None:
                    p["h"] = entry.get("h")
        out.append(p)
    return out


@functools.lru_cache(maxsize=1)
def commons_credits() -> dict:
    """Author/licence per Commons file name, from pipeline/commons_credits.py (empty if not run)."""
    try:
        with open(DATA / "sources" / "commons_credits.json", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def photo_entry(rec: Rec, p: dict) -> dict | None:
    if not isinstance(p, dict):
        return None
    url = p.get("url")
    source_url = p.get("source_url") or rec.raw.get("url")
    commons = None
    if rec.source == "wikidata" and isinstance(url, str) and "/wiki/File:" in url:
        source_url = url
        # Commons' robots.txt disallows Special:FilePath, so point at the original on
        # upload.wikimedia.org (path = first one and two hex digits of the name's MD5).
        fname = unquote(url.split("/wiki/File:", 1)[1]).replace(" ", "_")
        digest = hashlib.md5(fname.encode("utf-8")).hexdigest()
        url = f"https://upload.wikimedia.org/wikipedia/commons/{digest[0]}/{digest[:2]}/{quote(fname)}"
        commons = commons_credits().get(fname) or {}
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return None
    site = SOURCE_SITE.get(rec.source, rec.source)
    credit = p.get("credit")
    caption = p.get("caption") or None
    if not credit and rec.source != "wikidata":
        # A register photo's caption often carries the photographer where the structured
        # credit field doesn't ("9/10/05--Cabin (Bob Eckler photo-courtesy Bill Starr)"), so
        # the generic site-name fallback below never has to be the whole story. Applied here
        # (not in the fetchers) so it also picks up every caption already committed, with no
        # re-crawl needed.
        caption, extracted = extract_photo_credit(caption)
        if extracted:
            credit = extracted
    if rec.source == "wikidata":
        author = (commons or {}).get("author")
        if author and (not credit or credit.lower().startswith("wikimedia commons")):
            credit = author
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
        "license": p.get("license") or (commons or {}).get("license") or PHOTO_LICENSE.get(rec.source),
        "caption": caption,
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
        elif src == "ffla_rentals":
            out.append({"label": "FFLA lookout rentals list (firelookout.org)", "url": url, "kind": "association"})
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
        elif src in ASSOCIATION_SOURCES:
            assoc = (rec.extra.get("association") or {}).get("name") or SOURCE_SITE.get(src, src)
            out.append({"label": f"{assoc}: work on {name}", "url": url, "kind": "association"})
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


LINK_KIND_ORDER = ["relocated_from", "relocated_to", "register", "rental", "reference", "association", "wikipedia", "site", "agency", "website",
                   "category", "commons", "wikidata", "osm"]


def pick(field_name: str, members: list[Rec], getter) -> tuple[object, Rec | None]:
    """First value from the members in the field's precedence order (ties by key)."""
    # (within a source, a border row -- the other state's list again -- comes after the home row)
    for m in sorted(members, key=lambda m: (source_rank(field_name, m.source), is_border_row(m), m.key)):
        v = getter(m)
        if v is not None:
            return v, m
    return None, None


def loc_region_of(members: list[Rec]) -> str | None:
    _, m = location_pick(members)
    return m.region if m is not None else None


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


# Words that make a place read better with "the": "now at the State Fair", but "now at
# Kathio State Park".
ARTICLE_WORDS = {"museum", "center", "centre", "fair", "fairgrounds", "fairplex", "experience",
                 "depot", "school", "village", "office", "building", "zoo", "campus", "institute",
                 "display", "shop", "headquarters", "college", "university", "academy"}
_TRAILING_LOOKOUT_RE = re.compile(r"(\s+(?:fire|lookout|lookouts|tower|firetower|station|observation))+$", re.I)


def short_place(site: str) -> str:
    """"OFS Cool Springs Fire Tower" -> "OFS Cool Springs" (for "now at ...")."""
    return _TRAILING_LOOKOUT_RE.sub("", site).strip(" -\u2013") or site


def with_article(place: str) -> str:
    return f"the {place}" if set(name_tokens(place)) & ARTICLE_WORDS else place


def _no_parens(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\s*\([^)]*\)", " ", text)).strip()


def historical_name(origin: str, pool: list[Rec], origin_tower: "Tower | None" = None) -> str:
    """The lookout's own name, spelled the way a source spells it with "Lookout"/"Fire
    Tower" ("Makomis Fire Tower"); else the original site's fuller name plus "Lookout"
    ("Castro" -> "Castro Peak Lookout"); else the origin plus "Lookout"."""
    oforms = name_forms(origin)
    for m in sorted(pool, key=lambda m: (source_rank("name", m.source), m.key)):
        if not m.display or m.annotation or not has_lookout_word(m.display):
            continue
        score = name_score(oforms, m.forms)
        if score is not None and score >= STRONG:
            return _no_parens(m.display)
    base = origin
    if origin_tower is not None:
        named = [m for m in origin_tower.members if m.display and not m.annotation and m.forms]
        if named:
            best = _no_parens(sorted(named, key=lambda m: (source_rank("name", m.source), m.key))[0].display)
            if best and len(name_tokens(best)) >= len(name_tokens(origin)):
                base = best  # the fuller of the two: "Castro" -> "Castro Peak", not "Roberts Mountain" -> "Roberts"
    return base if has_lookout_word(base) else f"{base} Lookout"


def history_naming(tower: Tower, members: list[Rec], region: str | None, default_name: str) -> tuple[str, str | None, dict | None]:
    """Name, id text and timeline event for a structure whose name carries its history.

    Named the way a visitor looks for it: the lookout's own name first, where it stands now
    second ("Padlock Hill Lookout (now at the State Fair)", id ...-padlock-hill-at-state-fair)."""
    h = tower.history
    ann = h.annotation
    site = h.display or default_name
    place = short_place(site)
    at = with_article(place)
    state = STATE_NAMES.get(ann.get("origin_region") or "")
    other_state = bool(ann.get("origin_region")) and ann.get("origin_region") != region
    origin = ann.get("origin")
    event = None
    name, slug = default_name, _no_parens(site)

    def ev(note: str, moved_from: str | None) -> dict:
        return {"year": None, "event": "relocated", "note": note, "from": h.source,
                "moved_from": moved_from, "moved_to": place}

    pool = members + (tower.origin.members if tower.origin else [])
    if ann["kind"] == "relocated" and ann.get("same_place"):
        hist = historical_name(_no_parens(origin or site), pool, tower.origin)
        name = f"{hist} (moved from its original spot)"
        slug = f"{short_place(hist)} moved"
        event = ev("Moved a short way, to a new spot on the same site.", origin or place)
    elif ann["kind"] == "relocated" and ann.get("unknown_origin"):
        name = f"{default_name} (moved from an unknown site)"
        event = ev(f"Moved to {at} from a site not recorded.", None)
    elif ann["kind"] == "relocated":
        if origin and not ann.get("near"):
            hist = historical_name(origin, pool, tower.origin)
            name = f"{hist} (from {state}, now at {at})" if other_state else f"{hist} (now at {at})"
            slug = f"{short_place(hist)} at {place}"
            from_txt = f"{origin}, {state}" if other_state else origin
        elif origin:
            from_txt = f"near {origin}" + (f", {state}" if other_state else "")
            name = f"{default_name} (moved from {from_txt})"
        elif state:
            from_txt = state
            name = f"{default_name} (moved from {state})"
        else:
            from_txt = None
        event = ev(f"Moved from {from_txt} to {at}." if from_txt else f"Moved to {at} from another site.", from_txt)
    elif ann["kind"] == "replica":
        if ann.get("replica_of"):
            name = f"{historical_name(ann['replica_of'], members)} replica (at {at})"
            slug = f"{ann['replica_of']} replica"
        else:
            name = f"{default_name} (replica)"
            slug = f"{place} replica"
        if origin:
            event = ev(f"The replica was moved here from {with_article(origin)}.", origin)
    elif ann["kind"] == "parts" and origin:
        event = ev(f"Built with parts of the {origin} tower.", origin)
    return name, slug, event


def link_relocations(resolved: list[tuple[Tower, dict]]) -> list[dict]:
    """Link a moved structure and its original site both ways (links of kind relocated_from
    / relocated_to, by id), and mark the original site "relocated" when its sources say the
    lookout is no longer there. Returns rows for the report."""
    by_tower = {id(t): (t, r) for t, r in resolved}
    rows = []
    for t, r in resolved:
        if not t.history:
            continue
        ann = t.history.annotation
        row = {"id": t.id, "name": r["name"], "kind": ann["kind"], "note": ann["raw"],
               "origin": ann.get("origin"), "origin_id": None,
               "origin_alternatives": [by_tower[id(u)][0].id for u in t.origin_alternatives if id(u) in by_tower]}
        rows.append(row)
        pair = by_tower.get(id(t.origin)) if t.origin else None
        if not pair:
            continue
        o, orec = pair
        row["origin_id"] = o.id
        if r.get("hidden") or orec.get("hidden"):
            row["skipped"] = "one of the two is hidden"
            continue
        place = short_place(t.history.display or r["name"])
        at = with_article(place)
        lt, lo = set(r.get("locked") or []), set(orec.get("locked") or [])
        if "links" not in lt:
            label = {"relocated": f"Original site: {orec['name']}", "parts": f"Parts came from {orec['name']}"}.get(
                ann["kind"], f"Moved here from {orec['name']}")
            _add_link(r, {"label": label, "url": f"../{o.id}/", "kind": "relocated_from", "id": o.id})
        if "links" not in lo:
            label = {"parts": f"Parts reused at {at}"}.get(ann["kind"], f"Now at {at}")
            _add_link(orec, {"label": label, "url": f"../{t.id}/", "kind": "relocated_to", "id": t.id})
        if ann["kind"] == "relocated":
            if "status" not in lo and orec.get("status") in ("gone", "ruins", "unknown", "relocated"):
                orec["status"] = "relocated"
            if "events" not in lo:
                _add_event(orec, {"year": None, "event": "relocated", "note": f"The lookout was moved to {at}.",
                                  "from": t.history.source, "moved_from": orec["name"], "moved_to": place})
    return rows


def _add_link(rec: dict, link: dict) -> None:
    if link.get("id"):
        drop = lambda l: l.get("kind") == link["kind"] and l.get("id") == link["id"]
    else:
        drop = lambda l: isinstance(l.get("url"), str) and link_norm(l["url"]) == link_norm(link["url"])
    links = [l for l in rec.get("links") or [] if not (isinstance(l, dict) and drop(l))]
    links.append(link)
    links.sort(key=lambda l: LINK_KIND_ORDER.index(l["kind"]) if l.get("kind") in LINK_KIND_ORDER else len(LINK_KIND_ORDER))
    rec["links"] = links


def _add_event(rec: dict, event: dict) -> None:
    events = [e for e in rec.get("events") or [] if not (e.get("event") == event["event"] and e.get("note") == event["note"])]
    events.append(event)
    events.sort(key=lambda e: (e.get("year") if isinstance(e.get("year"), int) else 9999, e["event"]))
    rec["events"] = events


def _event_refs(out: dict, src_event: dict) -> dict:
    """Carry the page that supports an event (source_url, and source_urls when several) from a
    source's event to the tower's, as research events already do."""
    for k in ("source_url", "source_urls"):
        if src_event.get(k):
            out[k] = src_event[k]
    return out


def loose_key(name: str) -> str:
    toks = [t for t in name_tokens(name) if t not in GENERIC_WORDS or t in ("ground", "house", "cabin")]
    return " ".join(toks)


def resolve(tower: Tower, today: str, headers: dict, photos_manifest: dict | None = None) -> dict:
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
    history_event = None
    if tower.history is not None:
        region_now = (loc_region_of(members) or tower.old_region)
        name, tower.slug_text, history_event = history_naming(tower, members, region_now, name or rec.get("name") or "Unnamed lookout")
        name_src = tower.history
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
            if m.status_info:
                cand.append(m.status_info["original"])  # "Buffalo Lookout Tower (Demolished)", for search
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
    # Kind: a bare lookout point ("Firefinder", "Map Board") only when no source records a structure.
    v, s = pick("kind", members, lambda m: m.raw.get("kind") if m.raw.get("kind") not in (None, "unknown", "point") else None)
    if v is None:
        v, s = pick("kind", members, lambda m: m.raw.get("kind") if m.raw.get("kind") == "point" else None)
    v_design, s_design = pick("design", members, lambda m: (m.extra.get("design") or None) if isinstance(m.extra.get("design"), str) else None)
    design_ids, design_src = tower_design_ids(members, rec.get("design") if "design" in locked else v_design, s_design)
    if v is None:
        # No kind from any source, but a recognised steel-tower design (an Aermotor) is a tower.
        did = structure.design_is_tower(design_ids, DESIGN_FACTS)
        if did:
            v, s = "tower", design_src.get(did)
    tower.source_kind = (v, s.source if s else None)
    if v is None and "kind" not in rec:
        v = "unknown"
    set_field("kind", v, s)
    set_field("design", v_design, s_design)
    # Material: explicit source words first, then the design (DESIGN.md 3.5).
    if "material" not in locked:
        kind_now = rec.get("kind")
        mat, mat_src = pick("material", members, lambda m: record_material(m, kind_now))
        if mat is not None:
            rec["material"], rec["material_from"] = mat, mat_src.source
            contributed[mat_src.key].add("material")
        else:
            mat, did = structure.design_material(design_ids, kind_now, DESIGN_FACTS, rec.get("region"))
            rec["material"], rec["material_from"] = mat, ("design" if mat else None)
            if mat and design_src.get(did) is not None:
                contributed[design_src[did].key].add("material")
    if "roles" not in locked:
        roles = []
        for m in sorted(members, key=lambda m: (global_rank(m.source), m.key)):
            for role in m.structure.get("roles") or []:
                if role not in roles:
                    roles.append(role)
                    contributed[m.key].add("roles")
        rec["roles"] = roles
    v, s = pick("height_m", members, record_height)
    set_field("height_m", v, s)
    status, status_src = pick("status", members, record_status)
    if status is None and "status" not in rec:
        status = "unknown"
    set_field("status", status, status_src)
    tower.source_status = (status, status_src.source if status_src else None)
    # A note on the status from a name ("(likely gone)", "(unknown)"), shown with the status.
    if "status" not in locked:
        note, note_src = pick("status", members, lambda m: ((m.status_info or {}).get("note") if not (m.status_info or {}).get("access") else None)
                              or m.structure.get("status_note"))
        rec["status_note"] = note
        if note_src is not None:
            contributed[note_src.key].add("status")

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
        # "unknown" (e.g. OSM's access=* tag, which describes the structure, not the land -- see
        # record_access()) is not a real determination: don't let it block a better one below,
        # but keep its note as a last resort if nothing better turns up.
        weak_note, weak_src = (None, None)
        if isinstance(acc, dict) and acc.get("level") == "unknown":
            weak_note, weak_src = acc.get("note"), acc_src
            acc, acc_src = None, None
        if acc is None and rec.get("ownership") == "tribal":
            acc = {"level": "permission", "note": "On tribal land. Ask the tribe before visiting."}
            acc_src = s
        if acc is None:
            private = next((m for m in members if m.source == "ffla_rentals" and m.extra.get("ownership") == "private"), None)
            if private is not None:
                acc, acc_src = {"level": "permission", "note": "Private property. The way in is to book a stay through the listing."}, private
        if acc is None:
            # A recreation.gov listing is itself evidence of public access.
            ridb = next((m for m in members if m.source == "ridb"), None)
            if ridb is not None:
                rental = ridb.raw.get("rental") or {}
                if rental.get("available") is not False and rental:
                    note = "Overnight stays by reservation on recreation.gov. Check the listing for road, trail and seasonal closures."
                else:
                    note = "Listed as a visitor site on recreation.gov. Check the listing for seasonal closures."
                acc, acc_src = {"level": "public", "note": note}, ridb
        if acc is None and weak_note:
            acc, acc_src = {"level": "unknown", "note": weak_note}, weak_src
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

    # Rental: recreation.gov (RIDB) first. The FFLA rentals list adds who manages the lookout and
    # a closure note ("Maintenance Closure 2026") to a RIDB rental, and is the rental itself
    # (booking link outside recreation.gov: a state park, a private owner) when RIDB has none.
    if "rental" not in locked:
        ridb = [m for m in members if m.source == "ridb"]
        rentals = [m for m in ridb if isinstance(m.raw.get("rental"), dict)]
        rentals.sort(key=lambda m: (m.raw["rental"].get("available") is not True, m.key))
        old_rental = rec.get("rental")
        was_ridb = (isinstance(old_rental, dict) and old_rental.get("provider") == "recreation.gov"
                    and old_rental.get("source") != "ffla")
        if rentals:
            rec["rental"] = copy.deepcopy(rentals[0].raw["rental"])
            rec["rental"].setdefault("checked", headers.get("ridb", {}).get("retrieved"))
            contributed[rentals[0].key].add("rental")
        elif ridb and was_ridb:
            rec["rental"]["available"] = False
            rec["rental"].pop("warning", None)
        elif not ridb and was_ridb and "ridb" in headers:
            # Never delete a rental: RIDB's own weekly export simply no longer has this
            # facility (removed, renumbered, or missed by matching this run, not something a
            # merge can tell apart) -- "ridb" in headers means the export WAS read this run,
            # so this is a real absence, not a skipped fetch. Leave "available" and "checked"
            # exactly as they were and say so visibly instead (the page already shows
            # rental.warning above the booking link, same as the "burned lookout" case below).
            rec["rental"]["available"] = False
            rec["rental"]["warning"] = (
                f"Last confirmed on recreation.gov {old_rental.get('checked') or 'at an earlier refresh'}. "
                f"The {headers.get('ridb', {}).get('retrieved') or today} refresh no longer finds this "
                f"facility in RIDB's export -- it may have been delisted or renumbered. Check "
                f"recreation.gov directly before relying on this listing."
            )
        else:
            rec.setdefault("rental", None)
        listed = sorted((m for m in members if m.source == "ffla_rentals" and isinstance(m.raw.get("rental"), dict)),
                        key=lambda m: m.key)
        cur_rental = rec.get("rental")
        if isinstance(cur_rental, dict) and not rentals and cur_rental.get("source") != "ffla":
            for k in ("status_note", "status_note_from", "manager"):
                cur_rental.pop(k, None)     # a note the FFLA list no longer gives goes away
        if not listed and isinstance(old_rental, dict) and old_rental.get("source") == "ffla" and "ffla_rentals" in headers:
            # Never delete a rental: the FFLA list no longer has this one (removed, renamed, or missed by
            # matching this run). Leave it visible and say so, as for a vanished recreation.gov facility.
            rec["rental"]["available"] = False
            rec["rental"]["warning"] = (
                f"Last confirmed on the FFLA rentals list {old_rental.get('checked') or 'at an earlier refresh'}. "
                f"The {headers.get('ffla_rentals', {}).get('retrieved') or today} refresh no longer finds it there. "
                f"Check with the booking site before relying on this listing.")
        if listed:
            noted = next((m for m in listed if m.raw["rental"].get("status_note")), listed[0])
            fr = noted.raw["rental"]
            managed = next((m.raw["rental"]["manager"] for m in listed if m.raw["rental"].get("manager")), None)
            if rentals:
                cur = rec["rental"]
            else:
                first = listed[0].raw["rental"]
                cur = {"available": True, "source": "ffla", "provider": first.get("provider"), "url": first.get("url"),
                       "ridb_facility_id": first.get("ridb_facility_id"),
                       "checked": first.get("checked") or headers.get("ffla_rentals", {}).get("retrieved")}
                rec["rental"] = cur
            if managed:
                cur["manager"] = managed
            if fr.get("status_note"):
                cur["status_note"] = fr["status_note"]
                cur["status_note_from"] = "ffla"
            contributed[listed[0].key].add("rental")

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
                    events.append(_event_refs({"year": e["year"], "event": "built", "note": e.get("note"), "from": e.get("from") or built_src.source}, e))
            contributed[built_src.key].add("events")
        for m in sorted(members, key=lambda m: (source_rank("events", m.source), m.key)):
            for e in m.raw.get("events") or []:
                if not isinstance(e, dict) or not e.get("event") or e.get("event") == "built":
                    continue
                k = (e["event"], e.get("year"))
                if k in seen_ev:
                    continue
                seen_ev.add(k)
                events.append(_event_refs({"year": e.get("year"), "event": e["event"], "note": e.get("note"), "from": e.get("from") or m.source}, e))
                contributed[m.key].add("events")
        if history_event is not None:
            events.append(history_event)
            contributed[tower.history.key].add("events")
        if events or "events" not in rec:
            old_other = [e for e in rec.get("events") or [] if isinstance(e, dict) and (e.get("event"), e.get("year")) not in seen_ev
                         and e.get("from") not in {m.source for m in members} and "moved_to" not in e
                         and e.get("from") != "research"]
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
        # keep mirrored copies made by the photo step, for a url the manifest does not (yet)
        # cover: carry file/thumb over from the previous merge by URL.
        manifest = photos_manifest or {}
        old_by_url = {p.get("url"): p for p in rec.get("photos") or [] if isinstance(p, dict)}
        for p in photos:
            prev = old_by_url.get(p["url"])
            if prev and not manifest.get(p["url"]):
                p["file"], p["thumb"] = prev.get("file"), prev.get("thumb")
        # data/photos_manifest.json is authoritative when present: fill file/thumb/w/h, and
        # drop a photo it could not use rather than show a dead link.
        rec["photos"] = apply_photo_manifest(photos, manifest) + apply_photo_manifest(old, manifest)

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
            if isinstance(link, dict) and str(link.get("kind") or "").startswith("relocated_"):
                continue  # recomputed by link_relocations()
            if isinstance(link, dict) and isinstance(link.get("url"), str) and link_norm(link["url"]) not in seen_links:
                seen_links.add(link_norm(link["url"]))
                links.append(link)
        links.sort(key=lambda l: LINK_KIND_ORDER.index(l["kind"]) if l.get("kind") in LINK_KIND_ORDER else len(LINK_KIND_ORDER))
        rec["links"] = links

    # A listing for a lookout another source records as gone (Flag Point, OR: "Burned 2026"):
    # warn, don't hide. The listing and its link stay; "available" is false so it is not
    # counted or filtered as rentable, and "warning" says why, for the page to show above the
    # booking link.
    r_ = rec.get("rental")
    if "rental" not in locked and isinstance(r_, dict) and rec.get("status") in ("gone", "ruins"):
        r_.pop("status_note", None)
        if r_.get("available") or r_.get("warning"):
            r_["available"] = False
            r_["warning"] = rental_warning(rec, status_src, r_)

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
            if isinstance(s_, dict) and s_.get("key") not in member_keys and s_.get("source") not in present \
                    and s_.get("source") != "research":
                stale = dict(s_)
                stale["fields"] = []
                stale.setdefault("missing_since", today)
                refs.append(stale)
        rec["sources"] = refs

    rec.setdefault("locked", [])
    for k, default in (("county", None), ("elevation_m", None), ("material", None), ("material_from", None), ("roles", []),
                       ("design", None), ("height_m", None),
                       ("agency", None), ("registers", []), ("events", []), ("photos", []),
                       ("links", []), ("conflicts", []), ("rental", None), ("other_names", []),
                       ("verification", "unverified"), ("ownership", "unknown")):
        rec.setdefault(k, default)
    return rec


SHORT_NAME = {"ffla": "FFLA", "ffla_rentals": "the FFLA rentals list", "nhlr": "NHLR", "fflos": "FFLOS", "firelookout_com": "firelookout.com",
              "idaho_fl": "idahofirelookouts.com", "osm": "OpenStreetMap", "wikidata": "Wikidata",
              "fire_lookouts_org": "fire-lookouts.org", "pa_storymap": "the PA fire towers StoryMap",
              "andyarthur_ny": "andyarthur.org", "cskt": "CSKT", "ridb": "recreation.gov"}


def rental_warning(rec: dict, status_src: Rec | None, rental: dict | None = None) -> str:
    """"FFLA reports this lookout burned in 2026, but recreation.gov still lists it. Check
    with the forest before booking." (A rental that came from the FFLA rentals list says
    "the FFLA rentals list" where recreation.gov would be.)"""
    lister = "recreation.gov"
    if rental and rental.get("source") == "ffla":
        lister = "the FFLA rentals list"
    who = SHORT_NAME.get(status_src.source, status_src.source) if status_src else "Another source"
    what = "is gone" if rec.get("status") == "gone" else "is in ruins"
    if status_src is not None:
        verbs = {"burned": "burned", "destroyed": "was destroyed", "removed": "was removed", "abandoned": "was abandoned"}
        for e in status_src.raw.get("events") or []:
            if isinstance(e, dict) and e.get("event") in verbs:
                what = verbs[e["event"]] + (f" in {e['year']}" if isinstance(e.get("year"), int) else "")
                break
    agency = str(rec.get("agency") or "")
    if re.search(r"forest service|national forest", agency, re.I):
        whom = "the forest"
    elif re.search(r"bureau of land management|\bblm\b", agency, re.I):
        whom = "the Bureau of Land Management"
    else:
        whom = "the managing agency"
    return f"{who} reports this lookout {what}, but {lister} still lists it. Check with {whom} before booking."


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
        # One year apart is usually "built" vs "completed" or a season's slip: not reported.
        if by_source and max(by_source.values()) - min(by_source.values()) >= BUILT_CONFLICT_YEARS:
            values = [{"source": src, "value": b} for src, b in by_source.items()]
            out.append({"field": "built", "values": values, "distance_m": None,
                        "note": "Sources give different build years. Often one counts the first lookout on the site "
                                "and another the structure there now."})
    # Kind, only where it decides whether there was a structure at all (which map group it is in).
    kinds = {}
    for m in sorted(members, key=lambda m: (source_rank("kind", m.source), m.key)):
        k = m.raw.get("kind")
        if k not in (None, "unknown", "point") and m.source not in kinds:
            kinds[m.source] = k
    if set(kinds.values()) & NO_STRUCTURE and set(kinds.values()) - NO_STRUCTURE:
        out.append({"field": "kind", "values": [{"source": s, "value": k} for s, k in kinds.items()],
                    "distance_m": None, "note": "Sources disagree on whether a tower or building stood here, or only a camp or lookout tree."})
    # Material, when two sources name different ones in so many words.
    mats = {}
    for m in sorted(members, key=lambda m: (source_rank("material", m.source), m.key)):
        v = record_material(m, rec.get("kind"))
        if v is not None and m.source not in mats:
            mats[m.source] = v
    if len(set(mats.values())) > 1 and rec.get("material") in mats.values():
        out.append({"field": "material", "values": [{"source": s, "value": v} for s, v in mats.items()],
                    "distance_m": None, "note": "Sources name different materials. Often one describes an earlier structure."})
    return out


def hidden_for(rec: dict, members: list[Rec]) -> tuple[bool, str | None]:
    for m in members:
        if m.key in HIDE_KEYS:
            return True, HIDE_KEYS[m.key]
    registered = any(m.source in ("nhlr", "fflos")
                     or any(str(r.get("register") or "").upper() in ("NHLR", "FFLOS") for r in (m.raw.get("registers") or []))
                     for m in members)
    for m in members:
        if (m.status_info or {}).get("hidden_reason") and not registered:
            return True, m.status_info["hidden_reason"]
        nonfire = (re.search(r"non-?fire", str(m.raw.get("status_raw") or ""), re.I)
                   or re.search(r"non-?fire", str(m.raw.get("type_raw") or ""), re.I)
                   or re.search(r"non-?fire", str((m.annotation or {}).get("note") or ""), re.I))
        # A tower on a lookout register stays visible whatever one table calls it (warn, don't hide).
        if nonfire and not registered and not re.search(r"non-?wildfire", str(m.raw.get("status_raw") or ""), re.I):
            return True, f"Not a fire lookout ({SHORT_NAME.get(m.source, m.source)} lists it as a non-fire tower)"
    kind = rec.get("kind")
    if kind in HIDDEN_KIND_REASON:
        return True, HIDDEN_KIND_REASON[kind]
    structural = any(m.raw.get("kind") not in (None, "unknown", *NO_STRUCTURE) for m in members if m.source != "ffla")
    ffla = [m for m in members if m.source == "ffla"]
    for m in ffla:
        st = str(m.raw.get("status_raw") or "").strip().lower()
        if st in NEVER_BUILT_STATUS and not registered and not structural:
            return True, f"Never built (FFLA lists it as \"{m.raw.get('status_raw')}\")"
        section = str(m.extra.get("section") or "").lower()
        if section.startswith(NOT_A_LOOKOUT_SECTION) and not registered:
            return True, "Not a fire lookout (FFLA: determined not to have been used as a wildland fire lookout)"
    if (ffla and not structural and not registered
            and all(str(m.extra.get("section") or "").lower().startswith(UNDOCUMENTED_SECTION) for m in ffla)):
        return True, "Not confirmed as a lookout (FFLA lists it only as unknown or undocumented)"
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
# Research overlay: data/research/<id>.json on top of the source merge (DESIGN.md 3.5)
# ---------------------------------------------------------------------------------------

# Research facts that replace the source-merged value (unless the field is locked).
RESEARCH_FACTS = ("design", "height_m", "status", "status_note", "kind", "staffing", "access", "visit", "agency")
VERIFIED_VERDICTS = {"pass", "fixed"}
# Research event names that are plainly a vocabulary event under another word. Anything else
# outside data/vocab.json is left out of the timeline and listed in the report.
RESEARCH_EVENT_ALIASES = {"unstaffed": "staffed_last", "decommissioned": "abandoned",
                          "renovated": "restored", "restoration_completed": "restored"}
RESEARCH_FIELD_ORDER = ["summary", "kind", "design", "height_m", "status", "agency", "access", "staffing",
                        "visit", "events", "photos", "links", "verification"]


def _vocab() -> dict:
    try:
        return json.loads((DATA / "vocab.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def load_research(research_dir: Path | None) -> tuple[dict[str, dict], list[dict]]:
    """Research files by tower id, and problems that stop a file from being used."""
    found: dict[str, dict] = {}
    problems: list[dict] = []
    if research_dir is None or not research_dir.is_dir():
        return found, problems
    for path in sorted(research_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            problems.append({"file": path.name, "problem": f"not valid JSON: {e}"})
            continue
        if not isinstance(data, dict):
            problems.append({"file": path.name, "problem": "not a JSON object"})
            continue
        rid = data.get("id")
        if rid != path.stem:
            problems.append({"file": path.name, "problem": f"id {rid!r} does not match the file name"})
            continue
        found[rid] = data
    return found, problems


def _cite_urls(res: dict, cites) -> list[str]:
    by_n = {s.get("n"): s.get("url") for s in res.get("sources") or [] if isinstance(s, dict)}
    out = []
    for n in cites if isinstance(cites, list) else [cites] if cites is not None else []:
        url = by_n.get(n)
        if isinstance(url, str) and url.startswith(("http://", "https://")) and url not in out:
            out.append(url)
    return out


def research_status_note(facts: dict, status: str | None) -> str | None:
    """The research status note, shown beside the status. Only for a status that needs a
    caveat (gone, ruins, moved, replica, unknown): pilot files used it on standing lookouts for
    design history ("Hip roof replaced the original flat roof in 1992") and editor remarks,
    which belong in the story or notes_for_editor."""
    note = facts.get("status_note")
    if not (isinstance(note, str) and note.strip()) or status == "standing":
        return None
    return note.strip()


def apply_research(t: Tower, rec: dict, res: dict, vocab: dict) -> dict:
    """Lay one research file over a merged tower. Returns what the report needs:
    {"corrections": [...], "problems": [...], "fields": [...]}. Locked fields win; corrections
    are never applied."""
    locked = set(rec.get("locked") or [])
    rid = rec["id"]
    when = res.get("researched") if isinstance(res.get("researched"), str) else None
    problems: list[str] = []
    fields: set[str] = set()
    statuses = set(vocab.get("status") or [])
    kinds = set(vocab.get("kind") or [])
    access_levels = set(vocab.get("access") or [])
    staffing_values = set(vocab.get("staffing") or [])
    event_names = set(vocab.get("event") or [])

    # Summary
    summary = res.get("summary")
    if isinstance(summary, str) and summary.strip() and "summary" not in locked:
        rec["summary"] = summary.strip()
        fields.add("summary")

    # Facts
    facts = res.get("facts") if isinstance(res.get("facts"), dict) else {}
    conflicts = [c for c in rec.get("conflicts") or []
                 if not any(isinstance(v, dict) and v.get("source") == "research" for v in c.get("values") or [])]

    def research_conflict(field: str, new, source_value: tuple) -> None:
        old, old_src = source_value
        if old in (None, "unknown") or new == old:
            return
        if field == "status" and status_group(old) == status_group(new):
            return
        values = [{"source": "research", "value": new}]
        existing = next((c for c in conflicts if c.get("field") == field), None)
        if existing is not None:
            conflicts.remove(existing)
            values += [v for v in existing.get("values") or [] if v.get("source") != "research"]
        else:
            values.append({"source": old_src or "sources", "value": old})
        what = {"status": "status", "kind": "kind of structure"}[field]
        conflicts.insert(0, {"field": field, "values": values, "distance_m": None,
                             "note": f"Research{' (' + when + ')' if when else ''} gives {new} where the source records give "
                                     f"{old}. The page shows the researched {what}; please tell us if it is wrong."})

    for key in RESEARCH_FACTS:
        if key not in facts:
            continue
        value = facts[key]
        target = "status" if key == "status_note" else key
        if target in locked:
            continue
        if key == "status_note":
            continue  # applied with "status" below, or on its own when status is absent
        if value is None:
            continue
        ok = True
        if key == "status":
            ok = value in statuses
        elif key == "kind":
            ok = value in kinds
        elif key == "height_m":
            ok = _num(value)
        elif key in ("design", "agency"):
            ok = isinstance(value, str) and bool(value.strip())
        elif key == "access":
            ok = isinstance(value, dict) and value.get("level") in access_levels
        elif key == "staffing":
            ok = isinstance(value, dict) and value.get("status") in staffing_values
        elif key == "visit":
            ok = isinstance(value, dict)
        if not ok:
            problems.append(f"facts.{key} {value!r} is not valid; not applied")
            continue
        if key == "status":
            research_conflict("status", value, t.source_status)
            rec["status"] = value
            rec["status_note"] = research_status_note(facts, value)
        elif key == "kind":
            research_conflict("kind", value, t.source_kind)
            rec["kind"] = value
        elif key == "visit":
            visit = dict(rec.get("visit") or {})
            visit.update({k: v for k, v in value.items() if k in ("climbable", "drive_up", "trail_note") and v is not None})
            rec["visit"] = visit
        elif key in ("access", "staffing"):
            rec[key] = {k: value.get(k) for k in (("level", "note") if key == "access" else ("status", "as_of"))}
        else:
            rec[key] = value.strip() if isinstance(value, str) else round(float(value), 1)
        fields.add(key)
    if "status" not in facts and "status" not in locked and research_status_note(facts, rec.get("status")):
        rec["status_note"] = research_status_note(facts, rec.get("status"))
        fields.add("status")
    if "conflicts" not in locked:
        rec["conflicts"] = conflicts

    # Events: union with the sources' events, same year + event once (research's, with its citation)
    if "events" not in locked:
        events = [e for e in rec.get("events") or [] if isinstance(e, dict)]
        for ev in res.get("events") or []:
            if isinstance(ev, dict) and ev.get("event") in RESEARCH_EVENT_ALIASES:
                ev = {**ev, "event": RESEARCH_EVENT_ALIASES[ev["event"]]}
            if not isinstance(ev, dict) or ev.get("event") not in event_names:
                name = ev.get("event") if isinstance(ev, dict) else ev
                problems.append(f"event {name!r} ({ev.get('year') if isinstance(ev, dict) else '?'}) is not in vocab.event; left out of the timeline")
                continue
            year = ev.get("year") if isinstance(ev.get("year"), int) else None
            urls = _cite_urls(res, ev.get("cite"))
            prev = [e for e in events if e.get("event") == ev["event"] and e.get("year") == year]
            note = ev.get("note") or next((e.get("note") for e in prev if e.get("note")), None)
            events = [e for e in events if e not in prev]
            new = {"year": year, "event": ev["event"], "note": note, "from": "research",
                   "source_url": urls[0] if urls else None}
            if len(urls) > 1:
                new["source_urls"] = urls
            events.append(new)
            fields.add("events")
        events.sort(key=lambda e: (e.get("year") if isinstance(e.get("year"), int) else 9999, e["event"]))
        rec["events"] = events

    # Photos: appended, credit and licence kept, de-duplicated by URL
    if "photos" not in locked:
        photos = list(rec.get("photos") or [])
        seen = {p.get("url") for p in photos if isinstance(p, dict)}
        for ph in res.get("photos") or []:
            if not isinstance(ph, dict) or not isinstance(ph.get("url"), str) or not ph["url"].startswith(("http://", "https://")):
                problems.append(f"photo {ph!r} has no usable url; not applied")
                continue
            fields.add("photos")  # supplied, whether added now or on an earlier run
            if ph["url"] in seen:
                continue
            seen.add(ph["url"])
            photos.append({"file": None, "thumb": None, "url": ph["url"], "source_url": ph.get("source_url"),
                           "credit": ph.get("credit"), "license": ph.get("license"), "caption": ph.get("caption"),
                           "year": ph.get("year") if isinstance(ph.get("year"), int) else None})
            fields.add("photos")
        rec["photos"] = photos

    # Cited sources become reference links
    if "links" not in locked:
        for src in res.get("sources") or []:
            if not isinstance(src, dict) or not isinstance(src.get("url"), str) or not src["url"].startswith(("http://", "https://")):
                continue
            norm = link_norm(src["url"])
            fields.add("links")  # supplied, whether added now or on an earlier run
            if any(link_norm(l["url"]) == norm for l in rec.get("links") or [] if isinstance(l, dict) and isinstance(l.get("url"), str)):
                continue
            title = str(src.get("title") or "").strip() or urlsplit(src["url"]).netloc
            publisher = str(src.get("publisher") or "").strip()
            label = f"{title} ({publisher})" if publisher and publisher.lower() not in title.lower() else title
            _add_link(rec, {"label": label, "url": src["url"], "kind": "reference"})
            fields.add("links")

    # Verification and the research stamp the page shows
    check = res.get("verification") if isinstance(res.get("verification"), dict) else {}
    verdict = check.get("verdict")
    if "verification" not in locked:
        rec["verification"] = "verified" if verdict in VERIFIED_VERDICTS else "researched"
        fields.add("verification")
    rec["research"] = {"researched": when, "checked": check.get("checked"), "verdict": verdict,
                       "confidence": res.get("confidence")}

    # Provenance
    if "sources" not in locked:
        refs = [s_ for s_ in rec.get("sources") or [] if not (isinstance(s_, dict) and s_.get("source") == "research")]
        refs.append({"source": "research", "key": f"research:{rid}", "fields": [f for f in RESEARCH_FIELD_ORDER if f in fields]})
        rec["sources"] = refs

    corrections = []
    for c in res.get("corrections") or []:
        if isinstance(c, dict):
            corrections.append({"id": rid, "name": rec.get("name"), "field": c.get("field"), "current": c.get("current"),
                                "proposed": c.get("proposed"), "evidence": c.get("evidence"),
                                "sources": _cite_urls(res, c.get("cite")), "researched": when})
    return {"corrections": corrections, "problems": problems, "fields": sorted(fields)}


# ---------------------------------------------------------------------------------------
# Ids and output
# ---------------------------------------------------------------------------------------


def assign_ids(towers: list[tuple[Tower, dict]], taken: set[str]) -> None:
    """Give new towers ids, deterministically: sorted by (state, slug, position, first key),
    "-2", "-3"... for clashes. Existing ids are never changed or reused."""
    new = [(t, r) for t, r in towers if t.id is None]

    def slug_of(t: Tower, r: dict) -> str:
        return slugify(t.slug_text) if t.slug_text else id_slug(r["name"])

    def sort_key(item):
        t, r = item
        loc = r.get("location") or {}
        return (r.get("region") or "", slug_of(t, r), -(loc.get("lat") or 0), loc.get("lon") or 0,
                min((m.key for m in t.members), default=""))

    for t, r in sorted(new, key=sort_key):
        base = f"us-{(r.get('region') or 'xx').lower()}-{slug_of(t, r)}"
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
        dry_run: bool = False, log=print, photos_manifest: dict | None = None,
        photos_manifest_path: Path | None = None, research_dir: Path | None = None) -> dict:
    # `photos_manifest` (an already-loaded dict) wins when given -- tests pass {} for
    # isolation; otherwise load from `photos_manifest_path` (default data/photos_manifest.json).
    if photos_manifest is None:
        photos_manifest = load_photo_manifest(photos_manifest_path or DATA / "photos_manifest.json")
    headers, records = load_sources(sources_dir, log)
    research, research_problems = load_research(research_dir)
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
        if sid != "ffla_rentals":      # has no positions: placed by name once every tower exists
            m.match_source(sid, records[sid])
    m.place_without_coords()
    if "ffla_rentals" in records:
        m.match_rentals(records["ffla_rentals"])
    m.find_origins()

    resolved: list[tuple[Tower, dict]] = []
    for t in m.towers:
        if not t.members and t.existing is None:
            continue
        if not t.members:
            resolved.append((t, copy.deepcopy(t.existing)))
            continue
        resolved.append((t, resolve(t, today, headers, photos_manifest)))
    assign_ids(resolved, taken)
    relocations = link_relocations(resolved)

    # Research on top of the sources, every run (so a re-merge never loses it).
    vocab = _vocab()
    by_id = {t.id: (t, r) for t, r in resolved}
    research_rows: dict[str, dict] = {}
    for rid, res in sorted(research.items()):
        if rid not in by_id:
            research_problems.append({"file": f"{rid}.json", "problem": "no tower has this id"})
            continue
        t, r = by_id[rid]
        r["id"] = rid
        research_rows[rid] = apply_research(t, r, res, vocab)
        for prob in research_rows[rid]["problems"]:
            research_problems.append({"file": f"{rid}.json", "problem": prob})

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

    report = build_report(m, resolved, headers, today, written, unchanged, relocations)
    report["research"] = {
        "files": len(research) + sum(1 for p in research_problems if "JSON" in p["problem"] or "file name" in p["problem"]),
        "applied": len(research_rows),
        "by_verdict": dict(sorted(Counter(str((res.get("verification") or {}).get("verdict") if isinstance(res.get("verification"), dict) else None)
                                          for rid, res in research.items() if rid in research_rows).items())),
        "problems": research_problems,
        "notes_for_editor": [{"id": rid, "note": res["notes_for_editor"]} for rid, res in sorted(research.items())
                             if rid in research_rows and isinstance(res.get("notes_for_editor"), str) and res["notes_for_editor"].strip()],
    }
    report["research_corrections"] = [c for rid in sorted(research_rows) for c in research_rows[rid]["corrections"]]
    if report_path and not dry_run:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def ffla_rentals_report(m: Matcher, resolved: list[tuple[Tower, dict]]) -> dict | None:
    """How the FFLA rentals list landed on the towers, and how it compares with recreation.gov's:
    the rentals FFLA lists that recreation.gov (RIDB) did not give us, and the rentable towers of
    ours that FFLA does not list. None when there is no ffla_rentals extract."""
    listed = [mem for t, _ in resolved for mem in t.members if mem.source == "ffla_rentals"]
    if not listed and not any(u.source == "ffla_rentals" for u in m.unplaced):
        return None
    rows, ffla_only, noted, per_how = [], [], [], Counter()
    for t, r in resolved:
        for mem in t.members:
            if mem.source != "ffla_rentals":
                continue
            per_how[mem.match] += 1
            has_ridb = any(o.source == "ridb" and isinstance(o.raw.get("rental"), dict) for o in t.members)
            row = {"key": mem.key, "name": mem.raw.get("name"), "region": mem.region, "tower": r["id"], "how": mem.match,
                   "recreation_gov_has_it": has_ridb, "provider": (mem.raw.get("rental") or {}).get("provider")}
            rows.append(row)
            if not has_ridb:
                ffla_only.append(row)
            if (mem.raw.get("rental") or {}).get("status_note"):
                noted.append({"tower": r["id"], "name": r["name"], "note": mem.raw["rental"]["status_note"]})
    unplaced = [{"key": u.key, "name": u.display, "region": u.region, "reason": u.match_note}
                for u in m.unplaced if u.source == "ffla_rentals"]
    not_listed = [{"tower": r["id"], "name": r["name"], "region": r.get("region"), "provider": r["rental"].get("provider"),
                   "url": r["rental"].get("url")}
                  for t, r in resolved
                  if not r.get("hidden") and isinstance(r.get("rental"), dict) and r["rental"].get("available") is not False
                  and not any(mem.source == "ffla_rentals" for mem in t.members)]
    return {
        "listed": len(listed) + len(unplaced), "placed": len(listed), "placed_by": dict(sorted(per_how.items())),
        "unplaced": unplaced,
        "listed_by_ffla_not_in_recreation_gov_data": sorted(ffla_only, key=lambda x: (x["region"], x["name"])),
        "with_closure_note": sorted(noted, key=lambda x: x["tower"]),
        "rentable_but_not_listed_by_ffla": sorted(not_listed, key=lambda x: x["tower"]),
    }


def build_report(m: Matcher, resolved: list[tuple[Tower, dict]], headers: dict, today: str,
                 written: int, unchanged: int, relocations: list[dict] | None = None) -> dict:
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
    # Checks on the final towers, so every run reports them (not only the run that matched).
    review = []
    for t, r in resolved:
        mems = list(t.members)
        for mem in mems:
            others = [f for o in mems if o is not mem for f in o.forms]
            s_ = name_score(mem.forms, others)
            if s_ is not None and s_ < PARTIAL:
                review.append({"type": "matched_different_names", "key": mem.key, "name": mem.display,
                               "tower": r["id"], "tower_name": r["name"], "score": s_})
        for i, a in enumerate(mems):
            for b in mems[i + 1:]:
                shared = {k for k in a.reg_keys if " US " in k} & {k for k in b.reg_keys if " US " in k}
                d = a.dist(b)
                if shared and d is not None and d > REGISTER_FAR_M:
                    review.append({"type": "register_match_far", "keys": [a.key, b.key], "registers": sorted(shared),
                                   "tower": r["id"], "distance_m": round(d)})
    for item in m.review:
        if item["type"] in ("matched_different_names", "register_match_far"):
            continue
        item = dict(item)
        if "tower_seq" in item:
            item["tower"] = seq_to_id.get(item.pop("tower_seq"))
        if "nearby_tower_seq" in item:
            item["nearby_tower"] = seq_to_id.get(item.pop("nearby_tower_seq"))
        if "tower_seqs" in item:
            item["towers"] = [seq_to_id.get(s) for s in item.pop("tower_seqs")]
        review.append(item)
    for t, r in resolved:
        if isinstance(r.get("rental"), dict) and r["rental"].get("warning"):
            review.append({"type": "rental_on_gone_lookout", "tower": r["id"], "note": r["rental"]["warning"]})
    rental_hints = []
    for t, r in resolved:
        if r.get("rental"):
            continue
        for mem in t.members:
            if mem.source in ("nhlr", "fflos") and isinstance(mem.raw.get("rental"), dict) and mem.raw["rental"].get("available"):
                rental_hints.append({"id": r["id"], "name": r["name"], "key": mem.key})
    ffla_rentals = ffla_rentals_report(m, resolved)
    match_by_source: dict[str, Counter] = defaultdict(Counter)
    for t, _ in resolved:
        for mem in t.members:
            match_by_source[mem.source][mem.match] += 1
    for rec in m.unplaced:
        match_by_source[rec.source]["unplaced"] += 1
    # Type/status wording with no deliberate mapping in structure.py (test_structure fails on these).
    unmapped: dict[str, Counter] = defaultdict(Counter)
    for rec in [mem for t, _ in resolved for mem in t.members] + list(m.unplaced):
        for field_, value in rec.structure.get("unmapped") or []:
            unmapped[rec.source][f"{field_}: {value}"] += 1

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
            "visible_with_no_structure": sum(1 for r in visible if r.get("kind") in NO_STRUCTURE),
            "visible_by_material": counts(visible, "material"),
            "visible_by_material_from": counts(visible, "material_from"),
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
        "unplaced": [{"key": r.key, "name": r.display, "region": r.region, "county": record_county(r),
                      "reason": r.match_note} for r in m.unplaced],
        "coordinates_not_used": [{"key": mem.key, "name": mem.display, "region": mem.region,
                                  "lat": mem.raw.get("lat"), "lon": mem.raw.get("lon")}
                                 for t, _ in resolved for mem in t.members if mem.bad_coords == "outside_us"]
                                + [{"key": r.key, "name": r.display, "region": r.region, "lat": r.raw.get("lat"), "lon": r.raw.get("lon")}
                                   for r in m.unplaced if r.bad_coords == "outside_us"],
        "coordinates_outside_own_state": [
            {"key": mem.key, "name": mem.display, "region": mem.region, "lat": mem.lat, "lon": mem.lon,
             "inside": [st for st, (a, b, c, d) in sorted(STATE_BBOX.items()) if a <= mem.lat <= b and c <= mem.lon <= d],
             "tower": r["id"], "used_for_location": (r.get("location") or {}).get("from") == mem.source}
            for t, r in resolved for mem in t.members if mem.bad_coords == "outside_state"],
        "relocations": relocations or [],
        "rental_hints_without_ridb": rental_hints,
        "ffla_rentals": ffla_rentals,
        "unmapped_structure_values": {s_: dict(c.most_common()) for s_, c in sorted(unmapped.items())},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sources", type=Path, default=DATA / "sources")
    ap.add_argument("--towers", type=Path, default=DATA / "towers")
    ap.add_argument("--report", type=Path, default=DATA / "merge_report.json")
    ap.add_argument("--research", type=Path, default=DATA / "research",
                    help="research files laid over the merge (default: data/research)")
    ap.add_argument("--today", default=dt.date.today().isoformat(), help="date stamped on changed records (YYYY-MM-DD)")
    ap.add_argument("--dry-run", action="store_true", help="match and report, but write nothing")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    log = (lambda *a, **k: None) if args.quiet else print
    rep = run(args.sources, args.towers, args.report, args.today, args.dry_run, log, research_dir=args.research)
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
