"""Countries and their regions (states, provinces, territories): the one table every part of
the pipeline reads (DESIGN.md 3.3, "Countries and regions"; owner decision 2026-10-20: Alaska,
Hawaii and all of Canada join the lower 48).

- A tower's `country` is an ISO 3166-1 alpha-2 code ("US", "CA"); its `region` the state,
  province or territory code inside that country ("OR", "AK", "ON", "QC"), as postal services
  write them.
- Ids are `<country>-<region>-<slug>`, lower case: `us-or-abbot-butte`, `ca-on-shining-tree`.
- Tower files: `data/towers/<dir>/<id>.json`, where `<dir>` is the bare state code for a US tower
  (`or/`, as since 2026-10-03, so no existing file moves) and `<country>-<region>` for every other
  country (`ca-on/`, `ca-bc/`). A two-letter folder is always a US state or territory; a hyphenated
  one always names its country, so a future country whose codes repeat a US state's (Australia's
  WA, NT, SA) can never share a folder with it. `tower_dir()` is the rule.
- Region codes are unique across the countries listed here today (checked at import). Merge keys
  some indexes by region code alone, so a country whose codes repeat another's needs those keys
  country-qualified first (DESIGN.md 3.3).

Bounding boxes are generous (about 0.1 to 0.5 degrees of padding), for sanity checks only: they
flag a likely sign slip or a row filed under the wrong region for a human; they never move a
point. Alaska has two boxes because the Aleutians cross the 180th meridian (Attu is at 172.9 E).

Python 3.12, standard library only.
"""

from __future__ import annotations

import functools
import json
import re
import unicodedata
from pathlib import Path

COUNTRY_NAMES = {"US": "United States", "CA": "Canada"}
# Words for a country's regions, singular and plural, for page copy.
REGION_WORDS = {"US": ("state", "states"), "CA": ("province or territory", "provinces and territories")}
# Shown order: the US first (its states alphabetically), then Canada.
COUNTRY_ORDER = ["US", "CA"]

