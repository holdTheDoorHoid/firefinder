"""Per-lookout pages of FFLA's chapters, affiliates and "Friends of ..." groups, the sites FFLA's links page
(firelookout.org/resources/links/) lists under "Website Links - FFLA Chapters and Affiliates", plus the
Friends groups FFLA's New York chapter lists (nysffla.org/friends/friends.html).

These sites are small: each runs one to thirty lookouts. What they give Firefinder is (1) a link, on the
lookout's own page, to the group that looks after it (the people to ask about a visit, a work party, the
key), and (2) from the one site that tabulates its chapter's towers, firelookouthost.org (FFLA
California-South), the NHLR register number and current condition of ~30 Southern California towers.

How the sites were read (reconnaissance, 2026-10-08)
-----------------------------------------------------
 * Each page below was fetched (robots.txt honoured, 2 s apart, cached under data/raw/ffla_groups/) and
   must answer 200 for its link to be kept; a dead page is reported and dropped.
 * firelookouthost.org/southern-california is a Wix page with a table of 31 towers: name, county, NHLR#,
   operator, condition. Each row links the tower's NHLR (or FFLOS) page; the register number is taken from
   that link (via the committed NHLR / FFLOS extracts), not from the table's own number column, which has
   at least one typo. County is not used (it has "Sta. Barbara" and puts Tahquitz Peak in San Bernardino).
 * The group sites are curated below (GROUP_PAGES), not scraped: their navigation is hand-built and each
   names the lookout only in its page title. Names and counties are written as Firefinder's own pages
   have them, so the merge can place each link.
 * Not used: friendsofsterlingforest.org (the domain now serves an Indonesian gambling site; FFLA should
   drop the link), argentinelookout.org and ffla-ccwr.org (no DNS), townofkentny.gov (404), nwmt-ffla.org
   (separate agent), Facebook pages.

Facts only (name, register number, operator, a status word); no prose is copied.

Output: data/sources/ffla_groups.json
Re-run: python3 pipeline/regional/ffla_groups.py
"""

from __future__ import annotations

import datetime
import html as htmlmod
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import (FetchError, fetch_text, names_agree, register_by_url, register_url_key, slugify,  # noqa: E402
                     write_source_json)

SOURCE = "ffla_groups"
HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
SOCAL_URL = "https://www.firelookouthost.org/southern-california"

# group id -> (credit name used in link labels, home page)
GROUPS = {
    "ffla_cas": ("FFLA California-South chapter", "https://www.firelookouthost.org/"),
    "scmf": ("Southern California Mountains Foundation", "https://mountainsfoundation.org/programs/fire-lookouts/"),
    "sdrc": ("FFLA San Diego-Riverside chapter", "https://www.ffla-sandiego.org/"),
    "monterey": ("FFLA Monterey chapter", "https://ffla-monterey.org/"),
    "anffla": ("Angeles National Forest Fire Lookout Association", "https://www.anffla.org/"),
    "hi_mountain": ("Hi Mountain Lookout Project", "https://www.condorlookout.org/"),
    "buckrock": ("Buck Rock Foundation", "https://buckrock.org/"),
    "sandmountain": ("Sand Mountain Society", "https://sandmountain.org/"),
    "snoqualmie": ("Snoqualmie Fire Lookouts Association", "https://www.snoqualmielookouts.org/"),
    "mvffla": ("Methow Valley Forest Fire Lookout Association", "https://www.mvffla.org/"),
    "stregis": ("Friends of St. Regis Mountain Fire Tower", "http://www.friendsofstregis.org/"),
    "stissing": ("Friends of Stissing Landmarks", "https://stissingfiretower.org/"),
    "azure": ("Azure Mountain Friends", "https://www.azuremountain.org/"),
    "pokeo": ("Friends of Poke-O-Moonshine", "https://www.pokeomoonshine.org/"),
    "arab": ("Friends of Mount Arab", "https://friendsofmtarab.org/"),
    "bald": ("Friends of Bald (Rondaxe) Mountain", "https://www.masterpieces.com/bald.htm"),
    "bramley": ("Bramley Mountain Fire Tower", "https://bramleymountainfiretower.org/"),
    "hurricane": ("Friends of Hurricane Mountain", "https://www.hurricanefiretower.org/"),
    "hadley": ("Hadley Mountain Fire Tower Friends", "https://hadleymtfiretower.org/"),
    "wilton": ("Town of Wilton", "https://townofwilton.com/visitors/cornell-hill-fire-tower/"),
    "balsam": ("Balsam Lake Mountain (Catskill Fire Tower Project)", "https://viewsandbrews.com/balsamlake/"),
    "stillwater": ("Friends of Stillwater Fire Tower", "http://www.friendsofstillwaterfiretower.com/"),
}

