"""Fetcher for Ron Kemnow's western "FOREST LOOKOUTS" weebly sites, the siblings of
easternuslookouts.weebly.com / centraluslookouts.weebly.com (weebly_lookouts.py):

  westlookouts.weebly.com        AK AZ CO NE NV NM ND SD UT WY     (nav grouped by state)
  californialookouts.weebly.com  CA                                 (nav grouped by county)
  idaholookouts.weebly.com       ID                                 (county)
  montanalookouts.weebly.com     MT                                 (county)
  oregonlookouts.weebly.com      OR                                 (county)
  washingtonlookouts.weebly.com  WA                                 (county)

FFLA's links page (firelookout.org/resources/links/) points to the author's index, ronkemnow.weebly.com,
which links all of them. Same author, same template, same page-per-lookout layout as the eastern and
central sites, but the western template differs in what sits under the name: a National Forest (or
other land manager) and a township-range-section ("38S-11W-30") instead of "<State> - <County> County
- <Agency>", and the county comes from the nav (a "BAKER COUNTY" header over its lookouts) rather
than from the page.

Reconnaissance, 2026-10-08
--------------------------
 * ~3,900 nav entries across the six sites; about 60% of the tower pages embed a Weebly map widget
   whose iframe URL carries `long=` / `lat=` (the author's own placement; the same widget the eastern
   fetcher reads). The rest have only the township-range-section, kept as extra.plss.
 * Most of what these sites list is already in Firefinder (they are built from the same Kresek /
   Kamstra / FFLA material): comparing names only, 2,990 of 3,080 western tower names match a tower we
   have. What the site adds is the long tail of sites, plus a link to the author's page for each.
 * California's and Montana's county index pages also carry a few lookouts that have no page of their
   own (name, forest, township-range-section, no coordinates). They are not read: nothing places them.
 * Pages for things that are not lookouts ("Work Party - 2015", "To Locate", "Misc. Notes") are skipped.

Per DESIGN.md 2/3.2 the pages' newspaper quotes and narrative are never stored; the record carries
facts only: name, county, land manager, status (a standalone word such as "Removed" only), height and
design where a phrase says so, the township-range-section, the map widget's coordinates, and links
(the page, its firelookout.com twin and any NHLR / FFLOS register page).

Output:  data/sources/west_us_lookouts.json

Re-run:
  python3 pipeline/regional/weebly_west.py                    # all six sites (~3,900 pages, ~45 min
                                                                # per 1,400 pages: 2 s per request)
  python3 pipeline/regional/weebly_west.py --site oregon      # one site
  python3 pipeline/regional/weebly_west.py --crawl-only --site washington   # just fill the cache
Pages are cached under data/raw/west_us_lookouts/<host>/, so a re-run is free and a crashed one resumes.
"""

from __future__ import annotations

import argparse
import datetime
import html as htmlmod
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import FetchError, fetch_text, slugify, write_source_json  # noqa: E402
import weebly_lookouts as W  # noqa: E402  (same author, same template: reuse its page reader)

SOURCE = "west_us_lookouts"
HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

SITES = {
    "west": {"host": "westlookouts.weebly.com", "group": "state",
             "states": ["AK", "AZ", "CO", "NE", "NV", "NM", "ND", "SD", "UT", "WY"]},
    "california": {"host": "californialookouts.weebly.com", "group": "county", "states": ["CA"]},
    "idaho": {"host": "idaholookouts.weebly.com", "group": "county", "states": ["ID"]},
    "montana": {"host": "montanalookouts.weebly.com", "group": "county", "states": ["MT"]},
    "oregon": {"host": "oregonlookouts.weebly.com", "group": "county", "states": ["OR"]},
    "washington": {"host": "washingtonlookouts.weebly.com", "group": "county", "states": ["WA"]},
}

LICENSE = (
    "No licence stated; facts only (county, land manager, status word, coordinates where the page's own "
    "map widget gives them, township-range-section, height and design hints, links). The site's own "
    "newspaper quotes, citations and narrative are not reproduced."
)

STATE_BY_NAME = {k: v for k, v in W.STATE_FULL.items()}
STATE_BY_NAME["ALASKA"] = "AK"
STATE_BY_NAME.update({"ARIZONA": "AZ", "COLORADO": "CO", "IDAHO": "ID", "MONTANA": "MT", "NEBRASKA": "NE",
                      "NEVADA": "NV", "NEW MEXICO": "NM", "NORTH DAKOTA": "ND", "OREGON": "OR",
                      "UTAH": "UT", "WASHINGTON": "WA", "WYOMING": "WY", "CALIFORNIA": "CA"})

