"""Fetcher for Ron Kemnow's "Canada's Fire Lookouts", canada-lookouts.weebly.com (2026-10-20).

The Canadian sibling of the US "FOREST LOOKOUTS" weebly sites already read by weebly_lookouts.py and
weebly_west.py: same author, same template (a sidebar nav with one header per province and a page per
lookout; the page's own content starts at its first <h2>). Two kinds of page carry lookouts:

  * a **province index** (/british-columbia-index.html, /alberta1.html, /saskatchewan.html,
    /manitoba.html, /northwest-territories.html, /yukon.html, /ontario.html, /quebec.html,
    /new-brunswick.html, /nova-scotia.html, /newfoundland.html): one block per lookout, its name in
    capitals (an <h2> on most pages, a bold paragraph on part of Manitoba's), then the place line the
    author files it under (a BC regional district, an Ontario district or county, a New Brunswick or
    Nova Scotia county, an Alberta forest or national park, a Quebec protective association and its
    division...) and sometimes dated clippings. Many index names have no page of their own (BC: 348
    names, 198 pages).
  * a **lookout page** in the nav: the name, the place line, for some BC pages a "Latitude: 49.383
    Longitude: 120.407 Elevation: 1593" line (longitude written positive-west), for a few others a
    Weebly map widget (`generateMap.php?...long=&lat=`), dated clippings from annual reports and
    newspapers, and sometimes a standalone status word ("Removed").

One record per lookout: the page when there is one (the index block filling the place line it may
lack), else the index block. Facts only (DESIGN.md 2 / 3.2): name, place line, the page's own
coordinates and elevation, a standalone status word, a register link, and dated events read from the
clippings by narrow patterns (a tower erected / built / removed in a year the page gives exactly),
each with a note in our words and the page as its source. The clippings' text is never stored.

Local units. `county` carries only a real local unit the page names: a BC regional district (the
author's pre-2000s names kept as he writes them, "Thompson-Nicola", "Fraser-Cheam"), an Ontario district
or county, a New Brunswick or Nova Scotia county. A forest, district office, park, association or
community the author files a lookout under is a place hint (`extra.place_line`), not a unit. Quebec
names are given their official spelling (Commission de toponymie, read through the CGNDB's GeoNames
service, one cached query per name) when exactly one spelling there folds to the author's accent-free
form; the author's spelling stays in `extra.aliases` (DESIGN.md 3.3).

robots.txt (2026-10-20): `Disallow: /ajax/, /apps/` only. One request every 2.2 s, our User-Agent.
The expansion surveys had already fetched most pages (data/raw/expansion/{bc-yt,prairies-north,qc-atl});
`seed_cache()` copies those files into this source's cache, so only pages no survey read are fetched
(Ontario's index and its 51 pages, 2026-10-20). The index page's "go" buttons point at
canadafirelookouts.weebly.com, a domain taken over by spam: never followed.

Output:  data/sources/canada_lookouts_weebly.json
Re-run:  python3 pipeline/regional/canada_lookouts_weebly.py            (cache only after the first run)
         python3 pipeline/regional/canada_lookouts_weebly.py --crawl-only
"""

from __future__ import annotations

import argparse
import datetime
import html as htmlmod
import json
import pathlib
import re
import shutil
import sys
import unicodedata
import urllib.parse

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _common import RAW_ROOT, FetchError, fetch, fetch_text, slugify, write_source_json  # noqa: E402
import weebly_lookouts as W  # noqa: E402  (same author, same template)

SOURCE = "canada_lookouts_weebly"
HOST = "canada-lookouts.weebly.com"
BASE = f"https://{HOST}"
REPO_ROOT = HERE.parent.parent
OUT = REPO_ROOT / "data" / "sources" / f"{SOURCE}.json"
CACHE = RAW_ROOT / SOURCE / HOST

LICENSE = ("No licence stated; facts only (name, the place the author files the lookout under, the page's own "
           "coordinates and elevation, a standalone status word, dated events read from the clippings, written "
           "in our words, and a link to the page). The site's quotations and narrative are not reproduced.")

# Where the expansion surveys cached the same pages (their file names are the site's own page names).
SURVEY_CACHES = [
    ("expansion/bc-yt/canada_lookouts_weebly/pages", None),
    ("expansion/prairies-north/cw", None),
    ("expansion/qc-atl/cl", None),
]
SURVEY_FILES = {   # whole-file copies whose names differ from the page's
    "expansion/bc-yt/canada_lookouts_weebly/home.html": "index.html",
    "expansion/qc-atl/cl_quebec.html": "quebec.html",
    "expansion/qc-atl/cl_new-brunswick.html": "new-brunswick.html",
    "expansion/qc-atl/cl_nova-scotia.html": "nova-scotia.html",
    "expansion/qc-atl/cl_newfoundland.html": "newfoundland.html",
}


def seed_cache(log=print) -> int:
    """Copy the pages the expansion surveys already fetched into this source's cache (never
    overwriting). Returns how many files were copied."""
    n = 0
    CACHE.mkdir(parents=True, exist_ok=True)
    for rel, _ in SURVEY_CACHES:
        d = RAW_ROOT / rel
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.html")):
            dest = CACHE / p.name
            if not dest.exists():
                shutil.copyfile(p, dest)
                n += 1
    for rel, name in SURVEY_FILES.items():
        p = RAW_ROOT / rel
        dest = CACHE / name
        if p.exists() and not dest.exists():
            shutil.copyfile(p, dest)
            n += 1
    if n:
        log(f"seeded {n} pages from the expansion surveys' caches")
    return n


def get_page(rel: str) -> str:
    """A page of the site by its path ("/agate.html"; "/" is the home page), from the cache or politely
    fetched (robots.txt honoured, 2 s per host by _common; the cache makes re-runs free)."""
    name = "index.html" if rel in ("", "/") else rel.lstrip("/")
    return fetch_text(f"{BASE}/{'' if name == 'index.html' else name}", SOURCE, f"{HOST}/{name}", encoding="utf-8")


