#!/usr/bin/env python3
"""Build the data files the Firefinder website loads (DESIGN.md section 3.6).

Reads the canonical towers (data/towers/**/*.json), stories (data/stories/<id>.md), the
vocabularies (data/vocab.json) and source extract headers (data/sources/*.json), and writes
web/public/data/:

  towers.geojson   every visible lookout as a point, with short property names (below)
  t/<id>.json      the full canonical record, plus "story_html" when a story exists and
                   "design_ids" when a standard design is recognised
  meta.json        counts, the source list with credit lines and retrieved dates, build date
  designs.json     the tower-designs guide: data/designs.json's facts plus the lookouts of
                   each design and how many lookouts have a recognisable design

A tower's "photos" pass through unchanged: pipeline/merge.py is what fills in file/thumb
(from data/photos_manifest.json, written by pipeline/mirror_photos.py), and the site resolves
them against web/site.config.json's "photosBase" at render time, not here -- this script does
not copy or validate photo files.

towers.geojson properties (absent optional keys mean null / false; see meta.json "format"):

  i  id            n  name           r  region (state code)
  k  kind          s  status         v  verification       a  access level
  b  built year    rt rentable (1)   rg on a register (1)   o  other names, "|"-joined
  c  county        y0 first year it stood   y1 year it came down   d  design ids, "|"-joined

Coordinates are [lon, lat] rounded to 5 decimal places.

y0 / y1 drive the map's "Lookouts standing in year ..." view (year_range below). They are left
out when no event records them; a tower that still stands has no y1. meta.json "history" counts
how many towers have which dates, so the site can say how many it cannot place in time.

d lists the standard designs (L-4, R-6, Aermotor...) recognised in the tower's design field and
its sources' type and design fields (pipeline/designs.py). designs.json pairs the guide's facts
(data/designs.json) with every lookout of each design.

Hidden records (hidden: true) are skipped. Records that fail basic checks are skipped with a
warning, so one bad file never takes the site down; pass --strict to fail instead.

If the towers folder has no records and --fallback-fixtures is given, the sample records in
web/fixtures/ are used instead, with a loud banner in the log and "fixtures": true in
meta.json (the site then shows a "Sample data" notice).

Python 3.12, standard library only.
"""

from __future__ import annotations

import auto_summary  # noqa: E402  (pipeline/ is on sys.path when run as a script)
import argparse
import datetime as dt
import html
import json
import os
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import designs as design_names  # noqa: E402  (pipeline/designs.py)
import structure  # noqa: E402  (pipeline/structure.py: kinds, materials, the no-structure group)

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
FIXTURES = REPO / "web" / "fixtures"
DEFAULT_OUT = REPO / "web" / "public" / "data"
MARKER = ".firefinder-site-data"

ID_RE = re.compile(r"^[a-z]{2}-[a-z0-9]{1,3}-[a-z0-9]+(?:-[a-z0-9]+)*$")

GEOJSON_FORMAT = {
    "i": "id",
    "n": "name",
    "r": "region (state code)",
    "k": "kind (vocab.kind)",
    "s": "status (vocab.status)",
    "v": "verification (vocab.verification)",
    "a": "access level (vocab.access)",
    "b": "year built (absent = unknown)",
    "rt": "1 = rentable (absent = not rentable)",
    "rg": "1 = listed on a register such as NHLR or FFLOS (absent = not listed)",
    "o": "other names joined with | (absent = none)",
    "c": "county, to tell same-named lookouts apart (absent = unknown)",
    "y0": "first year a lookout is recorded standing here: built, rebuilt, replaced or first staffed (absent = unknown)",
    "y1": "year it came down: destroyed, burned, removed or abandoned (absent = still standing, or not recorded)",
    "d": "standard designs recognised (designs.json ids) joined with | (absent = none recognised)",
    "m": "material of the main structure (vocab.material) (absent = not recorded)",
}

# Events that show a lookout stood at the site in that year, and events that end it. The
# owner's rule (DESIGN.md §1, extras): a tower counts as standing in a year if it was built on
# or before that year and not yet gone.
START_EVENTS = ("built", "rebuilt", "replaced", "staffed_first")
END_EVENTS = ("destroyed", "burned", "removed", "abandoned")
# Statuses that mean the structure stands today, so nothing has ended it yet.
STANDING_NOW = ("standing", "replica")
FIRST_PLAUSIBLE_YEAR = 1850


def _event_years(rec: dict, names: tuple[str, ...], this_year: int) -> list[int]:
    return [
        e["year"]
        for e in rec.get("events") or []
        if isinstance(e, dict)
        and e.get("event") in names
        and isinstance(e.get("year"), int)
        and not isinstance(e.get("year"), bool)
        and FIRST_PLAUSIBLE_YEAR <= e["year"] <= this_year
    ]


