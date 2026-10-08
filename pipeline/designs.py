#!/usr/bin/env python3
"""Recognise standard fire-lookout designs in free-text design strings.

Sources write designs many ways: "L-4", "L4", "L-4 ground cab", "R-6 flattop", "USFS Region 6
Flat Top cab", "Aermotor MC-39 steel tower", "McKlintock-Marshall 86-ft steel tower", "a
California Region 5 Plan BC-301 on a 10 foot enclosed timber tower", "60' CT-2 wooden tower with
a L-4 hip roof cab". This module maps such strings to the design ids used by data/designs.json and
the designs guide (/designs/ on the site), and nothing more: it never guesses. A string that names
no recognisable design gives no match, and a string that names several (an L-4 cab on a CT-2
tower, or an L-4 cab that replaced a D-6) gives all of them, so the guide can list the lookout
under each with the source's own wording beside it.

Which design is a cab, a ground house, a tower or a whole lookout (`part`), its material, and
which family it belongs to (an Aermotor MC-39 is also an Aermotor) are facts kept in
data/designs.json; see `family_ids` and `pair` below for how pipeline/build_site_data.py uses
them.

Used by pipeline/build_site_data.py and pipeline/extract_design_mentions.py. Python 3.12,
standard library only.
"""

from __future__ import annotations

import re
from typing import Iterable

# A code like "L-4" is matched only as a whole token: "\b" before the letter keeps "CL-4" or
# "BL-4" from counting as L-4, and "\b(?![.-]\d)" after it keeps "L-45" or "L-4.5" from
# counting (a space and a number may follow: "CL-30 13'x13' cab").
_END = r"\b(?![.-]\d)"