PLSS_RE = re.compile(r"^\d{1,2}\s*[NS]\s*-\s*\d{1,3}\s*[EW]\s*-\s*\d{1,2}$", re.I)
COUNTY_HEADER_RE = re.compile(r"^(.*?)\s+(?:County|Parish)\.?$", re.I)
# A county header in the sidebar (the page's own location line uses the plain COUNTY_HEADER_RE).
# Besides "BAKER COUNTY" the author writes "IDAHO COUNTY (A-L)" and "IDAHO COUNTY (M-W)" (a county split
# into two alphabetical halves), "LANE COUNTY - 2" (a second page of one county), "(cont.)" and, once,
# "**Harney County***" (a county note set off with asterisks). Words after the county word that name
# something else ("Los Angeles County Fairplex", "Pike County Peak") are not headers.
NAV_COUNTY_HEADER_RE = re.compile(
    r"^[\s*\W_]*(?P<name>[A-Za-z][A-Za-z.' -]*?)\s+(?:County|Parish)\b"
    r"(?:\s*(?:\([^()]*\)|[-\u2013\u2014]+\s*(?:\d+\b|[A-Za-z]\b|cont\.?|continued|part\s*\w+\b)|cont\.?|continued))*"
    r"[\s*\W_]*$",
    re.I,
)
# A sidebar anchor with its attributes, so a top-level menu item ("wsite-menu-item": a county, or a page
# such as "To Locate") can be told from a lookout inside a county's dropdown ("wsite-menu-subitem").
NAV_ANCHOR_RE = re.compile(r'<a\s+([^>]*href="[^"]+"[^>]*)>(.*?)</a>', re.S | re.I)
HREF_RE = re.compile(r'href="([^"]+)"')
TOP_LEVEL_RE = re.compile(r'class="[^"]*\bwsite-menu-item\b')
# A quote or a dated news item starts the page's narrative; nothing after it is location data.
NARRATIVE_START_RE = re.compile(
    r"^(?:<?\d{4}\b|[A-Z][a-z]+\.?\s+\d{1,2},?\s+\d{4}|[\"“]|Activated:|Built|Constructed|In\s)", re.I
)
AGENCY_WORD_RE = re.compile(
    r"National Forest|National Park|National Monument|National Recreation|Nat'l|Indian Reservation|"
    r"Reservation|Wildlife Refuge|NWR|State Forest|State Park|^State$|Department|Division of|Bureau|BLM|"
    r"Private|Protective Association|Protective Assoc|Timber|Tree Farm|Corporation|Company|Lumber|"
    r"Weyerhaeuser|Land Management|Navy|Army|Air Force|Forest Service|Fish and Wildlife|Preserve|"
    r"Experimental Forest|Military|Rayonier|Boise Cascade|Plum Creek|Simpson|Crown Zellerbach|"
    r"Forest\b|Forests\b|Station\b",
    re.I,
)
# Page names that are not lookouts, or not one place.
SKIP_NAME_RE = re.compile(
    r"\b(?:work party|to locate|misc\.?|notes?|general|index|contributors|search)\b", re.I
)
SKIP_PAGE_NAMES = {"", "FOREST LOOKOUTS", "HOME", "OREGON LOOKOUTS", "IDAHO LOOKOUTS", "MONTANA LOOKOUTS",
                   "WASHINGTON LOOKOUTS", "CALIFORNIA LOOKOUTS", "WESTERN LOOKOUTS"}
# Standalone status words (the page's own status field), the same list the eastern fetcher trusts.
STATUS_EXACT = W.STATUS_EXACT

REX_HOST_RE = re.compile(r"firelookout\.com", re.I)


