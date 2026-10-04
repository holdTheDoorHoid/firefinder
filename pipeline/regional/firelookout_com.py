"""Fetcher for firelookout.com (Rex Kamstra's Pacific NW / Rockies lookout site).

Covers Montana, Washington, Oregon, Idaho, Wyoming and South Dakota. Each
state has two Google-Maps-API-v2-era HTML pages full of
``GV_Draw_Marker({...})`` / ``GV_Marker(gmap,{...})`` calls: a "<ST>map.html"
with every known site (standing + gone) and a "<ST>mapstanding.html" with
standing sites only. Every marker carries lat/lon/name and (almost always) a
link to a per-tower detail page with a short prose history, agency, county,
elevation, and photos.

Output:
  data/sources/firelookout_com.json   -- one record per tower site
  data/sources/designs_reference.json -- facts about L-4/L-5/L-6/R-6/D-6/Aermotor
                                          cab designs, from lktpix.html

Status is derived structurally (present on the "standing" map == standing;
present only on the "all sites" map == gone) rather than guessed from prose,
since that is the one fact the site itself encodes unambiguously.

Detail-page fetching is capped by --detail-scope (default: "standing") since
fetching all ~3,250 "all sites" detail pages as well would be thousands of
requests at the mandated 2s/host rate limit. Gone-site records still get
name/coordinates/url/status from the map markers; a future run with
--detail-scope all can fill in the rest -- the on-disk cache makes that free
for anything already fetched.

Re-run:
  python3 pipeline/regional/firelookout_com.py
  python3 pipeline/regional/firelookout_com.py --detail-scope all   # slow, thousands of requests
  python3 pipeline/regional/firelookout_com.py --detail-scope none  # markers only, no detail fetch
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import (  # noqa: E402
    FetchError,
    cache_path,
    fetch_text,
    ft_to_m,
    slugify,
    write_source_json,
)

SOURCE = "firelookout_com"
BASE = "https://www.firelookout.com"
HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

STATES = [
    # (region, all_sites_page, standing_page, base_page, detail_prefix)
    ("MT", "MTmap.html", "MTmapstanding.html", "mt.html", "mt"),
    ("WA", "WAmap.html", "WAmapstanding.html", "wa.html", "wa"),
    ("OR", "ORmap.html", "ORmapstanding.html", "or.html", "or"),
    ("ID", "IDmap.html", "IDmapstanding.html", "id.html", "id"),
    ("WY", "WYmap.html", "WYmapstanding.html", "wy.html", "wy"),
    ("SD", "SDmap.html", "SDmapstanding.html", "sd.html", "sd"),
]

STATE_NAME = {
    "MT": "Montana", "WA": "Washington", "OR": "Oregon",
    "ID": "Idaho", "WY": "Wyoming", "SD": "South Dakota",
}

# Matches a GV_Draw_Marker({...}) or GV_Marker(gmap,{...}) object body,
# regardless of which wrapper function this particular page used (the site
# is inconsistent about that -- see pipeline notes / final report).
MARKER_RE = re.compile(
    r"\{lat:([\-\d.]+),lon:([\-\d.]+),name:'((?:[^'\\]|\\.)*)',"
    r"desc:'((?:[^'\\]|\\.)*)',color:'[^']*',icon:'([^']*)'"
    # A couple of MT entries have a copy-paste typo in the source page --
    # url:'url:\'http://...' -- tolerate the stray "url:\'" prefix.
    r"(?:,url:'(?:url:\\')?([^']*)')?,icon_size:"
)

# South Dakota map markers carry no url at all, and the names used on the
# marker vs. on sd.html's own link list often don't share a normalizable
# slug (e.g. marker "Black Elk (Harney) Peak" vs link "Harney Peak
# Lookout"). Small enough list (28 sites) to hand-map the mismatches.
SD_NAME_ALIASES = {
    "black-elk-harney-peak": "harney-peak",
    "mt-coolidge": "coolidge-mount",
    "seth-bullock-peak": "seth-bullock",
    "lacreek": "lacreek-nwr",
}

LINK_RE = re.compile(
    r'HREF="([a-z]{2}/[a-z0-9]+\.html)"[^>]*>([^<]+)</A>', re.IGNORECASE
)

DESIGN_RE = re.compile(r"\b(L-4|L-5|L-6|R-6|D-6|Aermotor)\b")
HEIGHT_RE = re.compile(r"(\d{1,3})['’]\s*(?:pole|steel tower|wood(?:en)? tower|tower|cab|concrete base)", re.I)
RIP_RE = re.compile(r"R\.I\.P\.\s*(\d{4})\s*-\s*(\d{4}|\?)")
BUILT_RE = re.compile(
    r"(?:built|constructed|developed|erected)\D{0,15}?(?:in|during)\D{0,5}(\d{4})", re.I
)
GONE_BY_RE = re.compile(r"gone by (\d{4})", re.I)
REMOVED_RE = re.compile(r"removed in (\d{4})", re.I)
ABANDONED_RE = re.compile(r"abandoned[^.]{0,30}?in (\d{4})", re.I)
BURNED_RE = re.compile(r"burned(?: down)?[^.]{0,20}?in (\d{4})", re.I)
YEAR_RE = re.compile(r"\b(1[89]\d\d|20[0-2]\d)\b")
ELEV_RE = re.compile(r"Elevation\s*([\d,]+)'", re.I)
COUNTY_RE = re.compile(r"([A-Za-z.' ]+?)\s+Count(?:y|ies),\s*([A-Za-z ]+)")
TITLE_RE = re.compile(r"<TITLE>(.*?)</TITLE>", re.I | re.S)
NAME_H_RE = re.compile(r"<U>(.*?)</U>", re.I | re.S)
PROSE_RE = re.compile(r"<TD[^>]*ROWSPAN[^>]*>\s*<H5>(.*?)</H5>", re.I | re.S)
AGENCY_RE = re.compile(r"</TABLE>.*", re.S)  # not used; agency parsed positionally below
IMG_RE = re.compile(
    r'<A HREF="([^"]+\.jpg)"[^>]*><IMG SRC="[^"]*"\s+alt="([^"]*)"', re.I
)
CREDIT_RE = re.compile(r"Photo[s]? courtesy (?:of )?([^<]+)</CENTER>", re.I)


def tag_rows(html: str) -> list[str]:
    """Pull out the plain-text content of each <TH>...</TH> row in the facts
    table (agency, location note, county/state, elevation). Order is fixed
    by the site's own template."""
    return [re.sub(r"<[^>]+>", "", t).strip() for t in re.findall(r"<TH[^>]*>(.*?)</TH>", html, re.I | re.S)]


