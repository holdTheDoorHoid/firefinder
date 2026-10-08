#!/usr/bin/env python3
"""Fetch and parse the Forest Fire Lookout Association (firelookout.org) registry.

Writes data/sources/ffla.json (see DESIGN.md section 3.2 for the record shape).
Resumable: every page fetched is cached under
/home/hoid/Desktop/firefinder/data/raw/ffla/ (or $FIREFINDER_RAW_ROOT/ffla/) and a re-run
reads from that cache instead of refetching.

FFLA publishes several list views of one state: the alphabetical list at /lookouts/us/<st>/
(the "primary" view, which names the record keys) and "Other sort" pages linked from it:
<st>-co (by county), <st>-st (standing only), <st>-rg (by region), plus the odd extra such as
ca-un (undocumented sites). Every view is crawled, and a row seen in more than one view is
ONE record (same key), enriched from the later views (the county, mainly); a row only a
secondary view lists becomes a record of its own, with extra.views saying where it was seen.

Usage:
    python3 pipeline/fetch_ffla.py             # read the cache, fetch only what is missing
    python3 pipeline/fetch_ffla.py --refresh   # refetch everything (2 s apart): the index,
                                               # sitemap, every state page and view, every -add page
"""
from __future__ import annotations

import argparse
import difflib
import html as html_mod
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RateLimiter, RobotsCache, STATE_ABBR, fetch, slugify, write_log  # noqa: E402
from state_bbox import flag_coordinate  # noqa: E402

SOURCE = "ffla"
BASE = "https://firelookout.org"
INDEX_URL = f"{BASE}/lookouts/us/"

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "sources" / "ffla.json"
# Logs/reports are crawl artifacts, not deliverables -- keep them in the shared,
# git-ignored raw-cache tree rather than inside the committed worktree.
from common import RAW_ROOT  # noqa: E402

LOG_PATH = RAW_ROOT / "_logs" / "fetch_ffla.log"
REPORT_PATH = RAW_ROOT / "_logs" / "fetch_ffla_report.json"

TAG_RE = re.compile(r"<[^>]+>")
A_HREF_RE = re.compile(r'<a\s+[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.S | re.I)


def strip_tags(s: str) -> str:
    s = TAG_RE.sub(" ", s)
    s = html_mod.unescape(s)
    s = s.replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def log(msg: str) -> None:
    print(msg, flush=True)
    write_log(LOG_PATH, msg)


# ---------------------------------------------------------------------------
# Index page: which states have a master table, an "-add" page, NHLR/FFLOS links
# ---------------------------------------------------------------------------

def parse_index(html: str) -> list[dict]:
    idx = html.find("<table")
    end = html.find("</table>", idx) + len("</table>")
    table = html[idx:end]
    rows = re.findall(r"<tr>(.*?)</tr>", table, re.S)
    out = []
    for r in rows[1:]:  # skip header row
        tds = re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)
        if len(tds) < 3:
            continue
        name_cell = tds[0]
        m = A_HREF_RE.search(name_cell)
        table_url = None
        if m:
            table_url = m.group(1)
            if table_url.startswith("/"):
                table_url = BASE + table_url
            if table_url.startswith("http://"):
                table_url = "https://" + table_url[len("http://"):]
        state_name = strip_tags(name_cell)
        total = strip_tags(tds[1]) or None
        standing = strip_tags(tds[2]) or None
        add_url = None
        for extra_cell in tds[3:]:
            m2 = A_HREF_RE.search(extra_cell)
            if m2 and "add" in m2.group(1):
                add_url = m2.group(1)
                if add_url.startswith("http://"):
                    add_url = "https://" + add_url[len("http://"):]
        abbr = STATE_ABBR.get(state_name)
        if not abbr:
            log(f"WARN: unrecognized state name in index: {state_name!r}")
            continue
        out.append(
            {
                "state": state_name,
                "abbr": abbr,
                "table_url": table_url,
                "add_url": add_url,
                "total": total,
                "standing": standing,
            }
        )
    return out


