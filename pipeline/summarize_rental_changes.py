#!/usr/bin/env python3
"""Summarise what the weekly RIDB refresh changed, for the Action's commit message
(.github/workflows/refresh-rentals.yml). Compares every data/towers/**/*.json file's `rental`
field against a git ref (default HEAD) using `git show`/`git diff --name-only`; stdlib + the
system `git` binary only (no pip installs, consistent with the rest of the pipeline).

Run: python3 pipeline/summarize_rental_changes.py [--ref HEAD] [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# Rental sub-fields worth calling out by name in the commit message (DESIGN.md section 3.3's rental
# shape). "checked" and "description" are left out: "checked" always moves when a listing is
# reconfirmed (not interesting on its own) and "description" is often just RIDB's prose
# reformatted, which would make every refresh "change" nearly every rental.
RENTAL_FIELDS = ["available", "season", "fee", "rules", "max_occupancy", "pets",
                 "access_note", "warning", "url"]


def changed_tower_paths(ref: str = "HEAD") -> list[Path]:
    """Every data/towers/**/*.json file added or modified relative to `ref`."""
    r = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=AM", ref, "--", "data/towers"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    return [REPO_ROOT / p for p in r.stdout.splitlines() if p.strip()]


def old_tower(path: Path, ref: str = "HEAD") -> dict | None:
    """The tower's content at `ref`, or None if the file did not exist there (a new tower)."""
    rel = path.relative_to(REPO_ROOT).as_posix()
    r = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=REPO_ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def diff_rental(old: dict | None, new: dict | None, name: str) -> str | None:
    """One line describing how `name`'s rental changed, or None if it did not (in any way
    this Action cares about -- see RENTAL_FIELDS)."""
    if old == new:
        return None
    if not isinstance(old, dict) and isinstance(new, dict):
        return f"{name}: new rental listing"
    if isinstance(old, dict) and not isinstance(new, dict):
        return f"{name}: rental listing removed from the record"
    if not isinstance(old, dict) or not isinstance(new, dict):
        return None
    changed = [f for f in RENTAL_FIELDS if old.get(f) != new.get(f)]
    if not changed:
        return None
    return f"{name}: {', '.join(changed)} changed"


def summarize(ref: str = "HEAD") -> list[str]:
    lines = []
    for path in sorted(changed_tower_paths(ref)):
        new = json.loads(path.read_text(encoding="utf-8"))
        old = old_tower(path, ref)
        line = diff_rental((old or {}).get("rental") if old else None, new.get("rental"),
                           new.get("name") or new.get("id") or path.stem)
        if line:
            lines.append(line)
    return lines


def build_message(lines: list[str]) -> str:
    if not lines:
        return "Weekly RIDB refresh: no rental field changes\n"
    title = f"Weekly RIDB refresh: {len(lines)} rental listing(s) changed"
    shown = lines[:50]
    body = "\n".join(f"- {l}" for l in shown)
    if len(lines) > 50:
        body += f"\n- ...and {len(lines) - 50} more"
    return f"{title}\n\n{body}\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ref", default="HEAD", help="git ref to diff against (default: HEAD)")
    ap.add_argument("--out", type=Path, help="write the commit message here (default: stdout)")
    args = ap.parse_args(argv)
    message = build_message(summarize(args.ref))
    if args.out:
        args.out.write_text(message, encoding="utf-8")
    else:
        print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