# Order matters only for display (the order designs are listed in a match).
# Each pattern is matched case-insensitively.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # --- USFS standard wooden cabs and houses -------------------------------------------------
    # L-4, including Region 4's copy of it ("Plan 80 (R-1 L-4)") and "R1/L-4".
    ("l4", re.compile(r"\bL[\s.-]?4" + _END + r"|\bplan\s+80\b(?![\s.-]?[A-Z0-9])|\bB-?420[0-9]\b", re.I)),
    ("l5", re.compile(r"\bL[\s.-]?5" + _END, re.I)),
    ("l6", re.compile(r"\bL[\s.-]?6" + _END, re.I)),
    # Region 1's L-2 frame lookout house and L-20 lookout cab. Hyphen or nothing only: "L 2"
    # is too common in other senses.
    ("l2", re.compile(r"\bL-?2" + _END, re.I)),
    ("l20", re.compile(r"\bL-?20" + _END, re.I)),
    # R-6 flat top, with Region 4's copies (Plan 80-A, 80-B) and its plan number B-4300. A bare
    # "flat top" is not enough: other regions built flat-roofed cabs too.
    # ("R6 to R2" is a radio signal strength.)
    ("r6", re.compile(r"\bR[\s.-]?6" + _END + r"(?!\s+to\s+R\d)|\bregion\s*6\s+flat(?:[\s-]?top)?\b|\bplan\s+80[\s-]?[AB]\b|\bB-?430[0-9]\b", re.I)),
    # Region 6's 1936 7 x 7 tower cab, by its plan numbers only (a bare "7x7 cab" says nothing).
    ("r6_7x7_cab", re.compile(r"\bB-?410[1-3]\b", re.I)),
    ("d6", re.compile(r"\bD[\s.-]?6" + _END, re.I)),
    ("d1", re.compile(r"\bD[\s.-]?1" + _END, re.I)),
    # Any other cupola house (a D-1 or D-6 already says it; see match_designs).
    # The word alone is not enough (FFLA lists a "Bus/cupola").
    ("cupola", re.compile(r"\bcupola[\s-]+(?:house|cabin|lookout|style)\b|\b(?:with|and|log\s+cabin|has)\s+(?:an?\s+)?(?:glass(?:ed)?\s+|framed\s+)?cupola\b", re.I)),
    # Region 3 (Southwest) cab: 12x12 or 14x14 with low sills. "R3 low sill cab", "R-3 design".
    ("r3_cab", re.compile(r"\bR-?3\s+(?:\d+\S*\s+)?(?:low[\s-]sill|live-in|cab|design|wooden)", re.I)),
    # --- California (Region 5) plans ----------------------------------------------------------
    # Plan 4-A (1917-1923); not 4-AR, and not "1817-4A" (a CDF plan number).
    ("plan_4a", re.compile(r"\bplan\s+(?:no\.?\s*)?4-?A\b(?![\s-]?R)|(?<![\w-])4-?A\s+(?:style|cabs?|cabins?|designs?|plans?|lookouts?|models?|or\s+4-?AR)\b", re.I)),
    # D-5, the 4-AR, nicknamed the "Supervisor Hall Special" in Oregon.
    ("d5", re.compile(r"\bD[\s.-]?5" + _END + r"|(?<![\w-])4-?AR\b|\bsupervisor\s+hall\b", re.I)),
    # C-3 (not "Camp C-3" or "Company C-3").
    ("c3", re.compile(r"(?<!camp )(?<!company )(?<![\w-])C-?3" + _END, re.I)),
    # BC-301 (also written BC-3, and the BC-302 variant); BC-201 lookout-fireman house.
    ("bc301", re.compile(r"\bBC-?(?:30[12]|3)" + _END, re.I)),
    ("bc201", re.compile(r"\bBC-?201" + _END, re.I)),
    # --- Region 1 (Northern Rockies) towers ---------------------------------------------------
    # "T-30" but not a township ("T-30-N", "T-30N").
    ("r1_towers", re.compile(r"\bT-[1-5]0" + _END + r"(?!-?[NS]\b)", re.I)),
    ("r1_cupola_towers", re.compile(r"\bT-[12]\s+(?:lookout\s+)?(?:tower|cupola)", re.I)),
    ("r1_patrol_tower", re.compile(r"\bT-3\s+(?:patrol\s+)?tower", re.I)),
    # --- Region 4 (Intermountain) plans -------------------------------------------------------
    ("plan_81a", re.compile(r"\bplan\s+81[\s-]?A\b", re.I)),
    ("plan_86", re.compile(r"\bplan\s+86\b", re.I)),
    ("sitpa", re.compile(r"\bSITPA\b", re.I)),
    # --- Region 6 (Pacific Northwest) timber towers -------------------------------------------
    ("r6_timber_towers", re.compile(r"\bCT-?[1-6]" + _END + r"|\bTT-?1" + _END, re.I)),
    # --- Steel cabs and towers ----------------------------------------------------------------
    # The national CL-100 series steel cab (CL-100 to CL-106), with California's CL-30 and its
    # predecessor CL-16.
    ("cl100", re.compile(r"\bCL-?(?:10[0-9]|30|16)" + _END, re.I)),
    # USFS standard steel tower plans of 1937, L-1400 series (L-1401...; 7 x 7 steel cab), built
    # by International Derrick and by Aermotor as its MC-99.
    ("l1401", re.compile(r"\bL-?14(?:0[1-9])\b|\bMC-?99\b", re.I)),
    # Its companion L-1600 series (L-1601...), a steel tower with a 14 x 14 platform for a wooden
    # cab: "an L-1600 series 30' steel K-Brace tower", "the USFS, 1600 series tower plans".
    ("l1600", re.compile(r"\bL-?16(?:0[0-9])\b|\b1600\s+series\b", re.I)),
    # Aermotor's models each have an entry; any other mention of the company or one of its
    # model codes (MC-40, MI-25...) counts as Aermotor, model not recorded.
    ("aermotor_ls40", re.compile(r"\bLS-?40\b", re.I)),
    ("aermotor_mc39", re.compile(r"\bMC-?39\b", re.I)),
    ("aermotor_ll25", re.compile(r"\bLL-?25\b", re.I)),
    ("aermotor_lx", re.compile(r"\bLX-?2[45]\b", re.I)),
    ("aermotor_mc24", re.compile(r"\bMC-?24\b", re.I)),
    ("aermotor", re.compile(r"\bae(?:r|ro)motor\b|\b(?:MC|LS|LX|LL|MI)-?\d{2,3}\b", re.I)),
    ("ideco", re.compile(r"\bideco\b|\binternational\s+derrick|\bE-?4898\b", re.I)),
    # Other steel makers. McClintic-Marshall is often misspelled McClintock- or McKlintock-, and
    # sometimes written the other way round.
    ("blaw_knox", re.compile(r"\bblaw[\s-]*knox\b", re.I)),
    ("mcclintic_marshall", re.compile(r"\bmc\s?[ck]l[ia]nt[io]c?k?[\s-]+marshall?\b|\bmarshall?[\s-]+mc\s?[ck]l[ia]nt[io]c?k?\b", re.I)),
    ("pacific_coast_steel", re.compile(r"\bpacific\s+coast\s+steel\b", re.I)),
    # Other named makers with too few lookouts on record for an entry of their own.
    ("other_steel", re.compile(r"\binternational[\s-]+stacey\b", re.I)),
    # --- State and Park Service designs -------------------------------------------------------
    ("wisconsin_standard", re.compile(r"\bwisconsin\s+standard\s+(?:steel\s+)?(?:tower|lookout)", re.I)),
    # California Division of Forestry (CDF) plans: the 809R lookout and the 732-6A cab.
    ("cdf_809r", re.compile(r"\b809-?RA?\b", re.I)),
    ("cdf_732_6a", re.compile(r"\b732-6A\b", re.I)),
    ("nps_rustic", re.compile(
        r"\bNPS\s+(?:rustic|frame|standardi[sz]ed|design|standard\s+(?:design|plan|lookout))"
        r"|\brustic[\w\s-]{0,30}\(NPS\s+design\)|\bnational\s+park\s+service\s+rustic|\bPG-?3040\b",
        re.I,
    )),
]

