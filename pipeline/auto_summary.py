"""A short plain-English summary of a lookout, written from its record alone (no research).

Shown on tower pages that have no researched story yet, labelled as a summary from records.
Every clause comes straight from a field; nothing is inferred beyond what the record says."""
from __future__ import annotations

STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico", "GU": "Guam", "VI": "U.S. Virgin Islands",
}
KIND = {
    "tower": "fire lookout tower", "ground": "ground-level fire lookout cabin",
    "two_story": "two-story fire lookout building", "three_story": "three-story fire lookout building",
    "enclosed_tower": "enclosed fire lookout tower", "platform": "open fire lookout tower",
}
END = {"burned": "burned", "destroyed": "was destroyed", "removed": "was removed", "abandoned": "was abandoned"}
REGISTER = {
    "NHLR": "the National Historic Lookout Register",
    "FFLOS": "the Former Fire Lookout Sites Register",
    "NRHP": "the National Register of Historic Places",
}


def _place(rec: dict) -> str | None:
    state = STATES.get(rec.get("region") or "", rec.get("region"))
    county = rec.get("county")
    if county and state:
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
    at = f", at {round(elev / 0.3048):,} ft ({round(elev):,} m)," if isinstance(elev, (int, float)) and elev > 0 else ""
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
        the = "the " if agency.startswith(("U.S.", "US ", "USDA", "Bureau", "National", "Forest Service", "Department", "State ")) else ""
        out.append(f"It is administered by {the}{agency}.")
    rental = rec.get("rental") or {}
    if rental.get("available") is True:
        out.append("It can be rented for overnight stays through recreation.gov.")
    return " ".join(out)