def norm(text: str) -> str:
    t = htmlmod.unescape(re.sub(r"<[^>]+>", " ", text))
    t = t.replace("​", "").replace("﻿", "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip(" \t\r\n-–")


def nav_entries(html: str, group: str, states: list[str]) -> list[dict]:
    """Every tower page in a site's sidebar nav, with the county or state its header puts it under:
    [{"rel": "/quail-prairie-mountain.html", "text": "Quail Prairie Mountain", "county": ..., "state": ...}].
    A header is a nav link whose text is "<Name> County" (county sites; NAV_COUNTY_HEADER_RE lists the
    spellings) or a state name (west site); county pages and state pages are not towers and are not
    returned. On a county site a top-level page that is not a county ends the county above it."""
    body = html[html.find("<body"):]
    body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
    body = re.sub(r"<style.*?</style>", "", body, flags=re.S)
    out, seen = [], set()
    county = None
    state = states[0] if len(states) == 1 else None
    for attrs, raw in NAV_ANCHOR_RE.findall(body):
        text = norm(raw)
        rel = htmlmod.unescape(HREF_RE.search(attrs).group(1))
        if not rel.endswith(".html") or rel.startswith("http") or not text:
            continue
        top_level = bool(TOP_LEVEL_RE.search(attrs))
        if group == "state":
            code = STATE_BY_NAME.get(re.sub(r"[>\s.]+$", "", text).upper())
            if code and not rel.rstrip("0123456789.html").endswith("-notes"):
                state, county = code, None
                continue
        else:
            m = NAV_COUNTY_HEADER_RE.match(text)
            if m and ("county" in rel.lower() or "parish" in rel.lower()):
                county = re.sub(r"\s+", " ", m.group("name")).strip().title()
                continue
            if top_level:
                # a top-level page that is not a county ("To Locate", with Jimmy Peak and Mount Jumbo
                # listed after it): what follows is not in the county above it
                county = None
        if SKIP_NAME_RE.search(text) or text.upper() in SKIP_PAGE_NAMES or not re.search(r"[A-Za-z0-9]", text):
            continue
        if rel in seen:
            continue
        seen.add(rel)
        out.append({"rel": rel, "text": text, "county": county, "state": state})
    return out


def parse_location_nodes(nodes: list[str]) -> dict:
    """Read the lines under the name, up to the first dated/quoted narrative line."""
    out = {"county": None, "state": None, "agency": None, "plss": None, "qualifier": None}
    i = 1
    if i < len(nodes) and re.fullmatch(r"\(.+\)", nodes[i] or ""):
        out["qualifier"] = nodes[i].strip("()").strip()
        i += 1
    for node in nodes[i:i + 6]:
        if not node:
            continue
        if NARRATIVE_START_RE.match(node) and not AGENCY_WORD_RE.search(node):
            break
        segs = [s for s in (norm(x) for x in re.split(r"\s+-\s+|\s*>\s*|\s*–\s*", node)) if s]
        hit = False
        for seg in segs:
            if PLSS_RE.match(seg):
                out["plss"] = re.sub(r"\s+", "", seg).upper()
                hit = True
            elif seg.upper() in STATE_BY_NAME:
                out["state"] = STATE_BY_NAME[seg.upper()]
                hit = True
            elif COUNTY_HEADER_RE.match(seg):
                out["county"] = out["county"] or COUNTY_HEADER_RE.match(seg).group(1).strip().title()
                hit = True
            elif AGENCY_WORD_RE.search(seg) and not out["agency"] and len(seg) <= 90:
                out["agency"] = seg
                hit = True
        if not hit and out["agency"] is None and out["plss"] is None and out["county"] is None:
            # an unrecognised line before any location data: the page has no location block
            break
    return out


def standalone_status(nodes: list[str]) -> tuple[str, str | None]:
    for node in nodes[1:12]:
        key = node.strip().lower().rstrip(".")
        if key in STATUS_EXACT:
            return STATUS_EXACT[key]
    return "unknown", None


def ownership_of(agency: str | None) -> str:
    return W.agency_to_ownership(agency)


def parse_page(html: str, entry: dict, host: str) -> dict | None:
    nodes = W.own_content_text_nodes(html)
    if not nodes:
        return None
    name = norm(nodes[0])
    if not name or name.upper() in SKIP_PAGE_NAMES or SKIP_NAME_RE.search(name):
        return None
    if not re.search(r"[A-Za-z0-9]", name):
        return None  # a divider ("************")
    if COUNTY_HEADER_RE.match(name) or NAV_COUNTY_HEADER_RE.match(name) or name.upper() in STATE_BY_NAME:
        return None  # a county or state index page
    loc = parse_location_nodes(nodes)
    full_name = W.unshout(f"{name} ({loc['qualifier']})" if loc["qualifier"] else name)
    status, status_raw = standalone_status(nodes)
    full_text = " ".join(nodes)
    height_ft, design = W.parse_height_and_design(full_text)
    m = W.IFRAME_COORD_RE.search(html)
    lat = float(m.group(2)) if m else None
    lon = float(m.group(1)) if m else None
    tail = html[W.H2_RE.search(html).start():]
    tail = re.sub(r"<script.*?</script>", "", tail, flags=re.S)
    tail = re.sub(r"<style.*?</style>", "", tail, flags=re.S)
    links = []
    for href, h, _label in W.REGISTER_LINK_RE.findall(tail):
        label = "National Historic Lookout Register" if "nhlr" in h else "Former Fire Lookout Sites Register"
        links.append({"label": label, "url": href, "kind": "register"})
    for href in re.findall(r'<a\s[^>]*href="(https?://(?:www\.)?firelookout\.com/[^"]+)"', tail, re.I):
        links.append({"label": "firelookout.com page (Rex Kamstra)", "url": href, "kind": "site"})
    state = loc["state"] or entry.get("state")
    county = loc["county"] or entry.get("county")
    return {
        "name": full_name, "state": state, "county": county, "agency": loc["agency"], "plss": loc["plss"],
        "lat": lat, "lon": lon, "status": status, "status_raw": status_raw, "height_ft": height_ft,
        "design": design, "links": links,
        "kind": "tree" if (W.TREE_SUFFIX_RE.search(name) or re.search(r"\btree$", name, re.I)) else "unknown",
    }


def build(site_keys: list[str], max_pages: int | None, crawl_only: bool) -> list[dict]:
    records: list[dict] = []
    seen_keys: set[str] = set()
    for site_key in site_keys:
        cfg = SITES[site_key]
        host = cfg["host"]
        base = f"https://{host}"
        nav_html = fetch_text(f"{base}/", SOURCE, f"{host}/index.html", encoding="utf-8")
        entries = nav_entries(nav_html, cfg["group"], cfg["states"])
        if max_pages:
            entries = entries[:max_pages]
        print(f"== {site_key}: {len(entries)} pages ==", file=sys.stderr)
        skipped = no_coord = 0
        for n, entry in enumerate(entries, 1):
            url = f"{base}{entry['rel']}"
            try:
                html = fetch_text(url, SOURCE, f"{host}/{entry['rel'].lstrip('/')}", encoding="utf-8")
            except FetchError as e:
                print(f"  ! {entry['text']!r} ({url}): {e}", file=sys.stderr)
                continue
            if n % 100 == 0:
                print(f"   {site_key} {n}/{len(entries)}", file=sys.stderr)
            if crawl_only:
                continue
            d = parse_page(html, entry, host) if "<h2" in html else None
            if not d or not d["state"]:
                skipped += 1
                continue
            slug = slugify(pathlib.PurePosixPath(entry["rel"]).stem)
            key = f"{SOURCE}:{d['state'].lower()}:{slug}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            if d["lat"] is None:
                no_coord += 1
            extra: dict = {}
            if d["plss"]:
                extra["plss"] = d["plss"]
            if d["lat"] is None:
                extra["location_text"] = ", ".join(
                    x for x in [d["county"] and f"{d['county']} County", d["agency"]] if x) or None
            if d["height_ft"]:
                extra["height_ft"] = d["height_ft"]
            if d["design"]:
                extra["design"] = d["design"]
            own = ownership_of(d["agency"])
            if own != "unknown":
                extra["ownership"] = own
            records.append({
                "key": key, "url": url, "name": d["name"], "country": "US", "region": d["state"],
                "county": d["county"],
                "lat": round(d["lat"], 5) if d["lat"] is not None else None,
                "lon": round(d["lon"], 5) if d["lon"] is not None else None,
                "elevation_m": None, "type_raw": None, "kind": d["kind"],
                "status_raw": d["status_raw"], "status": d["status"], "registers": [],
                "built": None, "agency": d["agency"], "events": [], "photos": [],
                "links": [{"label": f"{host}", "url": url}] + d["links"],
                "rental": None, "extra": extra,
            })
        print(f"   {site_key}: {len(entries)} pages, {skipped} not lookout pages, "
              f"{no_coord} records without coordinates", file=sys.stderr)
    return records


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", choices=list(SITES), action="append", help="limit to one site (repeatable)")
    ap.add_argument("--max-pages", type=int, default=None, help="cap pages per site (smoke test)")
    ap.add_argument("--crawl-only", action="store_true", help="fill the cache, write nothing")
    args = ap.parse_args()
    keys = args.site or list(SITES)
    records = build(keys, args.max_pages, args.crawl_only)
    if args.crawl_only:
        return
    if args.site or args.max_pages:
        print("partial run: not writing the source file", file=sys.stderr)
        return
    records.sort(key=lambda r: r["key"])
    out = REPO_ROOT / "data" / "sources" / f"{SOURCE}.json"
    write_source_json(
        out, source=SOURCE,
        title="FOREST LOOKOUTS -- western US (Ron Kemnow's weebly sites)",
        url="https://ronkemnow.weebly.com/", retrieved=datetime.date.today().isoformat(),
        license_=LICENSE, records=records,
    )
    print(f"wrote {len(records)} records -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