# (group, state, lookout name as Firefinder knows it, county or None, page URL, SoCal-table row or None)
# The county is only given where the name alone is ambiguous in the state.
GROUP_PAGES = [
    # -- Southern California Mountains Foundation: the seven San Bernardino NF lookouts (one page)
    *[("scmf", "CA", n, None, "https://mountainsfoundation.org/programs/fire-lookouts/fl-seven-lookouts/", row)
      for n, row in [("Black Mountain", "Black Mountain"), ("Butler Peak", "Butler Peak"),
                     ("Keller Peak", "Keller Peak"), ("Morton Peak", "Morton Peak"),
                     ("Red Mountain", "Red Mtn - Riverside"), ("Strawberry Peak", "Strawberry Peak"),
                     ("Tahquitz Peak", "Tahquitz Peak")]],
    # -- FFLA California-South chapter (Bald Mountain is its other area)
    ("ffla_cas", "CA", "Bald Mountain", "Mono", "https://www.firelookouthost.org/bald-mountain", None),
    # -- FFLA San Diego-Riverside chapter
    ("sdrc", "CA", "Boucher Hill", None, "https://www.ffla-sandiego.org/boucher-lookout/", "Boucher Hill"),
    ("sdrc", "CA", "High Point", None, "https://www.ffla-sandiego.org/highpoint-lookout/", "High Point"),
    ("sdrc", "CA", "Black Mountain", "San Diego",
     "https://www.ffla-sandiego.org/fire-lookout/southern-california-towers/black-mountain/", None),
    ("sdrc", "CA", "Bottle Peak", None,
     "https://www.ffla-sandiego.org/fire-lookout/southern-california-towers/bottle-peak/", None),
    ("sdrc", "CA", "Cuyamaca Peak", None,
     "https://www.ffla-sandiego.org/fire-lookout/southern-california-towers/cuyamaca-peak/", None),
    ("sdrc", "CA", "Estelle Mountain", None,
     "https://www.ffla-sandiego.org/fire-lookout/southern-california-towers/estelle-mountain/", "Estelle Mtn"),
    ("sdrc", "CA", "Hot Springs Mountain", None,
     "https://www.ffla-sandiego.org/fire-lookout/southern-california-towers/hot-springs-mountain/", "Hot Springs"),
    ("sdrc", "CA", "Los Pinos", None,
     "https://www.ffla-sandiego.org/fire-lookout/southern-california-towers/los-pinos/", "Los Pinos Mtn"),
    ("sdrc", "CA", "Lyons Peak", None,
     "https://www.ffla-sandiego.org/fire-lookout/southern-california-towers/lyons-peak/", "Lyons Peak"),
    ("sdrc", "CA", "Mount Woodson", None,
     "https://www.ffla-sandiego.org/fire-lookout/southern-california-towers/mount-woodson/", None),
    ("sdrc", "CA", "Red Mountain", "San Diego",
     "https://www.ffla-sandiego.org/fire-lookout/southern-california-towers/red-mountainsd/", "Red Mtn - San Diego"),
    ("sdrc", "CA", "San Juan", None,
     "https://www.ffla-sandiego.org/fire-lookout/southern-california-towers/san-juan/", None),
    ("sdrc", "CA", "Santa Margarita Peak", None,
     "https://www.ffla-sandiego.org/fire-lookout/southern-california-towers/santa-margarita-peak/", None),
    ("sdrc", "CA", "Santiago Peak", None,
     "https://www.ffla-sandiego.org/fire-lookout/southern-california-towers/santiago-peak/", None),
    ("sdrc", "CA", "Tecate Peak", None,
     "https://www.ffla-sandiego.org/fire-lookout/southern-california-towers/tecate/", None),
    ("sdrc", "CA", "Red Mountain", "Riverside",
     "https://www.ffla-sandiego.org/fire-lookout/southern-california-towers/red-mountainriverside/",
     "Red Mtn - Riverside"),
    # -- FFLA Monterey chapter
    ("monterey", "CA", "Chews Ridge", None, "https://ffla-monterey.org/chews-ridge-lookout/", "Chews Ridge"),
    ("monterey", "CA", "Cone Peak", None, "https://ffla-monterey.org/cone-peak-lookout/", "Cone Peak"),
    # -- Angeles National Forest Fire Lookout Association
    ("anffla", "CA", "Slide Mountain", None, "https://www.anffla.org/towers/slide-mountain/", "Slide Mtn"),
    ("anffla", "CA", "Vetter Mountain", None, "https://www.anffla.org/towers/vetter-mountain/", "Vetter Mtn"),
    ("anffla", "CA", "South Mount Hawkins", None, "https://www.anffla.org/towers/inactive-towers/", None),
    ("anffla", "CA", "Warm Springs", None, "https://www.anffla.org/towers/inactive-towers/", None),
    # -- Hi Mountain Lookout Project
    ("hi_mountain", "CA", "Hi Mountain", None, "https://www.condorlookout.org/", "Hi Mountain"),
    # -- Buck Rock Foundation
    ("buckrock", "CA", "Buck Rock", None, "https://buckrock.org/buck-rock-lookout/", None),
    ("buckrock", "CA", "Delilah", None, "https://buckrock.org/delilah-lookout/", None),
    ("buckrock", "CA", "Park Ridge", None, "https://buckrock.org/park-ridge-lookout/", None),
    # -- Sand Mountain Society (Oregon)
    ("sandmountain", "OR", "Gold Butte", "Marion", "https://sandmountain.org/projects/gold-butte-lookout/", None),
    ("sandmountain", "OR", "High Rock", "Clackamas", "https://sandmountain.org/projects/high-rock-lookout/", None),
    ("sandmountain", "OR", "Huckleberry Mountain", "Lane",
     "https://sandmountain.org/projects/huckleberry-mountain-lookout/", None),
    ("sandmountain", "OR", "Pearsoll Peak", None, "https://sandmountain.org/projects/pearsoll-peak/", None),
    ("sandmountain", "OR", "Pechuck", None, "https://sandmountain.org/projects/pechuk-lookout/", None),
    ("sandmountain", "OR", "Sand Mountain", None, "https://sandmountain.org/projects/sand-mountain-lookout/", None),
    ("sandmountain", "OR", "The Watchman", None, "https://sandmountain.org/projects/the-watchman-lookout/", None),
    ("sandmountain", "OR", "Wildhorse", None, "https://sandmountain.org/projects/wildhorse-lookout/", None),
    # -- Snoqualmie Fire Lookouts Association (Washington)
    ("snoqualmie", "WA", "Suntop", None, "https://www.snoqualmielookouts.org/suntop-lookout", None),
    ("snoqualmie", "WA", "Kelly Butte", "King", "https://www.snoqualmielookouts.org/kelly-butte-lookout", None),
    ("snoqualmie", "WA", "Granite Mountain", "King",
     "https://www.snoqualmielookouts.org/granite-mountain-lookout", None),
    # -- Methow Valley FFLA (Washington)
    ("mvffla", "WA", "North Twentymile", None, "https://www.mvffla.org/north-twentymile", None),
    ("mvffla", "WA", "Monument 83", None, "https://www.mvffla.org/monument-83", None),
    ("mvffla", "WA", "Mebee Pass", None, "https://www.mvffla.org/mebee-pass", None),
    ("mvffla", "WA", "Lookout Mountain", "Okanogan", "https://www.mvffla.org/lookout-mountain", None),
    ("mvffla", "WA", "First Butte", None, "https://www.mvffla.org/first-butte", None),
    ("mvffla", "WA", "Goat Peak", "Okanogan", "https://www.mvffla.org/goat-peak", None),
    ("mvffla", "WA", "Mount Leecher", None, "https://www.mvffla.org/mount-leecher", None),
    ("mvffla", "WA", "Slate Peak", None, "https://www.mvffla.org/slate-peak", None),
    # -- New York Friends groups (FFLA NYS chapter's list)
    ("stregis", "NY", "St. Regis Mountain", None, "http://www.friendsofstregis.org/", None),
    ("stissing", "NY", "Stissing Mountain", None, "https://stissingfiretower.org/", None),
    ("azure", "NY", "Azure Mountain", None, "https://www.azuremountain.org/", None),
    ("pokeo", "NY", "Poke-O-Moonshine", None, "https://www.pokeomoonshine.org/", None),
    ("arab", "NY", "Mount Arab", None, "https://friendsofmtarab.org/", None),
    ("bald", "NY", "Bald Mountain", "Herkimer", "https://www.masterpieces.com/bald.htm", None),
    ("bramley", "NY", "Bramley Mountain", None, "https://bramleymountainfiretower.org/", None),
    ("hurricane", "NY", "Hurricane Mountain", None, "https://www.hurricanefiretower.org/", None),
    ("hadley", "NY", "Hadley Mountain", None, "https://hadleymtfiretower.org/", None),
    ("wilton", "NY", "Cornell Hill Fire Tower at Wilton", "Saratoga",
     "https://townofwilton.com/visitors/cornell-hill-fire-tower/", None),
    ("balsam", "NY", "Balsam Lake Mountain", None, "https://viewsandbrews.com/balsamlake/", None),
    ("stillwater", "NY", "Stillwater Mountain", None, "http://www.friendsofstillwaterfiretower.com/", None),
]