US_STATES = {
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
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
US_OTHER = {
    "DC": "District of Columbia", "PR": "Puerto Rico", "GU": "Guam", "VI": "U.S. Virgin Islands",
    "AS": "American Samoa", "MP": "Northern Mariana Islands",
}
CA_PROVINCES = {
    "AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba", "NB": "New Brunswick",
    "NL": "Newfoundland and Labrador", "NS": "Nova Scotia", "NT": "Northwest Territories",
    "NU": "Nunavut", "ON": "Ontario", "PE": "Prince Edward Island", "QC": "Quebec",
    "SK": "Saskatchewan", "YT": "Yukon",
}
REGION_NAMES_BY_COUNTRY = {"US": {**US_STATES, **US_OTHER}, "CA": CA_PROVINCES}

# Official French names, for reading French sources (and the Quebec name as Quebec writes it).
# Pages use the English names.
CA_FRENCH = {
    "AB": "Alberta", "BC": "Colombie-Britannique", "MB": "Manitoba", "NB": "Nouveau-Brunswick",
    "NL": "Terre-Neuve-et-Labrador", "NS": "Nouvelle-Écosse", "NT": "Territoires du Nord-Ouest",
    "NU": "Nunavut", "ON": "Ontario", "PE": "Île-du-Prince-Édouard", "QC": "Québec",
    "SK": "Saskatchewan", "YT": "Yukon",
}
# Other spellings sources use. Lower case, accents folded (see fold()).
_ALIASES = {
    "pq": "QC", "que": "QC", "province of quebec": "QC", "province de quebec": "QC",
    "newfoundland": "NL", "labrador": "NL", "nfld": "NL", "nf": "NL",
    "nwt": "NT", "n.w.t": "NT", "northwest territory": "NT", "yukon territory": "YT", "yk": "YT",
    "pei": "PE", "p.e.i": "PE", "b.c": "BC", "alta": "AB", "sask": "SK", "man": "MB", "ont": "ON",
    "n.b": "NB", "n.s": "NS",
    "washington state": "WA", "district of columbia": "DC", "virgin islands": "VI",
    "us virgin islands": "VI", "u.s. virgin islands": "VI",
}

REGION_COUNTRY: dict[str, str] = {}
for _c, _tbl in REGION_NAMES_BY_COUNTRY.items():
    for _code in _tbl:
        if _code in REGION_COUNTRY:  # pragma: no cover - a table edit gone wrong
            raise RuntimeError(f"region code {_code} is used by {REGION_COUNTRY[_code]} and {_c}; "
                               "merge keys regions by code, so qualify them by country first (regions.py)")
        REGION_COUNTRY[_code] = _c
REGION_NAMES: dict[str, str] = {code: name for tbl in REGION_NAMES_BY_COUNTRY.values() for code, name in tbl.items()}

# ---------------------------------------------------------------------------------------------
# Boxes: (lat_min, lat_max, lon_min, lon_max), padded. A region may have several.
# ---------------------------------------------------------------------------------------------

REGION_BOXES: dict[str, list[tuple[float, float, float, float]]] = {
    "AL": [(30.0, 35.1, -88.6, -84.8)],
    # Alaska: the mainland and the Aleutians east of 180, and the Near and Rat Islands west of it.
    "AK": [(51.0, 71.6, -180.0, -129.0), (51.0, 53.2, 172.0, 180.0)],
    "AZ": [(31.1, 37.1, -114.9, -108.9)],
    "AR": [(32.9, 36.6, -94.7, -89.5)],
    "CA": [(32.4, 42.1, -124.5, -114.0)],
    "CO": [(36.9, 41.1, -109.2, -101.9)],
    "CT": [(40.9, 42.1, -73.8, -71.7)],
    "DE": [(38.3, 39.9, -75.9, -74.9)],
    "FL": [(24.4, 31.1, -87.7, -79.8)],
    "GA": [(30.3, 35.1, -85.7, -80.7)],
    # Hawaii: the main islands, and the Northwestern Hawaiian Islands out to Kure Atoll.
    "HI": [(18.8, 22.3, -160.3, -154.7), (22.3, 28.6, -178.5, -160.0)],
    "ID": [(41.9, 49.1, -117.3, -110.9)],
    "IL": [(36.9, 42.6, -91.6, -87.0)],
    "IN": [(37.7, 41.8, -88.2, -84.7)],
    "IA": [(40.3, 43.6, -96.7, -90.0)],
    "KS": [(36.9, 40.1, -102.1, -94.5)],
    "KY": [(36.4, 39.2, -89.6, -81.9)],
    "LA": [(28.8, 33.1, -94.1, -88.7)],
    "ME": [(42.9, 47.5, -71.2, -66.8)],
    "MD": [(37.8, 39.8, -79.5, -74.9)],
    "MA": [(41.1, 43.0, -73.6, -69.8)],
    "MI": [(41.6, 48.3, -90.5, -82.1)],
    "MN": [(43.4, 49.5, -97.3, -89.4)],
    "MS": [(30.1, 35.1, -91.7, -88.0)],
    "MO": [(35.9, 40.7, -95.9, -89.0)],
    "MT": [(44.3, 49.1, -116.1, -104.0)],
    "NE": [(39.9, 43.1, -104.2, -95.3)],
    "NV": [(34.9, 42.1, -120.1, -113.9)],
    "NH": [(42.6, 45.4, -72.6, -70.6)],
    "NJ": [(38.8, 41.4, -75.6, -73.8)],
    "NM": [(31.2, 37.1, -109.1, -102.9)],
    "NY": [(40.4, 45.1, -79.8, -71.7)],
    "NC": [(33.7, 36.7, -84.4, -75.3)],
    "ND": [(45.9, 49.1, -104.1, -96.5)],
    "OH": [(38.3, 42.0, -84.9, -80.4)],
    "OK": [(33.5, 37.1, -103.1, -94.3)],
    "OR": [(41.9, 46.4, -124.7, -116.4)],
    "PA": [(39.6, 42.4, -80.6, -74.6)],
    "RI": [(41.0, 42.1, -71.9, -71.0)],
    "SC": [(32.0, 35.3, -83.5, -78.4)],
    "SD": [(42.4, 46.1, -104.1, -96.3)],
    "TN": [(34.9, 36.8, -90.4, -81.6)],
    "TX": [(25.7, 36.6, -106.7, -93.4)],
    "UT": [(36.9, 42.1, -114.2, -108.9)],
    "VT": [(42.6, 45.1, -73.5, -71.4)],
    "VA": [(36.5, 39.5, -83.7, -75.1)],
    "WA": [(45.5, 49.1, -124.9, -116.9)],
    "WV": [(37.1, 40.7, -82.7, -77.6)],
    "WI": [(42.4, 47.2, -93.0, -86.2)],
    "WY": [(40.9, 45.1, -111.2, -104.0)],
    # US territories and DC
    "PR": [(17.8, 18.6, -67.4, -65.2)],
    "VI": [(17.6, 18.5, -65.1, -64.5)],
    "GU": [(13.2, 13.7, 144.6, 145.0)],
    "AS": [(-14.6, -11.0, -171.1, -168.1)],
    "MP": [(14.0, 20.6, 144.8, 146.1)],
    "DC": [(38.7, 39.0, -77.2, -76.9)],
    # Canada
    "AB": [(48.9, 60.1, -120.1, -109.9)],
    "BC": [(48.2, 60.1, -139.2, -114.0)],
    "MB": [(48.9, 60.1, -102.2, -88.9)],
    "NB": [(44.5, 48.2, -69.2, -63.7)],
    "NL": [(46.5, 60.5, -67.9, -52.5)],
    "NS": [(43.3, 47.1, -66.5, -59.6)],
    "NT": [(59.9, 78.9, -136.6, -101.9)],
    "NU": [(51.6, 83.2, -121.1, -61.0)],
    "ON": [(41.6, 56.9, -95.2, -74.3)],
    "PE": [(45.9, 47.1, -64.5, -61.9)],
    "QC": [(44.9, 62.6, -79.8, -57.1)],
    "SK": [(48.9, 60.1, -110.1, -101.3)],
    "YT": [(59.9, 69.7, -141.1, -123.7)],
}


def country_of(region: str | None) -> str | None:
    """"ON" -> "CA", "OR" -> "US"; None for an unknown code."""
    return REGION_COUNTRY.get((region or "").upper()) if region else None


def region_name(region: str | None) -> str:
    """English name of a region code ("ON" -> "Ontario"); the code itself if unknown."""
    if not region:
        return ""
    return REGION_NAMES.get(region.upper(), region)


def region_with_country(region: str | None) -> str:
    """"Oregon" for a US state; "Ontario, Canada" for a Canadian province, as page copy says it."""
    name = region_name(region)
    c = country_of(region)
    if c and c != "US" and name:
        return f"{name}, {COUNTRY_NAMES[c]}"
    return name


def id_prefix(country: str | None, region: str | None) -> str:
    """"us-or", "ca-on". A missing region is "xx" (validate.py rejects it)."""
    c = (country or country_of(region) or "US").lower()
    return f"{c}-{(region or 'xx').lower()}"


def tower_dir(tower_id: str) -> str:
    """The data/towers/ folder of a tower: "or" for us-or-..., "ca-on" for ca-on-... (module docstring)."""
    parts = tower_id.split("-")
    if len(parts) < 2:
        return "xx"
    return parts[1] if parts[0] == "us" else f"{parts[0]}-{parts[1]}"


def fold(text: str) -> str:
    """Lower case, accents dropped, spaces collapsed: "Québec" -> "quebec"."""
    t = unicodedata.normalize("NFKD", text)
    t = "".join(ch for ch in t if not unicodedata.combining(ch)).lower()
    return re.sub(r"\s+", " ", t).strip()


_BY_NAME: dict[str, str] = {}
for _code, _name in REGION_NAMES.items():
    _BY_NAME[fold(_name)] = _code
for _code, _name in CA_FRENCH.items():
    _BY_NAME[fold(_name)] = _code
    _BY_NAME[fold(_name).replace("-", " ")] = _code
for _alias, _code in _ALIASES.items():
    _BY_NAME[_alias] = _code


def parse_region(text: str | None, country: str | None = None) -> str | None:
    """A region code from a code or a name, English or French: "Ontario", "ON", "Québec",
    "Colombie-Britannique", "B.C." -> code. None when the text names no region (or one of
    another country than `country`). Never guesses from part of a word."""
    if not text:
        return None
    t = fold(str(text)).strip(" .,")
    code = None
    if len(t) == 2 and t.upper() in REGION_COUNTRY:
        code = t.upper()
    else:
        code = _BY_NAME.get(t) or _BY_NAME.get(t.replace(".", "")) or _BY_NAME.get(t.replace("-", " "))
    if code and country and REGION_COUNTRY.get(code) != country.upper():
        return None
    return code


def _in_box(box: tuple, lat: float, lon: float) -> bool:
    a, b, c, d = box
    return a <= lat <= b and c <= lon <= d


def in_region_box(region: str | None, lat: float, lon: float) -> bool:
    """True when the point is inside one of the region's boxes. Unknown regions: True (no claim)."""
    boxes = REGION_BOXES.get((region or "").upper())
    if not boxes:
        return True
    return any(_in_box(b, lat, lon) for b in boxes)


def regions_at(lat: float, lon: float, country: str | None = None) -> list[str]:
    """Every region whose box holds the point (boxes overlap along borders), in code order."""
    out = []
    for code, boxes in sorted(REGION_BOXES.items()):
        if country and REGION_COUNTRY.get(code) != country:
            continue
        if any(_in_box(b, lat, lon) for b in boxes):
            out.append(code)
    return out


def in_country(country: str | None, lat: float, lon: float) -> bool:
    """Inside one of the country's region boxes: the US's states and territories (Alaska's two
    boxes either side of 180), Canada's provinces and territories."""
    c = (country or "").upper()
    return any(_in_box(b, lat, lon) for code, boxes in REGION_BOXES.items()
               if REGION_COUNTRY.get(code) == c for b in boxes)


def in_coverage(lat: float, lon: float) -> bool:
    """Inside the area Firefinder covers: any region box of any country listed."""
    return any(_in_box(b, lat, lon) for boxes in REGION_BOXES.values() for b in boxes)


def country_at(lat: float, lon: float) -> str | None:
    """The one country whose boxes hold the point, else None (a border strip both claim)."""
    cs = {REGION_COUNTRY[r] for r in regions_at(lat, lon)}
    return cs.pop() if len(cs) == 1 else None


def flag_coordinate(region: str, lat: float, lon: float) -> str | None:
    """A short problem code, or None if the coordinate looks plausible for the region.

    North America is west of Greenwich and north of the equator, so a positive longitude or a
    negative latitude is a sign slip -- except inside a box of the region itself: the Aleutians
    west of 180 (Alaska's second box) and the Pacific territories."""
    boxes = REGION_BOXES.get((region or "").upper())
    if boxes and any(_in_box(b, lat, lon) for b in boxes):
        return None
    if lon > 0:
        return "lon_positive_sign"
    if lat < 0:
        return "lat_negative_sign"
    return "outside_state_bbox" if boxes else None


# ---------------------------------------------------------------------------------------------
# Local administrative units: the words a page adds after a county name
# ---------------------------------------------------------------------------------------------

# Alaska's census areas (the parts of the Unorganized Borough the Census Bureau counts as county
# equivalents). Any other Alaska unit is a borough (or a city and borough / municipality, which
# carry their own words).
AK_CENSUS_AREAS = {
    "aleutians west", "bethel", "chugach", "copper river", "dillingham", "hoonah-angoon",
    "kusilvak", "nome", "prince of wales-hyder", "southeast fairbanks", "yukon-koyukuk",
    "valdez-cordova", "wade hampton", "skagway-hoonah-angoon", "wrangell-petersburg",
    "prince of wales-outer ketchikan",
}
UNIT_WORDS_RE = re.compile(
    r"\b(County|Parish|Borough|Census Area|Municipality|City|City and Borough|District|"
    r"Regional District|Regional Municipality|Region|Division|Division No\.? ?\d+|Territory|"
    r"Unorganized|Unorganised|Township|Municipal District|Improvement District|Special Area)\b", re.I)


def local_unit_label(country: str | None, region: str | None, county: str | None) -> str | None:
    """The local unit as a page writes it: "Jefferson County", "Caddo Parish", "Bethel Census
    Area", "Matanuska-Susitna Borough"; a Canadian unit exactly as its source names it (they carry
    their own words: "Sudbury District", "Regional District of Central Kootenay", "Division No.
    18"). None when there is no county."""
    if not county or not str(county).strip():
        return None
    c = str(county).strip()
    country = (country or country_of(region) or "US").upper()
    if country != "US":
        return c
    if re.search(r"\b(County|Parish|Borough|Census Area|Municipality|City)$", c, re.I) or "/" in c:
        return c
    reg = (region or "").upper()
    if reg == "LA":
        return f"{c} Parish"
    if reg == "AK":
        return f"{c} Census Area" if fold(c) in AK_CENSUS_AREAS else f"{c} Borough"
    return f"{c} County"


# ---------------------------------------------------------------------------------------------
# Point in province: Natural Earth admin-1 polygons, for sources that give a position but no
# region (OSM, a plus-code address). Fetchers use it; the merge never needs it.
# ---------------------------------------------------------------------------------------------

NATURAL_EARTH_ADMIN1_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/"
    "ne_10m_admin_1_states_provinces.geojson")


