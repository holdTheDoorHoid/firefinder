#!/usr/bin/env python3
"""Build the data files the Firefinder website loads (DESIGN.md section 3.6).

Reads the canonical towers (data/towers/**/*.json), stories (data/stories/<id>.md), the
vocabularies (data/vocab.json) and source extract headers (data/sources/*.json), and writes
web/public/data/:

  towers.geojson   every visible lookout as a point, with short property names (below)
  t/<id>.json      the full canonical record, plus "story_html" when a story exists
  meta.json        counts, the source list with credit lines and retrieved dates, build date

A tower's "photos" pass through unchanged: pipeline/merge.py is what fills in file/thumb
(from data/photos_manifest.json, written by pipeline/mirror_photos.py), and the site resolves
them against web/site.config.json's "photosBase" at render time, not here -- this script does
not copy or validate photo files.

towers.geojson properties (absent optional keys mean null / false; see meta.json "format"):

  i  id            n  name           r  region (state code)
  k  kind          s  status         v  verification       a  access level
  b  built year    rt rentable (1)   rg on a register (1)   o  other names, "|"-joined
  c  county

Coordinates are [lon, lat] rounded to 5 decimal places.

Hidden records (hidden: true) are skipped. Records that fail basic checks are skipped with a
warning, so one bad file never takes the site down; pass --strict to fail instead.

If the towers folder has no records and --fallback-fixtures is given, the sample records in
web/fixtures/ are used instead, with a loud banner in the log and "fixtures": true in
meta.json (the site then shows a "Sample data" notice).

Python 3.12, standard library only.
"""

from __future__ import annotations

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
)


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
    for m in _INLINE_RE.finditer(text):
        out.append(_emphasis(_esc(text[pos : m.start()])))
        pos = m.end()
        if m.group("code") is not None:
            out.append(f"<code>{_esc(m.group('code'))}</code>")
        elif m.group("fn") is not None:
            out.append(notes.ref(m.group("fn")) if notes else _esc(m.group(0)))
        elif m.group("text") is not None:
            label = _inline(m.group("text"), None, allow_links=False)
            href = safe_href(m.group("url")) if allow_links else None
            out.append(f'<a href="{_esc(href)}">{label}</a>' if href else label)
        else:
            href = m.group("auto")
            out.append(f'<a href="{_esc(href)}">{_esc(href)}</a>' if allow_links else _esc(href))
    out.append(_emphasis(_esc(text[pos:])))
    return "".join(out)


_FRONT_MATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.S)
_FN_DEF_RE = re.compile(r"^\[\^([^\]\s]+)\]:\s?(.*)$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_HR_RE = re.compile(r"^(?:-{3,}|\*{3,}|_{3,})\s*$")
_UL_RE = re.compile(r"^[-*+]\s+(.*)$")
_OL_RE = re.compile(r"^\d{1,3}[.)]\s+(.*)$")


def markdown_to_html(md: str) -> str:
    """Convert story Markdown to HTML.

    Supports paragraphs, # headings (shifted down one level: the page title is the h1),
    *emphasis*, **strong**, `code`, [links](https://...), <https://autolinks>, "-" and "1."
    lists, > blockquotes, --- rules and footnotes ([^1] with "[^1]: text" definitions).
    Everything else, including any raw HTML, is escaped and shown as text. Links keep only
    http(s), mailto, relative and #fragment URLs.
    """
    text = md.replace("\r\n", "\n").replace("\r", "\n")
    text = _FRONT_MATTER_RE.sub("", text, count=1)
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


def feature(rec: dict) -> dict:
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


def load_source_headers(sources_dir: Path, log: Log) -> dict[str, dict]:
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
        headers[sid] = {
            "title": data.get("title"),
            "url": data.get("url"),
            "license": data.get("license"),
            "retrieved": data.get("retrieved"),
            "records": len(data["records"]) if isinstance(data.get("records"), list) else None,
        }
    return headers


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
) -> dict:
    log = log or Log()
    files = sorted(towers_dir.rglob("*.json")) if towers_dir.is_dir() else []
    vocab = json.loads(vocab_path.read_text(encoding="utf-8")) if vocab_path.is_file() else {}

    _prepare_out(out, log)
    features: list[dict] = []
    seen: dict[str, Path] = {}
    counts: dict[str, Counter] = {k: Counter() for k in ("status", "kind", "region", "verification")}
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

        for field in ("kind", "status", "verification"):
            allowed = vocab.get(field)
            if allowed and rec[field] not in allowed:
                log.warn(f"{rid}: {field} {rec[field]!r} is not in data/vocab.json", path)

        story = stories_dir / f"{rid}.md"
        if story.is_file():
            rec["story_html"] = markdown_to_html(story.read_text(encoding="utf-8"))
            stories += 1
        _write_json(out / "t" / f"{rid}.json", rec)
        features.append(feature(rec))
        counts["status"][rec["status"]] += 1
        counts["kind"][rec["kind"]] += 1
        counts["region"][rec["region"]] += 1
        counts["verification"][rec["verification"]] += 1
        rentable += is_rentable(rec)
        registered += bool(rec.get("registers"))
        for s in rec.get("sources") or []:
            if isinstance(s, dict) and isinstance(s.get("source"), str):
                cited[s["source"]] += 1

    if strict and skipped:
        raise SystemExit(f"{skipped} record(s) failed checks (see warnings above); --strict is set")

    features.sort(key=lambda f: f["properties"]["i"])
    _write_json(out / "towers.geojson", {"type": "FeatureCollection", "features": features})

    headers = load_source_headers(sources_dir, log)
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
            "total": len(features),
            "hidden": hidden,
            "skipped": skipped,
            "rentable": rentable,
            "registered": registered,
            "stories": stories,
            "by_status": dict(sorted(counts["status"].items())),
            "by_kind": dict(sorted(counts["kind"].items())),
            "by_region": dict(sorted(counts["region"].items())),
            "by_verification": dict(sorted(counts["verification"].items())),
        },
        "sources": sources,
        "format": {"towers.geojson": GEOJSON_FORMAT},
    }
    _write_json(out / "meta.json", meta)
    size = (out / "towers.geojson").stat().st_size
    log.info(
        f"Wrote {len(features)} lookouts ({hidden} hidden, {skipped} skipped, {stories} stories) "
        f"to {out}; towers.geojson is {size / 1024:.0f} KiB"
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