# Table rows that carry no link of their own, given the register page they belong to.
SOCAL_REGISTER_PAGES = {
    "Estelle Mtn": "http://nhlr.org/lookouts/us/ca/estelle-mountain-lookout/",
}
SOCAL_AGENCY = {
    "SBNF": "San Bernardino National Forest", "CNF": "Cleveland National Forest",
    "LPNF": "Los Padres National Forest", "ANF": "Angeles National Forest",
    "Cal Fire": "CAL FIRE", "Natl Parks": "National Park Service",
}
DESTROYED_RE = re.compile(r"destroyed\b.*?\b(20\d\d)", re.I)


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ")).strip()


def parse_socal(page_html: str) -> list[dict]:
    """The chapter's tower table: rows of name / county / NHLR# / operator / condition, each name linking
    its register page. Returns [{"name", "register_url", "operator", "condition"}] (county unused)."""
    body = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", page_html)
    links = {}
    for href, text in re.findall(r'<a\s[^>]*href="(https?://(?:www\.)?(?:nhlr|firetower)\.org/[^"]+)"[^>]*>(.*?)</a>',
                                 body, re.S | re.I):
        links.setdefault(clean(text), href)
    text = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|td|h\d|span)>", "\n", body)
    lines = [clean(x) for x in re.sub(r"<[^>]+>", " ", text).split("\n")]
    lines = [x for x in lines if x]
    try:
        i = lines.index("Status") + 1
        j = lines.index("Contact:", i)
    except ValueError:
        return []
    rows = []
    cells = lines[i:j]
    for k in range(0, len(cells) - 4, 5):
        name, county, number, operator, condition = cells[k:k + 5]
        if not number.isdigit():
            print(f"  ! unexpected table row {cells[k:k + 5]}", file=sys.stderr)
            continue
        rows.append({"name": name.replace(" - no link", ""),
                     "register_url": links.get(name) or SOCAL_REGISTER_PAGES.get(name.replace(" - no link", "")),
                     "table_number": number, "operator": operator, "condition": condition})
    return rows