def year_range(rec: dict, this_year: int) -> tuple[int | None, int | None]:
    """(first year it stood, year it came down) from a tower's events and status.

    Start: the earliest built / rebuilt / replaced / first-staffed year. End: for a lookout
    that does not stand today, the first destroyed / burned / removed / abandoned year after
    its last (re)build (a "relocated" year ends a site whose structure was moved away). A
    lookout standing today has no end, whatever happened before a rebuild; an "abandoned"
    lookout that still stands has not come down. Either value is None when no event records
    it: unknown, never guessed. Years outside 1850..this year are ignored as typos.
    """
    starts = _event_years(rec, START_EVENTS, this_year)
    start = min(starts) if starts else None
    if rec.get("status") in STANDING_NOW:
        return start, None
    last_start = max(starts) if starts else None
    ends = [y for y in _event_years(rec, END_EVENTS, this_year) if last_start is None or y >= last_start]
    if not ends and rec.get("status") == "relocated":
        ends = [y for y in _event_years(rec, ("relocated",), this_year) if last_start is None or y >= last_start]
    return start, (min(ends) if ends else None)


def history_counts(ranges: list[tuple[int | None, int | None, str]], this_year: int) -> dict:
    """How many towers can be placed in time. `ranges` holds (start, end, status) per tower."""
    standing = [r for r in ranges if r[2] in STANDING_NOW]
    starts = [r[0] for r in ranges if r[0] is not None]
    return {
        "this_year": this_year,
        "total": len(ranges),
        "with_start": len(starts),
        "with_end": sum(1 for r in ranges if r[1] is not None),
        "standing_now": len(standing),
        # Placed in every year: a start, and either an end or still standing.
        "complete": sum(1 for r in ranges if r[0] is not None and (r[1] is not None or r[2] in STANDING_NOW)),
        "start_no_end": sum(1 for r in ranges if r[0] is not None and r[1] is None and r[2] not in STANDING_NOW),
        "end_no_start": sum(1 for r in ranges if r[0] is None and r[1] is not None),
        "standing_no_start": sum(1 for r in standing if r[0] is None),
        # Neither a start nor an end year (standing ones are still placed today, by status).
        "no_dates": sum(1 for r in ranges if r[0] is None and r[1] is None),
        "no_dates_not_standing": sum(1 for r in ranges if r[0] is None and r[1] is None and r[2] not in STANDING_NOW),
        "first_year": min(starts) if starts else None,
    }

# Credit lines and licence notes for sources we know about. Titles, URLs and retrieved dates
# from data/sources/<id>.json headers take precedence where present.
KNOWN_SOURCES: dict[str, dict[str, str]] = {
    "ffla": {
        "title": "Forest Fire Lookout Association",
        "url": "https://firelookout.org/",
        "license": "No licence stated; facts only",
        "credit": "Forest Fire Lookout Association (firelookout.org)",
    },
    "nhlr": {
        "title": "National Historic Lookout Register",
        "url": "https://nhlr.org/",
        "license": "All rights reserved (American Resources Inc.); facts only, photos shown with credit",
        "credit": "National Historic Lookout Register (nhlr.org)",
    },
    "fflos": {
        "title": "Former Fire Lookout Sites Register",
        "url": "https://firetower.org/",
        "license": "All rights reserved (American Resources Inc.); facts only, photos shown with credit",
        "credit": "Former Fire Lookout Sites Register (firetower.org)",
    },
    "ridb": {
        "title": "Recreation Information Database (recreation.gov)",
        "url": "https://ridb.recreation.gov/",
        "license": "Public data from the US government",
        "credit": "Data source: ridb.recreation.gov",
    },
    "osm": {
        "title": "OpenStreetMap",
        "url": "https://www.openstreetmap.org/copyright",
        "license": "ODbL 1.0",
        "credit": "© OpenStreetMap contributors",
    },
    "wikidata": {
        "title": "Wikidata",
        "url": "https://www.wikidata.org/",
        "license": "CC0 1.0",
        "credit": "Wikidata",
    },
    "firelookout_com": {
        "title": "firelookout.com state maps",
        "url": "https://www.firelookout.com/",
        "license": "No licence stated; facts only",
        "credit": "firelookout.com",
    },
    "pa_storymap": {
        "title": "Pennsylvania fire towers StoryMap",
        "url": "https://www.arcgis.com/home/item.html?id=ed47c97ebe7246868ce8ef3e7139a0b4",
        "license": "No licence stated; facts only",
        "credit": "Pennsylvania fire towers StoryMap (ArcGIS)",
    },
    "andyarthur_ny": {
        "title": "New York fire towers (andyarthur.org)",
        "url": "https://andyarthur.org/",
        "license": "CC BY 3.0",
        "credit": "Andy Arthur, andyarthur.org (CC BY 3.0)",
    },
    "cskt": {
        "title": "Confederated Salish and Kootenai Tribes",
        "url": "https://csktribes.org/",
        "license": "Facts only",
        "credit": "Confederated Salish and Kootenai Tribes",
    },
    "idaho_fl": {
        "title": "Idaho Fire Lookouts (idahofirelookouts.com)",
        "url": "https://www.idahofirelookouts.com/",
        "license": "No licence stated; facts only",
        "credit": "idahofirelookouts.com",
    },
    "fire_lookouts_org": {
        "title": "fire-lookouts.org (Sierra National Forest)",
        "url": "https://fire-lookouts.org/",
        "license": "Reuse allowed with credit",
        "credit": "fire-lookouts.org",
    },
    "eastern_us_lookouts": {
        "title": "FOREST LOOKOUTS -- eastern US",
        "url": "https://easternuslookouts.weebly.com/",
        "license": "No licence stated; facts only",
        "credit": "easternuslookouts.weebly.com",
    },
    "central_us_lookouts": {
        "title": "FOREST LOOKOUTS -- central US",
        "url": "https://centraluslookouts.weebly.com/",
        "license": "No licence stated; facts only",
        "credit": "centraluslookouts.weebly.com",
    },
    "wikipedia_lookout_lists": {
        "title": "Wikipedia: per-state fire lookout tower lists",
        "url": "https://en.wikipedia.org/wiki/List_of_fire_lookout_towers_in_Louisiana",
        "license": "CC BY-SA 4.0; facts only, article prose not reproduced",
        "credit": "Wikipedia",
    },
    "nj_forest_fire_towers": {
        "title": "Wikipedia: List of New Jersey Forest Fire Service fire towers",
        "url": "https://en.wikipedia.org/wiki/List_of_New_Jersey_Forest_Fire_Service_fire_towers",
        "license": "CC BY-SA 4.0; facts only, article prose not reproduced",
        "credit": "Wikipedia (NJFFS fire tower list)",
    },
    "michigan_fire_tower": {
        "title": "Michigan Fire Towers",
        "url": "https://michiganfiretower.com/",
        "license": "No licence stated; facts only",
        "credit": "michiganfiretower.com",
    },
    "research": {
        "title": "Firefinder research",
        "url": None,
        "license": "Our own research notes; each fact cites its source in the lookout's story",
        "credit": "Firefinder research (sources cited in the story footnotes)",
    },
    "tnlandforms": {
        "title": "tnlandforms.us fire lookout towers (Tom Dunigan)",
        "url": "https://tnlandforms.us/towers/",
        "license": "No licence stated; facts only",
        "credit": "tnlandforms.us (Tom Dunigan)",
    },
}