class Admin1Lookup:
    """Point-in-polygon over Natural Earth's admin-1 file (public domain), cached once under
    $FIREFINDER_RAW_ROOT/natural_earth/. Only the US and Canada are kept."""

    def __init__(self, geojson_path: Path, countries=("US", "CA")):
        data = json.loads(geojson_path.read_text(encoding="utf-8"))
        self.features = []
        for feat in data["features"]:
            p = feat.get("properties") or {}
            iso = str(p.get("iso_3166_2") or "")
            if "-" not in iso:
                continue
            cc, code = iso.split("-", 1)
            if cc not in countries or code not in REGION_COUNTRY:
                continue
            g = feat.get("geometry") or {}
            polys = g.get("coordinates") if g.get("type") == "MultiPolygon" else [g.get("coordinates")]
            boxes = []
            for poly in polys or []:
                xs = [x for ring in poly for x, _ in ring]
                ys = [y for ring in poly for _, y in ring]
                boxes.append((min(xs), min(ys), max(xs), max(ys)))
            self.features.append((code, polys, boxes))

    @staticmethod
    def _inside(lon: float, lat: float, poly) -> bool:
        inside = False
        for ring in poly:
            n = len(ring)
            for i in range(n):
                x1, y1 = ring[i]
                x2, y2 = ring[(i + 1) % n]
                if (y1 > lat) != (y2 > lat):
                    if lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
                        inside = not inside
        return inside

    def region_for(self, lat: float, lon: float) -> str | None:
        for code, polys, boxes in self.features:
            for poly, (x0, y0, x1, y1) in zip(polys, boxes):
                if x0 <= lon <= x1 and y0 <= lat <= y1 and self._inside(lon, lat, poly):
                    return code
        return None

    def nearest_region(self, lat: float, lon: float, max_deg: float = 0.05) -> str | None:
        """region_for, or the region found by nudging the point up to max_deg (about 5 km) in
        eight directions, when exactly one region answers: a summit on a generalised coastline."""
        hit = self.region_for(lat, lon)
        if hit:
            return hit
        found = set()
        for dlat, dlon in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            r = self.region_for(lat + dlat * max_deg, lon + dlon * max_deg)
            if r:
                found.add(r)
        return found.pop() if len(found) == 1 else None


@functools.lru_cache(maxsize=2)
def admin1_lookup(raw_root: Path) -> Admin1Lookup:
    """Admin1Lookup over the cached Natural Earth file, fetched once if missing."""
    path = raw_root / "natural_earth" / "ne_10m_admin_1_states_provinces.geojson"
    if not path.exists():
        import urllib.request
        path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(NATURAL_EARTH_ADMIN1_URL, headers={
            "User-Agent": "FirefinderBot/0.1 (+https://github.com/holdTheDoorHoid/firefinder)"})
        with urllib.request.urlopen(req, timeout=120) as r:
            body = r.read()
        tmp = path.with_suffix(".part")
        tmp.write_bytes(body)
        tmp.replace(path)
    return Admin1Lookup(path)