# ---------------------------------------------------------------------------
# State table page -> source records
# ---------------------------------------------------------------------------

HEADER_SYNONYMS = {
    "name": "name",
    "tower name": "name",
    "lookout name": "name",
    "county": "county",
    "lat": "lat",
    "latitude": "lat",
    "long": "lon",
    "lon": "lon",
    "longitude": "lon",
    "type": "type",
    "status": "status",
    "nhlr/fflos": "register",
    "nhlr / fflos": "register",
    "nhlr": "register",
    "fflos": "register",
    "register": "register",
    "elevation": "elevation",
    "elev": "elevation",
    # the undocumented-sites list (ca-un) also has these
    "notes": "notes",
    "sec/twp/rng": "sec_twp_rng",
    "agency": "agency",
}

REGISTER_CELL_RE = re.compile(
    r"(NHLR|FFLOS)\s+(US\s*#?\s*\d+)\s*,?\s*([A-Za-z]{2}\s*#?\s*\d+)?", re.I
)

KIND_MAP = {
    "tower": "tower",
    "ground": "ground",
    "2-story cab": "two_story",
    "2 story cab": "two_story",
    "2-storycab": "two_story",
    "two-story cab": "two_story",
    "3-story cab": "three_story",
    "3 story cab": "three_story",
    "3-storycab": "three_story",
    "three-story cab": "three_story",
    "encl. tower": "enclosed_tower",
    "enclosed tower": "enclosed_tower",
    "platform": "platform",
    "tree": "tree",
    "tree platform": "tree",
    "camp": "camp",
    "beacon tower": "tower",
    "unknown": "unknown",
    # confident additional variants seen across state tables (DESIGN: "do not assume
    # every state uses identical columns" -- these are still clearly one of the vocab
    # kinds once the qualifier is read off)
    "enclosed tower": "enclosed_tower",
    "open tower": "tower",
    "obs tower": "tower",
    "obs. tower": "tower",
    "observation tower": "tower",
    "stone tower": "tower",
    "stone obs tower": "tower",
    "radio tower": "tower",
    "windmill tower": "tower",
    "clock tower": "tower",
    "security tower": "tower",
    "rooftop tower": "tower",
    "non-fire tower": "tower",
    "log tower": "tower",
    "aws tower": "tower",
    "wooden tower": "tower",
    "tower (unk)": "tower",
    "tower?": "tower",
    "tower/ground": "tower",
    "tower/ground*": "tower",
    "crowsnest": "platform",
    "crows nest": "platform",
    "platform tower": "platform",
    "platforms": "platform",
    "platfrom": "platform",  # typo seen on source pages
    "tree cab": "tree",
    "tree platform": "tree",
    "3-story stone": "three_story",
    "2-story": "two_story",
    "3-story": "three_story",
    "stone hut": "ground",
}

# DESIGN vocab status is {standing, gone, relocated, ruins, replica, unknown}. Several
# state tables fold a status *and* a year into one cell (e.g. "Burned 2026"); that year
# is pulled out into an `events` entry by extract_status_year() below rather than lost.
STATUS_MAP = {
    "standing": "standing",
    "gone": "gone",
    "abandoned": "gone",
    "removed": "gone",
    "burned": "gone",
    "relocated": "relocated",
    "replica": "replica",
    "ruins": "ruins",
    "standing (ruins)": "ruins",
    "unknown": "unknown",
    "new": "standing",
}

STATUS_YEAR_RE = re.compile(r"^(standing|gone|new|removed|burned)\s+(\d{4})$", re.I)
# "New 2026" on a lookout with an older build date means a new structure on the site, so it is a rebuild, not the first build.
STATUS_YEAR_EVENT = {"new": "rebuilt", "removed": "removed", "burned": "burned"}


def map_kind(raw: str, stats: Counter) -> str:
    key = raw.strip().lower().rstrip("*").strip()
    stats[raw.strip()] += 1
    return KIND_MAP.get(key, "unknown")


