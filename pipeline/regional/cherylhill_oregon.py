"""Fetcher for "Every Lookout in Oregon" (cherylhill.net/firelookouts/), Cheryl Hill's quest to visit
every standing fire lookout in Oregon, linked from FFLA's links page as "Every Lookout in Oregon".

What the site gives (reconnaissance, 2026-10-08): one table, "Oregon's Standing Lookouts" (155 rows as of
this run: name, agency, Kresek area, elevation, year built, status word, public access), almost every row
linking to its own page, a post written after a visit, whose first lines are a fact block ("Type: 53'
R-6 tower / Status / Elevation / Visited") and which often links the lookout's NHLR register page and
Rex Kamstra's firelookout.com page. A "Destroyed Lookouts" category lists posts about lookouts that have
burned, collapsed or been torn down. There are no coordinates anywhere (the author's own map is a
Google My Map, which Google's robots.txt keeps crawlers out of), so a row can only be matched by its
register number, when its post links an NHLR / FFLOS page (resolved here from the committed NHLR and
FFLOS extracts), or by name.

Facts only: name, agency, elevation, year built, design and height from the "Type" line, status word,
and links. The post text is not copied.

robots.txt on cherylhill.net allows everything but /wp-admin/. One request per 2 s, cached under
data/raw/cherylhill_oregon/.

Output: data/sources/cherylhill_oregon.json
Re-run: python3 pipeline/regional/cherylhill_oregon.py
"""

from __future__ import annotations

import datetime
import html as htmlmod
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import (FetchError, fetch_text, ft_to_m, names_agree, register_by_url, register_url_key,  # noqa: E402
                     slugify, write_source_json)

SOURCE = "cherylhill_oregon"
BASE = "https://cherylhill.net/firelookouts"
TABLE_URL = f"{BASE}/oregons-standing-lookouts/"
DESTROYED_URL = f"{BASE}/category/destroyed-lookouts/"
HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

# County written in by hand where a row's name alone matches several Oregon lookouts (Bald Mountain,
# Table Rock...). Each was chosen from the row's own elevation, agency and status against Firefinder's
# towers of that name; the county is a fact about the lookout, whichever site names it. Rows whose
# lookout could not be told apart (Silver Butte, torn down in 2012: two Oregon sites of that name) are
# left out.
COUNTY_HINTS = {
    "big-rock-green-mountain": "Linn", "gold-butte": "Marion", "huckleberry-mountain": "Lane",
    "indian-ridge": "Lane", "round-mountain": "Deschutes", "red-butte": "Douglas",
    "round-top": "Jackson", "table-mountain": "Jackson", "mt-scott": "Klamath",
    "bald-mountain": "Klamath", "green-mountain": "Lake", "tower-point": "Crook",
    "sugarloaf-mountain": "Harney", "table-rock": "Baker", "elk-mountain": "Union",
    "bald-butte": None,  # two rows (Fremont-Winema, Ochoco): told apart by register number or not at all
}
# The name Firefinder's other sources spell differently.
ALIASES = {"callimus-butte": ["Calimus Butte"]}

ROW_RE = re.compile(r'<tr class="row-\d+">(.*?)</tr>', re.S)
CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
HREF_RE = re.compile(r'<a\s[^>]*href="([^"]+)"', re.I)
TYPE_LINE_RE = re.compile(r"Type:\s*(.+?)\s*(?:Status:|Elevation:|Visited:|$)", re.S)
DESIGN_RE = re.compile(r"\b(R-6|L-4|L-5|L-6|D-6|CL-\d+|Aermotor(?:\s+\w+-?\d+)?|BC-\d+|IS-\d+)\b")
HEIGHT_RE = re.compile(r"(\d{2,3})\s*[′']")
ARTICLE_RE = re.compile(r"<article.*?</article>", re.S)
# "Destroyed Lookouts" post titles that name one lookout and say what happened to it.
DESTROYED_TITLES = [
    (re.compile(r"^(?P<n>.+?) Lookout Has Burned", re.I), "burned", "burned"),
    (re.compile(r"^(?P<n>.+?) Lookout Collapsed", re.I), "destroyed", "collapsed"),
    (re.compile(r"^(?P<n>.+?) lookout gone", re.I), None, None),  # cause varies; read the first line
]