def parse_markers(html: str) -> list[dict]:
    out = []
    for lat, lon, name, desc, icon, url in MARKER_RE.findall(html):
        out.append({
            "lat": float(lat),
            "lon": float(lon),
            "name": name.replace("\\'", "'").strip(),
            "desc": desc.replace("\\'", "'").strip() or None,
            "url": url or None,
        })
    return out


def parse_state_links(html: str) -> dict[str, tuple[str, str]]:
    """slugified name -> (display name, relative url) from a state's own
    listing page. Used where markers omit the url (South Dakota).

    South Dakota's link text always carries a trailing "Lookout" that the
    map markers' names don't ("Battle Mtn. Lookout" vs "Battle Mtn."), so
    every entry is indexed under both the full slug and the slug with a
    trailing "-lookout" trimmed."""
    out = {}
    for rel_url, text in LINK_RE.findall(html):
        name = text.strip()
        if not name:
            continue
        slug = slugify(name)
        out[slug] = (name, rel_url)
        if slug.endswith("-lookout"):
            out.setdefault(slug[: -len("-lookout")], (name, rel_url))
    return out


def fetch_cached(rel_path: str) -> str:
    """Read a page already in the shared cache (or fetch it if genuinely
    missing). All index/map pages used here were pre-populated during
    reconnaissance; this call is what makes a from-scratch re-run work too."""
    return fetch_text(f"{BASE}/{rel_path}", SOURCE, rel_path)


