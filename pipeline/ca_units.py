"""Canada's local units: which words in a source's place line name a real local unit, and how a
unit is compared (DESIGN.md 3.3 "Countries and regions", 3.5 "Approximate locations").

A Canadian source files a lookout under many kinds of place: a BC regional district, an Ontario
district or county, a New Brunswick or Nova Scotia county, a Quebec regional county municipality
(MRC), a census division ("Division No. 18"), but also forests, fire districts, parks, protective
associations and towns. Only a real local unit goes in a record's `county`: the merge compares
counties when it joins records by name, and the CGNDB approximate-pin rule (merge.CgndbIndex) looks
a lookout's hill up inside its unit. Everything else is a place hint for people.

Units are kept as the source writes them (DESIGN.md 3.3). `unit_key()` is how two spellings are
compared ("Regional District of Central Kootenay" = "Central Kootenay" = "Central Kootenay RD";
"Sudbury District" = "Sudbury"; "Thompson - Nicola" = "Thompson-Nicola"); merge.county_key() drops the
same words. `bc_current_districts()` maps a BC regional district the author of canada-lookouts.weebly.com
names in its pre-2000s form ("Fraser-Cheam", "Comox-Strathcona", "Powell River") to the district(s) that
cover its ground today, for the gazetteer, which knows only today's boundaries.

Python 3.12, standard library only.
"""

from __future__ import annotations

import re
import unicodedata

# Words that only say what kind of unit a name is. Dropped before comparing (merge.county_key too).
UNIT_WORDS_RE = re.compile(
    r"\b(regional district of|regional district|rd|district municipality of|district municipality|"
    r"district of|district|united counties of|united counties|regional municipality of|"
    r"regional municipality|rural municipality of|rural municipality|rm of|municipal district of|"
    r"municipal district|mrc de|mrc d|mrc|unorganized|unorganised|county of|county|counties|parish|"
    r"borough|census area|municipality|co)\b\.?", re.I)


def fold(text: str) -> str:
    t = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in t if not unicodedata.combining(ch)).lower()


def unit_key(unit: str | None) -> str | None:
    """A unit as it is compared: accents, case, punctuation, spaces and the unit's own kind words
    dropped. "Regional District of Central Kootenay" -> "centralkootenay"; "Okanogan - Similkameen"
    -> "okanogansimilkameen"; "Division No. 18" -> "divisionno18"; "Les Collines-de-l'Outaouais" ->
    "lescollinesdeloutaouais"."""
    if not isinstance(unit, str) or not unit.strip():
        return None
    u = fold(unit).replace("’", "'")
    u = UNIT_WORDS_RE.sub(" ", u)
    u = re.sub(r"\bste\b\.?", "sainte", u)
    u = re.sub(r"\bst\b\.?", "saint", u)
    return re.sub(r"[^a-z0-9]+", "", u) or None


# ---------------------------------------------------------------------------------------------
# British Columbia: regional districts
# ---------------------------------------------------------------------------------------------

# Today's 28 (the province's ABMS_REGIONAL_DISTRICTS_SP layer, 2026-10-20), by their short names.
BC_DISTRICTS = [
    "Alberni-Clayoquot", "Bulkley-Nechako", "Capital", "Cariboo", "Central Coast", "Central Kootenay",
    "Central Okanagan", "Columbia Shuswap", "Comox Valley", "Cowichan Valley", "East Kootenay",
    "Fraser Valley", "Fraser-Fort George", "Kitimat-Stikine", "Kootenay Boundary", "Metro Vancouver",
    "Mount Waddington", "Nanaimo", "North Coast", "North Okanagan", "Okanagan-Similkameen", "Peace River",
    "qathet", "Squamish-Lillooet", "Stikine", "Strathcona", "Sunshine Coast", "Thompson-Nicola",
]
# Older names (and the misspellings one source makes of them) -> today's district(s) on the same
# ground. Comox-Strathcona was split into Comox Valley and Strathcona in 2008 (part went to Mount
# Waddington's neighbour Strathcona); Fraser-Cheam, Central Fraser Valley and Dewdney-Alouette became
# Fraser Valley (1995, with part of Dewdney-Alouette going to Metro Vancouver); Powell River became
# qathet (2018); Skeena-Queen Charlotte became North Coast (2018); Greater Vancouver is Metro
# Vancouver; Fort Nelson-Liard became the Northern Rockies regional municipality (2009), which the
# layer does not list as a regional district, so it maps to nothing here.
BC_OLD_DISTRICTS = {
    "comoxstrathcona": ["Comox Valley", "Strathcona"],
    "fraservalley": ["Fraser Valley"],
    "frasercheam": ["Fraser Valley"],
    "centralfraservalley": ["Fraser Valley"],
    "dewdneyalouette": ["Fraser Valley", "Metro Vancouver"],
    "powellriver": ["qathet"],
    "skeenaqueencharlotte": ["North Coast"],
    "greatervancouver": ["Metro Vancouver"],
    "stikineregion": ["Stikine"],
    "stikineregionunincorporated": ["Stikine"],
    "okanogansimilkameen": ["Okanagan-Similkameen"],
    "northokanogan": ["North Okanagan"],
    "alberniclayoquot": ["Alberni-Clayoquot"],
    "albernicloyoquot": ["Alberni-Clayoquot"],
    "kootenayboundary": ["Kootenay Boundary"],
    "columbiashuswap": ["Columbia Shuswap"],
    "caribou": ["Cariboo"],
}
_BC_KEYS = {unit_key(n): n for n in BC_DISTRICTS}