# ---------------------------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------------------------

# Nav headers: the province index pages, by their path. ("Alberta1" is the Alberta index.)
PROVINCE_PAGES = {
    "/british-columbia-index.html": "BC", "/alberta1.html": "AB", "/saskatchewan.html": "SK",
    "/manitoba.html": "MB", "/northwest-territories.html": "NT", "/yukon.html": "YT", "/ontario.html": "ON",
    "/quebec.html": "QC", "/new-brunswick.html": "NB", "/nova-scotia.html": "NS", "/newfoundland.html": "NL",
}
# Pages in the nav that are not one lookout.
NOT_LOOKOUT_PAGES = {"/general-in-annual-reports.html", "/misc-unnamed-sites--etc.html"}

NAV_ANCHOR_RE = re.compile(r'<a\s+([^>]*href="[^"]+"[^>]*)>(.*?)</a>', re.S | re.I)
HREF_RE = re.compile(r'href="([^"]+)"')


def norm(text: str) -> str:
    t = htmlmod.unescape(re.sub(r"<[^>]+>", " ", text))
    t = t.replace("​", "").replace("﻿", "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip()


def nav_entries(home_html: str) -> list[dict]:
    """[{"rel": "/agate.html", "text": "Agate", "region": "BC"}, ...]: every lookout page in the sidebar,
    filed under the province header above it. Province index pages are returned with "index": True."""
    body = home_html[home_html.find("<body"):]
    body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
    body = re.sub(r"<style.*?</style>", "", body, flags=re.S)
    out, seen = [], set()
    region = None
    for attrs, raw in NAV_ANCHOR_RE.findall(body):
        m = HREF_RE.search(attrs)
        rel = htmlmod.unescape(m.group(1)) if m else ""
        if rel.startswith(BASE):
            rel = rel[len(BASE):]
        if not rel.startswith("/") or not rel.endswith(".html") or rel in seen:
            continue
        seen.add(rel)
        text = norm(raw)
        if rel in PROVINCE_PAGES:
            region = PROVINCE_PAGES[rel]
            out.append({"rel": rel, "text": text, "region": region, "index": True})
            continue
        if region is None or rel in NOT_LOOKOUT_PAGES or not text:
            continue
        out.append({"rel": rel, "text": text, "region": region, "index": False})
    return out


def crawl(log=print) -> list[dict]:
    """Seed the cache, read the nav, and make sure every index and lookout page is cached."""
    seed_cache(log)
    nav = nav_entries(get_page("/"))
    missing = [e for e in nav if not (CACHE / e["rel"].lstrip("/")).exists()]
    if missing:
        log(f"fetching {len(missing)} pages no survey cached (2.2 s apart)")
    for e in missing:
        try:
            get_page(e["rel"])
        except FetchError as err:
            log(f"  ! {e['rel']}: {err}")
    return nav




# ---------------------------------------------------------------------------------------------
# Reading a page's text
# ---------------------------------------------------------------------------------------------

sys.path.insert(1, str(HERE.parent))  # after regional/, whose _common.py shadows the pipeline's
import ca_units  # noqa: E402
import regions  # noqa: E402

BLOCK_BREAK_RE = re.compile(r"</(?:p|div|h\d|li|tr|td)>|<br\s*/?>|<h\d[^>]*>", re.I)


def content_lines(page_html: str) -> list[str]:
    """The page's own text, one line per block, from the content area to "Powered by" (the
    sidebar nav and the footer left out)."""
    i = page_html.find('id="wsite-content"')
    seg = page_html[page_html.find(">", i) + 1:] if i >= 0 else page_html
    seg = re.sub(r"<script.*?</script>|<style.*?</style>", "", seg, flags=re.S | re.I)
    seg = BLOCK_BREAK_RE.sub("\n", seg)
    seg = htmlmod.unescape(re.sub(r"<[^>]+>", "", seg))
    seg = seg.replace("​", "").replace("﻿", "").replace("\xa0", " ")
    out = []
    for line in seg.split("\n"):
        line = re.sub(r"\s+", " ", line).strip()
        if not line or line == ".":
            continue
        if line.startswith("Powered by"):
            break
        out.append(line)
    return out


# A clipping's date line: "1948:", "May 7, 1931:", "c.1942:", "1930's:", "1957-58:", "FY 1957-58:".
DATE_RE = re.compile(
    r"^(?P<circa>c\.?\s*|circa\s+|ca\.\s*|about\s+)?(?:FY\s*)?"
    r"(?:(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+(?:\d{1,2}(?:st|nd|rd|th)?,?\s+)?)?"
    r"(?:(?P<early>early|mid|late)[- ]+)?(?P<year>1[89]\d\d|20[0-2]\d)(?P<decade>'?s)?(?P<range>\s*[-/]\s*\d{2,4})?\s*[:.]\s*(?P<rest>.*)$",
    re.I)
COORD_LINE_RE = re.compile(
    r"\bLat(?:itude)?\.?:?\s*(?P<lat>\d{2}\.\d+)\s*,?\s*Lon(?:g|gitude)?\.?:?\s*(?P<lon>-?\d{2,3}\.\d+)"
    r"(?:\s*,?\s*Elev(?:ation)?\.?:?\s*(?P<elev>\d{2,4}))?",
    re.I)
# Lines that are page furniture, not place words.
JUNK_LINE_RE = re.compile(r"^(?:link|no link|notes?|station report.*|no latitude.*|click here.*|more information.*)$", re.I)
# The author's own description of the structure, not a place ("Steel tower", "80-foot light steel tower").
DESCRIPTION_RE = re.compile(r"^(?:an?\s+|the\s+)?(?:\d{2,3}[- ]?(?:foot|ft\.?|')\s+)?(?:light\s+|heavy\s+)?"
                            r"(?:steel|wood(?:en)?|timber|pole|log|crow's nest)\b|\batop\b", re.I)
TREE_RE = re.compile(r"\bcrow'?s nest atop\b.*\btree\b|\blookout tree\b|\btree (?:platform|lookout)\b", re.I)
BANNER_RE = re.compile(r"^[A-Z .]+ LOOKOUTS$")
# A photo caption under the heading ("1956 - D.C.H. Clark photo, Alberta ESRD online collection",
# "postcard, n/d - Ron Kemnow Collection"): neither a place nor a clipping.
PHOTO_CREDIT_RE = re.compile(r"\b(?:photo|postcard|collection|postmarked|n/d|no date)\b|^\d{4}(?:-\d)?\s*[-:]", re.I)
LINK_LABEL_RE = re.compile(r"\(\s*link\s*\)\s*$", re.I)
CITATION_RE = re.compile(r"^\(.*\)$|^\($|^\)$|^\+$")
HEIGHT_LINE_RE = re.compile(r"^(?:a\s+|an\s+|the\s+)?(\d{2,3})[- ]?(?:foot|ft\.?|')\b", re.I)
REGION_TITLES = {regions.fold(n) for n in regions.CA_PROVINCES.values()} | {
    "british columbia", "manitoba lookouts", "yukon territory", "northwest territories", "newfoundland",
    "alberta", "quebec", "ontario", "saskatchewan", "new brunswick", "nova scotia"}
INDEX_SKIP_LINES = {"link status", "active not active", "link status active not active", "click here for more information",
                    "link", "misc. sites", "misc sites", "unidentified images", "page undergoing updates", "notes",
                    "bear causes forest fire"}


def is_name_line(line: str, region: str = "") -> bool:
    """A lookout name on an index page: capitals (digits and a few marks allowed), not a link label
    and not a local unit written in capitals ("CBRM")."""
    if LINK_LABEL_RE.search(line) or regions.fold(line).strip(" .") in INDEX_SKIP_LINES:
        return False
    if region and ca_units.named_unit(region, line):
        return False
    core = re.sub(r"\([^)]*\)", "", line).strip()
    core = re.sub(r"\bMa?c(?=[A-Z]{2})", lambda m: m.group(0).upper(), core)   # "McBRIDE PEAK" is capitals too
    letters = [c for c in core if c.isalpha()]
    if len(letters) < 2 or len(core) > 48:
        return False
    if DATE_RE.match(line):
        return False
    return all(not c.islower() for c in core) and re.fullmatch(r"[A-Z0-9 .,'’&/#?!-]+", regions.fold(core).upper()) is not None


def is_alias_line(line: str) -> bool:
    return bool(re.fullmatch(r"\(\s*[^()]+\s*\)", line)) and not LINK_LABEL_RE.search(line)


# ---------------------------------------------------------------------------------------------
# Dated clippings -> events (narrow patterns; our own notes)
# ---------------------------------------------------------------------------------------------

STRUCTURE_RE = re.compile(r"\b(?:tower|lookout|look-out|cupola|lookout structure|lookout building)\b", re.I)
BUILT_RE = re.compile(r"\b(?:erected|erection|built|constructed|construction of|completed)\b", re.I)
REBUILT_RE = re.compile(r"\brebuil(?:t|ding)\b", re.I)
REMOVED_RE = re.compile(r"\b(?:removed|dismantled|torn down|taken down|demolished|pulled (?:over|down)|razed)\b", re.I)
BURNED_RE = re.compile(r"\b(?:burned|burnt|destroyed by fire|blew down|blown over|blown down|collapsed)\b", re.I)
MOVED_RE = re.compile(
    r"\b(?:tower|lookout|structure)s?\b[^.]{0,30}?\b(?:was|were|has been)\s+(?:moved|re-erected|relocated)\b|"
    r"\bmoved\s+(?:the\s+)?(?:[\w'-]+\s+){0,3}?(?:tower|lookout|structure)\b|\b(?:re-erected|relocated)\b|"
    r"\b(?:dismantled|taken down)\s+and\s+moved\b", re.I)
REPLACED_RE = re.compile(r"\breplace(?:d|ment)?\b", re.I)
CLOSED_RE = re.compile(r"\b(?:decommissioned|closed|discontinued)\b", re.I)
ABANDONED_RE = re.compile(r"\babandoned\b", re.I)
# Plans, work in progress, hopes and negations: nothing happened yet (or the year is not the event's).
PLAN_RE = re.compile(
    r"\b(?:planned|plans?|proposed|propose|will|would|to be|future|being|started|starts|hope[sd]?|expected|"
    r"announced|commenced|not|no|per cent|percent|preliminary|hauled|ordered|suggested|might|may|could|"
    r"purchased|material|materials|timber for|under construction|tender|offers?)\b", re.I)
# Something other than the lookout structure, or several lookouts, or a season's opening and closing.
OTHER_THING_RE = re.compile(
    r"\b(?:camps?|cabins?|telephone|road|roads|trail|trails|portage|masts?|pump|garage|residence|quarters|"
    r"house|frame building|log building|buildings|warehouse|bunkhouse|stable|line|lines|antenna|aerial|radio|transmitting|receiving|fence|shed|cache|barn|theat(?:er|re)|"
    r"tramway|ladder|right-of-way|piers?|anchors|guys|rods|wire|door|windows?|roof|stairs|daughter|"
    r"honeymoon|site for|sites|programme|program|several|towers|lookouts|winter|season|painted|"
    r"repaired|repainted|creosoted|examined|investigated)\b", re.I)
# A cab or cupola put on, taken off or replaced: a change to the lookout, not a new one.
PART_RE = re.compile(r"\b(?:cupola|cab)s?\b[^.]{0,40}\b(?:was|were)\s+(?:replaced|removed|constructed|built|installed|"
                     r"rebuilt)\b|\b(?:replacement of|new)\s+(?:the\s+)?(?:tower'?s\s+)?(?:cupola|cab)\b", re.I)
YEAR_IN_TEXT_RE = re.compile(r"\b(1[89]\d\d|20[0-2]\d)\b")
ANAPHORA_RE = re.compile(r"^\W*(?:the|this|our|that)\s+(?:[\w'-]+\s+){0,4}?(?:tower|lookout|look-out|structure)\b", re.I)
GENERIC_NAME_TOKENS = {"lake", "lakes", "mountain", "mount", "mt", "hill", "hills", "river", "creek", "tower", "lookout",
                       "fire", "the", "de", "des", "du", "la", "le", "les", "lac", "riviere", "mont", "point", "ridge",
                       "peak", "upper", "lower", "north", "south", "east", "west", "little", "big", "old", "new"}

EVENT_NOTES = {
    "built": "A lookout structure was built this year.",
    "arrived": "A tower brought from another site was put up here this year.",
    "replaced": "A new lookout structure replaced the old one this year.",
    "rebuilt": "The lookout was rebuilt this year.",
    "modified": "The cab or cupola was built, replaced or taken off this year.",
    "removed": "The tower was taken down this year.",
    "burned": "The structure was lost this year (burned, blown down or collapsed).",
    "relocated": "The tower was moved to another site this year.",
    "closed": "The lookout was closed this year.",
    "abandoned": "The lookout was abandoned this year.",
}


def name_tokens_of(names: list[str]) -> set[str]:
    """The distinctive words of a lookout's names ("Lac des Perles" -> {"perles"})."""
    out = set()
    for n in names:
        for t in re.findall(r"[a-z]+", regions.fold(n or "")):
            if len(t) >= 4 and t not in GENERIC_NAME_TOKENS:
                out.add(t)
    return out


def names_it(text: str, tokens: set[str]) -> bool:
    words = set(re.findall(r"[a-z]+", regions.fold(text)))
    return bool(words & tokens)


def classify_sentence(s: str, year: int, quoted: bool, tokens: set[str]) -> str | None:
    """One event the sentence states about this lookout's structure that year, or None (nothing,
    several things, plans, another object, another lookout, another year)."""
    if not STRUCTURE_RE.search(s) or PLAN_RE.search(s):
        return None
    if any(int(y) != year for y in YEAR_IN_TEXT_RE.findall(s)):
        return None                      # "was built in 1954", told in 1956: the header is not the event's year
    if quoted and not (names_it(s, tokens) or ANAPHORA_RE.match(s)):
        return None                      # a report's sentence that may be about another lookout
    if PART_RE.search(s):
        return None if OTHER_THING_RE.search(re.sub(r"\b(?:cupola|cab)s?\b", "", s)) else "modified"
    if OTHER_THING_RE.search(s):
        return None
    moved, removed, rebuilt = MOVED_RE.search(s), REMOVED_RE.search(s), REBUILT_RE.search(s)
    if removed and rebuilt and not moved and not re.search(r"\brebuilt\b[^.]*\bat\b", s):
        return "rebuilt"                 # "razed by the fire ... has been rebuilt"
    if moved or (removed and rebuilt):
        # Which way did the structure go? "moved from", "rebuilt at this site", a destination ("to ...",
        # "near ...", "re-erected at ...") that names this lookout: it arrived here. Otherwise it left.
        verb = moved or rebuilt
        after = s[verb.start():]
        dest = re.search(r"\b(?:to|near)\b(.*)$", after) or re.search(r"\b(?:re-erected|rebuilt)\b[^.]*?\bat\b(.*)$", after)
        if re.search(r"\bmoved from\b|\b(?:rebuilt|re-erected)\b[^.]*\bat this site\b", s, re.I) or (
                dest and names_it(dest.group(1), tokens)):
            return "arrived"
        return "relocated"
    found = set()
    if removed:
        found.add("removed")
    if BURNED_RE.search(s):
        found.add("burned")
    if rebuilt:
        found.add("rebuilt")
    if REPLACED_RE.search(s):
        other = (re.search(r"\breplace(?:d)?\s+(?:the\s+)?(?:old\s+)?((?:[A-Z][\w'.]*\s+){1,3})(?:saw\s*mill\s+)?(?:tower|lookout)", s)
                 or re.search(r"\breplace(?:ment)?\s+(?:for\s+)?(?:the\s+)?(?:old\s+)?(?:lookout|tower)\s+(?:on|at)\s+((?:[A-Z][\w'.]*\s*){1,3})", s))
        if (other and not names_it(other.group(1), tokens)) or re.search(
                r"\b(?:situated|located)\b[^.]*\b(?:miles?|km|kilometres?)\b", s):
            found.add("built")           # a new lookout here took over from another site's
        elif re.search(r"\breplaced by\b[^.]*\bat\s+[A-Z]", s):
            return None                  # its replacement went up somewhere else
        else:
            found.add("replaced")
    if not quoted and CLOSED_RE.search(s):
        found.add("closed")
    if not quoted and ABANDONED_RE.search(s):
        found.add("abandoned")
    if BUILT_RE.search(s):
        found.add("built")
    if found == {"replaced", "built"}:
        return "replaced"                # "a 100-foot tower was erected to replace the old one"
    if found == {"burned", "replaced"} or found == {"removed", "replaced"}:
        return "replaced"                # "wrecked by a storm and replaced with a new tower"
    return found.pop() if len(found) == 1 else None


def clip_events(lines: list[str], page_url: str, names: list[str]) -> list[dict]:
    """Events from the dated clippings: a date line with an exact year (no "c.", no decade, no
    range), then the text up to the next date line. Each sentence that states one event about the
    lookout's structure gives that event; a year whose sentences disagree gives nothing. A sentence
    quoted from a report or a newspaper counts only when it names the lookout (or says "the
    tower"); "closed" and "abandoned" only in the author's own words."""
    tokens = name_tokens_of(names)
    out: list[dict] = []
    i = 0
    while i < len(lines):
        m = DATE_RE.match(lines[i])
        if not m:
            i += 1
            continue
        exact = not (m.group("circa") or m.group("decade") or m.group("range") or m.group("early"))
        year = int(m.group("year"))
        body = [m.group("rest")] if m.group("rest") else []
        j = i + 1
        while j < len(lines) and not DATE_RE.match(lines[j]):
            if not CITATION_RE.match(lines[j]):
                body.append(lines[j])
            j += 1
        i = j
        if not exact or not body:
            continue
        text = " ".join(body)
        quoted = text.lstrip().startswith(("\"", "“", "'", "+"))
        kinds = {k for sent in re.split(r"(?<=[.!?\"”])\s+|\s\+\s", text)
                 if (k := classify_sentence(sent, year, quoted, tokens))}
        if kinds == {"removed", "relocated"}:
            kinds = {"relocated"}
        if len(kinds) == 1:
            out.append({"year": year, "event": kinds.pop()})
    # the first structure built is "built"; a later one "replaced" (DESIGN.md 3.7's convention)
    seen_built = False
    events: list[dict] = []
    have = set()
    for e in sorted(out, key=lambda e: e["year"]):
        ev, note = e["event"], EVENT_NOTES[e["event"]]
        if ev in ("built", "arrived"):
            ev = "replaced" if seen_built else "built"
            seen_built = True
        elif ev in ("replaced", "rebuilt"):
            seen_built = True
        if (ev, e["year"]) in have:
            continue
        have.add((ev, e["year"]))
        events.append({"year": e["year"], "event": ev, "note": note + " (Dated on Canada's Fire Lookouts.)",
                       "from": SOURCE, "source_url": page_url})
    return events


# ---------------------------------------------------------------------------------------------
# Names, place lines
# ---------------------------------------------------------------------------------------------

# A parenthetical after a name that tells two towers apart stays in the name; one that is another
# name for the lookout becomes an alias; "(secondary)" is a note.
KEEP_QUALIFIER_RE = re.compile(r"^(?:upper|lower|north|south|east|west|old|new|#?\s*\d+|no\.?\s*\d+|i+|first|second)$", re.I)
AKA_RE = re.compile(r"^(?:aka|a\.k\.a\.?|also known as|also)\s+", re.I)


SMALL_WORDS = {"au": "au", "aux": "aux", "de": "de", "des": "des", "du": "du", "la": "la", "le": "le", "les": "les",
               "en": "en", "sur": "sur", "of": "of", "on": "on", "at": "at", "to": "to", "by": "by", "in": "in",
               "and": "and", "go": "Go", "st": "St.", "mt": "Mt."}


def tidy_name(text: str) -> str:
    """The author's capitals in ordinary case ("McBRIDE PEAK" -> "McBride Peak", "LAC LA GARDE" ->
    "Lac la Garde"); codes such as "BM 229" and "MM 20" stay as they are."""
    t = re.sub(r"\s+", " ", text).strip(" .,;:")
    t = re.sub(r"\b(Ma?c)([A-Z]{2,})\b", lambda m: m.group(1) + m.group(2)[0] + m.group(2)[1:].lower(), t)
    t = W.unshout(t)
    words = t.split(" ")
    for i, w in enumerate(words):
        if i == 0 or not re.fullmatch(r"[A-Z]{2,3}\.?", w) or (i + 1 < len(words) and re.match(r"\d", words[i + 1])):
            continue
        low = w.rstrip(".").lower()
        if low in SMALL_WORDS:
            words[i] = SMALL_WORDS[low]
    t = " ".join(words)
    t = re.sub(r"\bMt\b(?!\.)", "Mt.", t)
    return t


def split_name(raw: str, alias_lines: list[str]) -> tuple[str, list[str], dict]:
    """(name, aliases, notes) from an index or page heading and the parenthetical lines under it."""
    aliases: list[str] = []
    notes: dict = {}
    m = re.match(r"^(?P<base>[^()]+?)\s*\((?P<par>[^()]+)\)\s*(?P<tail>.*)$", raw.strip())
    base, pars = (raw.strip(), []) if not m else (m.group("base") + (" " + m.group("tail") if m.group("tail") else ""), [m.group("par")])
    pars += [re.sub(r"^\(|\)$", "", a).strip() for a in alias_lines]
    keep = []
    for p in pars:
        p = p.strip()
        if not p:
            continue
        if re.fullmatch(r"secondary", p, re.I):
            notes["secondary"] = True
        elif KEEP_QUALIFIER_RE.match(p):
            keep.append(p.title())
        elif re.fullmatch(r"\?+", p):
            notes["name_doubt"] = True
        else:
            for part in re.split(r"\s+or\s+|\s*/\s*|\s*,\s*", AKA_RE.sub("", p)):
                if part.strip():
                    aliases.append(tidy_name(part))
    base = base.strip()
    if base.endswith("?"):
        notes["name_doubt"] = True
        base = base.rstrip(" ?")
    name = tidy_name(base) + "".join(f" ({q})" for q in keep)
    return name, [a for a in dict.fromkeys(aliases) if a and a != name], notes


def place_parts(region: str, lines: list[str]) -> tuple[str | None, list[str]]:
    """(the local unit the lines name, the other place words), from the lines between a lookout's
    name and its first clipping. A line "Pembrooke District - Algonquin Park" is split on its dash;
    a BC district written "Thompson - Nicola" is kept whole."""
    unit, places = None, []
    for line in lines:
        if unit is None and ca_units.named_unit(region, line):
            unit = ca_units.named_unit(region, line)
            continue
        parts = [p.strip() for p in re.split(r"\s+[-–]\s+", line) if p.strip()]
        for p in parts:
            if unit is None and ca_units.named_unit(region, p):
                unit = ca_units.named_unit(region, p)
            elif p not in places:
                places.append(p)
    return unit, places


def head_lines(lines: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Split the lines after a lookout's name: (parenthetical alias lines, place lines, the rest:
    coordinates, descriptions, dated clippings). Place lines are the short undated lines before the
    first clipping, coordinate line or description."""
    aliases, places = [], []
    i = 0
    while i < len(lines) and is_alias_line(lines[i]):
        aliases.append(lines[i])
        i += 1
    while i < len(lines) and len(places) < 4:
        line = lines[i]
        if JUNK_LINE_RE.match(line.strip(" .,")) or not re.search(r"[A-Za-z]", line):
            i += 1
            continue
        if (DATE_RE.match(line) or COORD_LINE_RE.search(line) or line.startswith(("\"", "“", "("))
                or HEIGHT_LINE_RE.match(line) or len(line) > 70 or re.search(r"[.!?]$", line)
                or DESCRIPTION_RE.search(line) or PHOTO_CREDIT_RE.search(line)
                or regions.fold(line).startswith(("notes", "a secondary", "an eighty", "misc"))
                or W.STATUS_EXACT.get(line.strip().lower().rstrip("."))):
            break
        places.append(line)
        i += 1
    return aliases, places, lines[i:]


def status_of(lines: list[str]) -> tuple[str, str | None]:
    for line in lines:
        k = line.strip().lower().rstrip(".")
        if k in W.STATUS_EXACT:
            return W.STATUS_EXACT[k]
    return "unknown", None


def height_of(lines: list[str]) -> int | None:
    """A tower height from the author's own description lines ("80-foot light steel tower with a
    square cab"), only when there is exactly one such line before any clipping."""
    hs = []
    for line in lines:
        if DATE_RE.match(line):
            break
        m = HEIGHT_LINE_RE.match(line)
        if m and re.search(r"\btower\b", line, re.I):
            hs.append(int(m.group(1)))
    return hs[0] if len(hs) == 1 else None


def name_key(name: str) -> str:
    """How an index heading is paired with a page heading: folded, without lookout words."""
    toks = re.findall(r"[a-z0-9]+", regions.fold(re.sub(r"\([^)]*\)", " ", name)))
    toks = [{"mt": "mount", "mtn": "mountain", "lk": "lake", "hgts": "heights", "pt": "point"}.get(t, t) for t in toks]
    toks = [t for t in toks if t not in {"tower", "lookout", "fire", "the", "station"}]
    return "".join(toks)


def similar_keys(a: str, b: str) -> bool:
    """Two name keys the author would use for one lookout: a one-letter slip in a long name, or one
    name the other plus a feature word ("Bodmin" / "Bodmin Hill")."""
    if not a or not b or a == b:
        return a == b and bool(a)
    import difflib
    short, long_ = sorted((a, b), key=len)
    if len(short) >= 5 and long_.startswith(short) and re.fullmatch(
            r"(?:lake|lakes|hill|hills|mountain|mountains|creek|ridge|peak|forest|house|sawmill|park|river)",
            long_[len(short):]):
        return True
    return len(short) >= 6 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.85


# ---------------------------------------------------------------------------------------------
# Index pages and lookout pages
# ---------------------------------------------------------------------------------------------

def index_entries(region: str, page_html: str) -> list[dict]:
    """The lookout blocks of a province index: [{"name", "aliases", "notes", "unit", "places",
    "lines", "href_slug"}] in page order."""
    lines = content_lines(page_html)
    # the "go" buttons link each block to its page on the old domain: /<slug>.html
    slugs = [pathlib.PurePosixPath(urllib.parse.urlparse(h).path).stem
             for h in re.findall(r"href=['\"](https?://canadafirelookouts\.weebly\.com/[^'\"]+\.html)['\"]", page_html)]
    blocks: list[tuple[str, list[str]]] = []
    for line in lines:
        if is_name_line(line, region) and not is_alias_line(line):
            if regions.fold(line).strip(" .") in REGION_TITLES:
                blocks.append(("", []))
                continue
            blocks.append((line, []))
        elif blocks:
            if LINK_LABEL_RE.search(line):
                continue
            blocks[-1][1].append(line)
    out = []
    for name, body in blocks:
        if not name:
            continue
        al, places, rest = head_lines(body)
        nm, aliases, notes = split_name(name, al)
        unit, other = place_parts(region, places)
        out.append({"name": nm, "aliases": aliases, "notes": notes, "unit": unit, "places": other,
                    "lines": rest, "all_lines": body})
    # pair the go-button slugs with the blocks that have them, in order (BC's index: one per block)
    if slugs and len(slugs) == len(out):
        for e, s in zip(out, slugs):
            e["href_slug"] = s
    return out


def page_record(region: str, rel: str, page_html: str) -> dict | None:
    """A lookout page's facts, or None when the page carries no lookout heading."""
    lines = content_lines(page_html)
    if not lines:
        return None
    # the first line is the province banner ("BRITISH COLUMBIA LOOKOUTS") on some pages
    while lines and (regions.fold(lines[0]).replace(" lookouts", "").strip() in REGION_TITLES
                     or BANNER_RE.match(lines[0])):
        lines = lines[1:]
    if not lines:
        return None
    nm, aliases, notes = split_name(lines[0], [])
    al, places, rest = head_lines(lines[1:])
    nm2, aliases2, notes2 = split_name(lines[0], al)
    unit, other = place_parts(region, places)
    lat = lon = elev = None
    for line in lines[1:12]:
        m = COORD_LINE_RE.search(line)
        if m:
            lat, lon = float(m.group("lat")), float(m.group("lon"))
            lon = -abs(lon)           # the author writes west longitudes as positive numbers
            elev = int(m.group("elev")) if m.group("elev") else None
            break
    if lat is None:
        m = W.IFRAME_COORD_RE.search(page_html)
        if m:
            lat, lon = float(m.group(2)), float(m.group(1))
    tree = any(TREE_RE.search(x) for x in lines[1:6])
    regs = [{"label": "National Historic Lookout Register" if "nhlr" in h else "Former Fire Lookout Sites Register",
             "url": href, "kind": "register"} for href, h, _ in W.REGISTER_LINK_RE.findall(page_html)]
    return {"name": nm2, "aliases": aliases2, "notes": {**notes, **notes2}, "unit": unit, "places": other,
            "lines": rest, "lat": lat, "lon": lon, "elevation_m": elev, "register_links": regs, "tree": tree}


# ---------------------------------------------------------------------------------------------
# Quebec: official spellings (Commission de toponymie, through the CGNDB's GeoNames service)
# ---------------------------------------------------------------------------------------------

GEONAMES_API = "https://geogratis.gc.ca/services/geoname/en/geonames.json"


def spelling_key(name: str) -> str:
    """A name with accents, case, hyphens, apostrophes and spaces dropped: "Rivière-à-Mars" and
    "Riviere a Mars" are one name."""
    return re.sub(r"[^a-z0-9]+", "", regions.fold(name))


def official_qc_name(name: str) -> str | None:
    """The official spelling of a Quebec name, when the CGNDB has exactly one official spelling that
    is the author's name with its accents (and hyphens) put back; else None. One cached query per name."""
    q = urllib.parse.quote(name)
    url = f"{GEONAMES_API}?q={q}&province=24&num=200"
    try:
        body = fetch(url, SOURCE, f"cgndb/{slugify(name)}.json")
    except FetchError:
        return None
    try:
        items = json.loads(body.decode("utf-8", "replace")).get("items") or []
    except (ValueError, AttributeError):
        return None
    key = spelling_key(name)
    hits = {it.get("name") for it in items if isinstance(it, dict) and it.get("name")
            and spelling_key(it["name"]) == key and str((it.get("status") or {}).get("code") or "official") == "official"}
    return hits.pop() if len(hits) == 1 else None


# ---------------------------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------------------------

# Page positions the expansion surveys found wrong; never used, never "fixed" (DESIGN.md 3.2).
FLAGGED_POSITIONS = {
    # 55.606, -121.431: Mount Bickford is at 55.618, -122.422, 62 km west, near Chetwynd; the
    # longitude looks mistyped (BC/Yukon survey, 2026-10-20).
    "/bickford.html": "The page's longitude looks mistyped: Mount Bickford is 62 km west of it.",
    # 49.554, -118.519 is Bluejoint's position (BC/Yukon survey): a copied pin.
    "/blueberry.html": "The page repeats Bluejoint's position, not this lookout's.",
}


def province_index_url(region: str) -> str:
    rel = next(r for r, code in PROVINCE_PAGES.items() if code == region)
    return f"{BASE}{rel}"


def record_from(region: str, page: dict | None, entry: dict | None, rel: str | None, key: str,
                nav_text: str | None) -> dict:
    url = f"{BASE}{rel}" if rel else province_index_url(region)
    name = (page or entry)["name"]
    aliases = list(dict.fromkeys((page or {}).get("aliases", []) + (entry or {}).get("aliases", [])))
    if entry and page and name_key(entry["name"]) != name_key(page["name"]) and entry["name"] not in aliases:
        aliases.append(entry["name"])
    if nav_text and name_key(nav_text) != name_key(name):
        alt = tidy_name(re.sub(r"[.,]+$", "", nav_text))
        if alt not in aliases and name_key(alt) != name_key(name):
            aliases.append(alt)
    aliases = [a for a in aliases if a != name]
    unit = (page or {}).get("unit") or (entry or {}).get("unit")
    places = list(dict.fromkeys((page or {}).get("places", []) + (entry or {}).get("places", [])))
    lines_page = (page or {}).get("lines", [])
    lines_index = (entry or {}).get("lines", [])
    names = [name] + aliases
    events = clip_events(lines_page, url, names) if page else []
    if entry:
        have = {(e["event"], e["year"]) for e in events}
        events += [e for e in clip_events(lines_index, province_index_url(region), names) if (e["event"], e["year"]) not in have]
        events.sort(key=lambda e: (e["year"], e["event"]))
    status, status_raw = status_of(lines_page)
    if status == "unknown" and entry:
        status, status_raw = status_of(lines_index)
    # a status word written into the place line ("Quetico Provincial Park - Standing, used as a repeater
    # station", "Cut down"): taken as the status, not as a place
    for p in list(places):
        k = regions.fold(p).strip(" .")
        word = "Standing" if k.startswith("standing") else "Cut down" if k == "cut down" else "Abandoned" if k == "abandoned" else None
        if word:
            places.remove(p)
            if word != "Abandoned" and status == "unknown":
                status_raw, status = word, {"Standing": "standing", "Cut down": "gone"}[word]
    lat, lon = (page or {}).get("lat"), (page or {}).get("lon")
    extra: dict = {}
    if lat is not None and rel in FLAGGED_POSITIONS:
        extra["position_note"] = FLAGGED_POSITIONS[rel]
        lat = lon = None
    if lat is not None and not regions.in_region_box(region, lat, lon):
        extra["position_note"] = f"The page's position ({lat}, {lon}) lies outside {regions.region_name(region)}."
        lat = lon = None
    if aliases:
        extra["aliases"] = aliases
    if places:
        extra["place_line"] = " - ".join(places)
    notes = {**(entry or {}).get("notes", {}), **(page or {}).get("notes", {})}
    if notes.get("secondary"):
        extra["secondary"] = True        # the author marks it a secondary tower
    if notes.get("name_doubt"):
        extra["name_doubt"] = True       # the author puts a question mark by the name
    h = height_of(lines_page) or height_of(lines_index)
    if h:
        extra["height_ft"] = h
    if page and entry is None:
        extra["index_entry"] = False
    if page is None:
        extra["page"] = False            # named on the province index only
    built = min((e["year"] for e in events if e["event"] == "built"), default=None)
    links = [{"label": f"Canada's Fire Lookouts (Ron Kemnow): {name}", "url": url, "kind": "site"}]
    links += (page or {}).get("register_links", [])
    return {
        "key": key, "url": url, "name": name, "country": "CA", "region": region, "county": unit,
        "lat": round(lat, 5) if lat is not None else None, "lon": round(lon, 5) if lon is not None else None,
        "elevation_m": float((page or {}).get("elevation_m")) if (page or {}).get("elevation_m") else None,
        "type_raw": None, "kind": "tree" if (page or {}).get("tree") else "unknown", "status_raw": status_raw, "status": status, "registers": [],
        "built": built, "agency": None, "events": events, "photos": [], "links": links, "rental": None,
        "extra": extra,
    }


def build(nav: list[dict], log=print) -> list[dict]:
    records: list[dict] = []
    by_region: dict[str, list[dict]] = {}
    for e in nav:
        by_region.setdefault(e["region"], []).append(e)
    for region, entries in sorted(by_region.items()):
        idx_nav = next((e for e in entries if e["index"]), None)
        index = index_entries(region, get_page(idx_nav["rel"])) if idx_nav else []
        pages = []
        for e in entries:
            if e["index"]:
                continue
            p = page_record(region, e["rel"], get_page(e["rel"]))
            if p is None:
                log(f"  {region} {e['rel']}: no lookout heading; skipped")
                continue
            pages.append((e, p))
        paired: dict[int, int] = {}          # page position -> index position
        used: set[int] = set()
        stems = {pathlib.PurePosixPath(e["rel"]).stem: n for n, (e, _) in enumerate(pages)}
        for i, ent in enumerate(index):
            n = stems.get(ent.get("href_slug") or "")
            if n is not None and n not in paired:
                paired[n] = i
                used.add(i)
        for n, (e, p) in enumerate(pages):
            if n in paired:
                continue
            for k in (name_key(p["name"]), name_key(e["text"])):
                hit = next((i for i, ent in enumerate(index) if i not in used and name_key(ent["name"]) == k), None)
                if hit is not None:
                    paired[n] = hit
                    used.add(hit)
                    break
        # the author's own variants of one name ("Doucet" / "Doucette", "Bodmin" / "Bodmin Hill",
        # "Crevice" / "Crevise"): a unique close match among the blocks still unpaired
        for n, (e, p) in enumerate(pages):
            if n in paired:
                continue
            k = name_key(p["name"])
            close = [i for i, ent in enumerate(index) if i not in used and similar_keys(k, name_key(ent["name"]))]
            if len(close) == 1:
                paired[n] = close[0]
                used.add(close[0])
        for n, (e, p) in enumerate(pages):
            ent = index[paired[n]] if n in paired else None
            key = f"{SOURCE}:{region.lower()}:{slugify(pathlib.PurePosixPath(e['rel']).stem)}"
            records.append(record_from(region, p, ent, e["rel"], key, e["text"]))
        count: dict[str, int] = {}
        for i, ent in enumerate(index):
            if i in used:
                continue
            slug = "index-" + slugify(ent["name"])
            count[slug] = count.get(slug, 0) + 1
            key = f"{SOURCE}:{region.lower()}:{slug}" + (f"-{count[slug]}" if count[slug] > 1 else "")
            records.append(record_from(region, None, ent, None, key, None))
        log(f"  {region}: {len(pages)} pages, {len(index)} index names, {len(paired)} paired")
    seen = set()
    for r in records:
        assert r["key"] not in seen, r["key"]
        seen.add(r["key"])
        if r["region"] == "QC":
            off = official_qc_name(r["name"])
            if off and off != r["name"]:
                r["extra"].setdefault("aliases", [])
                if r["name"] not in r["extra"]["aliases"]:
                    r["extra"]["aliases"].insert(0, r["name"])     # the author's spelling, kept for search
                r["extra"]["name_from"] = "cgndb_official_spelling"
                r["name"] = off
    return sorted(records, key=lambda r: r["key"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--crawl-only", action="store_true", help="fill the cache, write nothing")
    args = ap.parse_args(argv)
    import _common
    _common.MIN_INTERVAL_S = 2.2
    nav = crawl(lambda *a: print(*a, file=sys.stderr))
    if args.crawl_only:
        return 0
    records = build(nav, lambda *a: print(*a, file=sys.stderr))
    newest = max(p.stat().st_mtime for p in CACHE.glob("*.html"))
    write_source_json(OUT, source=SOURCE, title="Canada's Fire Lookouts (Ron Kemnow), canada-lookouts.weebly.com",
                      url=f"{BASE}/", retrieved=datetime.date.fromtimestamp(newest).isoformat(),
                      license_=LICENSE, records=records,
                      header_extra={"credit": "Canada's Fire Lookouts, by Ron Kemnow (canada-lookouts.weebly.com)"})
    from collections import Counter
    print(f"wrote {len(records)} records -> {OUT}", file=sys.stderr)
    print(f"  by region: {dict(sorted(Counter(r['region'] for r in records).items()))}", file=sys.stderr)
    print(f"  with a position: {sum(1 for r in records if r['lat'] is not None)}; with a unit: "
          f"{sum(1 for r in records if r['county'])}; events: {sum(len(r['events']) for r in records)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
