#!/usr/bin/env python3
"""Coverage audit: is every source record held by a tower?

Run it after `python3 pipeline/merge.py`. It reads every extract in data/sources/ and every
canonical tower in data/towers/, and lists each source record (from any source, not just FFLA)
that no tower holds, with the reason, and per source how many records there are, how many sit on
a visible tower, how many only on a hidden (out of scope) tower, and how many are not held. Of the
held ones, "approx" counts those on a tower shown at an approximate (GNIS) location: no source gives
its position (DESIGN.md 3.5, "Approximate locations").

A record is "held" when a tower's sources[] has its key. Out-of-scope records (tree platforms,
bare lookout points, ...) are still held, by a hidden tower, so they count as covered here; the
"hidden only" column says how many. A record is not held for one of these reasons:

  no_coordinates       the source gives no position (an FFLA row without lat/long, a rental
                       listed by name only that no tower's name matched). A tower needs a
                       position, so merge.py can place such a record only by register number, a
                       unique same-name tower in its state, or approximately, on the one
                       same-name GNIS high point in its county; the rest are listed on the site's
                       "Lookouts we can't place yet" pages.
  coordinates_outside_us   the position is not in the United States (a swapped or mistyped pair)
  duplicate_key        the key repeats inside the extract (merge keeps the first)
  unmatched            usable coordinates but no tower: this should never happen after a merge.
                       It means the tower files are older than the extracts: run merge.py.

Usage:
    python3 pipeline/coverage.py                 # per-source table, then the records not held
    python3 pipeline/coverage.py --source ffla   # one source
    python3 pipeline/coverage.py --json out.json # machine-readable result as well
    python3 pipeline/coverage.py --strict        # exit 1 if any `unmatched` record exists
    python3 pipeline/coverage.py --summary       # only the table

Python 3.12, standard library only.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import merge  # noqa: E402

REPO = HERE.parent
DATA = REPO / "data"

REASONS = ("no_coordinates", "coordinates_outside_us", "duplicate_key", "unmatched")


def load_extracts(sources_dir: Path) -> dict[str, list[dict]]:
    """{source id: [raw records]} for every lookout extract (reference files are skipped)."""
    out: dict[str, list[dict]] = {}
    for path in sorted(sources_dir.glob("*.json")):
        if path.name in merge.SKIP_FILES:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or not isinstance(data.get("records"), list):
            continue
        out[str(data.get("source") or path.stem)] = [r for r in data["records"] if isinstance(r, dict)]
    return out


def load_holders(towers_dir: Path) -> dict[str, list[dict]]:
    """{source record key: [the towers (id, hidden) whose sources[] name it]}."""
    held: dict[str, list[dict]] = defaultdict(list)
    for path in sorted(towers_dir.rglob("*.json")):
        try:
            t = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(t, dict):
            continue
        for s in t.get("sources") or []:
            # a source entry the merge kept only because its record disappeared is not a holder
            if isinstance(s, dict) and s.get("key") and not s.get("missing_since"):
                held[str(s["key"])].append({"id": t.get("id"), "hidden": bool(t.get("hidden")),
                                            "hidden_reason": t.get("hidden_reason"),
                                            "approximate": merge.is_approximate_location(t.get("location"))})
    return held


def reason_not_held(source: str, raw: dict, seen_keys: set) -> str:
    key = raw.get("key")
    if key in seen_keys:
        return "duplicate_key"
    rec = merge.Rec.build(source, raw, 0)
    if rec.has_coords:
        return "unmatched"
    if rec.bad_coords == "outside_us":
        return "coordinates_outside_us"
    return "no_coordinates"


def audit(sources_dir: Path, towers_dir: Path, report_path: Path | None = None,
          only: str | None = None) -> dict:
    extracts = load_extracts(sources_dir)
    holders = load_holders(towers_dir)
    review: dict[str, str] = {}
    if report_path and report_path.exists():
        try:
            for u in json.loads(report_path.read_text(encoding="utf-8")).get("unplaced") or []:
                review[u["key"]] = u.get("reason") or ""
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            pass
    per_source: dict[str, dict] = {}
    not_held: list[dict] = []
    for source, raws in extracts.items():
        if only and source != only:
            continue
        c: Counter = Counter()
        seen: set = set()
        for raw in raws:
            key = raw.get("key")
            if not key:
                continue
            c["records"] += 1
            towers = holders.get(str(key))
            if towers:
                c["held_visible" if any(not t["hidden"] for t in towers) else "held_hidden_only"] += 1
                c["held_approximate"] += any(t["approximate"] and not t["hidden"] for t in towers)
                seen.add(key)
                continue
            why = reason_not_held(source, raw, seen)
            seen.add(key)
            c["not_held"] += 1
            c[why] += 1
            not_held.append({
                "source": source, "key": key, "name": raw.get("name"), "region": raw.get("region"),
                "county": raw.get("county"), "lat": raw.get("lat"), "lon": raw.get("lon"),
                "reason": why, "note": review.get(str(key)) or None,
            })
        per_source[source] = {k: c.get(k, 0) for k in ("records", "held_visible", "held_approximate", "held_hidden_only", "not_held", *REASONS)}
    not_held.sort(key=lambda r: (r["source"], r["region"] or "", str(r["name"] or ""), r["key"]))
    return {
        "per_source": per_source,
        "totals": {k: sum(v[k] for v in per_source.values()) for k in
                   ("records", "held_visible", "held_approximate", "held_hidden_only", "not_held", *REASONS)},
        "not_held": not_held,
    }


def format_report(result: dict, show_list: bool = True) -> str:
    cols = [("records", "records"), ("held_visible", "on a visible tower"), ("held_approximate", "approx"), ("held_hidden_only", "hidden only"),
            ("not_held", "NOT HELD"), ("no_coordinates", "no coords"), ("coordinates_outside_us", "outside US"),
            ("duplicate_key", "dup key"), ("unmatched", "UNMATCHED")]
    rows = [["source", *[c[1] for c in cols]]]
    for s, v in sorted(result["per_source"].items()):
        rows.append([s, *[str(v[c[0]]) for c in cols]])
    rows.append(["TOTAL", *[str(result["totals"][c[0]]) for c in cols]])
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    lines = ["  ".join(cell.ljust(widths[i]) if i == 0 else cell.rjust(widths[i]) for i, cell in enumerate(r)) for r in rows]
    lines.insert(1, "  ".join("-" * w for w in widths))
    lines.insert(len(lines) - 1, "  ".join("-" * w for w in widths))
    out = ["\n".join(lines)]
    if show_list and result["not_held"]:
        out.append("")
        out.append("Records no tower holds:")
        for r in result["not_held"]:
            where = f"{r['lat']}, {r['lon']}" if r["lat"] is not None else "no position"
            out.append(f"  [{r['reason']}] {r['key']}  {r['name']!r} ({r['region'] or '?'}; {where})"
                       + (f"  -- {r['note']}" if r["note"] else ""))
    elif not result["not_held"]:
        out.append("")
        out.append("Every record is held by a tower.")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sources", type=Path, default=DATA / "sources")
    ap.add_argument("--towers", type=Path, default=DATA / "towers")
    ap.add_argument("--report", type=Path, default=DATA / "merge_report.json",
                    help="merge_report.json, read for the 'unplaced' reasons if it exists")
    ap.add_argument("--source", help="audit one source only (e.g. ffla)")
    ap.add_argument("--json", type=Path, help="also write the result here")
    ap.add_argument("--summary", action="store_true", help="print the table only, not each record")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 if a record with usable coordinates is held by no tower")
    args = ap.parse_args(argv)
    result = audit(args.sources, args.towers, args.report, args.source)
    print(format_report(result, show_list=not args.summary))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.strict and result["totals"]["unmatched"]:
        print(f"\n{result['totals']['unmatched']} record(s) with usable coordinates are held by no tower: run "
              "pipeline/merge.py (or fix the matching).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