def parse_detail_page(html: str) -> dict:
    title_m = TITLE_RE.search(html)
    title = title_m.group(1).strip() if title_m else ""
    kind_word = None
    for w in ("Tower", "Cabin", "House", "Cab"):
        if title.endswith(w):
            kind_word = w
            break

    name_m = NAME_H_RE.search(html)
    display_name = re.sub(r"\s+", " ", name_m.group(1)).strip() if name_m else None

    rip_m = RIP_RE.search(html)
    rip_start = int(rip_m.group(1)) if rip_m else None
    rip_end = int(rip_m.group(2)) if rip_m and rip_m.group(2) != "?" else None

    prose_m = PROSE_RE.search(html)
    prose = re.sub(r"<[^>]+>", " ", prose_m.group(1)).strip() if prose_m else ""
    prose = re.sub(r"\s+", " ", prose)

    designs = DESIGN_RE.findall(prose)
    design = designs[-1] if designs else None

    heights = [int(h) for h in HEIGHT_RE.findall(prose)]
    height_ft = heights[-1] if heights else None

    built_m = BUILT_RE.search(prose)
    built_year = int(built_m.group(1)) if built_m else rip_start
    if built_year is None:
        years = [int(y) for y in YEAR_RE.findall(prose)]
        built_year = min(years) if years else None

    destroyed_year = rip_end
    destroyed_event = "removed"
    if destroyed_year is None:
        m = GONE_BY_RE.search(prose)
        if m:
            destroyed_year, destroyed_event = int(m.group(1)), "removed"
    if destroyed_year is None:
        m = BURNED_RE.search(prose)
        if m:
            destroyed_year, destroyed_event = int(m.group(1)), "burned"
    if destroyed_year is None:
        m = REMOVED_RE.search(prose)
        if m:
            destroyed_year, destroyed_event = int(m.group(1)), "removed"
    if destroyed_year is None:
        m = ABANDONED_RE.search(prose)
        if m:
            destroyed_year, destroyed_event = int(m.group(1)), "abandoned"

    staffing = None
    low = prose.lower()
    if "staffed every summer" in low or "staffed each summer" in low or "currently staffed" in low:
        staffing = "staffed"
    elif "no longer staffed" in low or "unstaffed" in low:
        staffing = "unstaffed"
    elif "volunteer" in low:
        staffing = "volunteer"

    rows = tag_rows(html)
    # Fixed template order: title, optional "R.I.P. YYYY-YYYY", agency,
    # location note, "County, State", "Elevation N'". Not all pages have
    # all rows. Skip the title row itself and any R.I.P. row -- both are
    # <TH> cells too and would otherwise be mistaken for the agency line.
    rows = [r for r in rows[1:] if not RIP_RE.search(r)]
    agency_raw = None
    county = None
    elevation_ft = None
    for row in rows:
        if row.lower().startswith("elevation"):
            m = ELEV_RE.search(row)
            if m:
                elevation_ft = int(m.group(1).replace(",", ""))
        elif COUNTY_RE.search(row):
            m = COUNTY_RE.search(row)
            county = m.group(1).strip()
        elif agency_raw is None and row and "county" not in row.lower() and not row.lower().startswith("elevation"):
            # first non-elevation, non-county row after the title is the
            # agency/forest line in every observed page
            if re.search(r"(mile|km)s? (north|south|east|west|NN|NE|NW|SE|SW)", row, re.I) is None:
                agency_raw = row

    photos = []
    credit_m = CREDIT_RE.search(html)
    shared_credit = credit_m.group(1).strip().rstrip(".") if credit_m else None
    for img_url, alt in IMG_RE.findall(html):
        if "nophoto" in img_url.lower():
            continue
        year_m = re.search(r"(19|20)\d{2}", alt)
        photos.append({
            "url": img_url,
            "credit": shared_credit,
            "caption": alt.strip() or None,
            "year": int(year_m.group(0)) if year_m else None,
        })

    return {
        "display_name": display_name,
        "kind_word": kind_word,
        "agency_raw": agency_raw,
        "county": county,
        "elevation_ft": elevation_ft,
        "design": design,
        "height_ft": height_ft,
        "built_year": built_year,
        "destroyed_year": destroyed_year,
        "destroyed_event": destroyed_event,
        "staffing": staffing,
        "photos": photos,
        "rip": rip_m is not None,
    }


