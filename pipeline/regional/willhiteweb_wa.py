"""Fetcher for the lookout pages of WillhiteWeb.com's Washington Fire Lookouts section
(willhiteweb.com/washington/fire_lookouts/...), linked from FFLA's links page as "Washington Fire
Lookouts (willhiteweb.com)". A private Washington collection (the pages name no author; the home page
gives willhiteweb@yahoo.com): a page for each place in Washington that ever had a lookout (Osborne photo-survey images from the
1930s, topo clips, news), indexed by five list pages: the standing lookouts of the Cascades (58
links), the former Cascade sites (439), the Olympic Peninsula and Willapa Hills (131), northeast
Washington (146) and southeast Washington (18).

Only the five list pages are fetched (2 s apart, cached under data/raw/willhiteweb_wa/): each link is
the lookout's own page, so the pages themselves are not crawled (~780 requests for photos and prose
that are not copied). The record is therefore a name, a link and, from the Cascades standing list,
a status. No coordinates or counties are given on the lists, so the merge places each by name alone;
names that are not unique in Washington stay unplaced and get no link.

Skipped: list entries that are not a place (maps, "AWS Locations", structure counts). The site's
pages mix lookouts with camps, trees and platforms; the merge decides what is out of scope.
robots.txt is empty (everything allowed). No licence is stated.

Output: data/sources/willhiteweb_wa.json
Re-run: python3 pipeline/regional/willhiteweb_wa.py
"""

from __future__ import annotations

import datetime
import html as htmlmod
import pathlib
import re
import sys
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import FetchError, fetch_text, slugify, write_source_json  # noqa: E402

SOURCE = "willhiteweb_wa"
BASE = "http://www.willhiteweb.com"
HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

# (list page, True when every entry on it is a standing lookout)
LISTS = [
    ("/washington/fire_lookouts/locations_322.htm", True),
    ("/washington/fire_lookouts/former_sites/cascades_461.htm", False),
    ("/washington/fire_lookouts/olympics/list_460.htm", False),
    ("/washington/fire_lookouts/northeast/list_458.htm", False),
    ("/washington/fire_lookouts/southeast/list_459.htm", False),
]
LINK_RE = re.compile(r'<a\s[^>]*?href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)
PAGE_RE = re.compile(r"_\d{3}\.htm$")
SKIP_RE = re.compile(r"\b(?:maps?|guide|locations?|lists?|structures|museum|interview|index|home|hiking|"
                     r"panoramics?|research|pins?|trail|lookouts)\b", re.I)


def clean(s: str) -> str:
    s = htmlmod.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def list_entries(html: str, base_url: str) -> list[tuple[str, str]]:
    out, seen = [], set()
    for href, raw in LINK_RE.findall(html):
        url = urllib.parse.urljoin(base_url, htmlmod.unescape(href))
        if "willhiteweb.com" not in url or not PAGE_RE.search(url) or "/list_" in url or "locations_322" in url:
            continue
        name = clean(raw).replace("\\", "/").strip('" ')
        if not name or SKIP_RE.search(name) or url in seen:
            continue
        seen.add(url)
        out.append((name, url))
    return out


def main() -> None:
    retrieved = datetime.date.today().isoformat()
    records, seen_keys, standing_urls = [], set(), set()
    pages = []
    for path, standing in LISTS:
        url = BASE + path
        try:
            html = fetch_text(url, SOURCE, slugify(path) + ".html", encoding="latin-1")
        except FetchError as e:
            print(f"  ! {url}: {e}", file=sys.stderr)
            continue
        entries = list_entries(html, url)
        print(f"{path}: {len(entries)} lookout pages", file=sys.stderr)
        pages.append((entries, standing))
        if standing:
            standing_urls |= {u for _n, u in entries}
    for entries, standing in pages:
        for name, url in entries:
            slug = slugify(re.sub(r"^https?://(www\.)?willhiteweb\.com/", "", url).rsplit(".", 1)[0])
            key = f"{SOURCE}:wa:{slug}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            is_standing = url in standing_urls
            records.append({
                "key": key, "url": url, "name": name, "country": "US", "region": "WA", "county": None,
                "lat": None, "lon": None, "elevation_m": None, "type_raw": None, "kind": "unknown",
                "status_raw": "Standing" if is_standing else None,
                "status": "standing" if is_standing else "unknown", "registers": [], "built": None,
                "agency": None, "events": [], "photos": [],
                "links": [{"label": f"{name} on WillhiteWeb.com Washington Fire Lookouts", "url": url,
                           "kind": "site"}],
                "rental": None, "extra": {},
            })
    print(f"{len(records)} records", file=sys.stderr)
    out = REPO_ROOT / "data" / "sources" / f"{SOURCE}.json"
    write_source_json(
        out, source=SOURCE, title="WillhiteWeb.com: Washington Fire Lookouts",
        url="http://www.willhiteweb.com/washington/fire_lookouts/locations_322.htm", retrieved=retrieved,
        license_="No licence stated; names and page links only (the site's photos and text are not reproduced).",
        records=records,
    )
    print(f"wrote {len(records)} records -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