def map_status(raw: str, stats: Counter) -> tuple[str, bool, dict | None]:
    stats[raw.strip()] += 1
    key = raw.strip().lower().rstrip("*").strip()
    has_star = key == "standing" and "*" in raw  # the FFLA "Standing*" legend specifically
    event = None
    ym = STATUS_YEAR_RE.match(key)
    if ym:
        word, year = ym.group(1).lower(), int(ym.group(2))
        base_status = STATUS_MAP.get(word, "unknown")
        ev_name = STATUS_YEAR_EVENT.get(word)
        if ev_name:
            event = {
                "year": year,
                "event": ev_name,
                "note": f"From FFLA status column value {raw.strip()!r}",
                "from": "ffla",
            }
        return base_status, False, event
    return STATUS_MAP.get(key, "unknown"), has_star, None


def parse_register_cell(cell_html: str) -> tuple[list[dict], list[dict]]:
    """Returns (registers, links) parsed from a NHLR/FFLOS register table cell."""
    text = strip_tags(cell_html)
    if not text or text in ("&nbsp;",):
        return [], []
    registers = []
    links = []
    m = REGISTER_CELL_RE.search(text)
    if m:
        register, us_num, st_num = m.groups()
        registers.append(
            {
                "register": register.upper(),
                "number": re.sub(r"\s+", " ", us_num.replace("#", "")).strip(),
                "state_number": (
                    re.sub(r"\s+", " ", st_num.replace("#", "")).strip() if st_num else None
                ),
            }
        )
    href_m = A_HREF_RE.search(cell_html)
    if href_m:
        url = href_m.group(1)
        if url.startswith("http://"):
            # keep as-is: nhlr.org/firetower.org HTTPS resets in this environment,
            # but the canonical public URL is worth recording as given by the source
            pass
        label = "NHLR register entry" if registers and registers[0]["register"] == "NHLR" else "FFLOS register entry"
        links.append({"label": label, "url": url, "kind": "register"})
    return registers, links


def parse_header(row_html: str) -> dict | None:
    cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)
    if not cells:
        return None
    texts = [strip_tags(c).lower().rstrip("*").strip() for c in cells]
    mapping = {}
    unmapped = []
    for i, t in enumerate(texts):
        mapped = HEADER_SYNONYMS.get(t)
        if mapped:
            mapping[mapped] = i
        elif t:
            unmapped.append(t)
    if "name" not in mapping:
        return None
    # Some state pages (e.g. VA) leave the register column header blank. If the last
    # column has no header text and nothing else claimed the "register" slot, assume
    # it holds the NHLR/FFLOS cell per the site-wide table convention.
    if "register" not in mapping and len(texts) >= 2 and not texts[-1]:
        mapping["register"] = len(texts) - 1
    return {"mapping": mapping, "unmapped": unmapped, "ncols": len(cells)}


