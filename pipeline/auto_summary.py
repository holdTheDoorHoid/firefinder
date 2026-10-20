"""A short plain-English summary of a lookout, written from its record alone (no research).

Shown on tower pages that have no researched story yet, labelled as a summary from records.
Every clause comes straight from a field; nothing is inferred beyond what the record says."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import regions  # noqa: E402

# State, province and territory names (regions.py).
STATES = regions.REGION_NAMES
KIND = {
    "tower": "fire lookout tower", "ground": "ground-level fire lookout cabin",
    "two_story": "two-story fire lookout building", "three_story": "three-story fire lookout building",
    "enclosed_tower": "enclosed fire lookout tower", "platform": "open fire lookout tower",
    "rooftop": "fire lookout cab on a rooftop", "mobile": "trailer fire lookout",
    # Sites with no structure (data/structure_kinds.json group "no_structure").
    "camp": "summit fire lookout camp", "tree": "fire lookout tree",
    "point": "bare fire lookout point",
}
END = {"burned": "burned", "destroyed": "was destroyed", "removed": "was removed", "abandoned": "was abandoned"}
REGISTER = {
    "NHLR": "the National Historic Lookout Register",
    "FFLOS": "the Former Fire Lookout Sites Register",
    "NRHP": "the National Register of Historic Places",
}


def _country(rec: dict) -> str:
    return rec.get("country") or regions.country_of(rec.get("region")) or "US"


def _place(rec: dict) -> str | None:
    """"Jefferson County, Oregon"; "Sudbury District, Ontario, Canada" (a Canadian unit carries its
    own words); "Bethel Census Area, Alaska"."""
    region = rec.get("region")
    state = STATES.get(region or "", region)
    if state and _country(rec) != "US":
        state = f"{state}, {regions.COUNTRY_NAMES.get(_country(rec), _country(rec))}"
    county = rec.get("county")
    if county and state:
        if _country(rec) != "US" or region == "AK":
            return f"{regions.local_unit_label(_country(rec), region, county)}, {state}"
        suffix = "" if any(w in county for w in ("County", "Parish", "Borough", "Municipality")) else (
            " Parish" if rec.get("region") == "LA" else " County")
        return f"{county}{suffix}, {state}"
    return state


def _years(rec: dict, *events: str) -> list[int]:
    return sorted({e["year"] for e in rec.get("events") or []
                   if e.get("event") in events and isinstance(e.get("year"), int)})


def summarize(rec: dict) -> str | None:
    name = rec.get("name")
    if not name:
        return None
    status = rec.get("status")
    what = KIND.get(rec.get("kind") or "", "fire lookout")
    design = rec.get("design")
    if isinstance(design, str) and len(design) <= 24 and len(design.split()) <= 3:
        what += f" ({design} design)"
    place = _place(rec)
    elev = rec.get("elevation_m")
    # Units: feet first in the US, metres first everywhere else (DESIGN.md 4, "Units").
    if isinstance(elev, (int, float)) and elev > 0:
        at = (f", at {round(elev / 0.3048):,} ft ({round(elev):,} m)," if _country(rec) == "US"
              else f", at {round(elev):,} m ({round(elev / 0.3048):,} ft),")
    else:
        at = ""
    where = f" in {place}" if place else ""
    out = []
    if status == "standing":
        out.append(f"{name} is a {what}{where}{at}".rstrip(",") + ".")
    elif status in ("gone", "ruins"):
        out.append(f"{name} was a {what}{where}{at}".rstrip(",") + ".")
    elif status == "relocated":
        out.append(f"{name} was a {what}{where}{at}".rstrip(",") + "; the structure has since been moved.")
    elif status == "replica":
        out.append(f"{name} is a replica {what}{where}.")
    else:
        out.append(f"{name} is a {what} site{where}{at}".rstrip(",") + ". Whether it still stands is not recorded.")

    built = _years(rec, "built")
    rebuilt = _years(rec, "rebuilt", "replaced")
    if built and rebuilt and rebuilt[-1] > built[0]:
        out.append(f"A lookout was first built here in {built[0]}; the site was rebuilt in {rebuilt[-1]}.")
    elif built:
        out.append(f"It was built in {built[0]}.")
    if status in ("gone", "ruins"):
        ends = [(y, ev) for ev in END for y in _years(rec, ev)]
        if ends:
            y, ev = max(ends)
            out.append(f"It {END[ev]} in {y}.")
        if status == "ruins":
            out.append("Only footings or remains survive.")
    regs = []
    for r in rec.get("registers") or []:
        label = REGISTER.get(r.get("register"))
        if label and label not in [x[0] for x in regs]:
            regs.append((label, r.get("number")))
    if regs:
        parts = [label + (f" ({number})" if number else "") for label, number in regs]
        joined = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
        out.append(f"It is recorded on {joined}.")
    if status == "standing" and rec.get("agency"):
        agency = rec["agency"]
        the = "the " if agency.startswith(("U.S.", "US ", "USDA", "Bureau", "National", "Forest Service", "Department", "State ",
                                           "Ministry", "Government", "Province")) else ""
        out.append(f"It is administered by {the}{agency}.")
    rental = rec.get("rental") or {}
    if rental.get("available") is True:
        provider = rental.get("provider") or "recreation.gov"
        out.append(f"It can be rented for overnight stays through {provider}.")
    loc = rec.get("location") or {}
    if loc.get("approximate") is True:
        feature = (loc.get("gnis") or {}).get("name")
        out.append("No source gives where it stood; the map shows it approximately"
                   + (f", on {feature}." if feature else "."))
    return " ".join(out)
