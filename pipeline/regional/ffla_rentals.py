"""Fetcher for the Forest Fire Lookout Association's "Lookout Rentals" list
(https://firelookout.org/resources/rentals/): every fire lookout the FFLA knows to be
rentable for overnight stays, grouped by state, each with a link to where it is booked.

The page is one hand-edited WordPress post. Each state is a paragraph that starts with the
state's name in bold; every rental below it is a link (its text is the lookout's name, its
address the booking or manager page) optionally followed by a bracketed note: a closure
("Maintenance Closure 2026", "Administrative Closure 2026", "Currently Unavailable") or who
runs it when that is not the Forest Service ("Managed by private owner", "Managed by MT DNRC").
The page says: unless otherwise noted these rentals are booked through recreation.gov, and the
FFLA is not involved in managing any rental program. There are no coordinates, so this source
cannot place a lookout on the map by itself: merge.py matches each entry to a tower by its
recreation.gov facility number (the link's last path segment is RIDB's facility id), or by name
and state, or through the override table FFLA_RENTAL_OVERRIDES in pipeline/merge.py.

A record is facts only (state, name, link, manager, closure note); no sentence of the page is
copied. Output: data/sources/ffla_rentals.json

Re-run:
    python3 pipeline/regional/ffla_rentals.py             # read the cached page if there is one
    python3 pipeline/regional/ffla_rentals.py --refresh   # fetch the live page again
"""

from __future__ import annotations

import argparse
import datetime
import html as html_mod
import importlib.util
import pathlib
import re
import sys
from urllib.parse import urlsplit

# pipeline/ has a _common.py too (the data-registers helpers), so a plain `from _common import`
# would pick up whichever of the two a test run imported first. Load regional/'s by path.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from common import STATE_ABBR  # noqa: E402
_spec = importlib.util.spec_from_file_location("regional_common", pathlib.Path(__file__).with_name("_common.py"))
_regional = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_regional)
cache_path, fetch_text, slugify, write_source_json = (
    _regional.cache_path, _regional.fetch_text, _regional.slugify, _regional.write_source_json)

SOURCE = "ffla_rentals"
URL = "https://firelookout.org/resources/rentals/"
CACHE_REL = "firelookout.org/resources/rentals/index.html"
HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

A_RE = re.compile(r'<a\s[^>]*?href="([^"]*)"[^>]*>(.*?)</a>', re.S | re.I)
STRONG_RE = re.compile(r"<strong[^>]*>(.*?)</strong>", re.S | re.I)
P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.S | re.I)
INVISIBLE = "​‌‍﻿ "
CLOSURE_RE = re.compile(r"closure|closed|unavailable|not available|temporarily", re.I)
MANAGED_RE = re.compile(r"managed\s+by\s+(.+)$", re.I)

# Who runs the booking page, by host. The recreation.gov entries are the Forest Service's (and a
# few other federal agencies'); the rest say who manages them in their note.
PROVIDER_BY_HOST = {
    "recreation.gov": "recreation.gov",
    "airbnb.com": "Airbnb",
    "parks.wa.gov": "Washington State Parks",
    "wvstateparks.com": "West Virginia State Parks",
    "dnrc.mt.gov": "Montana DNRC",
}


# The FFLA list gives no coordinates, and a rental that is on no other list (so no tower of ours)
# needs a position to become a tower. Only these are placed, each with the reason; everything else
# is matched to a tower we already have (pipeline/merge.py, match_rentals).
#
# MoonPass Lookouts, Wallace, Idaho: five new, custom-built 30-foot lookout towers on 55 private
# acres about seven miles from the town (moonpasslookouts.com; the FFLA lists the Half Moon and
# Full Moon towers as "Replica" rentals booked on Airbnb). The owner publishes no coordinates, so
# both sit on the town of Wallace (47.47, -115.92) rounded to two decimals, which the merge
# reports as an *approximate* position, and show as the rental they are, on private land. The
# two towers share that point and a name ("Moon Pass Replica Lookout"), so they become one tower
# with two booking links; each record keeps the FFLA's own wording in extra.listed_as.
_MOON_PASS = {"lat": 47.47, "lon": -115.92, "kind": "tower", "status": "replica", "name": "Moon Pass Replica Lookout"}
SITE_POSITIONS: dict[str, dict] = {
    "ffla_rentals:id:moon-pass-replica-lookout-half-moon": _MOON_PASS,
    "ffla_rentals:id:moon-pass-replica-lookout-full-moon": _MOON_PASS,
}
PRIVATE_OWNER = "private owner"


def clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_mod.unescape(text)
    for ch in INVISIBLE:
        text = text.replace(ch, " ")
    return re.sub(r"\s+", " ", text).strip()


def entry_content(html: str) -> str:
    i = html.find('class="entry-content"')
    if i == -1:
        return html
    j = html.find("<!-- .entry-content -->", i)
    return html[i:j if j != -1 else len(html)]


def host_of(url: str) -> str:
    return urlsplit(url).netloc.lower().removeprefix("www.")


def canonical_url(url: str) -> str:
    """The booking link without the page's tracking: https for recreation.gov and Airbnb, and no
    query string on an Airbnb room (the FFLA's links carry a "source_impression_id")."""
    parts = urlsplit(url)
    host = parts.netloc.lower().removeprefix("www.")
    if host in ("recreation.gov", "airbnb.com"):
        query = "" if host == "airbnb.com" else parts.query
        parts = parts._replace(scheme="https", query=query, fragment="")
    return parts.geturl()