class Log:
    def __init__(self, quiet: bool = False) -> None:
        self.quiet = quiet
        self.warnings = 0
        self.gha = os.environ.get("GITHUB_ACTIONS") == "true"

    def info(self, msg: str) -> None:
        if not self.quiet:
            print(msg)

    def warn(self, msg: str, file: Path | None = None) -> None:
        self.warnings += 1
        if self.gha:
            loc = f" file={file}" if file else ""
            print(f"::warning{loc}::{msg}")
        else:
            print(f"WARNING: {msg}" + (f" ({file})" if file else ""), file=sys.stderr)


# ---------------------------------------------------------------------------------------
# Markdown (a small, safe subset) -> HTML
# ---------------------------------------------------------------------------------------

_SAFE_SCHEMES = ("http", "https", "mailto")


def safe_href(url: str) -> str | None:
    """Return the URL if it is http(s), mailto, relative or a #fragment; else None."""
    url = url.strip()
    if not url:
        return None
    probe = re.sub(r"[\x00-\x20\x7f]+", "", url).lower()
    m = re.match(r"^([a-z][a-z0-9+.-]*):", probe)
    if m:
        return url if m.group(1) in _SAFE_SCHEMES else None
    return url


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


_FN_LABEL_RE = re.compile(r"[^a-z0-9-]+")


def _fn_slug(label: str) -> str:
    return _FN_LABEL_RE.sub("-", label.lower()).strip("-") or "note"


_EMPHASIS = [
    (re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"__(?=\S)(.+?)(?<=\S)__"), r"<strong>\1</strong>"),
    (re.compile(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])"), r"<em>\1</em>"),
    (re.compile(r"(?<![\w_])_(?=\S)(.+?)(?<=\S)_(?![\w_])"), r"<em>\1</em>"),
]


def _emphasis(escaped: str) -> str:
    for pattern, repl in _EMPHASIS:
        escaped = pattern.sub(repl, escaped)
    return escaped


_INLINE_RE = re.compile(
    r"`(?P<code>[^`]+)`"
    r"|\[\^(?P<fn>[^\]\s]+)\]"
    r"|\[(?P<text>[^\]]+)\]\((?P<url>[^)\s]+)(?:\s+\"[^\"]*\")?\)"
    r"|<(?P<auto>https?://[^>\s]+)>"
    # a bare URL, as research footnotes write them; trailing punctuation stays outside
    r"|(?P<bare>https?://[^\s<>\"]*[^\s<>\".,;:!?)\]'])"
)

# External links in stories open in the same tab but pass no referrer or window handle.
EXTERNAL_REL = "noopener noreferrer"


def _link(href: str, label: str) -> str:
    rel = f' rel="{EXTERNAL_REL}"' if href.lower().startswith(("http://", "https://")) else ""
    return f'<a href="{_esc(href)}"{rel}>{label}</a>'


class _Notes:
    """Footnote numbering in order of first reference."""

    def __init__(self, definitions: dict[str, str]) -> None:
        self.definitions = definitions
        self.order: list[str] = []
        self.ref_counts: Counter[str] = Counter()

    def ref(self, label: str) -> str:
        if label not in self.definitions:
            return _esc(f"[^{label}]")
        if label not in self.order:
            self.order.append(label)
        self.ref_counts[label] += 1
        n = self.order.index(label) + 1
        slug = _fn_slug(label)
        count = self.ref_counts[label]
        ref_id = f"fnref-{slug}" + (f"-{count}" if count > 1 else "")
        return f'<sup id="{ref_id}" class="fnref"><a href="#fn-{slug}" aria-label="Note {n}">{n}</a></sup>'