def condition_status(cond: str) -> tuple[str | None, int | None]:
    low = cond.lower()
    if low.startswith("destroyed"):
        m = DESTROYED_RE.search(cond)
        return "gone", int(m.group(1)) if m else None
    if "steel legs only" in low:
        return "ruins", None
    return "standing", None


def main() -> None:
    retrieved = datetime.date.today().isoformat()
    reg = register_by_url()

    # -- the chapter's table
    socal: dict[str, dict] = {}
    try:
        html = fetch_text(SOCAL_URL, SOURCE, "southern-california.html", encoding="utf-8")
        for row in parse_socal(html):
            socal[row["name"]] = row
        print(f"{len(socal)} rows in the California-South table", file=sys.stderr)
    except FetchError as e:
        print(f"  ! California-South table unavailable: {e}", file=sys.stderr)

    # -- verify every group page once
    alive: dict[str, bool] = {}
    for _g, _s, name, _c, url, _row in GROUP_PAGES:
        if url in alive:
            continue
        try:
            fetch_text(url, SOURCE, "pages/" + slugify(re.sub(r"^https?://(www\.)?", "", url)) + ".html", encoding="utf-8")
            alive[url] = True
        except FetchError as e:
            alive[url] = False
            print(f"  ! {name!r}: {url}: {e}", file=sys.stderr)

    recs: dict[str, dict] = {}

    def record_for(state: str, name: str, county: str | None, row: dict | None) -> dict:
        key = f"{SOURCE}:{state.lower()}:{slugify(name)}" + (f"-{slugify(county)}" if county else "")
        if row is not None:
            key = f"{SOURCE}:{state.lower()}:socal-{slugify(row['name'])}"
        if key not in recs:
            registers = []
            if row is not None and row.get("register_url") and register_url_key(row["register_url"]) in reg:
                hit = reg[register_url_key(row["register_url"])]
                if names_agree(row["name"], hit["name"]):
                    registers = [dict(hit["register"])]
                else:
                    print(f"  ! {row['name']!r} links register page {hit['name']!r}: not used", file=sys.stderr)
            status = year = None
            events, extra = [], {}
            agency = None
            if row is not None:
                status, year = condition_status(row["condition"])
                agency = SOCAL_AGENCY.get(row["operator"])
                extra = {"operator": row["operator"], "condition": row["condition"]}
                if year:
                    events = [{"year": year, "event": "destroyed", "note": row["condition"], "from": SOURCE}]
            recs[key] = {
                "key": key, "url": None, "name": name, "country": "US", "region": state, "county": county,
                "lat": None, "lon": None, "elevation_m": None, "type_raw": None, "kind": "unknown",
                "status_raw": row["condition"] if row else None, "status": status, "registers": registers,
                "built": None, "agency": agency, "events": events, "photos": [], "links": [], "rental": None,
                "extra": extra,
            }
        return recs[key]

    # the table's own rows first (they carry the register numbers)
    for sname, row in socal.items():
        state = "CA"
        rec = record_for(state, sname, None, row)
        rec["links"].append({"label": "FFLA California-South chapter: Southern California lookouts",
                             "url": SOCAL_URL, "kind": "association"})
    for group, state, name, county, url, srow in GROUP_PAGES:
        if not alive.get(url):
            continue
        row = socal.get(srow) if srow else None
        if srow and row is None:
            row = None  # the table did not load or the row is gone: fall back to name matching
        rec = record_for(state, name, county, row)
        gname, _home = GROUPS[group]
        label = f"{gname}" if url == _home else f"{name} lookout: {gname}"
        rec["links"].append({"label": label, "url": url, "kind": "association"})
        if rec["name"] != name and name not in rec["extra"].get("also_called", []):
            rec["extra"].setdefault("also_called", []).append(name)

    records = sorted(recs.values(), key=lambda r: r["key"])
    for r in records:
        seen, links = set(), []
        for l in r["links"]:
            if l["url"] not in seen:
                seen.add(l["url"])
                links.append(l)
        r["links"] = links
        r["extra"] = {k: v for k, v in r["extra"].items() if v}
    print(f"{len(records)} records, {sum(1 for r in records if r['registers'])} with a register number, "
          f"{sum(len(r['links']) for r in records)} links", file=sys.stderr)
    out = REPO_ROOT / "data" / "sources" / f"{SOURCE}.json"
    write_source_json(
        out, source=SOURCE, title="FFLA chapters, affiliates and Friends groups: lookout pages",
        url="https://firelookout.org/resources/links/", retrieved=retrieved,
        license_=("Links to the groups' own pages; facts only from the California-South chapter's tower "
                  "table (register page, operator, condition). No text or photos reproduced."),
        records=records,
    )
    print(f"wrote {len(records)} records -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
