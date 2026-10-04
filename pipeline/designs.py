#!/usr/bin/env python3
"""Recognise standard fire-lookout designs in free-text design strings.

Sources write designs many ways: "L-4", "L4", "L-4 ground cab", "R-6 flattop", "USFS Region 6
Flat Top cab", "Aermotor MC-39 steel tower", "McKlintock-Marshall 86-ft steel tower". This
module maps such strings to the design ids used by data/designs.json and the designs guide
(/designs/ on the site), and nothing more: it never guesses. A string that names no
recognisable design gives no match, and a string that names several (an L-4 cab that replaced
a D-6) gives all of them, so the guide can list the lookout under each with the source's own
wording beside it.

Used by pipeline/build_site_data.py. Python 3.12, standard library only.
"""

from __future__ import annotations

import re
from typing import Iterable

# Order matters only for display (the order designs are listed in a match).
# Each pattern is matched case-insensitively against the whole string.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # USFS standard cabs. "\b" before the letter keeps "CL-4" or "BL-4" from counting as L-4.
    ("l4", re.compile(r"\bL[\s.-]?4\b(?![\s.-]?\d)", re.I)),
    ("l5", re.compile(r"\bL[\s.-]?5\b(?![\s.-]?\d)", re.I)),
    ("l6", re.compile(r"\bL[\s.-]?6\b(?![\s.-]?\d)", re.I)),
    # R-6 flat top. A bare "flat top" is not enough: other regions built flat-roofed cabs too.
    ("r6", re.compile(r"\bR[\s.-]?6\b(?![\s.-]?\d)|\bregion\s*6\s+flat[\s-]?top", re.I)),
    ("d6", re.compile(r"\bD[\s.-]?6\b(?![\s.-]?\d)", re.I)),
    ("d1", re.compile(r"\bD[\s.-]?1\b(?![\s.-]?\d)", re.I)),
    # Any other cupola house (a D-1 or D-6 already says it; see match_designs).
    # The word alone is not enough (FFLA lists a "Bus/cupola").
    ("cupola", re.compile(r"\bcupola[\s-]+(?:house|cabin|lookout|style)\b|\b(?:with|and|log\s+cabin|has)\s+(?:an?\s+)?(?:glass(?:ed)?\s+|framed\s+)?cupola\b", re.I)),
    # California Region 5's own plans: Plan 4-A, BC-301, the CL-30 / CL-104 steel cab.
    ("r5_lookouts", re.compile(r"\bBC[\s-]?301\b|\bplan\s+4[\s-]?A\b|\bCL[\s-]?(?:30|104)\b", re.I)),
    # Steel tower makers. Aermotor's model codes (MC-39, LS-40, LX-24, LX-25, MI-25) only ever
    # appear for Aermotor towers in our sources.
    ("aermotor", re.compile(r"\baermotor\b|\b(?:MC|LS|LX|MI)[\s-]?\d{2}\b", re.I)),
    ("ideco", re.compile(r"\bideco\b|\binternational\s+derrick", re.I)),
    # Blaw-Knox and McClintic-Marshall (often misspelled McClintock- or McKlintock-Marshall).
    ("other_steel", re.compile(r"\bblaw[\s-]*knox\b|\bmc\s?[ck]l[ia]nt[io]c?k?[\s-]+marshall\b", re.I)),
]

# Aermotor model codes, kept so the guide can say "Aermotor MC-39".
AERMOTOR_MODEL = re.compile(r"\b(MC|LS|LX|MI)[\s-]?(\d{2})\b", re.I)


# A design named only to say the lookout is NOT one ("predates the standard L-4 design",
# "unlike the L-4") does not count. Checked in the few words before each mention.
NEGATION = re.compile(r"\b(?:predat(?:es|ed|ing)|unlike|not\s+an?|rather\s+than|instead\s+of|other\s+than)\b[^.;:,()]{0,30}$", re.I)


def match_designs(text: str | None) -> list[str]:
    """Design ids named in one string, in PATTERNS order. Empty when none is recognisable."""
    if not isinstance(text, str) or not text.strip():
        return []
    found = []
    for did, pattern in PATTERNS:
        if any(not NEGATION.search(text[: m.start()]) for m in pattern.finditer(text)):
            found.append(did)
    if "cupola" in found and ("d1" in found or "d6" in found):
        found.remove("cupola")
    return found


def aermotor_models(text: str | None) -> list[str]:
    """Aermotor model codes in a string, normalised to "MC-39" form."""
    if not isinstance(text, str):
        return []
    seen: list[str] = []
    for m in AERMOTOR_MODEL.finditer(text):
        code = f"{m.group(1).upper()}-{m.group(2)}"
        if code not in seen:
            seen.append(code)
    return seen


def tower_designs(strings: Iterable[str | None]) -> list[str]:
    """Union of the designs named in several strings (the tower's design field and its
    sources' type and design fields), keeping first-seen order."""
    out: list[str] = []
    for s in strings:
        for did in match_designs(s):
            if did not in out:
                out.append(did)
    return out


# Display names, used when data/designs.json has no entry for a matched id.
DESIGN_NAMES: dict[str, str] = {
    "l4": "L-4",
    "l5": "L-5",
    "l6": "L-6",
    "r6": "R-6",
    "d6": "D-6",
    "d1": "D-1",
    "cupola": "Cupola house",
    "r5_lookouts": "California (Region 5) plan",
    "aermotor": "Aermotor",
    "ideco": "IDECO",
    "other_steel": "Other steel maker",
}