PATTERN_IDS = [did for did, _ in PATTERNS]

# Codes naming one variant within a design, kept so the guide can say "Aermotor MC-39" or
# "CT-2" beside the lookout.
VARIANT_CODES: dict[str, re.Pattern[str]] = {
    "aermotor": re.compile(r"\b(MC|LS|LX|LL|MI)-?(\d{2,3})\b", re.I),
    "aermotor_lx": re.compile(r"\b(LX)-?(2[45])\b", re.I),
    "r6_timber_towers": re.compile(r"\b(CT|TT)-?([1-6])\b", re.I),
    "r1_towers": re.compile(r"\b(T)-([1-5]0)\b", re.I),
    "r1_cupola_towers": re.compile(r"\b(T)-([12])\b", re.I),
    "cl100": re.compile(r"\b(CL)-?(10[0-9]|30|16)\b", re.I),
    "bc301": re.compile(r"\b(BC)-?(30[12])\b", re.I),
}
# Kept for older callers: Aermotor model codes in "MC-39" form.
AERMOTOR_MODEL = VARIANT_CODES["aermotor"]

# Designs that name a cupola house themselves; the generic "cupola" match is dropped beside them.
_CUPOLA_DESIGNS = {"d1", "d6", "l2", "l6", "r1_cupola_towers"}

# A design named only to say the lookout is NOT one ("predates the standard L-4 design",
# "unlike the L-4", "similar to an LS-40", "as compared to the more common Aermotor brand"),
# or named as the design's ancestor or successor, does not count. Checked in the few words
# before each mention.
NEGATION = re.compile(
    r"\b(?:predat(?:es|ed|ing)|unlike|not\s+an?|rather\s+than|instead\s+of|other\s+than|similar\s+to|"
    r"reminiscent\s+of|resembl(?:es|ed|ing)|compared\s+(?:to|with)|as\s+opposed\s+to|"
    r"(?:precursor|predecessor|forerunner|successor)\s+(?:to|of))\b[^.;:,()]{0,30}$",
    re.I,
)