def kind_from_word(word: str | None) -> str:
    if word in ("Tower",):
        return "tower"
    if word in ("Cabin", "House", "Cab"):
        return "ground"
    return "unknown"


def agency_to_ownership(agency_raw: str | None) -> str:
    if not agency_raw:
        return "unknown"
    low = agency_raw.lower()
    if "reservation" in low or "tribal" in low or "tribe" in low:
        return "tribal"
    if ("national forest" in low or "national park" in low or "blm" in low
            or "bureau of land" in low or "national wildlife refuge" in low
            or "wildlife refuge" in low):
        return "federal"
    if "state forestry" in low or "state forest" in low or "state park" in low:
        return "state"
    return "unknown"


def _recover_url(m: dict, link_map: dict[str, tuple[str, str]], region: str) -> str | None:
    if m.get("url"):
        return m["url"]
    slug = slugify(m["name"])
    if region == "SD":
        slug = SD_NAME_ALIASES.get(slug, slug)
    hit = link_map.get(slug)
    return hit[1] if hit else None


def _identity(m: dict) -> str:
    """One stable key per site: name + coordinates at the same precision
    as rec_key. Deliberately URL-independent -- the site itself sometimes
    gives one marker two different urls on its "all sites" vs "standing"
    maps (e.g. Sex Peak's all-sites marker points to the regional index
    page "mtsanders.html" instead of its own "mt/sexpeak.html"), and
    keying on url would wrongly split one real site into two records."""
    return f"{slugify(m['name'])}:{m['lat']:.4f}:{m['lon']:.4f}"


def _is_real_tower_url(url: str | None) -> bool:
    """True for a per-tower subpage like "mt/sexpeak.html", false for a
    bare state/region index page like "mtsanders.html" or "mt.html"."""
    if not url:
        return False
    path = re.sub(r"^https?://[^/]+/", "", url)
    return "/" in path


