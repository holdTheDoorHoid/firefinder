"""Fetcher for the "FOREST LOOKOUTS" weebly sites: easternuslookouts.weebly.com
and centraluslookouts.weebly.com (same unknown author, same template, split by
region). Together they are the single highest-leverage candidate for the FFLA
gap states (DESIGN.md Sec 2 / docs/sources-candidates.md Tier 1): one page per
tower, covering AL, CT, FL, GA, KY, MA, MI, MS, NJ, NC, PA, SC, TN (eastern
site) and AR, LA, MO, OK (central site). Each site also covers several states
already handled elsewhere (DE, IN, ME, MD, NH, NY, OH, RI, VT, VA on the
eastern site; IL, IA, KS, MN, TX, WI on the central site) -- STATES below
restricts each site to the gap states this project cares about; pass
--states to widen it.

Site structure (reconnaissance, 2026-10-04)
--------------------------------------------
Every page on a site carries the SAME sidebar dropdown nav: one header per
state (its own page, e.g. "/louisiana.html") followed by every tower page in
that state, in order. A state occasionally has its header repeated partway
through the list (Georgia, Delaware) or split into alphabetical sub-pages
(Pennsylvania: A-F / G-P / R-Z) -- both cases still segment correctly here,
since every repeated header just re-confirms the same state code. This nav is
fetched ONCE (home page) to build the full tower-url list per state; no need
to visit each state's own index page.

Each tower's own content starts at the page's first <h2> (the nav itself has
no headings, only <a> links, so this cleanly separates nav from content).
From there the template is a free-text, per-entry-inconsistent "timeline":
  NAME
  (qualifier)                      -- optional: a nearby place/alt name
  <State> - <County> County - <Agency>   -- formats vary; see parse_location()
  <date>:  "<quoted or paraphrased excerpt>"  (<citation>)   -- 0+ of these
  <standalone status word>          -- optional: "Removed", "Standing", ...
  National Geodetic Survey ... DESIGNATION / PID / STATE-COUNTY / STATION
    DESCRIPTION ...                 -- optional: present when the tower (or
                                        its site) is also an NGS/NOAA survey
                                        mark; public-domain US government
                                        text, used here only to pull height_ft
                                        and a design hint, never copied whole
  [National Historic Lookout Register] / [Former Fire Lookout Sites Register]
    -- optional button linking to nhlr.org / firetower.org
  [Satellite View]                  -- optional button (hillmap.com)

Coordinates are NOT in that text: when the page author placed a map, it is a
Weebly "generateMap.php" iframe widget with `long=`/`lat=` in its own src
query string. Only about half the towers surveyed have one -- DESIGN.md Sec
3.2's rule applies: no iframe means lat/lon null and the location text (the
county/agency line, and any nearby-place qualifier) goes in extra.location_text,
not a guess.

The per-entry text is each written by hand over ~15 years with no fixed
schema, mixing direct newspaper quotes with the author's own paraphrase. Per
DESIGN.md Sec 2/3.2 (facts only, no copied prose) this fetcher never stores
that narrative text. It pulls out structured facts only:
  - name, optional place qualifier
  - county/parish (regex against the location line)
  - agency, best-effort (trailing dash-segment of the same line, or the next
    line if it is clearly not a date/quote/button/status/survey-grid-code)
  - status: an exact standalone status line ("Removed") is trusted outright;
    a small, deliberately narrow set of unambiguous multi-word phrases
    ("torn down", "no longer stands", ...) is also matched anywhere in the
    page's own text as a fallback, but single ambiguous words like "moved" or
    "abandoned" are NOT auto-matched (DESIGN.md: unknown is null, never a
    guess) -- most entries have no detectable status and stay "unknown"
  - height_ft / design, pulled from a handful of fixed phrasings (NGS
    descriptions and "N-foot ... tower" mentions)
  - a link to the NHLR/FFLOS register page when the page has that button
    (kind "register"; no register NUMBER is parsed from it, since the button
    only carries nhlr.org's internal page id, not the printed register
    number -- DESIGN.md: never guess a register number)
  - photos: every page repeats several decorative site-chrome images
    (buttons, divider graphics) with no distinguishing filename; these are
    filtered out by cross-page frequency (an image seen on more than
    PHOTO_DECORATION_THRESHOLD different tower pages on the same site is
    chrome, not a tower photo) rather than a hardcoded list, so the filter
    keeps working if the site's chrome images change.

Output:
  data/sources/eastern_us_lookouts.json
  data/sources/central_us_lookouts.json

Re-run:
  python3 pipeline/regional/weebly_lookouts.py                      # both sites
  python3 pipeline/regional/weebly_lookouts.py --site eastern       # one host
  python3 pipeline/regional/weebly_lookouts.py --states PA,NJ       # subset
  python3 pipeline/regional/weebly_lookouts.py --max-per-state 5    # smoke test

The on-disk cache (data/raw/<source>/) makes every run resumable: a page
already fetched is never re-requested. Eastern covers ~1,330 tower pages and
central ~460; at the mandated 2 s/host this is roughly 45 and 15 minutes
respectively -- run with run_in_background, or as two separate --site
invocations (different hosts rate-limit independently).
"""