def clean(s: str) -> str:
    s = htmlmod.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def table_rows(html: str) -> list[dict]:
    rows = []
    for r in ROW_RE.findall(html):
        cells = CELL_RE.findall(r)
        if len(cells) < 7:
            continue
        name_cell = cells[0]
        name = clean(name_cell).replace("*", "").strip()
        post = HREF_RE.search(name_cell)
        status_cell = cells[5]
        rental = next((h for h in HREF_RE.findall(status_cell) if "recreation.gov" in h), None)
        rows.append({
            "name": name, "post": post.group(1) if post else None, "agency": clean(cells[1]),
            "area": clean(cells[2]), "elevation_raw": clean(cells[3]), "built_raw": clean(cells[4]),
            "status_raw": clean(status_cell), "public": clean(cells[6]), "rental": rental,
            "multiple": "*" in clean(name_cell),
        })
    return rows


def elevation_ft(raw: str) -> int | None:
    m = re.search(r"(\d[\d,]*)", raw or "")
    return int(m.group(1).replace(",", "")) if m else None


def post_facts(html: str, row_name: str) -> dict:
    """The fact block and outbound links of one post (first article on the page)."""
    m = ARTICLE_RE.search(html)
    art = m.group(0) if m else html
    text = clean(art)
    out: dict = {"type_raw": None, "design": None, "height_ft": None, "links": [], "nhlr": None}
    t = TYPE_LINE_RE.search(text)
    if t:
        out["type_raw"] = t.group(1).strip()
        d = DESIGN_RE.search(out["type_raw"])
        out["design"] = d.group(1) if d else None
        h = HEIGHT_RE.search(out["type_raw"])
        out["height_ft"] = int(h.group(1)) if h else None
    reg = register_by_url()
    for href in HREF_RE.findall(art):
        host = re.sub(r"^https?://(www\.)?", "", href).split("/")[0].lower()
        if host in ("nhlr.org", "firetower.org") and register_url_key(href) in reg:
            hit = reg[register_url_key(href)]
            # the "more information" links are sometimes a previous post's: keep one only when the
            # register entry is named like this row (found: "Bald Butte" linking Sugarpine Mountain)
            if names_agree(row_name, hit["name"]):
                out["nhlr"] = hit["register"]
            else:
                out["rejected_register"] = hit["name"]
    return out


def destroyed_posts(html: str) -> list[dict]:
    out = []
    for art in re.findall(r"<article.*?</article>", html, re.S):
        h = re.search(r'<h2[^>]*>\s*<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', art, re.S)
        d = re.search(r"Posted on\s+([A-Z][a-z]+ \d{1,2}, \d{4})", clean(art))
        if not h or not d:
            continue
        title = clean(h.group(2))
        for pat, event, _why in DESTROYED_TITLES:
            m = pat.match(title)
            if m:
                # "X lookout gone" posts say when only loosely ("last June"), so they carry no event
                year = int(d.group(1)[-4:]) if event else None
                out.append({"name": m.group("n").strip(), "url": h.group(1), "year": year, "event": event})
                break
    return out