def parse_state_table(
    html: str, abbr: str, url: str, kind_stats: Counter, status_stats: Counter, coord_stats: Counter,
    groups: bool = False,
) -> list[dict]:
    """The rows of a list view as source records. With `groups` (the by-region view), a heading
    that is followed straight away by another heading names the region: extra.group."""
    records = []
    seen_keys: dict[str, int] = {}
    tables = re.findall(r"<table[^>]*>.*?</table>", html, re.S)
    for table in tables:
        rows = re.findall(r"<tr>(.*?)</tr>", table, re.S)
        section = None
        group = None  # the by-region view puts a region heading above the section heading
        prev_was_heading = False
        header = None
        for row in rows:
            cells_raw = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            # A heading is a row of one cell, or a bold first cell with every other cell blank
            # (NH's standing list pads its "Non-Wildland Lookouts" heading out to the full width).
            texts = [strip_tags(c) for c in cells_raw]
            lone = len(cells_raw) == 1 or (cells_raw and texts[0] and "<strong>" in cells_raw[0]
                                           and not any(texts[1:]))
            if lone:
                txt = texts[0]
                if "<strong>" in cells_raw[0] or txt:
                    if txt and txt.lower() not in ("name", ""):
                        if groups and prev_was_heading:
                            group = section  # two headings in a row: the first one names a group
                        section = txt
                        # The column header is NOT reset: a section may follow its heading with
                        # rows straight away (the "Relocated / Replica Lookouts" at the foot of
                        # OR's, WV's ... list has no header row of its own) and then uses the
                        # layout of the table above.
                        prev_was_heading = True
                        continue
            maybe_header = parse_header(row)
            if maybe_header is not None:
                header = maybe_header
                prev_was_heading = False
                continue
            if header is None:
                continue  # data row before any header seen; skip defensively
            mapping = header["mapping"]
            if "name" not in mapping or len(cells_raw) < 2:
                continue

            def cell(field):
                i = mapping.get(field)
                if i is None or i >= len(cells_raw):
                    return ""
                return cells_raw[i]

            name = strip_tags(cell("name"))
            if not name:
                continue
            if len(texts) > 1 and not any(texts[i] for i in range(len(texts)) if i != mapping["name"]) \
                    and (len(name.split()) >= 8 or name.endswith(".")):
                continue   # a sentence of the page's own text in a row (UT's and WY's list notes)
            county = strip_tags(cell("county")) or None
            lat_raw = strip_tags(cell("lat"))
            lon_raw = strip_tags(cell("lon"))
            type_raw = strip_tags(cell("type")) or None
            status_raw = strip_tags(cell("status")) or None
            register_cell_html = cell("register")

            lat = lon = None
            coord_problem = None
            if not lat_raw or not lon_raw:
                coord_stats["missing"] += 1
            else:
                try:
                    lat = round(float(lat_raw), 5)
                    lon = round(float(lon_raw), 5)
                except ValueError:
                    coord_stats["invalid"] += 1
                    lat = lon = None
                else:
                    problem = flag_coordinate(abbr, lat, lon)
                    if problem:
                        coord_stats[problem] += 1
                        coord_problem = problem
                    else:
                        coord_stats["ok"] += 1

            kind = map_kind(type_raw, kind_stats) if type_raw else "unknown"
            status, has_star, status_event = ("unknown", False, None)
            if status_raw:
                status, has_star, status_event = map_status(status_raw, status_stats)

            registers, links = ([], [])
            if register_cell_html:
                registers, links = parse_register_cell(register_cell_html)

            slug = slugify(name)
            lat_key = f"{lat:.4f}" if lat is not None else "null"
            lon_key = f"{lon:.4f}" if lon is not None else "null"
            base_key = f"ffla:{abbr.lower()}:{slug}:{lat_key}:{lon_key}"
            key = base_key
            if key in seen_keys:
                seen_keys[key] += 1
                key = f"{base_key}:{seen_keys[base_key] if base_key in seen_keys else 1}"
                # ensure true uniqueness even on repeated collisions
                while key in seen_keys:
                    seen_keys[base_key] += 1
                    key = f"{base_key}:{seen_keys[base_key]}"
            seen_keys.setdefault(base_key, 0)
            seen_keys[key] = 0

            extra = {"section": section}
            if has_star:
                extra["standing_asterisk"] = True
                extra["standing_asterisk_note"] = (
                    "FFLA legend (firelookout.org/lookouts/): 'Standing*' = retains tower "
                    "structure/support even though the cab is no longer in place."
                )
            if group:
                extra["group"] = group
            for field_, key_ in (("notes", "notes"), ("sec_twp_rng", "sec_twp_rng"), ("agency", "agency_raw")):
                val = strip_tags(cell(field_))
                if val and val.lower() not in ("xx-xx-xx",):
                    extra[key_] = val
            if coord_problem:
                extra["coordinate_problem"] = coord_problem
            if header["unmapped"]:
                extra["unmapped_columns"] = header["unmapped"]

            rec = {
                "key": key,
                "url": url,
                "name": name,
                "country": "US",
                "region": abbr,
                "county": county,
                "lat": lat,
                "lon": lon,
                "elevation_m": None,
                "type_raw": type_raw,
                "kind": kind,
                "status_raw": status_raw,
                "status": status,
                "registers": registers,
                "built": None,
                "agency": None,
                "events": [status_event] if status_event else [],
                "photos": [],
                "links": links,
                "rental": None,
                "extra": extra,
            }
            records.append(rec)
    return records