def _clean(span: str) -> str:
    return re.sub(r"\s+", " ", span).strip()


def find_mentions(text: str | None) -> list[tuple[str, str]]:
    """(design id, matched words) for every design named in a text, negated mentions left out,
    in PATTERNS order, each id once (its first mention). The matched words are a short term
    ("Aermotor", "MC-39", "R-6", "cupola cabin"), never a sentence; match_designs() on them gives
    the id back."""
    if not isinstance(text, str) or not text.strip():
        return []
    found: list[tuple[str, str]] = []
    for did, pattern in PATTERNS:
        for m in pattern.finditer(text):
            if not NEGATION.search(text[: m.start()]):
                found.append((did, _clean(m.group(0))))
                break
    ids = {d for d, _ in found}
    if "cupola" in ids and ids & _CUPOLA_DESIGNS:
        found = [(d, s) for d, s in found if d != "cupola"]
    return found


def match_designs(text: str | None) -> list[str]:
    """Design ids named in one string, in PATTERNS order. Empty when none is recognisable."""
    return [did for did, _ in find_mentions(text)]


def variant_codes(did: str, text: str | None) -> list[str]:
    """Variant codes of one design in a string, normalised to "MC-39" / "CT-2" form."""
    rx = VARIANT_CODES.get(did)
    if rx is None or not isinstance(text, str):
        return []
    seen: list[str] = []
    for m in rx.finditer(text):
        if NEGATION.search(text[: m.start()]):
            continue
        code = f"{m.group(1).upper()}-{m.group(2).upper()}"
        if code not in seen:
            seen.append(code)
    return seen


def aermotor_models(text: str | None) -> list[str]:
    """Aermotor model codes in a string, normalised to "MC-39" form."""
    return variant_codes("aermotor", text)


def tower_designs(strings: Iterable[str | None]) -> list[str]:
    """Union of the designs named in several strings (the tower's design field and its
    sources' type and design fields), keeping first-seen order."""
    out: list[str] = []
    for s in strings:
        for did in match_designs(s):
            if did not in out:
                out.append(did)
    return out


def family_ids(ids: list[str], family_of: dict[str, str]) -> list[str]:
    """The ids plus each one's family head (an Aermotor MC-39 is also an Aermotor), so a filter
    on the family finds every member. `family_of` maps a design id to its family's id
    (data/designs.json "family"); heads map to themselves."""
    out = list(ids)
    for did in ids:
        head = family_of.get(did)
        if head and head not in out:
            out.append(head)
    return out


# Words that say a text describes more than one structure over time ("replaced an Aermotor
# tower", "the original cab", "an earlier L-4"). Two designs named in such a text may belong to
# different structures, so they are not paired as one lookout's cab and tower.
SEVERAL_STRUCTURES = re.compile(
    r"\b(?:replac\w*|original\w*|earlier|previous\w*|former\w*|preced\w*|predecessor|rebuilt|"
    r"supersed\w*|supplant\w*|succeeded|moved|relocated|first\s+(?:lookout|structure|tower|cab|cabin))\b",
    re.I,
)


def describes_several(text: str | None) -> bool:
    """Whether a text names two or more designs and also says it describes more than one
    structure over time, so its designs cannot be paired as one lookout's cab and tower."""
    if not isinstance(text, str) or len(match_designs(text)) < 2:
        return False
    return bool(SEVERAL_STRUCTURES.search(text))


def most_specific(ids: list[str], family_of: dict[str, str]) -> list[str]:
    """The ids without a family head named beside one of its own members (Aermotor + MC-39 =
    MC-39): what a lookout's page lists."""
    return [d for d in ids if not any(o != d and family_of.get(o) == d for o in ids)]