def main() -> None:
    retrieved = datetime.date.today().isoformat()
    table_html = fetch_text(TABLE_URL, SOURCE, "oregons-standing-lookouts.html", encoding="utf-8")
    rows = table_rows(table_html)
    print(f"{len(rows)} table rows", file=sys.stderr)
    records, seen = [], set()
    for row in rows:
        facts = {"type_raw": None, "design": None, "height_ft": None, "links": [], "nhlr": None}
        if row["post"]:
            slug = slugify(row["post"].rstrip("/").rsplit("/", 1)[-1])
            try:
                post_html = fetch_text(row["post"], SOURCE, f"post-{slug}.html", encoding="utf-8")
                facts = post_facts(post_html, row['name'])
            except FetchError as e:
                print(f"  ! {row['name']!r} ({row['post']}): {e}", file=sys.stderr)
        slug = slugify(row["post"].rstrip("/").rsplit("/", 1)[-1] if row["post"] else row["name"])
        slug_row = slugify(row["name"].replace("/", " "))
        key = f"{SOURCE}:or:{slug}"
        if key in seen:
            continue
        seen.add(key)
        url = row["post"] or TABLE_URL
        built = int(row["built_raw"]) if re.fullmatch(r"(1[89]|20)\d\d", row["built_raw"] or "") else None
        elev = elevation_ft(row["elevation_raw"])
        county = COUNTY_HINTS.get(slug_row)
        extra = {"area": row["area"], "public_access": row["public"], "elevation_ft": elev}
        if ALIASES.get(slug_row):
            extra["aliases"] = ALIASES[slug_row]
        if facts["design"]:
            extra["design"] = facts["design"]
        if facts["height_ft"]:
            extra["height_ft"] = facts["height_ft"]
        if row["multiple"]:
            extra["more_than_one_structure"] = True
        links = [{"label": "Every Lookout in Oregon (Cheryl Hill)", "url": url, "kind": "site"}, *facts["links"]]
        if row["rental"]:
            links.append({"label": "Recreation.gov listing", "url": row["rental"], "kind": "rental"})
        records.append({
            "key": key, "url": url, "name": row["name"], "country": "US", "region": "OR", "county": county,
            "lat": None, "lon": None,
            "elevation_m": ft_to_m(elev) if elev else None,
            "type_raw": facts["type_raw"], "kind": "unknown",
            "status_raw": row["status_raw"], "status": "standing",
            "registers": [facts["nhlr"]] if facts["nhlr"] else [],
            "built": built, "agency": row["agency"] or None,
            "events": [{"year": built, "event": "built", "note": None, "from": SOURCE}] if built else [],
            "photos": [], "links": links, "rental": None, "extra": extra,
        })

    destroyed_html = fetch_text(DESTROYED_URL, SOURCE, "category-destroyed-lookouts.html", encoding="utf-8")
    nd = 0
    for d in destroyed_posts(destroyed_html):
        key = f"{SOURCE}:or:destroyed-{slugify(d['name'])}"
        if key in seen:
            continue
        seen.add(key)
        nd += 1
        records.append({
            "key": key, "url": d["url"], "name": d["name"], "country": "US", "region": "OR", "county": None,
            "lat": None, "lon": None, "elevation_m": None, "type_raw": None, "kind": "unknown",
            "status_raw": d["event"], "status": "gone", "registers": [], "built": None, "agency": None,
            "events": ([{"year": d["year"], "event": d["event"], "note": "Reported on Every Lookout in Oregon",
                         "from": SOURCE}] if d["event"] else []),
            "photos": [], "links": [{"label": "Every Lookout in Oregon (Cheryl Hill)", "url": d["url"],
                                     "kind": "site"}],
            "rental": None, "extra": {"destroyed_post": True},
        })
    print(f"{len(records) - nd} standing rows, {nd} destroyed posts, "
          f"{sum(1 for r in records if r['registers'])} with a register number", file=sys.stderr)

    out = REPO_ROOT / "data" / "sources" / f"{SOURCE}.json"
    write_source_json(
        out, source=SOURCE, title="Every Lookout in Oregon (Cheryl Hill)",
        url="https://cherylhill.net/firelookouts/", retrieved=retrieved,
        license_=("No licence stated; facts only (name, agency, elevation, year built, design and height, "
                  "status word, links). Posts' narrative and photos are not reproduced."),
        records=records,
    )
    print(f"wrote {len(records)} records -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
