#!/usr/bin/env python3
"""Check the canonical tower records in data/towers (DESIGN.md section 3.3).

Errors (exit status 1):
  * a file that is not a JSON object, or is missing a required key
  * an id that is not us-<st>-<slug>, does not match its file name, or is used twice
  * coordinates that are missing, not numbers, or outside the United States
  * a kind, status, ownership, access level, staffing status, verification or event name
    that is not in data/vocab.json
  * malformed lists: registers, events, photos, links, sources, conflicts, locked

Research files (data/research/<id>.json, research/STORY_GUIDE.md) and stories
(data/stories/<id>.md) are checked too. Errors: a file that is not a JSON object, an id that
does not match its file name or any tower, a missing or malformed date, summary, source list or
citation, a story footnote [^n] with no definition or no research source n. Warnings: values
outside data/vocab.json (the merge leaves those out), a summary over 200 characters, photos
without credit or licence, a story without research or the other way round. --strict makes
warnings errors.

Warnings (reported, exit status 0):
  * coordinates outside the record's own state (border lookouts, or a bad source row)
  * a record kept in a folder other than data/towers/<region>/

An empty or missing towers folder is fine (the site then builds from fixtures).

Usage:
    python3 pipeline/validate.py [--towers data/towers] [--research data/research]
                                 [--stories data/stories] [--vocab data/vocab.json] [--strict]

Python 3.12, standard library only.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from state_bbox import STATE_BBOX  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"

ID_RE = re.compile(r"^(?P<country>[a-z]{2})-(?P<region>[a-z0-9]{1,3})-[a-z0-9]+(?:-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

REQUIRED = [
    "id", "name", "other_names", "country", "region", "county", "location", "elevation_m",
    "kind", "design", "height_m", "status", "registers", "agency", "ownership", "access",
    "staffing", "visit", "rental", "events", "photos", "links", "sources", "conflicts",
    "verification", "locked", "hidden", "hidden_reason", "updated",
]
# Written by every merge since 2026-10-08 (pipeline/structure.py); checked when present so tower
# files from an older merge still validate until the next one.

# US states, DC and territories. The 50 states and DC come from state_bbox (padded boxes);
# territories are added here.
TERRITORY_BBOX = {
    "PR": (17.8, 18.6, -67.4, -65.2),
    "VI": (17.6, 18.5, -65.1, -64.5),
    "GU": (13.2, 13.7, 144.6, 145.0),
    "AS": (-14.6, -11.0, -171.1, -168.1),
    "MP": (14.0, 20.6, 144.8, 146.1),
    "DC": (38.7, 39.0, -77.2, -76.9),
}
US_BOXES = {**STATE_BBOX, **TERRITORY_BBOX}


def _num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def in_box(box: tuple, lat: float, lon: float) -> bool:
    lat_min, lat_max, lon_min, lon_max = box
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def vocab_set(vocab: dict, key: str) -> set:
    v = vocab.get(key)
    if isinstance(v, dict):
        return set(v)
    if isinstance(v, list):
        return set(v)
    return set()


def check(rec: object, path: Path, vocab: dict) -> tuple[list[str], list[str]]:
    errs: list[str] = []
    warns: list[str] = []
    if not isinstance(rec, dict):
        return ["not a JSON object"], warns
    missing = [k for k in REQUIRED if k not in rec]
    if missing:
        errs.append(f"missing keys: {', '.join(missing)}")

    rid = rec.get("id")
    m = ID_RE.match(rid) if isinstance(rid, str) else None
    if not m or len(rid) > 120:
        errs.append(f"id {rid!r} is not of the form us-<st>-<slug>")
    else:
        if path.stem != rid:
            errs.append(f"file name {path.name} does not match id {rid}")
        region = rec.get("region")
        if isinstance(region, str) and m.group("region") != region.lower():
            # ids never change, so a later region fix may leave them apart; flag, don't fail
            warns.append(f"id state {m.group('region')} differs from region {region}")
        if path.parent.name != m.group("region"):
            warns.append(f"kept in {path.parent.name}/, expected {m.group('region')}/")

    if not isinstance(rec.get("name"), str) or not rec["name"].strip():
        errs.append("name is missing or empty")
    if rec.get("country") != "US":
        errs.append(f"country {rec.get('country')!r} is not US")
    region = rec.get("region")
    if not isinstance(region, str) or region.upper() not in US_BOXES:
        errs.append(f"region {region!r} is not a US state or territory code")

    loc = rec.get("location")
    if not isinstance(loc, dict) or not _num(loc.get("lat")) or not _num(loc.get("lon")):
        errs.append("location.lat / location.lon missing or not numbers")
    else:
        lat, lon = loc["lat"], loc["lon"]
        if not any(in_box(b, lat, lon) for b in US_BOXES.values()):
            errs.append(f"coordinates {lat}, {lon} are outside the United States")
        elif isinstance(region, str) and region.upper() in US_BOXES and not in_box(US_BOXES[region.upper()], lat, lon):
            warns.append(f"coordinates {lat}, {lon} are outside {region}")
        if loc.get("precision") not in (None, "exact", "approximate"):
            errs.append(f"location.precision {loc.get('precision')!r} is not exact/approximate")

    for key, vkey in (("kind", "kind"), ("status", "status"), ("ownership", "ownership"),
                      ("verification", "verification")):
        allowed = vocab_set(vocab, vkey)
        if allowed and rec.get(key) not in allowed:
            errs.append(f"{key} {rec.get(key)!r} is not in vocab.{vkey}")
    if rec.get("material") is not None and rec["material"] not in vocab_set(vocab, "material"):
        errs.append(f"material {rec['material']!r} is not in vocab.material")
    if rec.get("material") is not None and not (isinstance(rec.get("material_from"), str) and rec["material_from"]):
        errs.append("material has no material_from")
    roles = rec.get("roles", [])
    if not isinstance(roles, list) or any(r not in vocab_set(vocab, "role") for r in roles):
        errs.append(f"roles {roles!r} is not a list of vocab.role values")
    access = rec.get("access")
    if not isinstance(access, dict) or access.get("level") not in vocab_set(vocab, "access"):
        errs.append(f"access.level {access.get('level') if isinstance(access, dict) else access!r} is not in vocab.access")
    staffing = rec.get("staffing")
    if not isinstance(staffing, dict) or staffing.get("status") not in vocab_set(vocab, "staffing"):
        errs.append("staffing.status is not in vocab.staffing")
    if not isinstance(rec.get("visit"), dict):
        errs.append("visit is not an object")

    if rec.get("summary") is not None and not (isinstance(rec["summary"], str) and rec["summary"].strip()):
        errs.append("summary is neither null nor text")
    if rec.get("research") is not None and not isinstance(rec["research"], dict):
        errs.append("research is neither null nor an object")
    if rec.get("status_note") is not None and not (isinstance(rec["status_note"], str) and rec["status_note"].strip()):
        errs.append("status_note is neither null nor text")
    for key in ("elevation_m", "height_m"):
        if rec.get(key) is not None and not _num(rec.get(key)):
            errs.append(f"{key} is not a number")

    if not isinstance(rec.get("hidden"), bool):
        errs.append("hidden is not true/false")
    elif rec["hidden"] and not (isinstance(rec.get("hidden_reason"), str) and rec["hidden_reason"].strip()):
        errs.append("hidden record has no hidden_reason")

    events_ok = vocab_set(vocab, "event")
    lists = {
        "other_names": lambda x: isinstance(x, str) and x.strip(),
        "registers": lambda x: isinstance(x, dict) and isinstance(x.get("register"), str) and (x.get("number") or x.get("state_number")),
        "events": lambda x: isinstance(x, dict) and x.get("event") in events_ok and (x.get("year") is None or isinstance(x.get("year"), int))
            and (x.get("source_url") is None or _http(x.get("source_url"))),
        "photos": lambda x: isinstance(x, dict) and (x.get("url") or x.get("file")),
        "links": lambda x: isinstance(x, dict) and isinstance(x.get("label"), str) and x["label"].strip() and isinstance(x.get("url"), str) and (
            x["url"].startswith(("http://", "https://"))
            # a link to another tower page: relocated_from / relocated_to, by id
            or (str(x.get("kind") or "").startswith("relocated_") and isinstance(x.get("id"), str)
                and ID_RE.match(x["id"]) is not None and x["url"] == f"../{x['id']}/")),
        "sources": lambda x: isinstance(x, dict) and isinstance(x.get("source"), str) and isinstance(x.get("key"), str) and isinstance(x.get("fields", []), list),
        "conflicts": lambda x: isinstance(x, dict) and isinstance(x.get("field"), str) and isinstance(x.get("values", []), list),
        "locked": lambda x: isinstance(x, str),
    }
    for key, ok in lists.items():
        val = rec.get(key)
        if not isinstance(val, list):
            errs.append(f"{key} is not a list")
            continue
        bad = [i for i, x in enumerate(val) if not ok(x)]
        if bad:
            errs.append(f"{key}[{bad[0]}] is malformed" + (f" (and {len(bad) - 1} more)" if len(bad) > 1 else ""))
    if isinstance(rec.get("sources"), list) and not rec["sources"]:
        errs.append("sources is empty")
    photo_keys = ("file", "thumb", "url", "source_url", "credit", "license", "caption", "year")
    if isinstance(rec.get("photos"), list) and any(isinstance(p, dict) and not all(k in p for k in photo_keys) for p in rec["photos"]):
        warns.append("photo without the full {file, thumb, url, source_url, credit, license, caption, year} shape")
    rental = rec.get("rental")
    if rental is not None and not (isinstance(rental, dict) and "available" in rental):
        errs.append("rental is neither null nor an object with 'available'")
    if isinstance(rental, dict):
        for k in ("provider", "url", "manager", "status_note", "status_note_from", "source"):
            if rental.get(k) is not None and not (isinstance(rental[k], str) and rental[k].strip()):
                errs.append(f"rental.{k} is neither null nor text")
        if rental.get("source") not in (None, "ffla"):
            errs.append("rental.source is not 'ffla' (a rental from recreation.gov has no source key)")
    if not (isinstance(rec.get("updated"), str) and DATE_RE.match(rec["updated"])):
        errs.append("updated is not a YYYY-MM-DD date")
    return errs, warns


RESEARCH_FACT_KEYS = {"design", "height_m", "status", "status_note", "kind", "staffing", "access", "visit", "agency"}
EVENT_ALIASES = {"unstaffed", "decommissioned", "renovated", "restoration_completed"}  # see merge.RESEARCH_EVENT_ALIASES
FOOTNOTE_REF_RE = re.compile(r"\[\^([^\]\s]+)\](?!:)")
FOOTNOTE_DEF_RE = re.compile(r"^\[\^([^\]\s]+)\]:", re.M)


def _http(u: object) -> bool:
    return isinstance(u, str) and u.startswith(("http://", "https://"))


def check_research(data: object, path: Path, vocab: dict, tower_ids: set[str] | None) -> tuple[list[str], list[str]]:
    """Shape and vocabulary of one research file (research/STORY_GUIDE.md)."""
    errs: list[str] = []
    warns: list[str] = []
    if not isinstance(data, dict):
        return ["not a JSON object"], warns
    if data.get("id") != path.stem:
        errs.append(f"id {data.get('id')!r} does not match the file name")
    elif tower_ids is not None and data["id"] not in tower_ids:
        errs.append(f"no tower has the id {data['id']}")
    if not (isinstance(data.get("researched"), str) and DATE_RE.match(data["researched"])):
        errs.append("researched is not a YYYY-MM-DD date")
    summary = data.get("summary")
    if not (isinstance(summary, str) and summary.strip()):
        errs.append("summary is missing")
    elif len(summary) > 200:
        warns.append(f"summary is {len(summary)} characters (guide: 200 at most)")
    sources = data.get("sources")
    numbers: set = set()
    if not isinstance(sources, list) or not sources:
        errs.append("sources is missing or empty")
    else:
        for i, src in enumerate(sources):
            if not isinstance(src, dict) or not isinstance(src.get("n"), int):
                errs.append(f"sources[{i}] has no number n")
                continue
            if src["n"] in numbers:
                errs.append(f"source number {src['n']} is used twice")
            numbers.add(src["n"])
            if not _http(src.get("url")):
                errs.append(f"source {src['n']} has no http(s) url")
            if not (isinstance(src.get("title"), str) and src["title"].strip()):
                errs.append(f"source {src['n']} has no title")
            if src.get("accessed") is not None and not (isinstance(src["accessed"], str) and DATE_RE.match(src["accessed"])):
                warns.append(f"source {src['n']} accessed is not a YYYY-MM-DD date")

    def cites_ok(where: str, cite: object) -> None:
        if not isinstance(cite, list) or not cite:
            errs.append(f"{where} cites no source")
            return
        missing = [c for c in cite if c not in numbers]
        if missing:
            errs.append(f"{where} cites source(s) {missing} that are not in sources")

    facts = data.get("facts", {})
    if not isinstance(facts, dict):
        errs.append("facts is not an object")
        facts = {}
    for key in sorted(set(facts) - RESEARCH_FACT_KEYS):
        warns.append(f"facts.{key} is not a fact the merge uses")
    checks = {
        "status": lambda v: v in vocab_set(vocab, "status"),
        "kind": lambda v: v in vocab_set(vocab, "kind"),
        "height_m": _num,
        "design": lambda v: isinstance(v, str) and v.strip(),
        "agency": lambda v: isinstance(v, str) and v.strip(),
        "status_note": lambda v: isinstance(v, str) and v.strip(),
        "staffing": lambda v: isinstance(v, dict) and v.get("status") in vocab_set(vocab, "staffing"),
        "access": lambda v: isinstance(v, dict) and v.get("level") in vocab_set(vocab, "access"),
        "visit": lambda v: isinstance(v, dict) and set(v) <= {"climbable", "drive_up", "trail_note"},
    }
    for key, ok in checks.items():
        if key in facts and facts[key] is not None and not ok(facts[key]):
            warns.append(f"facts.{key} {facts[key]!r} is not valid (not applied)")
    for i, ev in enumerate(data.get("events") or []):
        if not isinstance(ev, dict):
            errs.append(f"events[{i}] is not an object")
            continue
        if ev.get("event") not in vocab_set(vocab, "event") and ev.get("event") not in EVENT_ALIASES:
            warns.append(f"event {ev.get('event')!r} ({ev.get('year')}) is not in vocab.event (left out of the timeline)")
        if ev.get("year") is not None and not isinstance(ev.get("year"), int):
            errs.append(f"events[{i}] year {ev.get('year')!r} is not a whole year")
        cites_ok(f"event {ev.get('event')!r} ({ev.get('year')})", ev.get("cite"))
    for i, c in enumerate(data.get("corrections") or []):
        if not isinstance(c, dict) or not c.get("field") or "proposed" not in c:
            errs.append(f"corrections[{i}] needs field and proposed")
            continue
        cites_ok(f"correction to {c['field']}", c.get("cite"))
    for i, ph in enumerate(data.get("photos") or []):
        if not isinstance(ph, dict) or not _http(ph.get("url")):
            errs.append(f"photos[{i}] has no http(s) url")
            continue
        for k in ("credit", "license"):
            if not (isinstance(ph.get(k), str) and ph[k].strip()):
                warns.append(f"photos[{i}] has no {k}")
    if data.get("confidence") not in (None, "high", "medium", "low"):
        warns.append(f"confidence {data.get('confidence')!r} is not high, medium or low")
    ver = data.get("verification")
    if ver is not None:
        if not isinstance(ver, dict):
            errs.append("verification is not an object")
        else:
            if ver.get("verdict") not in ("pass", "fixed", "fail"):
                errs.append(f"verification.verdict {ver.get('verdict')!r} is not pass, fixed or fail")
            if not (isinstance(ver.get("checked"), str) and DATE_RE.match(ver["checked"])):
                errs.append("verification.checked is not a YYYY-MM-DD date")
            for k in ("claims_checked", "unsupported_removed", "errors_fixed"):
                if k in ver and not (isinstance(ver[k], int) and ver[k] >= 0):
                    errs.append(f"verification.{k} is not a count")
    return errs, warns


def check_story(md: str, research: dict | None) -> tuple[list[str], list[str]]:
    """Every footnote reference [^n] has a definition and, with a research file, source n."""
    errs: list[str] = []
    warns: list[str] = []
    defs = FOOTNOTE_DEF_RE.findall(md)
    refs = FOOTNOTE_REF_RE.findall(md)
    for label in sorted(set(refs) - set(defs), key=str):
        errs.append(f"footnote [^{label}] has no definition")
    for label in sorted(set(defs) - set(refs), key=str):
        warns.append(f"footnote [^{label}] is defined but never used")
    if research is None:
        warns.append("no research file for this story")
    else:
        numbers = {str(s.get("n")) for s in research.get("sources") or [] if isinstance(s, dict)}
        for label in sorted(set(refs) | set(defs), key=str):
            if label not in numbers:
                errs.append(f"footnote [^{label}] has no matching source {label} in the research file")
    for label, body in re.findall(r"^\[\^([^\]\s]+)\]:\s*(.*)$", md, re.M):
        if not re.search(r"https?://", body):
            errs.append(f"footnote [^{label}] has no http(s) link")
    if not refs:
        warns.append("story has no footnotes")
    return errs, warns


def validate_research(research_dir: Path | None, stories_dir: Path | None, vocab: dict,
                      tower_ids: set[str] | None, log=print) -> tuple[int, int]:
    n_err = n_warn = 0
    found: dict[str, dict] = {}
    rfiles = sorted(research_dir.glob("*.json")) if research_dir and research_dir.is_dir() else []
    for path in rfiles:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            log(f"ERROR research/{path.name}: not valid JSON: {e}")
            n_err += 1
            continue
        errs, warns = check_research(data, path, vocab, tower_ids)
        if isinstance(data, dict):
            found[path.stem] = data
        for e in errs:
            log(f"ERROR research/{path.name}: {e}")
        for w in warns:
            log(f"warning research/{path.name}: {w}")
        n_err += len(errs)
        n_warn += len(warns)
    sfiles = sorted(stories_dir.glob("*.md")) if stories_dir and stories_dir.is_dir() else []
    for path in sfiles:
        errs, warns = check_story(path.read_text(encoding="utf-8"), found.get(path.stem))
        if tower_ids is not None and path.stem not in tower_ids:
            errs.append(f"no tower has the id {path.stem}")
        for e in errs:
            log(f"ERROR stories/{path.name}: {e}")
        for w in warns:
            log(f"warning stories/{path.name}: {w}")
        n_err += len(errs)
        n_warn += len(warns)
    for rid in sorted(set(found) - {p.stem for p in sfiles}):
        log(f"warning research/{rid}.json: no story file")
        n_warn += 1
    if rfiles or sfiles:
        log(f"Checked {len(rfiles)} research files and {len(sfiles)} stories: {n_err} error(s), {n_warn} warning(s).")
    return n_err, n_warn


def validate(towers_dir: Path, vocab_path: Path, log=print, research_dir: Path | None = None,
             stories_dir: Path | None = None, strict: bool = False) -> int:
    vocab = json.loads(vocab_path.read_text(encoding="utf-8"))
    files = sorted(towers_dir.rglob("*.json")) if towers_dir.is_dir() else []
    if not files:
        log(f"No tower records in {towers_dir}; nothing to check.")
        r_err, r_warn = validate_research(research_dir, stories_dir, vocab, None, log)
        return 1 if r_err or (strict and r_warn) else 0
    seen: dict[str, Path] = {}
    n_err = n_warn = 0
    warn_kinds: Counter = Counter()
    internal_links: list[tuple[Path, str]] = []
    for path in files:
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            log(f"ERROR {path}: not valid JSON: {e}")
            n_err += 1
            continue
        errs, warns = check(rec, path, vocab)
        if isinstance(rec, dict):
            for link in rec.get("links") or []:
                if isinstance(link, dict) and str(link.get("kind") or "").startswith("relocated_") and isinstance(link.get("id"), str):
                    internal_links.append((path, link["id"]))
        rid = rec.get("id") if isinstance(rec, dict) else None
        if isinstance(rid, str):
            if rid in seen:
                errs.append(f"duplicate id (also in {seen[rid]})")
            else:
                seen[rid] = path
        for e in errs:
            log(f"ERROR {path.relative_to(towers_dir)}: {e}")
        for w in warns:
            warn_kinds[re.sub(r"[-\d.]+, [-\d.]+", "<coords>", w.split(" (")[0])[:60]] += 1
        n_err += len(errs)
        n_warn += len(warns)
    for path, target in internal_links:
        if target not in seen:
            log(f"ERROR {path.relative_to(towers_dir)}: links to tower {target}, which does not exist")
            n_err += 1
    log(f"Checked {len(files)} tower records: {n_err} error(s), {n_warn} warning(s).")
    for kind, n in warn_kinds.most_common(8):
        log(f"  warning x{n}: {kind}")
    r_err, r_warn = validate_research(research_dir, stories_dir, vocab, set(seen), log)
    n_err += r_err
    n_warn += r_warn
    return 1 if n_err or (strict and n_warn) else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--towers", type=Path, default=DATA / "towers")
    ap.add_argument("--vocab", type=Path, default=DATA / "vocab.json")
    ap.add_argument("--research", type=Path, default=DATA / "research")
    ap.add_argument("--stories", type=Path, default=DATA / "stories")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = ap.parse_args(argv)
    return validate(args.towers, args.vocab, research_dir=args.research, stories_dir=args.stories, strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