def _inline(text: str, notes: _Notes | None, allow_links: bool = True) -> str:
    out: list[str] = []
    pos = 0
    last_fn_end = -1
    for m in _INLINE_RE.finditer(text):
        out.append(_emphasis(_esc(text[pos : m.start()])))
        pos = m.end()
        if m.group("code") is not None:
            out.append(f"<code>{_esc(m.group('code'))}</code>")
        elif m.group("fn") is not None:
            if notes and last_fn_end == m.start() and m.group("fn") in notes.definitions:
                out.append('<sup class="fnsep">,</sup>')  # "[^3][^1]" reads 3,1 and not 31
            out.append(notes.ref(m.group("fn")) if notes else _esc(m.group(0)))
            last_fn_end = m.end()
        elif m.group("text") is not None:
            label = _inline(m.group("text"), None, allow_links=False)
            href = safe_href(m.group("url")) if allow_links else None
            out.append(_link(href, label) if href else label)
        else:
            href = m.group("auto") or m.group("bare")
            out.append(_link(href, _esc(href)) if allow_links else _esc(href))
    out.append(_emphasis(_esc(text[pos:])))
    return "".join(out)


_FRONT_MATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.S)
_FN_DEF_RE = re.compile(r"^\[\^([^\]\s]+)\]:\s?(.*)$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_HR_RE = re.compile(r"^(?:-{3,}|\*{3,}|_{3,})\s*$")
_UL_RE = re.compile(r"^[-*+]\s+(.*)$")
_OL_RE = re.compile(r"^\d{1,3}[.)]\s+(.*)$")


def _plain(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def markdown_to_html(md: str, title: str | None = None) -> str:
    """Convert story Markdown to HTML.

    Supports paragraphs, # headings (shifted down one level: the page title is the h1),
    *emphasis*, **strong**, `code`, [links](https://...), <https://autolinks>, "-" and "1."
    lists, > blockquotes, --- rules and footnotes ([^1] with "[^1]: text" definitions).
    Everything else, including any raw HTML, is escaped and shown as text. Links keep only
    http(s), mailto, relative and #fragment URLs.
    """
    text = md.replace("\r\n", "\n").replace("\r", "\n")
    text = _FRONT_MATTER_RE.sub("", text, count=1)
    # A first line "# <the lookout's name>" repeats the page's own h1: drop it.
    first = re.match(r"\A\s*#(?!#)\s*([^\n]*)\n", text)
    if first and title and _plain(first.group(1)) and _plain(first.group(1)) in _plain(title):
        text = text[first.end():]
    lines = text.split("\n")

    # 1. Pull out footnote definitions (with indented continuation lines).
    definitions: dict[str, str] = {}
    body: list[str] = []
    i = 0
    while i < len(lines):
        m = _FN_DEF_RE.match(lines[i])
        if m:
            label, content = m.group(1), [m.group(2)]
            i += 1
            while i < len(lines) and (lines[i].startswith("    ") or lines[i].startswith("\t")):
                content.append(lines[i].strip())
                i += 1
            definitions.setdefault(label, " ".join(c for c in content if c))
            continue
        body.append(lines[i])
        i += 1

    notes = _Notes(definitions)
    out: list[str] = []

    # 2. Blocks.
    para: list[str] = []
    list_kind: str | None = None
    list_items: list[str] = []
    quote: list[str] = []

    def flush_para() -> None:
        if para:
            out.append(f"<p>{_inline(' '.join(s.strip() for s in para), notes)}</p>")
            para.clear()

    def flush_list() -> None:
        nonlocal list_kind
        if list_kind:
            items = "".join(f"<li>{_inline(it, notes)}</li>" for it in list_items)
            out.append(f"<{list_kind}>{items}</{list_kind}>")
            list_items.clear()
            list_kind = None

    def flush_quote() -> None:
        if quote:
            inner = " ".join(s.strip() for s in quote if s.strip())
            out.append(f"<blockquote><p>{_inline(inner, notes)}</p></blockquote>")
            quote.clear()

    def flush_all() -> None:
        flush_para()
        flush_list()
        flush_quote()

    for line in body:
        stripped = line.strip()
        if not stripped:
            flush_all()
            continue
        if stripped.startswith(">"):
            flush_para()
            flush_list()
            quote.append(stripped[1:])
            continue
        flush_quote()
        h = _HEADING_RE.match(stripped)
        if h:
            flush_all()
            level = min(len(h.group(1)) + 1, 4)
            content = _inline(h.group(2), notes)
            slug = _fn_slug(re.sub(r"<[^>]+>", "", h.group(2)))[:60]
            out.append(f'<h{level} id="s-{slug}">{content}</h{level}>')
            continue
        if _HR_RE.match(stripped):
            flush_all()
            out.append("<hr>")
            continue
        ul, ol = _UL_RE.match(stripped), _OL_RE.match(stripped)
        if ul or ol:
            flush_para()
            kind = "ul" if ul else "ol"
            if list_kind and list_kind != kind:
                flush_list()
            list_kind = kind
            list_items.append((ul or ol).group(1))  # type: ignore[union-attr]
            continue
        if list_kind and line.startswith(("  ", "\t")):
            list_items[-1] += " " + stripped
            continue
        flush_list()
        para.append(stripped)
    flush_all()

    # 3. Footnotes: referenced ones in order of first use, then any never referenced.
    labels = notes.order + [label for label in definitions if label not in notes.order]
    if labels:
        items = []
        for label in labels:
            slug = _fn_slug(label)
            content = _inline(definitions[label], None)
            back = ""
            if label in notes.order:
                back = f' <a href="#fnref-{slug}" class="fn-back" aria-label="Back to the text">↩</a>'
            items.append(f'<li id="fn-{slug}">{content}{back}</li>')
        out.append(
            '<section class="footnotes" aria-label="Notes and sources"><ol>' + "".join(items) + "</ol></section>"
        )
    return "\n".join(out)


# ---------------------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------------------


def _num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_record(rec: object) -> str | None:
    """Return a problem description, or None if the record is usable."""
    if not isinstance(rec, dict):
        return "not a JSON object"
    rid = rec.get("id")
    if not isinstance(rid, str) or not ID_RE.match(rid) or len(rid) > 120:
        return f"id {rid!r} is missing or not of the form us-<st>-<slug>"
    if not isinstance(rec.get("name"), str) or not rec["name"].strip():
        return "name is missing"
    loc = rec.get("location")
    if not isinstance(loc, dict) or not _num(loc.get("lat")) or not _num(loc.get("lon")):
        return "location.lat / location.lon missing"
    if not (-90 <= loc["lat"] <= 90 and -180 <= loc["lon"] <= 180):
        return "coordinates out of range"
    for key in ("region", "kind", "status", "verification"):
        if not isinstance(rec.get(key), str):
            return f"{key} is missing"
    return None


def built_year(rec: dict) -> int | None:
    years = [
        e.get("year")
        for e in rec.get("events") or []
        if isinstance(e, dict) and e.get("event") == "built" and isinstance(e.get("year"), int)
    ]
    return min(years) if years else None


def is_rentable(rec: dict) -> bool:
    r = rec.get("rental")
    return isinstance(r, dict) and r.get("available") is not False


def feature(rec: dict, this_year: int | None = None, design_ids: list[str] | None = None) -> dict:
    loc = rec["location"]
    props: dict[str, object] = {
        "i": rec["id"],
        "n": rec["name"],
        "r": rec["region"],
        "k": rec["kind"],
        "s": rec["status"],
        "v": rec["verification"],
        "a": ((rec.get("access") or {}).get("level")) or "unknown",
    }
    b = built_year(rec)
    if b is not None:
        props["b"] = b
    if is_rentable(rec):
        props["rt"] = 1
    if rec.get("registers"):
        props["rg"] = 1
    others = [n for n in rec.get("other_names") or [] if isinstance(n, str) and n.strip()]
    if others:
        props["o"] = "|".join(n.replace("|", "/") for n in others)
    if isinstance(rec.get("county"), str) and rec["county"].strip():
        props["c"] = rec["county"].strip()
    y0, y1 = year_range(rec, this_year or dt.date.today().year)
    if y0 is not None:
        props["y0"] = y0
    if y1 is not None:
        props["y1"] = y1
    if design_ids:
        props["d"] = "|".join(design_ids)
    if isinstance(rec.get("material"), str) and rec["material"]:
        props["m"] = rec["material"]
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [round(loc["lon"], 5), round(loc["lat"], 5)]},
        "properties": props,
    }