def build_state_records(region: str, all_page: str, standing_page: str, base_page: str,
                         prefix: str, detail_scope: str) -> list[dict]:
    all_html = fetch_cached(all_page)
    standing_html = fetch_cached(standing_page)
    base_html = fetch_cached(base_page)

    all_markers = parse_markers(all_html)
    standing_markers = parse_markers(standing_html)
    link_map = parse_state_links(base_html)

    standing_ids = {_identity(m) for m in standing_markers}

    # Merge "all" and "standing" by stable identity, so every site appears
    # exactly once even though it is listed on both maps. When the two
    # markers disagree on url (see _identity's docstring), prefer whichever
    # one is a real per-tower subpage over a bare region-index page.
    merged: dict[str, dict] = {}
    for m in all_markers + standing_markers:
        key = _identity(m)
        if key not in merged:
            merged[key] = dict(m)
            continue
        existing_url, new_url = merged[key].get("url"), m.get("url")
        if new_url and (not existing_url or (_is_real_tower_url(new_url) and not _is_real_tower_url(existing_url))):
            merged[key]["url"] = new_url

    records = []
    for key, m in merged.items():
        url = _recover_url(m, link_map, region)
        status = "standing" if key in standing_ids else "gone"

        slug = slugify(m["name"])
        rec_key = f"firelookout_com:{region.lower()}:{slug}:{m['lat']:.4f}:{m['lon']:.4f}"
        # Marker urls are already absolute (http://www.firelookout.com/...);
        # link-list-recovered urls (South Dakota) are relative. Normalize
        # both to one absolute https url plus a bare relative path, the
        # latter doubling as the on-disk cache key.
        if url:
            rel_path = re.sub(r"^https?://[^/]+/", "", url)
            page_url = f"{BASE}/{rel_path}"
        else:
            rel_path = None
            page_url = f"{BASE}/{base_page}"

        detail = None
        fetch_detail = detail_scope == "all" or (detail_scope == "standing" and status == "standing")
        if rel_path and fetch_detail:
            try:
                detail_html = fetch_text(page_url, SOURCE, rel_path)
                detail = parse_detail_page(detail_html)
            except FetchError as e:
                print(f"  ! {region} {m['name']}: {e}", file=sys.stderr)

        # The marker name ("Warren Peak") is clean title case; the detail
        # page's own heading is shouted caps with a "LOOKOUT" suffix
        # ("WARREN PEAK LOOKOUT") -- prefer the marker name.
        name = m["name"]
        kind_word = detail.get("kind_word") if detail else None
        kind_raw = kind_word or m.get("desc") or None
        kind = kind_from_word(kind_word) if kind_word else "unknown"

        events = []
        agency_raw = detail.get("agency_raw") if detail else None
        if detail:
            if detail["built_year"]:
                events.append({"year": detail["built_year"], "event": "built", "note": None, "from": "firelookout_com"})
            if detail["destroyed_year"]:
                events.append({
                    "year": detail["destroyed_year"],
                    "event": detail["destroyed_event"],
                    "note": None,
                    "from": "firelookout_com",
                })

        photos = []
        for p in (detail.get("photos") if detail else []):
            photos.append({
                "url": p["url"],
                "credit": p["credit"],
                "caption": p["caption"],
                "year": p["year"],
            })

        extra = {}
        if detail is None and url and detail_scope != "none":
            extra["detail_fetch_skipped"] = f"detail_scope={detail_scope}"

        rec = {
            "key": rec_key,
            "url": page_url,
            "name": name,
            "country": "US",
            "region": region,
            "county": (detail.get("county") if detail else None),
            "lat": round(m["lat"], 5),
            "lon": round(m["lon"], 5),
            "elevation_m": ft_to_m(detail["elevation_ft"]) if detail and detail.get("elevation_ft") else None,
            "type_raw": kind_raw,
            "kind": kind,
            "status_raw": "Standing" if status == "standing" else "Not on standing map",
            "status": status,
            "registers": [],
            "built": (detail.get("built_year") if detail else None),
            "agency": agency_raw,
            "events": events,
            "photos": photos,
            "links": [{"label": "firelookout.com", "url": page_url}],
            "rental": None,
            "extra": {
                **extra,
                **({"elevation_ft": detail["elevation_ft"]} if detail and detail.get("elevation_ft") else {}),
                **({"design": detail["design"]} if detail and detail.get("design") else {}),
                **({"height_ft": detail["height_ft"]} if detail and detail.get("height_ft") else {}),
                **({"ownership": agency_to_ownership(agency_raw)} if agency_raw else {}),
                **({"staffing_hint": detail["staffing"]} if detail and detail.get("staffing") else {}),
            },
        }
        records.append(rec)

    return records


