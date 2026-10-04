#!/usr/bin/env python3
"""Check the canonical tower records in data/towers (DESIGN.md section 3.3).

Errors (exit status 1):
  * a file that is not a JSON object, or is missing a required key
  * an id that is not us-<st>-<slug>, does not match its file name, or is used twice
  * coordinates that are missing, not numbers, or outside the United States
  * a kind, status, ownership, access level, staffing status, verification or event name
    that is not in data/vocab.json
  * malformed lists: registers, events, photos, links, sources, conflicts, locked

Warnings (reported, exit status 0):
  * coordinates outside the record's own state (border lookouts, or a bad source row)
  * a record kept in a folder other than data/towers/<region>/

An empty or missing towers folder is fine (the site then builds from fixtures).

Usage:
    python3 pipeline/validate.py [--towers data/towers] [--vocab data/vocab.json]

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
    access = rec.get("access")
    if not isinstance(access, dict) or access.get("level") not in vocab_set(vocab, "access"):
        errs.append(f"access.level {access.get('level') if isinstance(access, dict) else access!r} is not in vocab.access")
    staffing = rec.get("staffing")
    if not isinstance(staffing, dict) or staffing.get("status") not in vocab_set(vocab, "staffing"):
        errs.append("staffing.status is not in vocab.staffing")
    if not isinstance(rec.get("visit"), dict):
        errs.append("visit is not an object")

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
        "events": lambda x: isinstance(x, dict) and x.get("event") in events_ok and (x.get("year") is None or isinstance(x.get("year"), int)),
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
    if not (isinstance(rec.get("updated"), str) and DATE_RE.match(rec["updated"])):
        errs.append("updated is not a YYYY-MM-DD date")
    return errs, warns


def validate(towers_dir: Path, vocab_path: Path, log=print) -> int:
    vocab = json.loads(vocab_path.read_text(encoding="utf-8"))
    files = sorted(towers_dir.rglob("*.json")) if towers_dir.is_dir() else []
    if not files:
        log(f"No tower records in {towers_dir}; nothing to check.")
        return 0
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
    return 1 if n_err else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--towers", type=Path, default=DATA / "towers")
    ap.add_argument("--vocab", type=Path, default=DATA / "vocab.json")
    args = ap.parse_args(argv)
    return validate(args.towers, args.vocab)


if __name__ == "__main__":
    sys.exit(main())
