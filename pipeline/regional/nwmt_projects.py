"""Northwest Montana Lookout Association (NMLA): the work it has done on lookouts, year by year.

  https://nwmt-ffla.org/   (an FFLA chapter since 2013; its own 501(c)(3) since 2020)

NMLA restores and maintains fire lookouts for Glacier National Park, the Flathead and Kootenai
National Forests and Montana DNRC, and reports each season's work, project by project: restored,
repaired, re-roofed, repainted, assessed. This source turns those reports into dated events on
the lookouts' timelines, each linked to the report that gives it, plus the few facts the reports
state (build years, design and dimensions, tower height, agency, staffing). Built on the shared
association-project shape (pipeline/regional/_projects.py, DESIGN.md 3.7).

What is read (2026-10-08, robots.txt allows everything but /wp-admin and a few WordPress paths):
  * the project posts: /2026/03/07/2026-projects/ and /2025/03/04/2025-projects/ (HTML, a heading
    per lookout), and /YYYY/09/01/YYYY-projects/ for 2014-2024, each of which only embeds a PDF,
    "<year> Completed Projects", a print-out of NMLA's previous website;
  * those 11 PDFs (wp-content/uploads/2025/09/<year>-completed-projects.pdf);
  * the yearly newsletter PDFs 2015-2025 (8 of them twice a year before 2018), for the
    lookout-history articles and the 2024 season (the 2024 projects PDF is only a list of titles);
  * the category pages (/category/projects/, .../completed/ and its page 2, .../in-progress/)
    and the sitemap, to notice a new report. There is no per-lookout list page on the site.
Not read: oral-history interviews and member profiles (people, not lookouts), event pages, and the
Google My Map of "historic, staffed and rental lookouts" linked from the home page (robots.txt
disallows /maps/ on google.com).

The reports are prose, so the facts are curated by hand in nwmt_projects_data.py (our own words,
each fact citing its report) and this script checks every citation against the report's text.
NMLA publishes no coordinates: each lookout's position is copied from its NHLR or FFLA record
(extra.position_from) and the record names the tower we expect it to join (extra.tower_hint).

Licence: no licence stated. Dates, names, dimensions and the kind of work done are facts; the
notes are ours; each event links to the NMLA page or PDF it comes from.

Output: data/sources/nwmt_projects.json
Re-run: python3 pipeline/regional/nwmt_projects.py [--no-check]
"""

from __future__ import annotations

import argparse
import datetime
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import FetchError, fetch, fetch_text  # noqa: E402
import _projects as P  # noqa: E402
import nwmt_projects_data as D  # noqa: E402

SOURCE = "nwmt_projects"
BASE = D.BASE
ASSOCIATION = {"name": "Northwest Montana Lookout Association", "url": f"{BASE}/"}
CREDIT = "Northwest Montana Lookout Association (nwmt-ffla.org)"
LICENSE = (
    "No licence stated; facts only (dates, names, dimensions, the kind of work done). Every note is "
    "our own wording and every event links to the NMLA page or PDF it comes from. Positions are "
    "copied from the NHLR and FFLA records (NMLA publishes none)."
)
PROJECT_POST_RE = re.compile(r"https://nwmt-ffla\.org/(\d{4})/\d\d/\d\d/(\d{4})-projects/?$")


def doc_cache_name(doc: dict) -> str:
    if doc["kind"] == "post":
        return f"{doc['year']}-projects.html"
    return "pdf/" + doc["url"].rsplit("/", 1)[-1]


def load_docs(docs: P.DocSet, *, quiet: bool = False) -> None:
    """Fetch (cached, polite) every report and keep its normalized text for the citation check."""
    for d in D.DOCS:
        docs.add(d["id"], d["url"], d["label"], d["year"])
        try:
            if d["kind"] == "post":
                text = P.html_text(fetch_text(d["url"], SOURCE, doc_cache_name(d), encoding="utf-8"))
            else:
                raw = P.pdf_text(fetch(d["url"], SOURCE, doc_cache_name(d), timeout=90))
                text = P.squash_doubles(raw) if raw is not None else None
        except FetchError as e:
            print(f"  ! {d['id']}: {e}", file=sys.stderr)
            continue
        if text is None:
            if not quiet:
                print(f"  ! {d['id']}: pdftotext not available or failed; citations to it are not checked", file=sys.stderr)
            continue
        docs.texts[d["id"]] = P.norm(text)