from __future__ import annotations

import argparse
import datetime
import html as htmlmod
import pathlib
import re
import sys
from collections import Counter
from html import unescape as html_unescape

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import FetchError, fetch_text, ft_to_m, slugify, write_source_json  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

# Every state header that can appear in either site's nav (not just the gap
# states), so segmentation boundaries are correct even though we only keep
# the gap states below. Parenthetical suffixes ("(A-F)") are stripped before
# this lookup, so Pennsylvania's three alphabetical sub-headers all land here.
STATE_FULL = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARKANSAS": "AR", "CONNECTICUT": "CT", "DELAWARE": "DE",
    "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI", "ILLINOIS": "IL", "INDIANA": "IN",
    "IOWA": "IA", "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME",
    "MARYLAND": "MD", "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN",
    "MISSISSIPPI": "MS", "MISSOURI": "MO", "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ",
    "NEW YORK": "NY", "NORTH CAROLINA": "NC", "OHIO": "OH", "OKLAHOMA": "OK",
    "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX", "VERMONT": "VT",
    "VIRGINIA": "VA", "WEST VIRGINIA": "WV", "WISCONSIN": "WI",
}

SITES = {
    "eastern": {
        "source": "eastern_us_lookouts",
        "host": "easternuslookouts.weebly.com",
        "nav_path": "/",
        "nav_cache": "index.html",
        "title": 'FOREST LOOKOUTS -- eastern US (easternuslookouts.weebly.com)',
        "states": ["AL", "CT", "DE", "FL", "GA", "IN", "KY", "MA", "MD", "ME", "MI", "MS", "NC",
                   "NH", "NJ", "NY", "OH", "PA", "RI", "SC", "TN", "VA", "VT", "WV"],
    },
    "central": {
        "source": "central_us_lookouts",
        "host": "centraluslookouts.weebly.com",
        "nav_path": "/",
        "nav_cache": "index.html",
        "title": 'FOREST LOOKOUTS -- central US (centraluslookouts.weebly.com)',
        "states": ["AR", "IA", "IL", "KS", "LA", "MN", "MO", "OK", "TX", "WI"],
    },
}

