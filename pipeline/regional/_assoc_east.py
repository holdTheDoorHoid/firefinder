"""Shared plumbing for the eastern lookout-association project sources.

Each association module (nysffla_projects.py, st_regis_friends.py, ...) is the same job as
nwmt_projects.py: read the group's reports, write down once and in our own words what they say was
done to which lookout, check every citation against the report text, and write
data/sources/<source>.json in the shared shape of _projects.py. What differs between groups is only
where the reports are and what they say, so the common steps live here:

  * ``load_docs``       fetch (polite, cached under $FIREFINDER_RAW_ROOT/<source>/) every report in a
                        group's DOCS list, HTML page or PDF, and keep its normalized text;
  * ``build_records``   one record per curated lookout (``position_key`` copied from the register
                        entry of the tower it should join, ``extra.tower_hint`` naming that tower);
  * ``run``             load, build, check citations, write: the ``main()`` of every module.

Python 3.12 standard library only (pdftotext, from poppler, reads the PDFs).
"""

from __future__ import annotations

import argparse
import datetime
import html as _html
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import _common  # noqa: E402
from _common import FetchError, fetch  # noqa: E402
import _projects as P  # noqa: E402


def E(year: int | None, event: str, note: str, *cite: str) -> dict:
    """One curated event: ``E(2016, "restored", "New roof flown in and fitted.", "restoration")``."""
    return {"year": year, "event": event, "note": note, "cite": list(cite)}


def doc(doc_id: str, url: str, label: str, year: int | None, *, page: str | None = None, cache: str | None = None,
        kind: str | None = None) -> dict:
    """A report. ``kind`` is "pdf" (read with pdftotext) or "html" (default unless the URL ends .pdf);
    ``page`` is the page to link to when it differs from ``url`` (a PDF on a newsletter page);
    ``cache`` the file name under the source's cache directory."""
    kind = kind or ("pdf" if url.lower().split("?")[0].endswith(".pdf") else "html")
    return {"id": doc_id, "url": url, "label": label, "year": year, "page": page or url, "kind": kind,
            "cache": cache or (doc_id + (".pdf" if kind == "pdf" else ".html"))}


def page_text(page: str) -> str:
    """Plain text of an HTML page: scripts, styles and tags dropped, entities decoded. Pages of the
    old hand-made sites (font tags, <br>) and WordPress alike."""
    t = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", "", page)
    t = re.sub(r"(?s)<!--.*?-->", "", t)
    t = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h\d>|</tr>|</td>", "\n", t)
    t = _html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"[ \t\r\f\v\xa0]+", " ", t)


def load_docs(source: str, docs: P.DocSet, specs: list[dict], *, quiet: bool = False, timeout: float = 90.0,
              crawl_delay: float | None = None) -> None:
    """Register every report in ``docs`` and read its text (fetched once, cached, 2 s apart per host, or
    ``crawl_delay`` seconds when the site's robots.txt asks for a longer Crawl-delay)."""
    if crawl_delay:
        _common.MIN_INTERVAL_S = max(_common.MIN_INTERVAL_S, crawl_delay)
    for d in specs:
        docs.add(d["id"], d["page"], d["label"], d["year"])
        try:
            raw = fetch(d["url"], source, d["cache"], timeout=timeout)
        except FetchError as e:
            print(f"  ! {d['id']}: {e}", file=sys.stderr)
            continue
        if d["kind"] == "pdf":
            text = P.pdf_text(raw)
            if text is None:
                if not quiet:
                    print(f"  ! {d['id']}: pdftotext not available or failed; citations to it are not checked", file=sys.stderr)
                continue
        else:
            text = page_text(raw.decode("utf-8", errors="replace"))
        if not text.strip():
            if not quiet:
                print(f"  ! {d['id']}: no text (an image-only PDF?); citations to it are not checked", file=sys.stderr)
            continue
        docs.texts[d["id"]] = P.norm(text)


def build_records(source: str, association: dict, region: str, lookouts: list[dict], docs: P.DocSet,
                  specs: list[dict]) -> list[dict]:
    """One record per curated lookout. Each lookout dict: slug, name, tower (the tower id it should
    join), pos (register key to copy the position from), find (names to look for in the reports),
    events (``E(...)``), optional agency, ownership, design, height_ft, staffing, status, aliases,
    unit, county, page (the lookout's own page, when the group has one), position_note, extra."""
    index = P.source_index()
    page_of = {d["id"]: d["page"] for d in specs}
    year_of = {d["id"]: d["year"] or 0 for d in specs}
    order = {d["id"]: i for i, d in enumerate(specs)}
    records = []
    for lk in lookouts:
        events = [docs.event(e["year"], e["event"], e["note"], e["cite"]) for e in lk["events"]]
        cited = {c for e in lk["events"] for c in e["cite"]}
        latest = min(cited, key=lambda c: (-year_of[c], order[c]))
        extra = {"tower_hint": lk["tower"]}
        if lk.get("unit"):
            extra["unit"] = lk["unit"]
        for k in ("discrepancies", "position_note"):
            if lk.get(k):
                extra[k] = lk[k]
        extra.update(lk.get("extra") or {})
        records.append(P.lookout_record(
            source=source, association=association, slug=lk["slug"], name=lk["name"], region=region,
            url=lk.get("page") or page_of[latest], position_key=lk["pos"], index=index,
            county=lk.get("county"), forest=lk.get("unit"), agency=lk.get("agency"), ownership=lk.get("ownership"),
            design=lk.get("design"), height_ft=lk.get("height_ft"), staffing=lk.get("staffing"),
            status=lk.get("status", "unknown"), aliases=lk.get("aliases"), events=events, extra=extra))
    return records


def run(*, source: str, association: dict, credit: str, license_: str, region: str, specs: list[dict],
        lookouts: list[dict], description: str, crawl_delay: float | None = None) -> None:
    """The main() of an association module: fetch, build, check, write."""
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--no-check", action="store_true", help="skip the citation check against the report text")
    args = ap.parse_args()
    retrieved = datetime.date.today().isoformat()

    docs = P.DocSet(source)
    load_docs(source, docs, specs, crawl_delay=crawl_delay)
    records = build_records(source, association, region, lookouts, docs, specs)
    problems = P.check_citations(records, {f"{source}:{region.lower()}:{lk['slug']}": lk["find"] for lk in lookouts}, docs)
    hard = [p for p in problems if not p.startswith("(not checked")]
    for p in problems:
        print("  ! " + p, file=sys.stderr)
    if hard and not args.no_check:
        raise SystemExit(f"{len(hard)} citation problem(s); fix the curated facts for {source} (or pass --no-check)")

    out = P.REPO_ROOT / "data" / "sources" / f"{source}.json"
    P.write_association_source(out, source=source, association=association, url=association["url"], retrieved=retrieved,
                               license_=license_, credit=credit, records=records)
    events = sum(len(r["events"]) for r in records)
    print(f"wrote {len(records)} lookouts, {events} events -> {out}", file=sys.stderr)