def facility_id(url: str) -> str | None:
    """recreation.gov/camping/campgrounds/234262 -> '234262' (RIDB's facility id)."""
    if host_of(url) != "recreation.gov":
        return None
    m = re.search(r"/(?:camping/campgrounds|camping/campsites|permits|tour)/(\d+)", urlsplit(url).path)
    return m.group(1) if m else None


def normalise_closure(note: str) -> str:
    # the page writes "Maintenance Closure2026" in places
    return re.sub(r"([A-Za-z])(\d{4})\b", r"\1 \2", note).strip()


def split_notes(raw: str) -> dict:
    """The bracketed notes after a link: {'status_note': ..., 'manager': ..., 'notes': [...]}."""
    out: dict = {"status_note": None, "manager": None, "notes": []}
    for note in re.findall(r"\(([^()]*)\)", clean(raw)):   # clean first: inline styles hold "rgb(51, 51, 51)"
        note = normalise_closure(clean(note))
        if not re.search(r"[A-Za-z]", note):
            continue
        out["notes"].append(note)
        m = MANAGED_RE.match(note)
        if m:
            out["manager"] = m.group(1).strip().rstrip(".")
        elif CLOSURE_RE.search(note):
            out["status_note"] = note
    return out


def parse_rentals(html: str) -> list[dict]:
    """One dict per listed rental, in page order: state (abbr), name, url, and the notes."""
    body = entry_content(html)
    out: list[dict] = []
    for block in P_RE.findall(body):
        strong = STRONG_RE.search(block)
        state = clean(strong.group(1)) if strong else ""
        abbr = STATE_ABBR.get(state)
        if not abbr:
            continue
        rest = block[strong.end():]
        anchors = list(A_RE.finditer(rest))
        for i, a in enumerate(anchors):
            name = clean(a.group(2))
            if not name:
                continue   # an empty link (a stray zero-width space)
            nxt = anchors[i + 1].start() if i + 1 < len(anchors) else len(rest)
            after = rest[a.end():nxt]
            br = re.search(r"<br\s*/?>", after, re.I)
            if br:
                after = after[:br.start()]
            url = canonical_url(html_mod.unescape(a.group(1)).strip())
            out.append({"state": state, "region": abbr, "name": name, "url": url, **split_notes(after)})
    return out


def to_record(e: dict, taken: set[str], retrieved: str) -> dict:
    fid = facility_id(e["url"])
    host = host_of(e["url"])
    provider = PROVIDER_BY_HOST.get(host) or host
    base = f"{SOURCE}:{e['region'].lower()}:{slugify(e['name'])}"
    key = base
    if key in taken:
        key = f"{base}:{fid or slugify(host)}"
    n = 2
    while key in taken:
        key = f"{base}:{n}"
        n += 1
    taken.add(key)
    rental = {
        "available": True,
        "provider": provider,
        "url": e["url"],
        "ridb_facility_id": fid,
        "manager": e["manager"],
        "status_note": e["status_note"],
        "checked": retrieved,
    }
    site = SITE_POSITIONS.get(key, {})
    extra: dict = {}
    if e["notes"]:
        extra["notes"] = e["notes"]
    if (e["manager"] or "").lower() == PRIVATE_OWNER:
        extra["ownership"] = "private"
    if site:
        extra["position_note"] = "Approximate: the nearest town; the owner publishes no coordinates."
    if site.get("name") and site["name"] != e["name"]:
        extra["listed_as"] = e["name"]
    return {
        "key": key,
        "url": URL,
        "name": site.get("name", e["name"]),
        "country": "US",
        "region": e["region"],
        "county": None,
        "lat": site.get("lat"),
        "lon": site.get("lon"),
        "elevation_m": None,
        "type_raw": None,
        "kind": site.get("kind", "unknown"),
        "status_raw": None,
        "status": site.get("status", "unknown"),
        "registers": [],
        "built": None,
        "agency": None,
        "events": [],
        "photos": [],
        "links": [{"label": f"Book or read about {e['name']} ({provider})", "url": e["url"], "kind": "rental"}],
        "rental": rental,
        "extra": extra,
    }


def build_records(html: str, retrieved: str) -> list[dict]:
    taken: set[str] = set()
    return [to_record(e, taken, retrieved) for e in parse_rentals(html)]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--refresh", action="store_true", help="fetch the live page again instead of the cached copy")
    args = ap.parse_args(argv)
    if args.refresh:
        cache_path(SOURCE, CACHE_REL).unlink(missing_ok=True)
    html = fetch_text(URL, SOURCE, CACHE_REL, encoding="utf-8")
    retrieved = datetime.date.today().isoformat()
    records = build_records(html, retrieved)
    out_path = REPO_ROOT / "data" / "sources" / f"{SOURCE}.json"
    write_source_json(
        out_path,
        source=SOURCE,
        title="Forest Fire Lookout Association: lookout rentals",
        url=URL,
        retrieved=retrieved,
        license_="No licence stated; facts extracted only (state, name, booking link, manager, closure "
                 "note), no prose copied. The FFLA says it is not involved in managing any rental program.",
        records=records,
    )
    print(f"wrote {len(records)} rentals -> {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