def crawl_notes() -> list[str]:
    """Anything on the site that looks like a report nobody has curated yet."""
    notes: list[str] = []
    known = {d["url"] for d in D.DOCS} | {d["page"] for d in D.DOCS}
    seen: set[str] = set()
    for url in D.CATEGORY_PAGES:
        slug = re.sub(r"[^a-z0-9]+", "-", url.removeprefix(BASE).strip("/").lower()) or "home"
        try:
            html = fetch_text(url, SOURCE, f"category-{slug}.html", encoding="utf-8")
        except FetchError as e:
            notes.append(f"could not read {url}: {e}")
            continue
        for u in re.findall(r'href="(https://nwmt-ffla\.org/\d{4}/[^"#?]+)"', html):
            seen.add(u if u.endswith("/") else u + "/")
    try:
        sitemap = fetch_text(f"{BASE}/sitemap.xml", SOURCE, "sitemap.xml", encoding="utf-8")
        locs = set(re.findall(r"<loc>([^<]+)</loc>", sitemap))
    except FetchError as e:
        locs = set()
        notes.append(f"could not read the sitemap: {e}")
    for u in sorted(seen | {u for u in locs if PROJECT_POST_RE.match(u)}):
        if PROJECT_POST_RE.match(u) and u not in known:
            notes.append(f"NEW project report not curated yet: {u}")
    if locs:
        for d in D.DOCS:
            if d["page"] not in locs:
                notes.append(f"{d['id']}: page {d['page']} is not in the sitemap any more")
    return notes


def heading_notes(docs: P.DocSet) -> list[str]:
    """Headings of the 2025/2026 posts that name no curated lookout."""
    keys = [k for lk in D.LOOKOUTS for k in lk["find"]]
    out: list[str] = []
    for doc_id in ("p2026", "p2025"):
        d = next(x for x in D.DOCS if x["id"] == doc_id)
        sections = P.html_sections(fetch_text(d["url"], SOURCE, doc_cache_name(d), encoding="utf-8"))
        for h in P.unmatched_headings(sections, keys):
            if not any(h.lower().startswith(i) for i in D.IGNORED_HEADINGS):
                out.append(f"{doc_id}: heading {h!r} names no curated lookout")
    return out


def build_records(docs: P.DocSet) -> list[dict]:
    index = P.source_index()
    page_of = {d["id"]: d["page"] for d in D.DOCS}
    year_of = {d["id"]: d["year"] for d in D.DOCS}
    order = {d["id"]: i for i, d in enumerate(D.DOCS)}  # posts first, then newer PDFs
    records = []
    for lk in D.LOOKOUTS:
        events = [docs.event(e["year"], e["event"], e["note"], e["cite"]) for e in lk["events"]]
        cited = {c for e in lk["events"] for c in e["cite"]}
        latest = min(cited, key=lambda c: (-year_of[c], order[c]))   # newest report, a post before a PDF
        extra = {"tower_hint": lk["tower"], "unit": lk["unit"]}
        for k in ("discrepancies", "position_note"):
            if lk.get(k):
                extra[k] = lk[k]
        records.append(P.lookout_record(
            source=SOURCE, association=ASSOCIATION, slug=lk["slug"], name=lk["name"], region="MT",
            url=page_of[latest], position_key=lk["pos"], index=index, forest=lk["unit"],
            agency=lk.get("agency"), ownership=lk.get("ownership"), design=lk.get("design"),
            height_ft=lk.get("height_ft"), staffing=lk.get("staffing"), status="standing",
            aliases=lk.get("aliases"), events=events, extra=extra))
    return records


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--no-check", action="store_true", help="skip the citation check against the report text")
    args = ap.parse_args()
    retrieved = datetime.date.today().isoformat()

    docs = P.DocSet(SOURCE)
    load_docs(docs)
    for note in crawl_notes() + heading_notes(docs):
        print("  ! " + note, file=sys.stderr)
    records = build_records(docs)

    problems = P.check_citations(records, {f"{SOURCE}:mt:{lk['slug']}": lk["find"] for lk in D.LOOKOUTS}, docs)
    hard = [p for p in problems if not p.startswith("(not checked")]
    for p in problems:
        print("  ! " + p, file=sys.stderr)
    if hard and not args.no_check:
        raise SystemExit(f"{len(hard)} citation problem(s); fix nwmt_projects_data.py (or pass --no-check)")

    out = P.REPO_ROOT / "data" / "sources" / f"{SOURCE}.json"
    P.write_association_source(out, source=SOURCE, association=ASSOCIATION, url=ASSOCIATION["url"], retrieved=retrieved,
                               license_=LICENSE, credit=CREDIT, records=records)
    events = sum(len(r["events"]) for r in records)
    print(f"wrote {len(records)} lookouts, {events} events -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
