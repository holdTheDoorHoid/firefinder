"""Shared shape and helpers for lookout-association project sources.

Many lookout associations (FFLA chapters, "Friends of ..." groups, the Catskill Fire Tower
Project...) publish year-by-year reports of the work they did on particular lookouts:
restorations, repairs, assessments, rebuilds. Each such association is its own module in
pipeline/regional/ and writes its own data/sources/<source>.json, but all of them use the one
record shape below, so pipeline/merge.py treats them as one source family
(``ASSOCIATION_SOURCES`` there) and a new association needs no new merge logic. DESIGN.md 3.7
has the owner-level description and the "adding an association" steps; this file is the code.

The shape (a normal DESIGN.md 3.2 source record, plus a few conventions):

    {
      "key": "<source>:<state>:<slug>",         # unique and stable; the lookout, not the report
      "url": "https://...",                      # the association's best page for this lookout
      "name": "Numa Ridge Lookout",              # the association's own name for it
      "country": "US", "region": "MT", "county": null,
      "lat": 48.88402, "lon": -114.17898,        # see "Position" below; may be null
      "elevation_m": null, "type_raw": "...", "kind": "unknown",
      "status_raw": null, "status": "standing",  # what the reports show; "unknown" if unclear
      "registers": [], "built": null,
      "agency": "National Park Service (Glacier National Park)",
      "events": [{"year": 1934, "event": "built", "note": "...", "from": "<source>",
                  "source_url": "https://...", "source_urls": ["https://...", "..."]}],
      "photos": [], "links": [{"label": "...", "url": "..."}], "rental": null,
      "extra": {
        "association": {"name": "...", "url": "https://..."},
        "forest": "Kootenai National Forest",   # the unit the association groups it under
        "design": "L-4 cab on a 10-ft timber tower", "height_ft": 10,
        "staffing_hint": "staffed",              # staffed | emergency | volunteer | unstaffed
        "ownership": "federal",                  # federal | state | tribal | local | private
        "aliases": ["Coal Ridge Cabin"],         # other names the association uses
        "position_from": "nhlr:US 38"            # where lat/lon were copied from, if they were
      }
    }

Events are dated facts about the structure, each in our own words (a short note, at most
NOTE_MAX characters) with the association page that reports them in ``source_url`` (and
``source_urls`` when several pages do). Use the event names in data/vocab.json: ``built``,
``replaced``/``rebuilt`` (a later structure), ``restored`` (repair, rehabilitation,
re-roofing, repainting), ``modified`` (something added or changed), ``assessed`` (a condition
assessment), ``destroyed``, ``abandoned``, ``fire``, ``staffed``..., ``other`` (with a note).
One record may not have two events with the same name and year (merge keeps the first only):
put both facts in one note.

Position. Associations rarely publish coordinates. When the lookout is already in a register
or list we fetched, copy its position with ``position_from`` (a source record key such as
"nhlr:US 38") instead of leaving the record without one: merge then places the report on the
right tower by position, and ``extra.position_from`` says where the point came from. merge
counts association positions as part of the registers' lineage, so they never make a tower
"facts"-verified on their own. A lookout in no list at all needs a position from somewhere
else (say where in ``extra.position_note``); a record with none is matched by name only.

Python 3.12 standard library only (pdftotext, from poppler, is used if present to read PDFs).
"""

from __future__ import annotations

import html as _html
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import write_source_json  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
SOURCES_DIR = REPO_ROOT / "data" / "sources"
VOCAB_PATH = REPO_ROOT / "data" / "vocab.json"

FAMILY = "association_projects"
NOTE_MAX = 220
STAFFING_HINTS = ("staffed", "emergency", "volunteer", "unstaffed")
OWNERSHIPS = ("federal", "state", "tribal", "local", "private")
# Sources whose records give a lookout's position; checked in this order by source_index().
POSITION_SOURCES = ("nhlr", "fflos", "ffla", "ridb", "firelookout_com", "fire_lookouts_org")


# ---------------------------------------------------------------------------------------
# Documents (the reports a module cites) and events
# ---------------------------------------------------------------------------------------