def _write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _prepare_out(out: Path, log: Log) -> None:
    out = out.resolve()
    if out in (REPO, REPO.parent, Path(out.anchor)) or out == Path.home():
        raise SystemExit(f"Refusing to write site data into {out}")
    if out.exists() and any(out.iterdir()) and not (out / MARKER).exists():
        raise SystemExit(f"{out} is not empty and was not made by this script; refusing to clear it")
    out.mkdir(parents=True, exist_ok=True)
    (out / MARKER).write_text("Generated by pipeline/build_site_data.py. Safe to delete.\n")
    if (out / "t").exists():
        shutil.rmtree(out / "t")
    (out / "t").mkdir()


def load_source_headers(sources_dir: Path, log: Log, design_strings: dict[str, list[tuple[str, str]]] | None = None,
                        kind_words: dict[str, Counter] | None = None) -> dict[str, dict]:
    """Title, URL, licence and retrieved date of every source extract. With `design_strings`,
    also collects each source record's type and design wording by record key (for
    designs.tower_designs), e.g. {"ffla:or:...": [("type", "Tower")], "firelookout_com:...": [("design", "L-4")]}."""
    headers: dict[str, dict] = {}
    if not sources_dir.is_dir():
        return headers
    for path in sorted(sources_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            log.warn(f"could not read source extract: {e}", path)
            continue
        if not isinstance(data, dict):
            continue
        if data.get("kind") == "reference":
            continue  # not a list of lookouts (e.g. peaks_gnis.json, credited on the About page)
        sid = data.get("source") or path.stem
        if design_strings is not None and isinstance(data.get("records"), list):
            for r in data["records"]:
                if not isinstance(r, dict) or not isinstance(r.get("key"), str):
                    continue
                extra = r.get("extra") if isinstance(r.get("extra"), dict) else {}
                words = [(f, w.strip()) for f, w in (("type", r.get("type_raw")), ("design", extra.get("design"))) if isinstance(w, str) and w.strip()]
                if words:
                    design_strings[r["key"]] = words
        if kind_words is not None and sid in structure.SIMPLE_TYPES and isinstance(data.get("records"), list):
            # The sources' own words for each kind ("Rooftop", "Hotel", "Grain Elevator"), for the guide.
            for r in data["records"]:
                t = r.get("type_raw") if isinstance(r, dict) else None
                info = structure.type_info(sid, t) if isinstance(t, str) and t.strip() else None
                if info is not None and info.kind not in (None, structure.KEEP):
                    kind_words.setdefault(info.kind, Counter())[re.sub(r"\s+", " ", t.strip().rstrip("*"))] += 1
        headers[sid] = {
            "title": data.get("title"),
            "url": data.get("url"),
            "license": data.get("license"),
            "retrieved": data.get("retrieved"),
            "records": len(data["records"]) if isinstance(data.get("records"), list) else None,
        }
    return headers


def tower_design_texts(rec: dict, design_strings: dict[str, list[tuple[str, str]]]) -> tuple[list[str], bool]:
    """The tower's own design field first, then its sources' type and design wording; and
    whether any of it is a design field (a type such as FFLA's "Tower" or "Ground" alone says
    nothing about the plan, so it does not count as a recorded design)."""
    texts: list[str] = []
    has_design = False
    if isinstance(rec.get("design"), str) and rec["design"].strip():
        texts.append(rec["design"].strip())
        has_design = True
    for s in rec.get("sources") or []:
        if isinstance(s, dict) and isinstance(s.get("key"), str):
            for field, w in design_strings.get(s["key"], []):
                has_design = has_design or field == "design"
                if w not in texts:
                    texts.append(w)
    return texts, has_design


def design_entry(rec: dict, did: str, texts: list[str]) -> dict:
    """One lookout in the designs guide: id, name, state, status, kind, and the source's own
    wording when it says more than the bare design name ("L-4 cab on a 32-foot timber tower")."""
    entry: dict[str, object] = {"i": rec["id"], "n": rec["name"], "r": rec["region"], "s": rec["status"], "k": rec["kind"]}
    wording = next((t for t in texts if did in design_names.match_designs(t)), None)
    bare = design_names.DESIGN_NAMES.get(did, did).lower()
    if wording and wording.lower().strip(" .") not in (bare, bare.replace("-", ""), did):
        entry["w"] = wording[:240]
    if did == "aermotor":
        models = [m for t in texts for m in design_names.aermotor_models(t)]
        if models:
            entry["m"] = sorted(set(models))
    return entry


def write_designs(out: Path, facts_path: Path, towers: dict[str, list[dict]], with_text: int, total: int, log: Log) -> dict:
    """designs.json for the guide page: the curated facts (data/designs.json) in their order,
    each with its lookouts, plus coverage counts. Returns the coverage summary for meta.json."""
    facts: dict = {}
    if facts_path.is_file():
        try:
            facts = json.loads(facts_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            log.warn(f"could not read design facts: {e}", facts_path)
    entries = [d for d in facts.get("designs", []) if isinstance(d, dict) and isinstance(d.get("id"), str)]
    known = {d["id"] for d in entries}
    for did in towers:
        if did not in known:
            log.warn(f"design {did!r} matched {len(towers[did])} lookouts but has no entry in {facts_path.name}")
            entries.append({"id": did, "name": design_names.DESIGN_NAMES.get(did, did)})
    recognised = len({t["i"] for ts in towers.values() for t in ts})
    designs = []
    for d in entries:
        ts = sorted(towers.get(d["id"], []), key=lambda t: (str(t["r"]), str(t["n"]).lower(), str(t["i"])))
        status = Counter(str(t["s"]) for t in ts)
        designs.append({**d, "towers": ts, "count": len(ts), "by_status": dict(sorted(status.items()))})
    coverage = {
        "total": total,
        # A design field from the tower or one of its sources, recognised or not.
        "with_design_text": with_text,
        "recognised": recognised,
        "by_design": {d["id"]: d["count"] for d in designs},
    }
    _write_json(
        out / "designs.json",
        {
            "title": facts.get("title"),
            "note": facts.get("note"),
            "updated": facts.get("updated"),
            "sources": facts.get("sources", []),
            "coverage": coverage,
            "designs": designs,
        },
    )
    return coverage


def write_structure_kinds(out: Path, vocab_path: Path, by_kind: Counter, by_material: Counter,
                          kind_words: dict[str, Counter], log: Log) -> dict:
    """structure_kinds.json for the "Structure types" guide: data/structure_kinds.json's
    groups, kinds, materials and roles, each kind with how many lookouts are of it and the
    words the sources use for it. Returns the counts for meta.json."""
    try:
        vocab = json.loads(vocab_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log.warn(f"could not read the structure vocabulary: {e}", vocab_path)
        return {}
    group = {k["id"]: k.get("group") for k in vocab.get("kinds", [])}
    kinds = []
    for k in vocab.get("kinds", []):
        # One spelling per word ("Tower" and "tower"), the commonest; unsure ones ("Tower?") left out.
        seen: dict[str, str] = {}
        for w, _ in (kind_words.get(k["id"]) or Counter()).most_common():
            if "?" not in w:
                seen.setdefault(w.lower(), w)
        words = list(seen.values())[:12]
        kinds.append({**{x: k.get(x) for x in ("id", "label", "group", "about")}, "count": by_kind.get(k["id"], 0), "source_words": words})
    for kid in sorted(set(by_kind) - set(group)):
        log.warn(f"kind {kid!r} is on {by_kind[kid]} lookouts but not in {vocab_path.name}")
    groups = [{**{x: g.get(x) for x in ("id", "label", "shown_by_default", "about")},
               "count": sum(n for kid, n in by_kind.items() if group.get(kid, "structure") == g["id"])}
              for g in vocab.get("groups", [])]
    materials = [{**m, "count": by_material.get(m["id"], 0)} for m in vocab.get("materials", [])]
    summary = {
        "structures": sum(n for kid, n in by_kind.items() if group.get(kid, "structure") != "no_structure"),
        "no_structure": sum(n for kid, n in by_kind.items() if group.get(kid) == "no_structure"),
        "with_material": sum(by_material.values()),
    }
    _write_json(out / "structure_kinds.json", {"title": vocab.get("title"), "updated": vocab.get("updated"),
                                              "groups": groups, "kinds": kinds, "materials": materials,
                                              "roles": vocab.get("roles", []), "counts": summary})
    return summary


def build(
    towers_dir: Path,
    stories_dir: Path,
    _photos_dir: Path,  # unused: photos resolve client-side via site.config.json "photosBase"
    sources_dir: Path,
    vocab_path: Path,
    out: Path,
    *,
    fixtures: bool = False,
    strict: bool = False,
    log: Log | None = None,
    designs_path: Path | None = None,
    this_year: int | None = None,
    structure_kinds_path: Path | None = None,
) -> dict:
    log = log or Log()
    files = sorted(towers_dir.rglob("*.json")) if towers_dir.is_dir() else []
    vocab = json.loads(vocab_path.read_text(encoding="utf-8")) if vocab_path.is_file() else {}
    this_year = this_year or dt.date.today().year
    design_strings: dict[str, list[tuple[str, str]]] = {}
    kind_words: dict[str, Counter] = {}
    headers = load_source_headers(sources_dir, log, design_strings, kind_words)
    no_structure = structure.no_structure_kinds()
    design_towers: dict[str, list[dict]] = {}
    with_design_text = 0
    ranges: list[tuple[int | None, int | None, str]] = []

    _prepare_out(out, log)
    features: list[dict] = []
    seen: dict[str, Path] = {}
    counts: dict[str, Counter] = {k: Counter() for k in ("status", "kind", "region", "verification", "material")}
    hidden = rentable = registered = stories = skipped = 0
    cited: Counter[str] = Counter()
    any_fixture = fixtures

    for path in files:
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            log.warn(f"skipped, not valid JSON: {e}", path)
            skipped += 1
            continue
        problem = check_record(rec)
        if problem:
            log.warn(f"skipped: {problem}", path)
            skipped += 1
            continue
        if rec.get("hidden"):
            hidden += 1
            continue
        rid = rec["id"]
        if rid in seen:
            log.warn(f"skipped duplicate id {rid} (first seen in {seen[rid]})", path)
            skipped += 1
            continue
        seen[rid] = path
        any_fixture = any_fixture or bool(rec.get("fixture"))

        for field in ("kind", "status", "verification", "material"):
            allowed = vocab.get(field)
            if allowed and rec.get(field) is not None and rec[field] not in allowed:
                log.warn(f"{rid}: {field} {rec[field]!r} is not in data/vocab.json", path)

        story = stories_dir / f"{rid}.md"
        if story.is_file():
            rec["story_html"] = markdown_to_html(story.read_text(encoding="utf-8"), title=rec.get("name"))
            stories += 1
        else:
            # A plain summary written from the record alone, labelled as such on the page.
            rec["auto_summary"] = auto_summary.summarize(rec)
        texts, has_design = tower_design_texts(rec, design_strings)
        is_structure = rec["kind"] not in no_structure
        with_design_text += has_design and is_structure
        dids = design_names.tower_designs(texts)
        if dids:
            rec["design_ids"] = dids
            for did in dids:
                design_towers.setdefault(did, []).append(design_entry(rec, did, texts))
        _write_json(out / "t" / f"{rid}.json", rec)
        feat = feature(rec, this_year, dids)
        features.append(feat)
        if is_structure:
            # "Lookouts standing in 1935" counts structures; sites with no structure are left out.
            ranges.append((feat["properties"].get("y0"), feat["properties"].get("y1"), rec["status"]))
        counts["status"][rec["status"]] += 1
        counts["kind"][rec["kind"]] += 1
        counts["region"][rec["region"]] += 1
        counts["verification"][rec["verification"]] += 1
        if rec.get("material"):
            counts["material"][rec["material"]] += 1
        rentable += is_rentable(rec)
        registered += bool(rec.get("registers"))
        for s in rec.get("sources") or []:
            if isinstance(s, dict) and isinstance(s.get("source"), str):
                cited[s["source"]] += 1

    if strict and skipped:
        raise SystemExit(f"{skipped} record(s) failed checks (see warnings above); --strict is set")

    features.sort(key=lambda f: f["properties"]["i"])
    _write_json(out / "towers.geojson", {"type": "FeatureCollection", "features": features})

    structures_n = sum(1 for f in features if f["properties"]["k"] not in no_structure)
    designs_meta = write_designs(out, designs_path if designs_path is not None else DATA / "designs.json", design_towers, with_design_text, structures_n, log)
    kinds_meta = write_structure_kinds(out, structure_kinds_path if structure_kinds_path is not None else structure.VOCAB_FILE,
                                       counts["kind"], counts["material"], kind_words, log)
    source_ids = list(KNOWN_SOURCES) + sorted((set(headers) | set(cited)) - set(KNOWN_SOURCES))
    sources = []
    for sid in source_ids:
        known = KNOWN_SOURCES.get(sid, {})
        head = headers.get(sid, {})
        title = head.get("title") or known.get("title") or sid
        sources.append(
            {
                "id": sid,
                "title": title,
                "url": head.get("url") or known.get("url"),
                "license": head.get("license") or known.get("license"),
                "credit": known.get("credit") or title,
                "retrieved": head.get("retrieved"),
                "records": head.get("records"),
                "towers": cited.get(sid, 0),
            }
        )

    meta = {
        "built": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "fixtures": any_fixture,
        "counts": {
            # Every site shown on the map, and of those the structures and the sites with no
            # structure (camps, lookout trees, bare points; the map leaves those off by default).
            "total": len(features),
            "structures": kinds_meta.get("structures", structures_n),
            "no_structure": kinds_meta.get("no_structure", len(features) - structures_n),
            "hidden": hidden,
            "skipped": skipped,
            "rentable": rentable,
            "registered": registered,
            "stories": stories,
            "by_status": dict(sorted(counts["status"].items())),
            "by_kind": dict(sorted(counts["kind"].items())),
            "by_region": dict(sorted(counts["region"].items())),
            "by_verification": dict(sorted(counts["verification"].items())),
            "by_material": dict(sorted(counts["material"].items())),
        },
        "history": history_counts(ranges, this_year),
        "designs": designs_meta,
        "sources": sources,
        "format": {"towers.geojson": GEOJSON_FORMAT},
    }
    _write_json(out / "meta.json", meta)
    size = (out / "towers.geojson").stat().st_size
    hist = meta["history"]
    log.info(
        f"Wrote {len(features)} lookouts ({structures_n} structures, {len(features) - structures_n} with no structure; "
        f"{hidden} hidden, {skipped} skipped, {stories} stories) "
        f"to {out}; towers.geojson is {size / 1024:.0f} KiB"
    )
    log.info(
        f"Dates: {hist['with_start']} with a start year, {hist['with_end']} with an end year, "
        f"{hist['no_dates']} with neither ({hist['standing_no_start']} of the standing ones have no start year). "
        f"Designs: {designs_meta['recognised']} lookouts with a recognisable design, "
        f"{designs_meta['with_design_text'] - designs_meta['recognised']} more with design wording we could not match."
    )
    return meta


def _fixture_banner(log: Log, towers_dir: Path) -> None:
    bar = "=" * 78
    lines = [
        bar,
        "USING FIXTURE DATA (sample records), NOT THE REAL LOOKOUT DATABASE",
        f"  {towers_dir} has no tower records yet, so this build uses",
        f"  {FIXTURES}/towers instead. The site will show a 'Sample data' banner.",
        "  This goes away by itself once data/towers/ has records.",
        bar,
    ]
    print("\n".join(lines))
    if log.gha:
        print("::warning title=Site built from fixture data::data/towers/ is empty, so the site shows the sample records in web/fixtures/ with a 'Sample data' banner.")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as fh:
                fh.write("## ⚠️ Site built from fixture data\n\n`data/towers/` is empty, so this deploy shows the sample records from `web/fixtures/` with a visible *Sample data* banner.\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--towers", type=Path, default=DATA / "towers", help="canonical tower records (default: data/towers)")
    ap.add_argument("--stories", type=Path, default=None, help="story Markdown files (default: data/stories)")
    ap.add_argument("--photos", type=Path, default=None, help="unused; kept so old invocations still parse (photos now resolve via site.config.json's photosBase)")
    ap.add_argument("--sources", type=Path, default=DATA / "sources", help="source extracts (default: data/sources)")
    ap.add_argument("--vocab", type=Path, default=DATA / "vocab.json")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output folder (default: web/public/data)")
    ap.add_argument("--fallback-fixtures", action="store_true", help="use web/fixtures when the towers folder is empty")
    ap.add_argument("--strict", action="store_true", help="fail if any record is skipped")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    log = Log(args.quiet)

    towers, stories, photos = args.towers, args.stories, args.photos
    has_records = towers.is_dir() and any(towers.rglob("*.json"))
    fixtures = False
    if not has_records:
        if not args.fallback_fixtures:
            print(
                f"No tower records found in {towers}.\n"
                "Use --fallback-fixtures to build from the sample records in web/fixtures, "
                "or --towers to point at another folder.",
                file=sys.stderr,
            )
            return 2
        _fixture_banner(log, towers)
        towers = FIXTURES / "towers"
        stories = stories or FIXTURES / "stories"
        photos = photos or FIXTURES / "photos"
        fixtures = True
    stories = stories or DATA / "stories"
    photos = photos or DATA / "photos"

    build(towers, stories, photos, args.sources, args.vocab, args.out, fixtures=fixtures, strict=args.strict, log=log)
    if log.warnings:
        log.info(f"{log.warnings} warning(s); see above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