# Tower pages per site seen on more than this many pages are site chrome
# (buttons, divider graphics), not a photo of that specific tower. This
# catches the images that every page embeds by reference to the SAME
# uploaded resource id. It does NOT catch a handful of named badge/icon
# graphics ("lighthouse blue line" divider, a CCC-built badge, a "removed"
# headstone icon, a wings/shield logo) that Weebly re-uploads as a fresh
# resource id each time they're reused, so each copy's filename is unique
# and survives frequency filtering -- those are excluded by name instead,
# via DECORATIVE_IMAGE_RE (found by checking every image across the full
# eastern/central crawl, 2026-10-04: "headstone_NNN" appears on removed-
# status pages only -- a decorative "gone" badge, not a tower photo). Across
# that full crawl (1,779 pages) every embedded image was one of these kinds;
# no genuine tower photo was found on either site.
PHOTO_DECORATION_THRESHOLD = 2
DECORATIVE_IMAGE_RE = re.compile(
    r"lighthouse-blue-line|go-button|aws-logo|nophoto|ccc-logo|headstone|\d{8}wings", re.I
)
BORING_ALTS = {"picture", "image", "photo", ""}

# The sites' sidebar nav is hand-edited and has three kinds of slip, all found by comparing each
# header's towers with the towers' own pages (2026-10-08, links-survey):
#   - a "continuation" header carries the wrong state name: easternuslookouts.weebly.com's
#     /georgia1.html ("Georgia") lists 30 more *Indiana* towers (Borden ... Winamac) and
#     /delaware1.html ("Delaware") lists 178 more *Michigan* towers (Demond Hill ... Yates), and
#     centraluslookouts.weebly.com's /texas1.html ("Texas") lists 27 more *Missouri* towers
#     (Thomasville ... Wolf Mountain). Taken at face value the first put Indiana towers in Georgia
#     and the others dropped every one of those Michigan and Missouri towers.
#   - a state marker that is not a link to a state page at all: "WEST VIRGINIA >" and "MICHIGAN. >"
#     sit inside the Virginia and Michigan runs, with trailing arrow/period text.
#   - a state with no marker (nothing in this nav).
# HEADER_SLUG_STATE overrides a header by its link target; marker text is normalised before the
# lookup; and parse_detail() reads the state the page itself declares ("West Virginia - Cabell
# County - ...") and prefers it to the run a page was listed in.
HEADER_SLUG_STATE = {"/georgia1.html": "IN", "/delaware1.html": "MI", "/texas1.html": "MO"}
# Virginia's list resumes after the West Virginia run with no marker at all; its first tower page
# there is "Brushy Mountain." (/brushy-mountain2.html), so a run starts at that page.
RUN_START_STATE = {"/brushy-mountain2.html": "VA"}

