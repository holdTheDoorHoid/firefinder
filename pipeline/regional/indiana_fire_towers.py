"""Fetcher for Indiana Fire Towers (indianafiretowers.com), Mark Armantrout's guide to the 40-odd
Indiana lookout tower sites, standing and gone, "by Mark A". Lead from the chapters-east agent
(2026-10-08): not on FFLA's links page but the Indiana-Illinois chapter's own reports point to it.

The list page ("List of Indiana Fire Towers", ~43 sites in the author's order: climbable ones first,
then standing-but-overlooked, base corners left, gone, speculative, a replica) links one page per site.
Each page has an Information block (Names, Location, County, Topo quad, Condition), a Data block with
Latitude and Longitude, and links (NHLR page, Forest Service page, structural-survey number). The
coordinates are the author's, taken on site or from topos for the standing and base-corner sites.

Facts only: names, county, coordinates, a status read from the Condition line's first words (Standing,
"Not standing", "Base ... exists"), and links. The author's histories, trip reports and photos are not
copied. robots.txt asks for `Crawl-delay: 10` (honoured by regional/_common.py), so the ~45 requests take
about eight minutes; cached under data/raw/indiana_fire_towers/.

Output: data/sources/indiana_fire_towers.json
Re-run: python3 pipeline/regional/indiana_fire_towers.py
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

SOURCE = "indiana_fire_towers"
BASE = "https://www.indianafiretowers.com"
LIST_URL = f"{BASE}/list-of-indiana-fire-towers/"
HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

# Pages of the site that are not a tower.
NOT_TOWERS = {"", "list-of-indiana-fire-towers", "history", "black-and-white-map", "colorful-map",
              "sources-and-tools", "wp-content", "category", "tag", "feed"}
LINK_RE = re.compile(r'<a\s[^>]*?href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)


def clean(s: str) -> str:
    s = htmlmod.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def tower_links(list_html: str) -> list[tuple[str, str]]:
    """[(slug, link text)] of every tower page the list links, in list order."""
    out, seen = [], set()
    for href, raw in LINK_RE.findall(list_html):
        u = urllib.parse.urlparse(urllib.parse.urljoin(LIST_URL, htmlmod.unescape(href)))
        if u.netloc.removeprefix("www.") != "indianafiretowers.com" or u.query or u.fragment:
            continue
        parts = [p for p in u.path.split("/") if p]
        if len(parts) != 1 or parts[0] in NOT_TOWERS or parts[0] in seen:
            continue
        seen.add(parts[0])
        out.append((parts[0], clean(raw)))
    return out


def info_block(page_html: str) -> dict[str, str]:
    """{"Names": ..., "County": ..., "Condition": ..., "Latitude": ..., "Longitude": ...} from the page."""
    body = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", page_html)
    text = re.sub(r"(?i)</(p|div|li|h\d)>|<br\s*/?>", "\n", body)
    text = htmlmod.unescape(re.sub(r"<[^>]+>", " ", text))
    out: dict[str, str] = {}
    for line in text.split("\n"):
        line = re.sub(r"\s+", " ", line.replace("\xa0", " ")).strip()
        m = re.match(r"^(Names?|Location|County|Topo quad|Condition|Latitude|Longitude)\s*:\s*(.+)$", line)
        if m and m.group(1) not in out:
            out[m.group(1)] = m.group(2).strip()
    return out


def status_of(condition: str | None, page_text_hint: str = "") -> str | None:
    """Standing / gone / ruins from the first words of the Condition line, else None."""
    c = (condition or "").lower()
    if not c:
        return None
    if c.startswith("not standing") or c.startswith("gone") or c.startswith("removed") or c.startswith("no longer"):
        return "ruins" if re.search(r"\b(base|footing|foundation|corner)s?\b.*\bexist|\bexist.*\b(base|footing|corner)", c) else "gone"
    if c.startswith("standing") or c.startswith("still standing"):
        return "standing"
    if "base" in c and "exist" in c:
        return "ruins"
    if "standing" in c and "not standing" not in c:
        return "standing"
    return None


def main() -> None:
    retrieved = datetime.date.today().isoformat()
    list_html = fetch_text(LIST_URL, SOURCE, "list.html", encoding="utf-8")
    towers = tower_links(list_html)
    print(f"{len(towers)} tower pages linked", file=sys.stderr)
    records = []
    for slug, text in towers:
        url = f"{BASE}/{slug}/"
        try:
            page = fetch_text(url, SOURCE, f"{slugify(slug)}.html", encoding="utf-8")
        except FetchError as e:
            print(f"  ! {text!r} ({url}): {e}", file=sys.stderr)
            continue
        info = info_block(page)
        title = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
        name = clean(title.group(1)).split(" - ")[0] if title else text
        try:
            lat, lon = float(info["Latitude"]), float(info["Longitude"])
            if not (37.5 <= lat <= 41.9 and -88.2 <= lon <= -84.7):
                lat = lon = None
        except (KeyError, ValueError):
            lat = lon = None
        status = status_of(info.get("Condition"))
        county = re.sub(r"\s*\(.*$", "", info.get("County", "")).strip() or None
        county = re.sub(r"\s+County$", "", county or "") or None
        aliases = [a.strip() for a in re.split(r"[;,]|\baka\b", info.get("Names", "")) if a.strip() and a.strip() != name]
        extra = {k: v for k, v in {
            "aliases": aliases or None,
            "topo_quad": info.get("Topo quad"),
            "condition_text": info.get("Condition", "")[:140] or None,
            "location_text": info.get("Location"),
        }.items() if v}
        links = [{"label": f"{name} on Indiana Fire Towers (Mark Armantrout)", "url": url, "kind": "site"}]
        for href in re.findall(r'<a\s[^>]*href="(https?://(?:www\.)?(?:nhlr|firetower)\.org/[^"]+)"', page, re.I):
            links.append({"label": "register page", "url": href, "kind": "register"})
        records.append({
            "key": f"{SOURCE}:in:{slugify(slug)}", "url": url, "name": name, "country": "US", "region": "IN",
            "county": county, "lat": lat, "lon": lon, "elevation_m": None, "type_raw": None, "kind": "tower",
            "status_raw": None, "status": status or "unknown", "registers": [], "built": None, "agency": None,
            "events": [], "photos": [], "links": links, "rental": None, "extra": extra,
        })
    print(f"{len(records)} records, {sum(1 for r in records if r['lat'] is not None)} with coordinates", file=sys.stderr)
    out = REPO_ROOT / "data" / "sources" / f"{SOURCE}.json"
    write_source_json(
        out, source=SOURCE, title="Indiana Fire Towers (Mark Armantrout)", url=BASE + "/", retrieved=retrieved,
        license_=("No licence stated; facts only (names, county, coordinates, a status read from the condition "
                  "line, links). The guide's histories, trip reports and photos are not reproduced."),
        records=records,
    )
    print(f"wrote {len(records)} records -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