DESIGN_FACTS = {
    "L-4": {
        "aka": ["Aladdin"],
        "dimensions_ft": [14, 14],
        "years_in_use": "1929-1953",
        "roof": "peaked (early: gable; later: hip)",
        "notes": "Standard USFS pre-cut lookout house; wood shutter panels hinged over windows, lowered in winter.",
    },
    "L-5": {
        "aka": [],
        "dimensions_ft": [10, 10],
        "years_in_use": "1930s",
        "roof": None,
        "notes": "Smaller pre-cut house for secondary lookout points; name also applied to some 14x14 ft gable-roofed log cabins in ID/MT.",
    },
    "L-6": {
        "aka": [],
        "dimensions_ft": [8, 8],
        "years_in_use": None,
        "roof": None,
        "notes": "Smallest pre-cut cab, mounted atop tall wooden towers with separate ground-level living quarters.",
    },
    "R-6": {
        "aka": [],
        "dimensions_ft": [15, 15],
        "years_in_use": "1953-present",
        "roof": "flat, overhanging for shade",
        "notes": "Named for USFS Region 6 (Washington & Oregon), which originated the design.",
    },
    "D-6": {
        "aka": [],
        "dimensions_ft": [12, 12],
        "years_in_use": "1920s",
        "roof": "cupola, quarter-size second-floor observatory",
        "notes": "Named for former USFS District 6 (Pacific NW, later Region 6). Very few survive.",
    },
    "Aermotor": {
        "aka": [],
        "dimensions_ft": None,
        "years_in_use": None,
        "roof": None,
        "notes": "Steel tower by the Aermotor Company (Chicago), primarily a windmill-tower maker. More common in the southeastern US than the Pacific NW.",
    },
}


def build_designs_reference() -> dict:
    retrieved = datetime.date.today().isoformat()
    records = []
    for name, facts in DESIGN_FACTS.items():
        records.append({
            "key": f"firelookout_com:design:{slugify(name)}",
            "url": f"{BASE}/lktpix.html",
            "name": name,
            "country": "US", "region": None, "county": None,
            "lat": None, "lon": None,
            "elevation_m": None,
            "type_raw": "tower design", "kind": "unknown",
            "status_raw": None, "status": "unknown",
            "registers": [],
            "built": None, "agency": None,
            "events": [],
            "photos": [],
            "links": [{"label": "firelookout.com design reference", "url": f"{BASE}/lktpix.html"}],
            "rental": None,
            "extra": {
                "aka": facts["aka"],
                "dimensions_ft": facts["dimensions_ft"],
                "years_in_use": facts["years_in_use"],
                "roof": facts["roof"],
                "notes": facts["notes"],
            },
        })
    return {
        "source": "firelookout_com_designs",
        "title": "Fire lookout tower/cab designs (firelookout.com)",
        "url": f"{BASE}/lktpix.html",
        "retrieved": retrieved,
        "license": "No licence stated; facts only (design names, dimensions, era), paraphrased from firelookout.com's own definitions page.",
        "records": records,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--detail-scope", choices=["standing", "all", "none"], default="standing",
                     help="which tower detail pages to fetch (default: standing only)")
    ap.add_argument("--states", default=None,
                     help="comma-separated region codes to limit to, e.g. WY,SD (default: all six)")
    args = ap.parse_args()
    wanted = set(args.states.split(",")) if args.states else None

    retrieved = datetime.date.today().isoformat()
    all_records = []
    for region, all_page, standing_page, base_page, prefix in STATES:
        if wanted and region not in wanted:
            continue
        print(f"== {region} ({STATE_NAME[region]}) ==", file=sys.stderr)
        recs = build_state_records(region, all_page, standing_page, base_page, prefix, args.detail_scope)
        standing_n = sum(1 for r in recs if r["status"] == "standing")
        print(f"   {len(recs)} sites ({standing_n} standing)", file=sys.stderr)
        all_records.extend(recs)

    out_path = REPO_ROOT / "data" / "sources" / "firelookout_com.json"
    write_source_json(
        out_path,
        source=SOURCE,
        title="firelookout.com -- Rex Kamstra's Forest Fire Lookout Page",
        url=BASE + "/",
        retrieved=retrieved,
        license_="No licence stated on the site; facts only (coordinates, elevation, built/destroyed years, design, agency). Photos mirrored with the site's stated credit.",
        records=all_records,
    )
    print(f"wrote {len(all_records)} records -> {out_path}", file=sys.stderr)

    designs_path = REPO_ROOT / "data" / "sources" / "designs_reference.json"
    designs = build_designs_reference()
    with designs_path.open("w") as f:
        json.dump(designs, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"wrote designs reference -> {designs_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