# ---------------------------------------------------------------------------
# "-add" additional information pages
# ---------------------------------------------------------------------------

def parse_add_page(html: str, state_name: str) -> dict:
    idx = html.find('class="entry-content"')
    if idx == -1:
        return {"links": [], "text_present": False}
    start = html.find(">", idx) + 1
    # find the matching close of this div by tracking the next entry-content sibling marker
    end = html.find('<!-- .entry-content -->', start)
    if end == -1:
        end = start + 6000
    body = html[start:end]
    links = []
    for m in A_HREF_RE.finditer(body):
        url = m.group(1)
        label = strip_tags(m.group(2))
        if not label:
            continue
        if label.strip().lower() == state_name.strip().lower():
            continue  # the self-referential "State: <Name>" link back to the table page
        links.append({"label": label, "url": url})
    plain_text = strip_tags(body)
    has_prose = len(plain_text) > 0 and len(links) < len(plain_text.split())
    return {"links": links, "text_present": bool(plain_text), "text_sample": plain_text[:300]}


# ---------------------------------------------------------------------------
# Other list views of a state (by county, standing only, by region, ...)
# ---------------------------------------------------------------------------

def norm_url(url: str) -> str:
    """https, no fragment, one trailing slash on a page path (the site is WordPress)."""
    url = url.strip().split("#", 1)[0]
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    if url.startswith("/"):
        url = BASE + url
    if "?" not in url:
        head, sep, tail = url.partition("://")
        url = head + sep + re.sub(r"/{2,}", "/", tail)
        if not url.endswith("/") and "." not in url.rsplit("/", 1)[-1]:
            url += "/"
    return url


def entry_content(html: str) -> str:
    """The page body (the article text), without the header, menus and footer."""
    idx = html.find('class="entry-content"')
    if idx == -1:
        return ""
    start = html.find(">", idx) + 1
    end = html.find("<!-- .entry-content -->", start)
    return html[start:end if end != -1 else len(html)]


def view_url_re(abbr: str) -> re.Pattern:
    a = abbr.lower()
    return re.compile(rf"^https://firelookout\.org/lookouts/us/{a}/{a}-([a-z]+)/$")


def discover_views(html: str, abbr: str) -> dict[str, dict]:
    """Links to the state's other list views ("Other sort: by County", "Standing", ...) in the
    page body: {code: {"url": ..., "label": ...}}. The -add page (additional information) is
    not a list and is left to the index. Document order."""
    rx = view_url_re(abbr)
    out: dict[str, dict] = {}
    for m in A_HREF_RE.finditer(entry_content(html)):
        url = norm_url(m.group(1))
        mm = rx.match(url)
        if not mm or mm.group(1) == "add":
            continue
        out.setdefault(mm.group(1), {"url": url, "label": strip_tags(m.group(2)) or None})
    return out


def sitemap_views(xml: str, abbrs: list[str]) -> dict[str, dict[str, str]]:
    """Every /lookouts/us/<st>/<st>-<code>/ page the site's page sitemap lists, by state, in
    case a state page forgets to link one of its own views. {abbr: {code: url}}."""
    out: dict[str, dict[str, str]] = defaultdict(dict)
    rxs = {a: view_url_re(a) for a in abbrs}
    for loc in re.findall(r"<loc>(.*?)</loc>", xml):
        url = norm_url(html_mod.unescape(loc))
        for a, rx in rxs.items():
            mm = rx.match(url)
            if mm and mm.group(1) != "add":
                out[a][mm.group(1)] = url
    return out


def key_base(key: str) -> str:
    """A record key without its ':<n>' repeat suffix, and with the name's punctuation gone
    ("Roberts (Shorty's)" is "Shorty-s" in one list and "Shortys" in another): the same
    state, the same letters and digits of the name, the same position. The slug has no colons."""
    parts = key.split(":")
    if len(parts) >= 5:
        parts[2] = parts[2].replace("-", "")
    return ":".join(parts[:5])