def pair(ids: list[str], part_of: dict[str, str], family_of: dict[str, str] | None = None) -> dict[str, str] | None:
    """The one lookout these designs describe, as {"cab": id} or {"house": id} (at most one of
    the two), plus {"tower": id} when a tower design is named too, or {"whole": id}; None when
    the records name more than one structure.

    A real lookout is often a cab design on a tower design (an L-4 cab on a CT-2 tower; an
    Aermotor MC-24 carrying a Region 3 cab), or a ground house beside a tower (a BC-201 house
    and an Aermotor tower). `part_of` gives each design's part (data/designs.json "part": cab,
    house, tower or whole). A family head named beside one of its own members says nothing more
    (Aermotor + MC-39 = MC-39). A record naming two cabs or houses (an L-4 that replaced a D-6),
    two towers, or a whole lookout beside anything else describes several structures over time,
    and we do not guess which is today's."""
    specific = most_specific(ids, family_of or {})
    cabs = [d for d in specific if part_of.get(d) in ("cab", "house")]
    towers = [d for d in specific if part_of.get(d) == "tower"]
    wholes = [d for d in specific if part_of.get(d) == "whole"]
    if wholes:
        return {"whole": wholes[0]} if len(wholes) == 1 and not cabs and not towers else None
    if len(cabs) > 1 or len(towers) > 1 or not (cabs or towers):
        return None
    out: dict[str, str] = {}
    if cabs:
        out["house" if part_of.get(cabs[0]) == "house" else "cab"] = cabs[0]
    if towers:
        out["tower"] = towers[0]
    return out


# Display names, used when data/designs.json has no entry for a matched id (and by the site's
# map filter, web/src/lib/vocab.ts, which must list the same ids).
DESIGN_NAMES: dict[str, str] = {
    "l4": "L-4",
    "r6": "R-6",
    "l5": "L-5",
    "l6": "L-6",
    "l2": "L-2 house",
    "l20": "L-20 cab",
    "r1_towers": "Region 1 log towers T-10 to T-50",
    "r1_cupola_towers": "Region 1 towers with cupola (T-1, T-2)",
    "r1_patrol_tower": "Region 1 patrol tower (T-3)",
    "d6": "D-6",
    "d1": "D-1",
    "cupola": "Cupola house",
    "r6_7x7_cab": "Region 6 7 x 7 cab",
    "r6_timber_towers": "Region 6 timber towers (CT, TT)",
    "r5_lookouts": "California (Region 5) plan",
    "plan_4a": "Plan 4-A",
    "d5": "D-5 (4-AR)",
    "c3": "C-3",
    "bc301": "BC-301",
    "bc201": "BC-201",
    "plan_81a": "Plan 81-A",
    "plan_86": "Plan 86",
    "sitpa": "SITPA log lookout",
    "r3_cab": "Region 3 cab",
    "aermotor": "Aermotor",
    "aermotor_ls40": "Aermotor LS-40",
    "aermotor_mc39": "Aermotor MC-39",
    "aermotor_ll25": "Aermotor LL-25",
    "aermotor_lx": "Aermotor LX-24 / LX-25",
    "aermotor_mc24": "Aermotor MC-24",
    "ideco": "IDECO",
    "usfs_7x7_1932": "USFS 7 x 7 steel tower (1932)",
    "l1401": "L-1400 steel tower",
    "l1600": "L-1600 steel tower",
    "cl100": "CL-100",
    "d3_log_tower": "District 3 log tower",
    "r9_mast": "Region 9 pole mast",
    "other_steel": "Other steel maker",
    "blaw_knox": "Blaw-Knox",
    "mcclintic_marshall": "McClintic-Marshall",
    "pacific_coast_steel": "Pacific Coast Steel",
    "wisconsin_standard": "Wisconsin standard tower",
    "stone_lookouts": "Stone lookouts",
    "chimney_rock": "Chimney Rock plan",
    "nps_rustic": "National Park Service lookout",
    "cdf_809r": "CDF 809R",
    "cdf_732_6a": "CDF 732-6A",
}
