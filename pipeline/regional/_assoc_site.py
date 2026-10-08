"""Shared driver for the small association-project modules (one site, a few dozen pages or PDFs).

The association-project shape (``_projects.py``, DESIGN.md 3.7) says what a record looks like;
this module is the part every curated module repeats: fetch the cited pages and reports
(cached, polite, robots-checked by ``_common.fetch``), read their text, build each lookout's
record from a plain dict, check every cited fact against the text of the report that cites it,
and write ``data/sources/<source>.json``. A module is then only its data:

    SOURCE = "sand_mountain"
    ASSOCIATION = {"name": "...", "url": "https://..."}
    DOCS = [doc("gold", "https://.../gold-butte/", "Gold Butte Lookout (SMS)", 2025), ...]
    LOOKOUTS = [dict(slug=..., name=..., region="OR", tower="us-or-gold-butte", pos="nhlr:US 134",
                     find=["Gold Butte"], events=[E(1934, "built", "...", "gold")]), ...]
    if __name__ == "__main__":
        run(__doc__, SOURCE, ASSOCIATION, DOCS, LOOKOUTS, credit=..., license_=...)

``tower`` is the tower id the record is expected to join (``extra.tower_hint``); it is only a
note for the person checking the merge, never read by merge. ``pos`` is a source record key to
copy the position from (``_projects.lookout_record``'s ``position_key``); ``position_note``
instead names where a position came from when no list we hold has the lookout.

Python 3.12 standard library only.
"""

from __future__ import annotations

import argparse
import datetime
import html as _html
import pathlib
import re as _re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import FetchError, fetch, fetch_text  # noqa: E402
import _projects as P  # noqa: E402


def E(year: int | None, event: str, note: str, *cite: str, inferred: str | None = None) -> dict:
    """One dated fact in our own words, citing the documents (by id) that give it. ``inferred``
    says how the year was worked out when the report never prints it ("the season after 1967"):
    the citation check then does not insist on finding the year in the report."""
    e = {"year": year, "event": event, "note": note, "cite": list(cite)}
    if inferred:
        e["inferred"] = inferred
    return e


def doc(doc_id: str, url: str, label: str, year: int | None = None, *, kind: str = "html",
        cache: str | None = None, page: str | None = None) -> dict:
    """A page or PDF the module cites. ``year`` is the season a report covers (None for a page
    that is not one year's report); ``page`` is the web page that carries a PDF, when the
    link on the tower should go there instead of to the file."""
    return {"id": doc_id, "url": url, "label": label, "year": year, "kind": kind, "cache": cache, "page": page or url}


def page_text(page: str) -> str:
    """All the visible text of an HTML page (tables and boxes included, which ``P.html_text``,
    meant for a post's paragraphs, leaves out). Only used to check citations."""
    page = _re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", page)
    page = _re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|td|th|h[1-6]|table|section|article)>", "\n", page)
    return _html.unescape(_re.sub(r"<[^>]+>", " ", page))


def fold(text: str) -> str:
    """A comparison form that survives pdftotext's habit of dropping the letters of the "ti",
    "tt", "ft" and "fi" ligatures ("Kelly Bu e", "restora on"): lower case, only letters and
    digits, and the letters t, f and i removed. Names and years are compared in this form."""
    return _re.sub(r"[^a-z0-9]|[tfi]", "", text.lower())


def _cache_name(d: dict) -> str:
    if d.get("cache"):
        return d["cache"]
    tail = d["url"].split("//", 1)[-1].replace("/", "_").strip("_")
    return tail[:120] + (".pdf" if d["kind"] == "pdf" else ".html")


def load_docs(source: str, spec: list[dict], docs: P.DocSet, *, quiet: bool = False, folded: bool = False) -> list[str]:
    """Register every document in ``docs`` and read the text of those that can be fetched into
    ``docs.texts`` (normalised, for the citation check). Returns the ids that could not be read."""
    unread: list[str] = []
    for d in spec:
        docs.add(d["id"], d["page"], d["label"], d["year"])
        try:
            if d["kind"] == "pdf":
                raw = P.pdf_text(fetch(d["url"], source, _cache_name(d), timeout=90))
                text = P.squash_doubles(raw) if raw is not None else None
            else:
                text = page_text(fetch_text(d["url"], source, _cache_name(d), encoding="utf-8"))
        except FetchError as e:
            print(f"  ! {d['id']}: {e}", file=sys.stderr)
            unread.append(d["id"])
            continue
        if text is not None and not text.strip():
            text = None  # an image-only scan: nothing to check against
        if text is None:
            if not quiet:
                print(f"  ! {d['id']}: could not read the text; citations to it are not checked", file=sys.stderr)
            unread.append(d["id"])
            continue
        docs.texts[d["id"]] = fold(text) if folded else P.norm(text)
    return unread