# Views that are a different list, not another sort of the state's list: ca-un holds the
# "Unknown/Undocumented" sites from Mark Thornton's survey (emergency lookouts, never-built and
# planned ones), which FFLA keeps out of its lookout lists. Its rows are kept as records of
# their own and never paired with a row of the lookout lists by name or position.
SEPARATE_VIEWS = {"un"}


def combine_views(per_view: list[tuple[str, list[dict]]]) -> list[dict]:
    """One record per lookout from several list views of one state.

    per_view[0] is the primary (alphabetical) view and fixes the record keys, so the keys
    (and the towers and sources hung on them) do not change when a view is added. A row a
    later view repeats is the same record, found in this order:

      * the same key (state, name, position): the usual case;
      * the same letters and digits of the name at the same position, under a further repeat
        number: a lookout the by-county view lists under two counties (its county goes to
        extra.counties);
      * the same position, no key match, and exactly one record there that this view has not
        matched already: FFLA's views do not always spell a name alike ("Remer #1" and "Remer
        - first", "Gallinas Peak" and "Galilnas Peak"), the other spelling goes to
        extra.also_named;
      * no position in this view (FFLA leaves it out of some lists), and exactly one unmatched
        record of the same name and county;
      * a position FFLA's own bounding-box check flags as outside the state (a typo in this view),
        and exactly one unmatched record of the same name and county;
      * a position this view gives to a record the alphabetical list has none for (same name
        and county, exactly one such record): the record takes the position, and
        extra.position_from_view says which view it came from (its key keeps the "null").

    Views in SEPARATE_VIEWS are other lists, not other sorts: they only ever match by key.

    The record keeps the primary view's fields; extra.views names every view it was in and the
    county fills in if the primary lacks it. A row nothing matches becomes a record of its own
    (a lookout only that view lists)."""
    out: dict[str, dict] = {}
    by_base: dict[str, str] = {}
    by_pos: dict[tuple, list[str]] = defaultdict(list)
    by_name: dict[str, list[str]] = defaultdict(list)

    def squash(name: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", name.lower())

    def pos(r: dict):
        return (round(r["lat"], 4), round(r["lon"], 4)) if r.get("lat") is not None and r.get("lon") is not None else None

    def add(r: dict, view: str) -> None:
        r.setdefault("extra", {})["views"] = [view]
        out[r["key"]] = r
        by_base.setdefault(key_base(r["key"]), r["key"])
        if pos(r):
            by_pos[pos(r)].append(r["key"])
        by_name[squash(r["name"])].append(r["key"])

    def county_ok(cur: dict, r: dict) -> bool:
        a, b = (cur.get("county") or "").strip().lower(), (r.get("county") or "").strip().lower()
        return not a or not b or a == b or a in b or b in a

    def join(cur: dict, r: dict, view: str) -> None:
        if view not in cur["extra"]["views"]:
            cur["extra"]["views"].append(view)
        # Only the county is taken from another view. The views are separate hand-edited
        # tables and a register cell in one can sit on the wrong row (the by-county list gives
        # OR's West Eagle the register entry of Woods Point), so registers and links come from
        # the alphabetical list alone.
        if not cur.get("county") and r.get("county"):
            cur["county"] = r["county"]
        _note_county(cur, r)

    for r in per_view[0][1] if per_view else []:
        add(r, per_view[0][0])
    for view, recs in per_view[1:]:
        claimed: set[str] = set()
        leftover = []
        for r in recs:
            key = r["key"]
            target = key if key in out and key not in claimed else by_base.get(key_base(key))
            if target is not None and (target == key or key not in out):
                join(out[target], r, view)
                claimed.add(target)
            else:
                leftover.append(r)
        for r in leftover:
            p = pos(r)
            fills_position = False
            if view in SEPARATE_VIEWS:
                cands = []
            elif p is not None:
                cands = [k for k in by_pos.get(p, []) if k not in claimed]
                if len(cands) > 1:
                    best = sorted(cands, key=lambda k: -difflib.SequenceMatcher(None, squash(out[k]["name"]), squash(r["name"])).ratio())
                    if difflib.SequenceMatcher(None, squash(out[best[0]]["name"]), squash(r["name"])).ratio() >= 0.5:
                        cands = best[:1]
                if not cands and r["extra"].get("coordinate_problem"):
                    # a position FFLA's own bounding-box check flags (a latitude of 48.08 for a
                    # Wisconsin lookout at 44.08): a typo in this view of a lookout the primary
                    # view has, so the one unmatched record of that name and county
                    cands = [k for k in by_name.get(squash(r["name"]), [])
                             if k not in claimed and county_ok(out[k], r) and out[k].get("lat") is not None
                             and not out[k]["extra"].get("coordinate_problem")]
                if not cands:
                    # the alphabetical list may give the lookout no position at all while
                    # another view does: the one unmatched record of that name and county
                    cands = [k for k in by_name.get(squash(r["name"]), [])
                             if k not in claimed and out[k].get("lat") is None and county_ok(out[k], r)]
                    fills_position = len(cands) == 1
            else:
                cands = [k for k in by_name.get(squash(r["name"]), [])
                         if k not in claimed and county_ok(out[k], r)]
            if len(cands) == 1:
                cur = out[cands[0]]
                join(cur, r, view)
                claimed.add(cands[0])
                if fills_position:
                    for f in ("lat", "lon"):
                        cur[f] = r[f]
                    for f in ("coordinate_problem",):
                        if r["extra"].get(f):
                            cur["extra"][f] = r["extra"][f]
                    cur["extra"]["position_from_view"] = view
                    by_pos[pos(cur)].append(cands[0])
                if squash(cur["name"]) != squash(r["name"]):
                    also = cur["extra"].setdefault("also_named", [])
                    if r["name"] not in also:
                        also.append(r["name"])
            else:
                add(r, view)
                claimed.add(r["key"])
    return list(out.values())


def _note_county(cur: dict, other: dict) -> None:
    c = other.get("county")
    if c and c != cur.get("county"):
        seen = cur["extra"].setdefault("counties", [x for x in [cur.get("county")] if x])
        if c not in seen:
            seen.append(c)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--refresh", action="store_true",
                    help="refetch every page (index, sitemap, state lists and views, -add pages) "
                         "instead of reading the cache; still 2 s between requests")
    args = ap.parse_args(argv)

    rl = RateLimiter()
    robots = RobotsCache(rl)
    fetched_now: set[str] = set()

    def get(url: str):
        force = args.refresh and url not in fetched_now
        fetched_now.add(url)
        return fetch(SOURCE, url, rl, robots, force=force, log=log)

    log(f"=== fetch_ffla.py starting ({'refresh' if args.refresh else 'cache-first'}) ===")
    status, body, cached = get(INDEX_URL)
    if status != 200:
        log(f"FATAL: index page fetch failed with status {status}")
        sys.exit(1)
    states = parse_index(body)
    log(f"Index parsed: {len(states)} states listed")

    sm_views: dict[str, dict[str, str]] = {}
    status, sm_xml, _ = get(f"{BASE}/page-sitemap.xml")
    if status == 200:
        sm_views = sitemap_views(sm_xml, [st["abbr"] for st in states])
    else:
        log(f"WARN: page sitemap not available (status {status}); relying on the links in each state page")

    previous = {}
    if OUT_PATH.exists():
        try:
            previous = {r["key"]: r for r in json.loads(OUT_PATH.read_text(encoding="utf-8"))["records"]}
        except (OSError, ValueError, KeyError):
            previous = {}

    all_records = []
    additional_info = {}
    kind_stats = Counter()
    status_stats = Counter()
    coord_stats = Counter()
    per_state_counts = {}
    per_state_views: dict[str, dict] = {}
    states_with_table = 0
    states_without_table = []
    view_labels: dict[str, str] = {}
    sitemap_only_views = []
    unreachable_states = []

    for st in states:
        abbr = st["abbr"]
        primary_url = st["table_url"] or f"{BASE}/lookouts/us/{abbr.lower()}/"
        status, body, cached = get(primary_url)
        if status != 200:
            unreachable_states.append(abbr)
            log(f"{abbr}: state page {primary_url} status={status}")
            per_state_counts[abbr] = 0
            states_without_table.append(abbr)
            body = ""
        per_view = []
        if body:
            recs = parse_state_table(body, abbr, primary_url, kind_stats, status_stats, coord_stats)
            per_view.append(("alpha", recs))
            found = discover_views(body, abbr)
            for code, url in sm_views.get(abbr, {}).items():
                if code not in found:
                    found[code] = {"url": url, "label": None}
                    sitemap_only_views.append(f"{abbr}/{code}")
            for code, v in found.items():
                if v["label"]:
                    view_labels.setdefault(code, v["label"])
                vstatus, vbody, vcached = get(v["url"])
                if vstatus != 200:
                    log(f"{abbr}: view {code} {v['url']} status={vstatus}")
                    continue
                vrecs = parse_state_table(vbody, abbr, v["url"], kind_stats, status_stats, coord_stats,
                                          groups=(code == "rg"))
                per_view.append((code, vrecs))
        merged = combine_views(per_view)
        if merged:
            states_with_table += 1
            if abbr in states_without_table:
                states_without_table.remove(abbr)
        elif abbr not in states_without_table:
            states_without_table.append(abbr)
        all_records.extend(merged)
        per_state_counts[abbr] = len(merged)
        per_state_views[abbr] = {
            "rows_by_view": {v: len(r) for v, r in per_view},
            "records": len(merged),
            "only_in_secondary_views": sum(1 for r in merged if "alpha" not in r["extra"]["views"]),
        }
        log(f"{abbr}: {len(merged)} records from " + (", ".join(f"{v}={len(r)}" for v, r in per_view) or "no table"))

        if st["add_url"]:
            astatus, abody, _ = get(st["add_url"])
            if astatus == 200:
                info = parse_add_page(abody, st["state"])
                additional_info[abbr] = {"url": st["add_url"], **info}

    out = {
        "source": SOURCE,
        "title": "Forest Fire Lookout Association (FFLA) - US lookout lists",
        "url": INDEX_URL,
        "retrieved": __import__("datetime").date.today().isoformat(),
        "license": "No licence stated; facts extracted only, no prose copied.",
        "records": all_records,
        "additional_info": additional_info,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"Wrote {len(all_records)} records to {OUT_PATH}")

    new_keys = {r["key"] for r in all_records}
    only_secondary = [r for r in all_records if "alpha" not in r["extra"]["views"]]
    report = {
        "mode": "refresh" if args.refresh else "cache-first",
        "states_with_table": states_with_table,
        "states_without_table": states_without_table,
        "unreachable_states": unreachable_states,
        "per_state_counts": per_state_counts,
        "per_state_views": per_state_views,
        "view_labels": view_labels,
        "views_found_only_in_sitemap": sitemap_only_views,
        "rows_only_in_secondary_views": [
            {"key": r["key"], "name": r["name"], "region": r["region"], "views": r["extra"]["views"],
             "type": r["type_raw"], "status": r["status_raw"], "lat": r["lat"], "lon": r["lon"]}
            for r in only_secondary
        ],
        "keys_added_since_previous": sorted(new_keys - set(previous)) if previous else None,
        "keys_missing_since_previous": sorted(set(previous) - new_keys) if previous else None,
        "kind_raw_counts": dict(kind_stats),
        "status_raw_counts": dict(status_stats),
        "coord_stats": dict(coord_stats),
        "additional_info_states": sorted(additional_info.keys()),
        "total_records": len(all_records),
        "registers_present": sum(1 for r in all_records if r["registers"]),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"Report written to {REPORT_PATH}")
    log("=== fetch_ffla.py done ===")


if __name__ == "__main__":
    main()
