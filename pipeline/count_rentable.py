#!/usr/bin/env python3
"""Count reservable records in a source extract (default data/sources/ridb.json).

Used by the weekly RIDB refresh Action (.github/workflows/refresh-rentals.yml) as a
before/after guardrail: it runs this once before re-fetching and once after, and refuses to
merge or commit if the count dropped too far (RIDB's export failing partway through a
download, or recreation.gov truncating a response, would otherwise quietly wipe out most of
the site's rentals instead of failing loudly).

Run: python3 pipeline/count_rentable.py [PATH]   (default: data/sources/ridb.json)

Prints a single integer: the number of records in PATH whose "rental" field is a truthy
object. Prints 0 (not an error) when PATH does not exist yet, so the very first run -- before
data/sources/ridb.json has ever been committed -- has a baseline of 0 rather than failing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULT_PATH = Path(__file__).parent.parent / "data" / "sources" / "ridb.json"


def count_rentable(path: Path) -> int:
    if not path.exists():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    records = data.get("records")
    if not isinstance(records, list):
        return 0
    return sum(1 for r in records if isinstance(r, dict) and r.get("rental"))


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    path = Path(argv[0]) if argv else DEFAULT_PATH
    print(count_rentable(path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