NAV_LINK_RE = re.compile(r'<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")
# Catches "Misc. Notes", "Misc. Notes - Virginia", "Misc. History of
# Pennsylvania Lookouts", "General & Misc" -- none of these are a tower.
NOTES_PAGE_RE = re.compile(r"\bmisc\b", re.I)

H2_RE = re.compile(r"<h2[^>]*>", re.I)
TEXT_NODE_RE = re.compile(r">([^<>]{1,600})<")
IMG_RE = re.compile(r'<img[^>]*\ssrc="([^"]*uploads[^"]*)"[^>]*>', re.I)
ALT_RE = re.compile(r'\salt="([^"]*)"', re.I)
IFRAME_COORD_RE = re.compile(r"[?&]long=(-?\d+\.?\d*)&lat=(-?\d+\.?\d*)")
REGISTER_LINK_RE = re.compile(
    r'<a\s+[^>]*href="(https?://(?:www\.)?(nhlr\.org|firetower\.org)[^"]*)"[^>]*>\s*<span[^>]*>([^<]*)</span>',
    re.I | re.S,
)
SATELLITE_LINK_RE = re.compile(r'<a\s+[^>]*href="(https?://(?:www\.)?hillmap\.com[^"]*)"', re.I)

COUNTY_RE = re.compile(r"([A-Z][A-Za-z.'’ ]*?)\s+(Count(?:y|ies)|Parish)\b")
GRID_CODE_RE = re.compile(r"^\d{1,2}\s*[NS]\s*-?\s*\d{1,2}\s*[EW]\s*-?\s*[\d/]+$", re.I)
SEE_ALSO_RE = re.compile(r"^see:?$", re.I)
# Placeholder text the page authors themselves use for "we don't know" --
# never a real agency, so filtering this out beats leaking it into the data.
BORING_AGENCY = {"no information", "none", "unknown", "n/a", "not known", "information not available", "see:"}
DATE_LINE_RE = re.compile(
    r"^(?:<?\d{4}(?:\s*-\s*\d{2,4})?'?s?|[A-Za-z]+\.?\s+\d{1,2},?\s+\d{4}|"
    r"mid-?\d{4}'?s?|FY\s*\d{4}(?:-\d{2,4})?)\s*:?\s*$",
    re.I,
)
QUOTE_START_RE = re.compile(r'^[\s]*"')
NONAGENCY_BUTTONS = {
    "national geodetic survey", "national historic lookout register",
    "former fire lookout sites register", "satellite view",
}

# Standalone-line status words (the node's full text, trimmed and lowered,
# must equal one of these exactly -- this is a dedicated template field in
# the page, not a sentence, so an exact match is trustworthy).
STATUS_EXACT: dict[str, tuple[str, str]] = {
    "removed": ("gone", "Removed"),
    "destroyed": ("gone", "Destroyed"),
    "burned": ("gone", "Burned"),
    "burnt": ("gone", "Burnt"),
    "demolished": ("gone", "Demolished"),
    "dismantled": ("gone", "Dismantled"),
    "collapsed": ("ruins", "Collapsed"),
    "ruins": ("ruins", "Ruins"),
    "relocated": ("relocated", "Relocated"),
    "replica": ("replica", "Replica"),
    "standing": ("standing", "Standing"),
    "still standing": ("standing", "Still standing"),
    "active": ("standing", "Active"),
}
# Free-text fallback: deliberately narrow, multi-word, low-ambiguity phrases
# only -- a bare "removed"/"burned"/"moved"/"abandoned" anywhere in a quoted
# newspaper excerpt is too likely to be about something else to trust.
STATUS_KEYWORDS: list[tuple[re.Pattern, tuple[str, str]]] = [
    (re.compile(r"\btorn down\b", re.I), ("gone", "torn down")),
    (re.compile(r"\btaken down\b", re.I), ("gone", "taken down")),
    (re.compile(r"\bdismantled\b", re.I), ("gone", "dismantled")),
    (re.compile(r"\bdemolished\b", re.I), ("gone", "demolished")),
    (re.compile(r"\brazed\b", re.I), ("gone", "razed")),
    (re.compile(r"\bburned down\b", re.I), ("gone", "burned down")),
    (re.compile(r"\bburnt down\b", re.I), ("gone", "burnt down")),
    (re.compile(r"\bno longer stands\b", re.I), ("gone", "no longer stands")),
    (re.compile(r"\bcollapsed\b", re.I), ("ruins", "collapsed")),
    (re.compile(r"\bstill stands\b", re.I), ("standing", "still stands")),
    (re.compile(r"\bcurrently stands\b", re.I), ("standing", "currently stands")),
    (re.compile(r"\bstill standing\b", re.I), ("standing", "still standing")),
]

HEIGHT_RES = [
    re.compile(r"(\d{2,3})[-\s]foot\b", re.I),
    re.compile(r"overall height of (\d{2,3}) feet", re.I),
    re.compile(r"(\d{2,3})\s*feet in height", re.I),
    re.compile(r"(\d{2,3})\s*feet tall", re.I),
    re.compile(r"about (\d{2,3}) feet high", re.I),
]
DESIGN_RE = re.compile(r"\b(Aermotor|L-4|L-5|L-6|R-6|D-6)\b")
TREE_SUFFIX_RE = re.compile(r"\(\s*tree\s*\)", re.I)


def clean(s: str | None) -> str | None:
    if s is None:
        return None
    s = htmlmod.unescape(s).replace("​", "").replace("﻿", "")
    s = re.sub(r"\s+", " ", s).strip(" –-")
    return s or None


def header_text_key(text: str) -> str:
    """The state name in a nav header's text, upper-cased: drops a "(A-F)" suffix, the arrow
    ("WEST VIRGINIA &gt;") and full stop ("MICHIGAN.") some markers carry, and runs of space."""
    t = html_unescape(text)
    t = re.sub(r"\s*\([^)]*\)\s*$", "", t)
    t = re.sub(r"[>\s.]+$", "", t.strip())
    return re.sub(r"\s+", " ", t).strip().upper()


_KEEP_UPPER = {"CCC", "USFS", "BLM", "NPS", "AFC", "WMA", "FAA", "USGS", "NGS", "NWR", "AWS", "ELO", "GFC",
               "USMC", "WPA", "TVA", "NF", "FS", "ROTC", "HQ"}


def unshout(name: str) -> str:
    """The sites print most names in capitals ("MCNAB", "ALBERT RUSSELL", "WILDERNESS (Lampe)"):
    title-case every all-capital word of three letters or more (Mc- names keep their second capital),
    leave abbreviations and roman numerals, and leave mixed-case names alone."""
    def fix(m: re.Match) -> str:
        w = m.group(0)
        if w in _KEEP_UPPER or re.fullmatch(r"[IVX]+", w):
            return w
        t = w[:1] + w[1:].lower()
        t = re.sub(r"^(Mc)([a-z])", lambda x: x.group(1) + x.group(2).upper(), t)
        return re.sub(r"^([OD]['\u2019])([a-z])", lambda x: x.group(1) + x.group(2).upper(), t)

    name = re.sub(r"\b(MT|ST|FT|NO|MTN|PK)\.", lambda m: m.group(1)[0] + m.group(1)[1:].lower() + ".", name)
    return re.sub(r"\b[A-Z][A-Z'\u2019]{2,}\b", fix, name)


def nav_segments(html: str, target_states: set[str]) -> dict[str, list[tuple[str, str]]]:
    """state code -> ordered [(relative_url, raw_link_text), ...], restricted
    to target_states. Segmentation uses the FULL state list (STATE_FULL) so a
    header for a state we're not keeping still correctly ends the previous
    state's run of links; only the returned dict is filtered."""
    body = html[html.find("<body") :]
    body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
    body = re.sub(r"<style.*?</style>", "", body, flags=re.S)
    cur: str | None = None
    out: dict[str, list[tuple[str, str]]] = {s: [] for s in target_states}
    for rel_url, raw_text in NAV_LINK_RE.findall(body):
        text = TAG_RE.sub("", raw_text).strip()
        if rel_url in HEADER_SLUG_STATE:
            cur = HEADER_SLUG_STATE[rel_url]
            continue
        header_key = header_text_key(text)
        if header_key in STATE_FULL:
            cur = STATE_FULL[header_key]
            continue
        cur = RUN_START_STATE.get(rel_url, cur)
        if cur is None or cur not in out:
            continue
        if NOTES_PAGE_RE.search(text):
            continue
        if not rel_url.endswith(".html") or rel_url.startswith("http"):
            continue
        out[cur].append((rel_url, text))
    return out


def own_content_text_nodes(html: str) -> list[str]:
    """Text nodes from the page's first <h2> (the tower's own content;
    everything before it is the shared sidebar nav) to the end, with scripts
    and styles stripped first so their text never leaks in."""
    m = H2_RE.search(html)
    if not m:
        return []
    tail = html[m.start() :]
    tail = re.sub(r"<script.*?</script>", "", tail, flags=re.S)
    tail = re.sub(r"<style.*?</style>", "", tail, flags=re.S)
    nodes = [clean(t) for t in TEXT_NODE_RE.findall(tail)]
    return [n for n in nodes if n]


def parse_location(nodes: list[str]) -> dict:
    """Walk the first few content nodes after the name for an optional
    "(qualifier)" or bare nearest-town line, then the county/parish line,
    pulling a best-effort agency out of the same or next line.

    Some entries are just a cross-reference stub: name, county, then "See:"
    and the name of the tower's real page under another name (e.g. "Bald
    Hill" -> "See: Mount Ochepituck"). These aren't a lookout of their own;
    out["see_also"] flags them so the caller can skip writing a record."""
    out = {"qualifier": None, "nearest_town": None, "county": None, "agency_raw": None, "see_also": False}
    i = 1
    n = len(nodes)
    # Optional "(qualifier)" right after the name.
    if i < n and re.fullmatch(r"\(.+\)", nodes[i] or ""):
        out["qualifier"] = nodes[i].strip("()").strip()
        i += 1
    # Optional bare nearest-town line (short, all caps, no digits) before the
    # county line, e.g. CT's "EAST HADDAM" ahead of "Middlesex County".
    if i < n and not COUNTY_RE.search(nodes[i]) and re.fullmatch(r"[A-Z][A-Z .'\-]{1,40}", nodes[i]):
        out["nearest_town"] = nodes[i].title()
        i += 1
    for j in range(i, min(i + 4, n)):
        m = COUNTY_RE.search(nodes[j])
        if not m:
            continue
        out["county"] = clean(m.group(1))
        trailing = nodes[j][m.end() :]
        for seg in re.split(r"\s*-\s*", trailing):
            seg = clean(seg)
            if seg and not GRID_CODE_RE.match(seg) and seg.lower() not in BORING_AGENCY:
                out["agency_raw"] = seg
                break
        if j + 1 < n and SEE_ALSO_RE.match(nodes[j + 1].strip()):
            out["see_also"] = True
        elif out["agency_raw"] is None and j + 1 < n:
            nxt = nodes[j + 1]
            low = nxt.strip().lower()
            if (
                not DATE_LINE_RE.match(nxt)
                and not QUOTE_START_RE.match(nxt)
                and low not in NONAGENCY_BUTTONS
                and low not in STATUS_EXACT
                and low not in BORING_AGENCY
                and not GRID_CODE_RE.match(nxt)
                and len(nxt) <= 80
                and re.search(r"[A-Za-z]", nxt)
            ):
                out["agency_raw"] = nxt
        break
    return out


_DECLARED_STATE_RE = re.compile(r"^([A-Za-z]+(?: [A-Za-z]+)?)\s*[-\u2013]\s")


def declared_state(nodes: list[str]) -> str | None:
    """The state a page names for itself in its location line ("West Virginia - Cabell County -
    ..."), as a two-letter code, or None (most pages open with just the county)."""
    for node in nodes[1:5]:
        m = _DECLARED_STATE_RE.match(node or "")
        if m and m.group(1).upper() in STATE_FULL:
            return STATE_FULL[m.group(1).upper()]
    return None


def parse_status(nodes: list[str], full_text: str) -> tuple[str, str | None]:
    for node in nodes:
        key = node.strip().lower()
        if key in STATUS_EXACT:
            return STATUS_EXACT[key]
    for pattern, (status, raw) in STATUS_KEYWORDS:
        if pattern.search(full_text):
            return status, raw
    return "unknown", None


def parse_height_and_design(full_text: str) -> tuple[int | None, str | None]:
    height_ft = None
    for pat in HEIGHT_RES:
        m = pat.search(full_text)
        if m:
            height_ft = int(m.group(1))
            break
    design_m = DESIGN_RE.search(full_text)
    design = design_m.group(1) if design_m else None
    return height_ft, design


def parse_detail(html: str) -> dict:
    nodes = own_content_text_nodes(html)
    if not nodes:
        return {"name": None}
    name = unshout(nodes[0])
    loc = parse_location(nodes)
    full_name = name if not loc["qualifier"] else unshout(f"{name} ({loc['qualifier']})")

    tail = html[H2_RE.search(html).start() :]
    tail_no_script = re.sub(r"<script.*?</script>", "", tail, flags=re.S)
    tail_no_script = re.sub(r"<style.*?</style>", "", tail_no_script, flags=re.S)
    full_text = " ".join(nodes)

    status, status_raw = parse_status(nodes, full_text)
    height_ft, design = parse_height_and_design(full_text)

    coord_m = IFRAME_COORD_RE.search(html)
    lat = float(coord_m.group(2)) if coord_m else None
    lon = float(coord_m.group(1)) if coord_m else None

    links = []
    for href, host, label in REGISTER_LINK_RE.findall(tail_no_script):
        reg_label = "National Historic Lookout Register" if "nhlr" in host else "Former Fire Lookout Sites Register"
        links.append({"label": reg_label, "url": href, "kind": "register"})
    sat_m = SATELLITE_LINK_RE.search(tail_no_script)
    if sat_m:
        links.append({"label": "Satellite view (hillmap.com)", "url": sat_m.group(1), "kind": "site"})

    photos = []
    for m in IMG_RE.finditer(tail_no_script):
        src = m.group(1)
        if DECORATIVE_IMAGE_RE.search(src):
            continue
        alt_m = ALT_RE.search(m.group(0))
        alt = clean(alt_m.group(1)) if alt_m else None
        photos.append({"src": src, "alt": alt})

    kind = "tree" if TREE_SUFFIX_RE.search(name) else "tower"

    return {
        "name": full_name,
        "declared_state": declared_state(nodes),
        "see_also": loc["see_also"],
        "nearest_town": loc["nearest_town"],
        "county": loc["county"],
        "agency_raw": loc["agency_raw"],
        "lat": lat,
        "lon": lon,
        "status": status,
        "status_raw": status_raw,
        "height_ft": height_ft,
        "design": design,
        "kind": kind,
        "links": links,
        "photos": photos,
        "location_text": ", ".join(
            x for x in [loc["nearest_town"], loc["county"] and f"{loc['county']} County/Parish", loc["agency_raw"]] if x
        ) or None,
    }


def agency_to_ownership(agency_raw: str | None) -> str:
    if not agency_raw:
        return "unknown"
    low = agency_raw.lower()
    if "national forest" in low or "national park" in low or "arsenal" in low or "blm" in low:
        return "federal"
    if "state" in low or "forestry commission" in low or "conservation commission" in low or "bureau of forestry" in low:
        return "state"
    if "tribal" in low or "reservation" in low:
        return "tribal"
    return "unknown"


def build_site(site_key: str, states_filter: set[str] | None, max_per_state: int | None) -> tuple[dict, dict]:
    cfg = SITES[site_key]
    source = cfg["source"]
    base = f"https://{cfg['host']}"
    retrieved = datetime.date.today().isoformat()

    target_states = set(cfg["states"])
    if states_filter:
        target_states &= states_filter
    if not target_states:
        return {"source": source, "title": cfg["title"], "url": base + "/", "retrieved": retrieved,
                "license": "No licence stated; facts only.", "records": []}, {}

    nav_html = fetch_text(f"{base}{cfg['nav_path']}", source, cfg["nav_cache"])
    segments = nav_segments(nav_html, target_states)

    no_coord_count = 0
    total = 0
    # Pass 1: fetch + parse every detail page, deferring photo assignment
    # until we know each image's cross-page frequency on this site.
    parsed: list[dict] = []
    image_freq: Counter[str] = Counter()
    for region in cfg["states"]:
        if region not in target_states:
            continue
        entries = segments.get(region, [])
        if max_per_state is not None:
            entries = entries[:max_per_state]
        print(f"== {source} {region}: {len(entries)} pages ==", file=sys.stderr)
        for rel_url, raw_text in entries:
            total += 1
            url = f"{base}{rel_url}"
            cache_rel = rel_url.lstrip("/")
            try:
                html = fetch_text(url, source, cache_rel)
            except FetchError as e:
                print(f"  ! {region} {raw_text!r} ({url}): {e}", file=sys.stderr)
                continue
            d = parse_detail(html)
            if not d.get("name"):
                print(f"  ! {region} {raw_text!r} ({url}): no content found, skipping", file=sys.stderr)
                continue
            if d.get("see_also"):
                print(f"  - {region} {raw_text!r} ({url}): cross-reference stub (\"See:\"), skipping", file=sys.stderr)
                continue
            d["region"] = d.get("declared_state") or region
            if d["region"] != region:
                print(f"  ~ {region} {raw_text!r}: the page says {d['region']}, using that", file=sys.stderr)
            d["url"] = url
            d["url_slug"] = slugify(pathlib.Path(rel_url).stem)
            if d["lat"] is None:
                no_coord_count += 1
            for p in d["photos"]:
                image_freq[p["src"]] += 1
            parsed.append(d)

    records = []
    for d in parsed:
        photos = []
        for p in d["photos"]:
            if image_freq[p["src"]] > PHOTO_DECORATION_THRESHOLD:
                continue  # site-wide chrome (button/divider), not this tower's photo
            caption = p["alt"] if p["alt"] and p["alt"].lower() not in BORING_ALTS else None
            photos.append({
                "url": f"{base}{p['src']}" if p["src"].startswith("/") else p["src"],
                "credit": cfg["host"],
                "caption": caption,
                "year": None,
            })

        key = f"{source}:{d['region'].lower()}:{d['url_slug']}"
        extra = {}
        if d["lat"] is None:
            extra["location_text"] = d["location_text"]
        if d["height_ft"]:
            extra["height_ft"] = d["height_ft"]
        if d["design"]:
            extra["design"] = d["design"]
        ownership = agency_to_ownership(d["agency_raw"])
        if ownership != "unknown":
            extra["ownership"] = ownership
        if d["nearest_town"]:
            extra["nearest_town"] = d["nearest_town"]

        rec = {
            "key": key,
            "url": d["url"],
            "name": d["name"],
            "country": "US",
            "region": d["region"],
            "county": d["county"],
            "lat": round(d["lat"], 5) if d["lat"] is not None else None,
            "lon": round(d["lon"], 5) if d["lon"] is not None else None,
            "elevation_m": None,
            "type_raw": None,
            "kind": d["kind"],
            "status_raw": d["status_raw"],
            "status": d["status"],
            "registers": [],
            "built": None,
            "agency": d["agency_raw"],
            "events": [],
            "photos": photos,
            "links": [{"label": cfg["title"].split(" (")[0], "url": d["url"]}] + d["links"],
            "rental": None,
            "extra": extra,
        }
        records.append(rec)

    print(f"{source}: {len(records)} records, {no_coord_count} with no coordinates "
          f"(of {total} pages attempted)", file=sys.stderr)

    payload = {
        "source": source,
        "title": cfg["title"],
        "url": base + "/",
        "retrieved": retrieved,
        "license": (
            "No licence stated; facts only (county, coordinates where the page's own map "
            "widget gives them, status, height, design hints, register links). The site's "
            "own historical quotes, newspaper citations and narrative are not reproduced."
        ),
        "records": records,
    }
    stats = {"total": total, "no_coord": no_coord_count, "records": len(records)}
    return payload, stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", choices=["eastern", "central"], default=None,
                     help="limit to one site's host (default: both)")
    ap.add_argument("--states", default=None,
                     help="comma-separated state codes to limit to (default: all gap states for the site)")
    ap.add_argument("--max-per-state", type=int, default=None,
                     help="cap tower pages fetched per state (smoke testing)")
    args = ap.parse_args()
    states_filter = set(s.strip().upper() for s in args.states.split(",")) if args.states else None
    sites = [args.site] if args.site else list(SITES)

    for site_key in sites:
        payload, stats = build_site(site_key, states_filter, args.max_per_state)
        out_path = REPO_ROOT / "data" / "sources" / f"{SITES[site_key]['source']}.json"
        write_source_json(
            out_path,
            source=payload["source"], title=payload["title"], url=payload["url"],
            retrieved=payload["retrieved"], license_=payload["license"], records=payload["records"],
        )
        print(f"wrote {len(payload['records'])} records -> {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