class DocSet:
    """The association's reports, by short id, so each event can cite them by id and the
    record gets real URLs. ``texts`` (id -> plain text) is filled by the module when it has
    read the report, and lets ``check_citations`` verify the curated facts against it."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.docs: dict[str, dict] = {}
        self.texts: dict[str, str] = {}

    def add(self, doc_id: str, url: str, label: str, year: int | None = None) -> None:
        if doc_id in self.docs:
            raise ValueError(f"duplicate document id {doc_id!r}")
        self.docs[doc_id] = {"url": url, "label": label, "year": year}

    def url(self, doc_id: str) -> str:
        return self.docs[doc_id]["url"]

    def event(self, year: int | None, event: str, note: str | None, cite=()) -> dict:
        """An event citing the given document ids (the first is ``source_url``). ``_cite`` is
        removed again by strip_private() before the extract is written."""
        cite = [cite] if isinstance(cite, str) else list(cite)
        ev: dict = {"year": year, "event": event, "note": note, "from": self.source}
        if cite:
            urls = [self.url(c) for c in cite]
            ev["source_url"] = urls[0]
            if len(urls) > 1:
                ev["source_urls"] = urls
        ev["_cite"] = cite
        return ev


def strip_private(records: list[dict]) -> None:
    for r in records:
        for e in r.get("events") or []:
            e.pop("_cite", None)


# ---------------------------------------------------------------------------------------
# Positions copied from the registers and lists we already fetched
# ---------------------------------------------------------------------------------------


def source_index(sources_dir: pathlib.Path | None = None, names=POSITION_SOURCES) -> dict[str, dict]:
    """Record key -> record, for the sources a position may be copied from."""
    index: dict[str, dict] = {}
    for name in names:
        path = (sources_dir or SOURCES_DIR) / f"{name}.json"
        if not path.exists():
            continue
        for r in json.loads(path.read_text(encoding="utf-8")).get("records") or []:
            if isinstance(r, dict) and isinstance(r.get("key"), str):
                index[r["key"]] = r
    return index


def position_from(key: str, index: dict[str, dict]) -> tuple[float, float]:
    r = index.get(key)
    if r is None or not isinstance(r.get("lat"), (int, float)) or not isinstance(r.get("lon"), (int, float)):
        raise KeyError(f"no source record with coordinates has the key {key!r}")
    return round(float(r["lat"]), 5), round(float(r["lon"]), 5)


# ---------------------------------------------------------------------------------------
# Building and checking records
# ---------------------------------------------------------------------------------------


def lookout_record(
    *,
    source: str,
    association: dict,
    slug: str,
    name: str,
    region: str,
    url: str,
    position_key: str | None = None,
    index: dict[str, dict] | None = None,
    county: str | None = None,
    forest: str | None = None,
    agency: str | None = None,
    ownership: str | None = None,
    design: str | None = None,
    height_ft: float | None = None,
    staffing: str | None = None,
    status: str = "unknown",
    kind: str = "unknown",
    type_raw: str | None = None,
    aliases: list[str] | None = None,
    events: list[dict] | None = None,
    links: list[dict] | None = None,
    extra: dict | None = None,
) -> dict:
    """One association record in the shared shape (see the module docstring)."""
    lat = lon = None
    ex: dict = {"association": {"name": association["name"], "url": association["url"]}}
    if position_key:
        lat, lon = position_from(position_key, index if index is not None else source_index())
        ex["position_from"] = position_key
    for k, v in (("forest", forest), ("design", design), ("height_ft", height_ft),
                 ("staffing_hint", staffing), ("ownership", ownership), ("aliases", aliases or None)):
        if v is not None:
            ex[k] = v
    ex.update(extra or {})
    return {
        "key": f"{source}:{region.lower()}:{slug}",
        "url": url,
        "name": name,
        "country": "US",
        "region": region.upper(),
        "county": county,
        "lat": lat,
        "lon": lon,
        "elevation_m": None,
        "type_raw": type_raw,
        "kind": kind,
        "status_raw": None,
        "status": status,
        "registers": [],
        "built": None,
        "agency": agency,
        "events": sorted(events or [], key=lambda e: (e["year"] if isinstance(e.get("year"), int) else 9999, e["event"])),
        "photos": [],
        "links": links or [],
        "rental": None,
        "extra": ex,
    }


def _http(u: object) -> bool:
    return isinstance(u, str) and u.startswith(("http://", "https://"))


def validate_records(records: list[dict], *, source: str, vocab_path: pathlib.Path | None = None,
                     this_year: int | None = None) -> list[str]:
    """Problems that would make merge ignore or mangle a record, as readable strings."""
    import datetime as _dt

    vocab = json.loads((vocab_path or VOCAB_PATH).read_text(encoding="utf-8"))
    events_ok = set(vocab.get("event") or [])
    kinds_ok, status_ok = set(vocab.get("kind") or {}), set(vocab.get("status") or {})
    last_year = this_year or _dt.date.today().year
    problems: list[str] = []
    seen_keys: set[str] = set()
    for r in records:
        k = r.get("key")
        where = k or "<no key>"
        if not isinstance(k, str) or not k.startswith(f"{source}:"):
            problems.append(f"{where}: key must start with '{source}:'")
        elif k in seen_keys:
            problems.append(f"{where}: duplicate key")
        seen_keys.add(str(k))
        if not r.get("name"):
            problems.append(f"{where}: no name")
        if not _http(r.get("url")):
            problems.append(f"{where}: url must be http(s)")
        if (r.get("lat") is None) != (r.get("lon") is None):
            problems.append(f"{where}: lat and lon must both be given or both null")
        if r.get("kind") not in kinds_ok:
            problems.append(f"{where}: kind {r.get('kind')!r} is not in vocab.kind")
        if r.get("status") not in status_ok:
            problems.append(f"{where}: status {r.get('status')!r} is not in vocab.status")
        ex = r.get("extra") or {}
        assoc = ex.get("association")
        if not (isinstance(assoc, dict) and assoc.get("name") and _http(assoc.get("url"))):
            problems.append(f"{where}: extra.association needs a name and an http(s) url")
        if ex.get("staffing_hint") is not None and ex["staffing_hint"] not in STAFFING_HINTS:
            problems.append(f"{where}: extra.staffing_hint {ex['staffing_hint']!r} is not one of {STAFFING_HINTS}")
        if ex.get("ownership") is not None and ex["ownership"] not in OWNERSHIPS:
            problems.append(f"{where}: extra.ownership {ex['ownership']!r} is not one of {OWNERSHIPS}")
        if ex.get("position_from") is None and r.get("lat") is not None and not ex.get("position_note"):
            problems.append(f"{where}: a position needs extra.position_from or extra.position_note saying where it came from")
        names: set[tuple] = set()
        for e in r.get("events") or []:
            tag = f"{where} {e.get('event')} {e.get('year')}"
            if e.get("event") not in events_ok:
                problems.append(f"{tag}: event {e.get('event')!r} is not in vocab.event")
            y = e.get("year")
            if y is not None and not (isinstance(y, int) and not isinstance(y, bool) and 1800 <= y <= last_year):
                problems.append(f"{tag}: year must be a whole year 1800-{last_year} or null")
            note = e.get("note")
            if note is not None and not (isinstance(note, str) and note.strip() and len(note) <= NOTE_MAX):
                problems.append(f"{tag}: note must be a non-empty string of at most {NOTE_MAX} characters")
            if e.get("event") == "other" and not note:
                problems.append(f"{tag}: an 'other' event needs a note")
            if not _http(e.get("source_url")):
                problems.append(f"{tag}: every event needs an http(s) source_url")
            for u in e.get("source_urls") or []:
                if not _http(u):
                    problems.append(f"{tag}: source_urls has a non-http(s) entry")
            if e.get("from") != source:
                problems.append(f"{tag}: from must be '{source}'")
            if (e.get("event"), y) in names:
                problems.append(f"{tag}: two events with the same name and year (merge keeps one); join them in one note")
            names.add((e.get("event"), y))
    return problems


def check_citations(records: list[dict], name_keys: dict[str, list[str]], docs: DocSet) -> list[str]:
    """Check each event against the reports it cites, where their text was read: the report
    must mention the lookout (any of ``name_keys[record key]``) and, unless it is that year's
    own report, the event's year. Catches typos and facts filed under the wrong report. A
    cited report whose text was not read is skipped, and listed once at the end."""
    problems: list[str] = []
    unread: set[str] = set()
    for r in records:
        keys = [norm(k) for k in name_keys.get(r["key"], [])]
        for e in r.get("events") or []:
            for doc_id in e.get("_cite") or []:
                text = docs.texts.get(doc_id)
                if text is None:
                    unread.add(doc_id)
                    continue
                tag = f"{r['key']} {e['event']} {e.get('year')} cites {doc_id}"
                if keys and not any(k in text for k in keys):
                    problems.append(f"{tag}: the report never mentions {name_keys[r['key']]}")
                y = e.get("year")
                if y is not None and docs.docs[doc_id].get("year") != y and str(y) not in text:
                    problems.append(f"{tag}: the report never mentions {y}")
    if unread:
        problems.append("(not checked: text of " + ", ".join(sorted(unread)) + " was not read)")
    return problems


def write_association_source(
    out_path: pathlib.Path,
    *,
    source: str,
    association: dict,
    url: str,
    retrieved: str,
    license_: str,
    records: list[dict],
    credit: str | None = None,
    title: str | None = None,
) -> None:
    """Validate (raising on any problem) and write data/sources/<source>.json with the family
    marker merge.py looks for."""
    strip_private(records)
    problems = validate_records(records, source=source)
    if problems:
        raise ValueError("association records are not valid:\n  " + "\n  ".join(problems))
    write_source_json(
        out_path,
        source=source,
        title=title or association["name"],
        url=url,
        retrieved=retrieved,
        license_=license_,
        records=records,
        header_extra={"family": FAMILY, "association": dict(association), "credit": credit or association["name"]},
    )


# ---------------------------------------------------------------------------------------
# Reading reports: HTML posts and PDFs
# ---------------------------------------------------------------------------------------


def norm(text: str) -> str:
    """Lower case, one space between words, plain quotes and dashes: for comparing text."""
    t = text.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    t = t.replace("–", "-").replace("—", "-").replace("‑", "-").replace("×", "x")
    return re.sub(r"\s+", " ", t).strip()


def html_sections(page: str, start_marker: str = 'class="entry-content') -> list[tuple[str, list[str]]]:
    """A WordPress post as [(heading, [paragraph, ...])]; text before the first heading has the
    heading ''. Scripts and styles are dropped; entities decoded."""
    i = page.find(start_marker)
    body = page[i:] if i >= 0 else page
    j = body.find("</article>")
    body = body[:j] if j >= 0 else body
    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", body, flags=re.S)
    out: list[tuple[str, list[str]]] = [("", [])]
    for part in re.split(r"(<h[1-6][^>]*>.*?</h[1-6]>)", body, flags=re.S):
        m = re.match(r"<h[1-6][^>]*>(.*?)</h[1-6]>", part, flags=re.S)
        if m:
            out.append((re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))).strip(), []))
            continue
        for pm in re.findall(r"<(?:p|li|figcaption)[^>]*>(.*?)</(?:p|li|figcaption)>", part, flags=re.S):
            t = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", "", pm))).strip()
            if t:
                out[-1][1].append(t)
    return out


def html_text(page: str) -> str:
    return "\n".join(h + "\n" + "\n".join(ps) for h, ps in html_sections(page))


def squash_doubles(text: str) -> str:
    """Web pages printed to PDF often carry every word twice ("First First permanent
    permanent"); drop a word that repeats the one before it. (A real "had had" is lost too,
    which is fine for finding names and years, the only thing this text is used for.)"""
    out: list[str] = []
    for w in text.split():
        if out and out[-1] == w:
            continue
        out.append(w)
    return " ".join(out)


def pdf_text(data: bytes) -> str | None:
    """Plain text of a PDF through poppler's pdftotext, or None when it is not installed or
    cannot read the file."""
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        src = pathlib.Path(tmp) / "doc.pdf"
        src.write_bytes(data)
        try:
            res = subprocess.run([exe, str(src), "-"], capture_output=True, timeout=120, check=False)
        except (OSError, subprocess.SubprocessError):
            return None
    return res.stdout.decode("utf-8", errors="replace") if res.stdout else None


def unmatched_headings(sections: list[tuple[str, list[str]]], name_keys: list[str]) -> list[str]:
    """Headings of a post that name none of the known lookouts: new lookouts to add, or
    section titles ("Assessments", "Glacier National Park") to ignore."""
    keys = [norm(k) for k in name_keys]
    return [h for h, _ in sections if h and not any(k in norm(h) for k in keys)]
