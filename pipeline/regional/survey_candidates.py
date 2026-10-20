"""Hand-compiled candidate lists from the expansion surveys -> source extracts (2026-10-20).

The expansion surveys (docs/sources/expansion_<key>.md) each left a hand-compiled candidate list,
$FIREFINDER_RAW_ROOT/expansion/<key>_candidates.json: {"key", "compiled", "note", "records": [...]},
records sharing one shape (name, other_names, country, region, county, lat, lon, location_from, kind,
status, built, agency, staffed_now, rental, access_note, sources[], and optional status_note,
location_hint, evidence[], extra{registers, elevation_m, ...}).

WHAT THIS WRITES: `curated_ak` (data/sources/curated_ak.json), the six Alaska lookouts of the ak-hi
survey (docs/sources/expansion_ak-hi.md), and (2026-10-20, the follow-up Canadian round) one extract
per Canadian survey: `survey_on`, `survey_prairies_north`, `survey_bc_yt`, `survey_qc_atl`, each a
hand-compiled source whose records link their evidence. A Canadian candidate is kept only when a
source it cites is not one of the bulk sources Firefinder reads itself (BULK_HOSTS: canada-lookouts.
weebly.com, firelookout.ca, the registers, OpenStreetMap, Wikidata, websiteservice.ca, the BC and
Ontario government layers): a row built only from those adds nothing their own extracts lack. The
per-survey rules (CA_RULES below) then apply the surveys' dated findings (DESIGN.md 3.5):
  - Nova Scotia: a lookout of the 2009 provincial network (Marscan's list) is gone, with the dated
    note that the province closed its towers in 2013 and took them down by 2015 (CBC), unless a source
    says it stands; STATUS_PICKS (pipeline/record_joins.py) lets that beat NHLR's 1998 listings.
  - Ontario: the hobbyist "still standing" list (c. 2009-2013) is standing with that dated note,
    ranking last, so any other source's gone wins.
  - Replicas stay replicas (Maniwaki, Aiguebelle, Medicine Lodge).
  - Saskatchewan: the provincial towers have no observer since the move to detection cameras
    (2013-14): staffing "unstaffed" with that note.
  - Yukon: the five lookouts staffed in 2024 (Moyles) are staffed, as of 2024; Sinkut (BC), as of 2026.
  - A unit the survey files a lookout under that is not a local unit (a park, "Vernon area") is a
    place hint, not a county.
  - A position the candidate copied from a bulk source is kept, so the record finds that source's
    tower by position, but marked `extra.position_copied_from` (the merge then never counts it as a
    second, independent position); a gazetteer's summit position (cdnrockiesdatabases.ca, BC
    Geographical Names) is a hint, never a position.

The generic rules (owner/orchestrator, 2026-10-20):
- key `<source>:<region lower>:<slug of the name>`; a repeated slug in one region gets -2, -3 in a
  fixed order (records with a position first, north to south, then by nearest place, list
  reference and first source URL), so a re-run gives the same keys.
- Position (lat/lon) only when the candidate's own `location_from` is a URL that publishes it, the
  point lies in the record's region box and the country, the survey does not flag it (extra.
  coord_problem, extra.placeholder_position) and it is not one of FLAGGED_POSITIONS. Never a
  position from the Alberta government's WF_WILDFIRE_LOOKOUT layer (geospatial.alberta.ca): that
  layer is read only by pipeline/regional/alberta_wildfire.py. `location_hint` (a GNIS or CGNDB hill
  of the same name) is NEVER a position: it is kept in extra.location_hint for people only.
- Name as the candidate gives it; other_names -> extra.aliases. Alaska counties are written as GNIS
  writes them ("Fairbanks North Star", "Matanuska-Susitna", "Anchorage"), without "Borough" or
  "Census Area", so the merge's GNIS approximate-pin rule (DESIGN.md 3.5) can find the hill.
  Canadian local units are kept in their own words.
- Status: a closed set of status_raw values, read through pipeline/structure.py (SURVEY_STATUS).
  These sources rank last in every field (unknown sources do), so any newer source wins.
- kind: the candidate's, if it is in data/vocab.json, else "unknown". built -> `built` and a built
  event. Other events only from an evidence item with a year that says unambiguously what happened;
  the note is ours (<= 120 chars), `from` the source id, `source_url` the evidence page.
- Registers: {"register": "NHLR", "number": "CAN 2, AB 2"} -> {"register": "NHLR", "number":
  "CAN 2", "state_number": "AB 2"}.
- Links: every URL in sources[] and evidence[], de-duplicated, as {label, url, kind: "reference"}
  with a short credit-ready label; the record's `url` is its first source URL.

The Alaska records (curated_ak): no source gives a tower position, so none has one; the merge
places each by the GNIS rule (a unique same-name summit, ridge... in the borough) or lists it as
"can't place yet". Glacier Lookout (Valdez) is not in the candidate file (the survey excludes it:
built as a glacier observatory). Hawaii: no lookout found, nothing to load. Each record carries a
`staffed` event for 1970, the year the BLM's Alaska Fire Report says the lookout was in use. After
writing curated_ak, re-run `python3 pipeline/fetch_gnis_places.py` so the AK names are looked up.

Output: data/sources/curated_ak.json, survey_on.json, survey_prairies_north.json, survey_bc_yt.json,
survey_qc_atl.json
Re-run: python3 pipeline/regional/survey_candidates.py
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import sys
import urllib.parse

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(HERE.parent))  # after regional/, whose _common.py shadows the pipeline's
from _common import RAW_ROOT, slugify, write_source_json  # noqa: E402
import regions  # noqa: E402

REPO = HERE.parent.parent
SOURCES_DIR = REPO / "data" / "sources"
EXPANSION = RAW_ROOT / "expansion"
VOCAB = REPO / "data" / "vocab.json"

# The default extract: survey key -> (source id, title, licence, credit).
CURATED = {
    "ak-hi": {
        "source": "curated_ak",
        "title": "Alaska fire lookouts named in the BLM's 1970 Alaska Fire Report (compiled by Firefinder)",
        "license": "Facts compiled from public documents (U.S. government works, a university bulletin); "
                   "each record links its sources",
        "credit": ("Compiled by Firefinder from the Bureau of Land Management's Alaska Fire Report (1970) and "
                   "University of Alaska Agricultural Experiment Station Bulletin 51 (1979); survey "
                   "docs/sources/expansion_ak-hi.md"),
        "doc": "docs/sources/expansion_ak-hi.md",
        "url": "https://archive.org/details/alaskafirereportunit",
    },
}

# The Canadian surveys of the follow-up round (2026-10-20): survey key -> source id, title, licence, credit.
CA_SURVEYS = {
    "on": {
        "source": "survey_on",
        "title": "Ontario fire lookouts compiled by Firefinder from the expansion survey",
        "credit": ("Compiled by Firefinder from Ontario's Fire Tower Lookouts (forestrangers.github.io), the Historical "
                   "Marker Database, Friends of Algonquin Park and the other pages each record links; survey "
                   "docs/sources/expansion_on.md"),
    },
    "prairies-north": {
        "source": "survey_prairies_north",
        "title": "Prairie and northern fire lookouts compiled by Firefinder from the expansion survey",
        "credit": ("Compiled by Firefinder from the Jasper Yellowhead Museum, the Manitoba Historical Society, Open "
                   "Alberta's 2009 lookout map, the Waskesiu Heritage Museum and the other pages each record links; "
                   "survey docs/sources/expansion_prairies-north.md"),
    },
    "bc-yt": {
        "source": "survey_bc_yt",
        "title": "British Columbia and Yukon fire lookouts compiled by Firefinder from the expansion survey",
        "credit": ("Compiled by Firefinder from ExploreNorth, Trina Moyles's \u201cKeeping Watch\u201d, Parks Canada, the "
                   "Canadian Register of Historic Places, The Rainlander and the other pages each record links; survey "
                   "docs/sources/expansion_bc-yt.md"),
    },
    "qc-atl": {
        "source": "survey_qc_atl",
        "title": "Quebec and Atlantic fire lookouts compiled by Firefinder from the expansion survey",
        "credit": ("Compiled by Firefinder from Marscan's Nova Scotia tower list, CBC News, the Répertoire du patrimoine "
                   "culturel du Québec, Newfoundland and Labrador's forestry history and the other pages each record "
                   "links; survey docs/sources/expansion_qc-atl.md"),
    },
}
for _k, _v in CA_SURVEYS.items():
    _v.setdefault("license", "Facts compiled from the sources each record links; no source text copied")
    _v.setdefault("doc", f"docs/sources/expansion_{_k}.md")

# The status_raw values these extracts write (closed set; pipeline/structure.py SURVEY_STATUS and,
# for the Canadian surveys, SURVEY_STATUS_CA).
STATUS_VALUES = ("standing", "gone", "ruins", "replica", "relocated", "likely gone", "unknown",
                 "gone (nova scotia closure)", "standing (ontario list c. 2009-2013)")

# Hosts Firefinder reads as sources of their own (2026-10-20), and the source id a position copied
# from each belongs to (None: never a position here). A Canadian candidate citing only these is left
# out: their extracts already hold what it says.
BULK_HOSTS: dict[str, str | None] = {
    "canada-lookouts.weebly.com": "canada_lookouts_weebly", "firelookout.ca": "firelookout_ca",
    "nhlr.org": "nhlr", "firetower.org": "fflos", "openstreetmap.org": "osm", "wikidata.org": "wikidata",
    "websiteservice.ca": "websiteservice_sk", "openmaps.gov.bc.ca": "bc_trim_lookouts",
    "sitesandtrailsbc.ca": "bc_rec_sites", "ws.lioservices.lrc.gov.on.ca": "ontario_lio",
    "geohub.lio.gov.on.ca": "ontario_lio", "geospatial.alberta.ca": None,
    # gazetteers (a hill's position is a hint, not the tower's) and a page naming no lookout
    "apps.gov.bc.ca": None, "geogratis.gc.ca": None, "gov.nt.ca": None,
}
# Hosts whose positions are a named hill's, never a tower's: kept as a hint for people.
HINT_HOSTS = {"cdnrockiesdatabases.ca", "apps.gov.bc.ca", "geogratis.gc.ca"}

# Positions a survey itself calls impossible or a placeholder, by (region, name): never used, never
# "fixed" by guessing. (websiteservice.ca's impossible digits; firelookout.ca's town pins.)
FLAGGED_POSITIONS = {
    ("SK", "Dube Fire Tower"), ("SK", "Molonosa Fire Tower"), ("SK", "Piwei Fire Tower"),
    ("SK", "Ridge Fire Tower"), ("SK", "Cumberland House Fire Tower"), ("SK", "Clear Lake Fire Tower"),
    # The Canadian Register's coordinate for Mount Revelstoke's Summit Fire Lookout is a place point 6 km
    # north-east of the summit (OpenStreetMap's tower is 350 m from the CGNDB summit); 2026-10-20.
    ("BC", "Summit Fire Lookout"),
}
# Hosts whose positions are never copied into these extracts.
BLOCKED_POSITION_HOSTS = {"geospatial.alberta.ca"}

# Short credit-ready labels: by exact URL first, then by host.
URL_LABELS = {
    "https://archive.org/details/alaskafirereportunit":
        "Bureau of Land Management, Alaska Fire Report 1970 (Internet Archive)",
    "https://www.uaf.edu/afes/publications/database/bulletin/files/pdfs/Bulletin_51.pdf":
        "University of Alaska Agricultural Experiment Station, Bulletin 51 (1979)",
    "https://www.jber.jb.mil/Services-Resources/Environmental/Nike/NSS/":
        "Joint Base Elmendorf-Richardson: Nike Site Summit",
}
HOST_LABELS = {
    "nhlr.org": "National Historic Lookout Register (nhlr.org)",
    "firetower.org": "Former Fire Lookout Sites Register (firetower.org)",
    "openstreetmap.org": "OpenStreetMap",
    "wikidata.org": "Wikidata",
    "archive.org": "Internet Archive",
    "hmdb.org": "The Historical Marker Database (hmdb.org)",
    "firelookout.ca": "Firelookout.ca, Open Canada Fire Lookout Index",
    "canada-lookouts.weebly.com": "Canada's Fire Lookouts (Ron Kemnow)",
    "websiteservice.ca": "Firetowers of Saskatchewan (websiteservice.ca)",
    "forestrangers.github.io": "Ontario's Fire Tower Lookouts (forestrangers.github.io)",
}

AK_UNIT_RE = re.compile(r"\s+(?:City and Borough|Borough|Census Area|Municipality)$", re.I)


def survey_source_id(key: str) -> str:
    """"ak-hi" -> "curated_ak"; any other key -> "survey_<key with - as _>"."""
    if key in CURATED:
        return CURATED[key]["source"]
    if key in CA_SURVEYS:
        return CA_SURVEYS[key]["source"]
    return "survey_" + key.replace("-", "_")


def vocab_kinds(path: pathlib.Path = VOCAB) -> set[str]:
    return set(json.loads(path.read_text(encoding="utf-8"))["kind"])


# ---------------------------------------------------------------------------------------------
# Fields
# ---------------------------------------------------------------------------------------------


def is_url(s) -> bool:
    return isinstance(s, str) and urllib.parse.urlparse(s.strip()).scheme in ("http", "https")


def host_of(url: str) -> str:
    return urllib.parse.urlparse(url.strip()).netloc.lower().removeprefix("www.")


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def position(c: dict) -> tuple[float | None, float | None, str | None]:
    """(lat, lon, None) when the candidate's own source publishes a usable position, else (None,
    None, why). `location_hint` is never read here."""
    lat, lon = c.get("lat"), c.get("lon")
    if not (_num(lat) and _num(lon)):
        return None, None, None
    src = c.get("location_from")
    region = str(c.get("region") or "").upper()
    country = regions.country_of(region) or str(c.get("country") or "").upper()
    extra = c.get("extra") or {}
    if not is_url(src):
        return None, None, "no source URL publishes this position"
    if host_of(src) in HINT_HOSTS:
        return None, None, "it is a gazetteer's position of the hill, not the tower's"
    if host_of(src) in BLOCKED_POSITION_HOSTS:
        return None, None, "a position from the Alberta government's lookout layer is not copied here"
    if extra.get("coord_problem") or extra.get("placeholder_position"):
        return None, None, "the survey flags this position"
    if (region, c.get("name")) in FLAGGED_POSITIONS:
        return None, None, "the survey flags this position as impossible or a placeholder"
    if not regions.in_region_box(region, float(lat), float(lon)) or not regions.in_country(country, float(lat), float(lon)):
        return None, None, "outside the record's region"
    return round(float(lat), 7), round(float(lon), 7), None


def split_register(reg: dict) -> dict | None:
    """{"register": "NHLR", "number": "CAN 2, AB 2"} -> {"register": "NHLR", "number": "CAN 2",
    "state_number": "AB 2"}. An entry already split is passed through."""
    if not isinstance(reg, dict) or not reg.get("register") or not reg.get("number"):
        return None
    name = str(reg["register"]).strip().upper()
    parts = [p.strip() for p in str(reg["number"]).split(",") if p.strip()]
    out = {"register": name, "number": parts[0], "state_number": reg.get("state_number")}
    if len(parts) > 1 and not out["state_number"]:
        out["state_number"] = parts[1]
    return out


def registers_of(c: dict) -> list[dict]:
    raw = list(c.get("registers") or []) + list((c.get("extra") or {}).get("registers") or [])
    out, seen = [], set()
    for reg in raw:
        r = split_register(reg)
        if r and (r["register"], r["number"]) not in seen:
            seen.add((r["register"], r["number"]))
            out.append(r)
    return out


def county_of(c: dict) -> str | None:
    county = c.get("county")
    if not isinstance(county, str) or not county.strip():
        return None
    county = re.sub(r"\s+", " ", county).strip()
    if str(c.get("region") or "").upper() == "AK":
        county = AK_UNIT_RE.sub("", county)       # GNIS writes "Matanuska-Susitna", not "... Borough"
    return county


def link_label(url: str) -> str:
    if url in URL_LABELS:
        return URL_LABELS[url]
    host = host_of(url)
    for h, label in HOST_LABELS.items():
        if host == h or host.endswith("." + h):
            return label
    return host


def links_of(c: dict) -> list[dict]:
    urls = [u for u in c.get("sources") or [] if is_url(u)]
    urls += [e.get("url") for e in c.get("evidence") or [] if isinstance(e, dict) and is_url(e.get("url"))]
    out, seen = [], set()
    for u in urls:
        u = u.strip()
        if u not in seen:
            seen.add(u)
            out.append({"label": link_label(u), "url": u, "kind": "reference"})
    return out


# Evidence wording -> event, for an item whose text says unambiguously what happened that year.
# (In use / manned that year -> `staffed`.) Anything else is left out.
EVIDENCE_EVENTS = [
    (re.compile(r"\b(?:in use|manned|staffed)\b", re.I), "staffed",
     "In use as a lookout this year ({src})."),
]
EVIDENCE_SOURCE_NAMES = {"archive.org": "BLM Alaska Fire Report"}


def evidence_events(c: dict, source: str) -> list[dict]:
    out = []
    for e in c.get("evidence") or []:
        if not isinstance(e, dict) or not isinstance(e.get("year"), int) or not isinstance(e.get("text"), str):
            continue
        hits = [(ev, note) for rx, ev, note in EVIDENCE_EVENTS if rx.search(e["text"])]
        if len(hits) != 1:
            continue                        # nothing said, or more than one thing: leave it out
        ev, note = hits[0]
        url = e.get("url") if is_url(e.get("url")) else None
        who = EVIDENCE_SOURCE_NAMES.get(host_of(url), link_label(url)) if url else "the source"
        item = {"year": e["year"], "event": ev, "note": note.format(src=who)[:120], "from": source}
        if url:
            item["source_url"] = url
        out.append(item)
    return out


def status_raw_of(c: dict) -> str:
    s = str(c.get("status") or "unknown").strip().lower()
    return s if s in STATUS_VALUES else "unknown"


STATUS_OF = {"standing": "standing", "gone": "gone", "ruins": "ruins", "replica": "replica",
             "relocated": "relocated", "likely gone": "unknown", "unknown": "unknown",
             "gone (nova scotia closure)": "gone", "standing (ontario list c. 2009-2013)": "standing"}


# ---------------------------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------------------------


def build_record(c: dict, source: str, kinds: set[str]) -> dict:
    region = str(c.get("region") or "").upper() or None
    country = regions.country_of(region) or (str(c.get("country") or "").upper() or None)
    lat, lon, why_not = position(c)
    sources = [u.strip() for u in c.get("sources") or [] if is_url(u)]
    kind = c.get("kind") if c.get("kind") in kinds else "unknown"
    built = c.get("built") if isinstance(c.get("built"), int) else None
    events = []
    if built:
        events.append({"year": built, "event": "built", "note": None, "from": source})
    for e in evidence_events(c, source):
        if (e["event"], e["year"]) not in {(x["event"], x["year"]) for x in events}:
            events.append(e)
    cx = c.get("extra") or {}
    extra: dict = {}
    aliases = [n for n in c.get("other_names") or [] if isinstance(n, str) and n.strip() and n != c.get("name")]
    if aliases:
        extra["aliases"] = aliases
    if why_not:
        extra["position_note"] = f"The survey's position is not used: {why_not}."
    if c.get("location_hint"):
        # A named hill or lake of the same name, for people only: never a position.
        extra["location_hint"] = c["location_hint"]
    if c.get("staffed_now") is True:
        extra["staffing_hint"] = "staffed"
    for k in ("status_note", "access_note", "nearest_place", "list_ref", "source_spelling", "confidence",
              "scope_flag", "type_raw"):
        v = c.get(k)
        if v not in (None, "", []):
            extra[{"access_note": "access_text", "type_raw": "type_text"}.get(k, k)] = v
    if _num(cx.get("elevation_m")):
        elevation = round(float(cx["elevation_m"]), 1)
    else:
        elevation = None
    for k, v in cx.items():
        if k not in ("registers", "elevation_m") and k not in extra and v not in (None, "", [], {}):
            extra[k] = v
    sr = status_raw_of(c)
    return {
        "key": None,      # set by assign_keys()
        "url": sources[0] if sources else None,
        "name": c.get("name"),
        "country": country,
        "region": region,
        "county": county_of(c),
        "lat": lat,
        "lon": lon,
        "elevation_m": elevation,
        "type_raw": None,
        "kind": kind,
        "status_raw": sr,
        "status": STATUS_OF[sr],
        "registers": registers_of(c),
        "built": built,
        "agency": (c.get("agency") or None),
        "events": events,
        "photos": [],
        "links": links_of(c),
        "rental": c.get("rental") if isinstance(c.get("rental"), dict) else None,
        "extra": extra,
    }


# ---------------------------------------------------------------------------------------------
# The Canadian surveys' rules (2026-10-20)
# ---------------------------------------------------------------------------------------------

def all_urls(c: dict) -> list[str]:
    urls = [u for u in c.get("sources") or [] if is_url(u)]
    urls += [e.get("url") for e in c.get("evidence") or [] if isinstance(e, dict) and is_url(e.get("url"))]
    return urls


def bulk_host(url: str) -> bool:
    h = host_of(url)
    return any(h == b or h.endswith("." + b) for b in BULK_HOSTS)


def camera_tower(c: dict) -> bool:
    """A Saskatchewan provincial tower the survey describes as one of the camera-equipped network."""
    text = " ".join(str(x) for x in (c.get("access_note"), c.get("notes"), (c.get("extra") or {}).get("notes"),
                                     (c.get("extra") or {}).get("note")) if x)
    return c.get("region") == "SK" and bool(re.search(r"\bcameras?\b", text, re.I))


def ca_keep(c: dict, key: str) -> bool:
    """A Canadian candidate adds something only when it cites a source Firefinder does not read itself;
    Saskatchewan's provincial towers also carry the survey's staffing finding (no observer since the
    move to cameras), kept when they have a position to find their tower by."""
    if any(not bulk_host(u) for u in all_urls(c)):
        return True
    return key == "prairies-north" and camera_tower(c) and _num(c.get("lat"))


UNIT_LIKE_RE = re.compile(r"^(?:Unorganized\s+)?Division No\.?\s*\d+$|\bNo\.?\s*\d+$|^Rural Municipality of\b", re.I)
NS_CLOSURE_RE = re.compile(r"closed its tower network in 2013", re.I)
ON_LIST_RE = re.compile(r"still standing c\.?\s*2009", re.I)


def ca_prepare(c: dict, key: str) -> tuple[dict, dict]:
    """(the candidate with the survey's dated findings applied, extra fields to add)."""
    import ca_units
    c = dict(c)
    add: dict = {}
    region = str(c.get("region") or "").upper()
    status = str(c.get("status") or "unknown").lower()
    note = " ".join(str(x) for x in (c.get("status_note"), c.get("notes")) if isinstance(x, str))
    # Nova Scotia: the 2009 network, closed 2013 and taken down by 2015 (CBC).
    if key == "qc-atl" and region == "NS" and status == "gone" and NS_CLOSURE_RE.search(note):
        c["status"] = "gone (nova scotia closure)"
    # Ontario: the hobbyist list of towers still standing, c. 2009-2013.
    if key == "on" and status == "standing" and any("forestrangers.github.io" in u for u in all_urls(c)) and (
            ON_LIST_RE.search(note) or "List asterisk" in note or "listed as standing" in note):
        c["status"] = "standing (ontario list c. 2009-2013)"
    # Staffing: what the survey found, with the year it holds for.
    if c.get("staffed_now") is True:
        add["staffing_hint"] = "staffed"
        add["staffing_as_of"] = 2026 if region == "BC" else 2024 if region == "YT" else None
    elif camera_tower(c):
        add["staffing_hint"] = "unstaffed"
        add["staffing_note"] = "No observer: Saskatchewan moved its towers to detection cameras from 2013-14."
    elif c.get("staffed_now") is False and status in ("standing", "replica"):
        add["staffing_hint"] = "unstaffed"
    # A unit that is not a local unit (a park, "Vernon area", a hill) is a place hint.
    county = c.get("county")
    if isinstance(county, str) and county.strip():
        if region == "BC":
            ok = ca_units.is_bc_district(county)
        elif region == "QC":
            ok = not re.search(r"\b(?:park|parc|area|reserve|national)\b", county, re.I)   # an MRC
        else:
            ok = bool(ca_units.named_unit(region, county) or ca_units.named_unit(region, county + " County")
                      or ca_units.named_unit(region, county + " District") or UNIT_LIKE_RE.search(county))
        if not ok:
            add["place_line"] = county
            c["county"] = None
    for k in ("division", "source_descriptor", "possible_duplicate_of", "cross_border_note", "approx_hint"):
        if c.get(k) not in (None, "", []):
            add[k] = c[k]
    return c, add


def copied_from(c: dict) -> str | None:
    """The source a candidate's position was copied from, when that is a source Firefinder reads itself."""
    src = c.get("location_from")
    if not is_url(src):
        return None
    h = host_of(src)
    sid = next((v for b, v in BULK_HOSTS.items() if h == b or h.endswith("." + b)), None)
    if sid == "bc_trim_lookouts" and (c.get("extra") or {}).get("rec_site_id"):
        return "bc_rec_sites"
    return sid


def _order(r: dict) -> tuple:
    """Fixed order for numbering a repeated slug: positioned first, north to south, then the
    record's own words."""
    ex = r["extra"]
    return (r["lat"] is None, -(r["lat"] or 0.0), str(ex.get("nearest_place") or ""),
            str(ex.get("list_ref") or ""), str(r.get("url") or ""), str(r.get("county") or ""))


def assign_keys(records: list[dict], source: str) -> list[dict]:
    """`<source>:<region>:<slug>`, -2, -3 for a slug repeated in one region (fixed order)."""
    groups: dict[tuple, list[dict]] = {}
    for r in records:
        groups.setdefault(((r["region"] or "xx").lower(), slugify(r["name"] or "unnamed")), []).append(r)
    for (region, slug), recs in groups.items():
        for i, r in enumerate(sorted(recs, key=_order)):
            r["key"] = f"{source}:{region}:{slug}" + (f"-{i + 1}" if i else "")
    return sorted(records, key=lambda r: r["key"])


def build_records(candidates: list[dict], source: str, kinds: set[str] | None = None,
                  survey: str | None = None) -> list[dict]:
    kinds = kinds if kinds is not None else vocab_kinds()
    if survey not in CA_SURVEYS:
        recs = [build_record(c, source, kinds) for c in candidates if isinstance(c, dict) and c.get("name")]
        return assign_keys(recs, source)
    recs = []
    for c in candidates:
        if not isinstance(c, dict) or not c.get("name") or not ca_keep(c, survey):
            continue
        c2, add = ca_prepare(c, survey)
        r = build_record(c2, source, kinds)
        r["extra"].update({k: v for k, v in add.items() if v is not None})
        cf = copied_from(c2)
        if r["lat"] is not None and cf:
            r["extra"]["position_copied_from"] = cf
        recs.append(r)
    return assign_keys(recs, source)


def load_candidates(key: str, root: pathlib.Path = EXPANSION) -> dict:
    path = root / f"{key}_candidates.json"
    if not path.exists():
        raise SystemExit(f"{path} is missing")
    return json.loads(path.read_text(encoding="utf-8"))


def check_ak_counties(records: list[dict], sources_dir: pathlib.Path = SOURCES_DIR) -> list[str]:
    """Alaska counties GNIS does not know (data/sources/gnis_places.json): each would stay unplaced."""
    path = sources_dir / "gnis_places.json"
    if not path.exists():
        return []
    known = set((json.loads(path.read_text(encoding="utf-8")).get("counties") or {}).get("AK") or [])
    return [f"{r['key']}: {r['county']!r}" for r in records
            if r["region"] == "AK" and r["county"] and known and r["county"] not in known]


def write(key: str, out_dir: pathlib.Path = SOURCES_DIR) -> pathlib.Path:
    data = load_candidates(key)
    source = survey_source_id(key)
    records = build_records(data.get("records") or [], source, survey=key)
    meta = CURATED.get(key) or CA_SURVEYS.get(key) or {
        "title": f"Expansion survey candidates ({key}), compiled by Firefinder",
        "license": "Facts compiled from the sources each record links; no source text copied",
        "credit": f"Compiled by Firefinder; survey docs/sources/expansion_{key}.md",
        "doc": f"docs/sources/expansion_{key}.md",
    }
    out = out_dir / f"{source}.json"
    write_source_json(out, source=source, title=meta["title"], url=meta.get("url") or meta["doc"],
                      retrieved=str(data.get("compiled") or "")[:10] or None, license_=meta["license"],
                      records=records,
                      header_extra={"credit": meta["credit"], "survey": key, "survey_doc": meta["doc"]})
    from collections import Counter
    print(f"wrote {len(records)} records -> {out}", file=sys.stderr)
    print(f"  by region: {dict(sorted(Counter(r['region'] for r in records).items()))}; with a position: "
          f"{sum(1 for r in records if r['lat'] is not None)}", file=sys.stderr)
    for line in check_ak_counties(records):
        print(f"  WARNING: county not in GNIS: {line}", file=sys.stderr)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--survey", action="append", metavar="KEY", default=[],
                    help="also convert another survey's candidates to survey_<key> with the generic rules")
    args = ap.parse_args(argv)
    for key in ["ak-hi", *CA_SURVEYS, *[k for k in args.survey if k != "ak-hi" and k not in CA_SURVEYS]]:
        write(key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