def build_records(source: str, association: dict, spec: list[dict], lookouts: list[dict], docs: P.DocSet,
                  index: dict[str, dict] | None = None) -> list[dict]:
    index = P.source_index() if index is None else index
    year_of = {d["id"]: d["year"] or 0 for d in spec}
    order = {d["id"]: i for i, d in enumerate(spec)}
    records = []
    for lk in lookouts:
        events = [docs.event(e["year"], e["event"], e["note"], e["cite"]) for e in lk["events"]]
        cited = {c for e in lk["events"] for c in e["cite"]}
        # the lookout's page: the one named, else the newest cited report (the first listed on a tie)
        url = lk.get("url") or docs.url(min(cited, key=lambda c: (-year_of[c], order[c])))
        extra = {"tower_hint": lk["tower"]} if lk.get("tower") else {}
        for k in ("discrepancies", "position_note", "unit", "moved_from", "moved_to"):
            if lk.get(k):
                extra[k] = lk[k]
        records.append(P.lookout_record(
            source=source, association=association, slug=lk["slug"], name=lk["name"], region=lk["region"], url=url,
            position_key=lk.get("pos"), index=index, county=lk.get("county"), forest=lk.get("forest"),
            agency=lk.get("agency"), ownership=lk.get("ownership"), design=lk.get("design"),
            height_ft=lk.get("height_ft"), staffing=lk.get("staffing"), status=lk.get("status", "unknown"),
            kind=lk.get("kind", "unknown"), type_raw=lk.get("type_raw"), aliases=lk.get("aliases"),
            events=events, links=lk.get("links"), extra=extra))
    return records


def drop_inferred(problems: list[str], source: str, lookouts: list[dict]) -> list[str]:
    """Remove the 'never mentions <year>' problems of events whose year is declared ``inferred``."""
    skip = set()
    for lk in lookouts:
        for e in lk["events"]:
            if e.get("inferred"):
                key = f"{source}:{lk['region'].lower()}:{lk['slug']} {e['event']} {e['year']} cites "
                skip.add((key, f"the report never mentions {e['year']}"))
    return [p for p in problems if not any(p.startswith(k) and p.endswith(tail) for k, tail in skip)]


def run(doc_text: str, source: str, association: dict, spec: list[dict], lookouts: list[dict], *,
        credit: str, license_: str, title: str | None = None, argv: list[str] | None = None, folded: bool = False) -> None:
    ap = argparse.ArgumentParser(description=(doc_text or "").strip().split("\n")[0])
    ap.add_argument("--no-check", action="store_true", help="skip the citation check against the report text")
    args = ap.parse_args(argv)

    docs = P.DocSet(source)
    load_docs(source, spec, docs, folded=folded)
    records = build_records(source, association, spec, lookouts, docs)

    keys = {f"{source}:{lk['region'].lower()}:{lk['slug']}": [fold(k) for k in lk["find"]] if folded else lk["find"] for lk in lookouts}
    problems = P.check_citations(records, keys, docs)
    problems = drop_inferred(problems, source, lookouts)
    hard = [p for p in problems if not p.startswith("(not checked")]
    for p in problems:
        print("  ! " + p, file=sys.stderr)
    if hard and not args.no_check:
        raise SystemExit(f"{len(hard)} citation problem(s); fix {source}'s data (or pass --no-check)")

    out = P.REPO_ROOT / "data" / "sources" / f"{source}.json"
    P.write_association_source(out, source=source, association=association, url=association["url"],
                               retrieved=datetime.date.today().isoformat(), license_=license_, credit=credit,
                               title=title, records=records)
    print(f"wrote {len(records)} lookouts, {sum(len(r['events']) for r in records)} events -> {out}", file=sys.stderr)