def bc_current_districts(unit: str | None) -> list[str]:
    """Today's regional district(s) for a BC unit as a source writes it ([] when it names none)."""
    k = unit_key(unit)
    if not k:
        return []
    if k in _BC_KEYS:
        return [_BC_KEYS[k]]
    return list(BC_OLD_DISTRICTS.get(k, []))


def is_bc_district(text: str | None) -> bool:
    return bool(bc_current_districts(text))


# ---------------------------------------------------------------------------------------------
# Ontario, New Brunswick, Nova Scotia: census districts and counties
# ---------------------------------------------------------------------------------------------

# Ontario's census divisions that a lookout source might name with "District" or "County" (the north's
# districts, the south's counties and united counties). An Ontario Ministry fire district of another
# name ("Pembroke District", "Sioux Lookout District", "Temagami District") is not one of these.
ON_DISTRICTS = ["Algoma", "Cochrane", "Kenora", "Manitoulin", "Muskoka", "Nipissing", "Parry Sound",
                "Rainy River", "Sudbury", "Thunder Bay", "Timiskaming"]
ON_COUNTIES = ["Haliburton", "Renfrew", "Lanark", "Hastings", "Frontenac", "Lennox and Addington",
               "Peterborough", "Northumberland", "Simcoe", "Bruce", "Grey", "Norfolk", "Leeds and Grenville",
               "Prescott and Russell", "Stormont, Dundas and Glengarry", "Dufferin", "Wellington", "Huron",
               "Perth", "Middlesex", "Oxford", "Elgin", "Lambton", "Essex", "Brant", "Victoria", "Durham",
               "Haldimand", "Prince Edward"]
NB_COUNTIES = ["Albert", "Carleton", "Charlotte", "Gloucester", "Kent", "Kings", "Madawaska", "Northumberland",
               "Queens", "Restigouche", "Saint John", "Sunbury", "Victoria", "Westmorland", "York"]
NS_COUNTIES = ["Annapolis", "Antigonish", "Cape Breton", "Colchester", "Cumberland", "Digby", "Guysborough",
               "Halifax", "Hants", "Inverness", "Kings", "Lunenburg", "Pictou", "Queens", "Richmond", "Shelburne",
               "Victoria", "Yarmouth"]
PE_COUNTIES = ["Kings", "Prince", "Queens"]

_UNIT_RE = re.compile(r"^\s*(?P<name>.+?)\s+(?P<word>District|County|Counties|District Municipality)\s*$", re.I)


def named_unit(region: str, text: str | None) -> str | None:
    """The local unit a place line names, as it is written ("Northumberland County", "Parry Sound
    District", "Thompson-Nicola"), or None when the line names something else (a forest, a fire
    district, a park, a town). Only a unit that exists in the region counts."""
    if not isinstance(text, str) or not text.strip():
        return None
    t = re.sub(r"\s*[-–]\s*", "-", re.sub(r"\s+", " ", text.strip())).strip(" .,;")
    region = (region or "").upper()
    if region == "BC":
        return t if is_bc_district(t) else None
    if region == "NS" and unit_key(t) in ("cbrm", "capebretonregional"):
        return t                   # Cape Breton Regional Municipality, the census division Cape Breton
    m = _UNIT_RE.match(t)
    if not m:
        return None
    name = unit_key(m.group("name"))
    pool = {"ON": ON_DISTRICTS + ON_COUNTIES, "NB": NB_COUNTIES, "NS": NS_COUNTIES, "PE": PE_COUNTIES}.get(region)
    if not pool:
        return None
    if region == "ON":
        word = m.group("word").lower()
        allowed = ON_DISTRICTS if word.startswith("district") else ON_COUNTIES
        if word == "district" and name == unit_key("Muskoka"):
            allowed = ON_DISTRICTS
        if name not in {unit_key(x) for x in allowed}:
            return None
        return t
    return t if name in {unit_key(x) for x in pool} else None
