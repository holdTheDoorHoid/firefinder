"""Fetcher for "Firetowers of Saskatchewan" (websiteservice.ca/firetowers_page4.htm), 2026-10-20.

Chris Rule's one-page directory of Saskatchewan's provincial fire towers and the Prince Albert National
Park towers, built from Maurice Bourassa's work: per tower a LOCATION (latitude x longitude, written as
degrees-minutes-seconds "53-42-41.9 X 105-59-52.2" or degrees and decimal minutes "53-22.1000 X
102-32.3667", longitudes west without a sign), often a legal land description ("LSD 14-36-54-28-W2"),
HEIGHT and tower class ("80'  Heavy steel", "40' wood"), YEAR of CONSTRUCTION (rarely filled in), the
towermen's names, NOTES, and photo thumbnails. The page is the only source with positions for the old
Saskatchewan network (Prairies/North survey, docs/sources/expansion_prairies-north.md).

What is kept (facts only, DESIGN.md 2): name, position, legal land description, height, material, a
full four-digit construction year, a "new cupola <year>" note as a dated change, the photos (credited
to the site, mirrored like every source's), and the page link. Towermen's names and the notes' prose
are not stored.

Positions. Read exactly as printed; a page slip of spacing or separators is not a different number
("53-19--53.7", a degree split over two lines "5 / 5-07-08.9", "56-54,6833 X 108.09.3833" for decimal
minutes). A value that cannot be a Saskatchewan position as printed (minutes or seconds of 60 or more,
a longitude of 197 degrees, a latitude of "5353") is not used and never "fixed" by guessing which digit
is wrong: the record keeps the text in `extra.coords_raw` with `extra.position_note`, and the merge
lists it on the can't-place-yet page (Dube, Molonosa, Piwei, Ridge; the survey found the same four).
The province comes from the position (Natural Earth admin-1, regions.Admin1Lookup): Duck Mountain and
Porcupine, listed here, stand east of 102 W in Manitoba.

robots.txt: none (404). One page, fetched once by the survey; this module reads the survey's copy and
fetches only if it is missing.

Output: data/sources/websiteservice_sk.json
Re-run: python3 pipeline/regional/websiteservice_sk.py
"""

from __future__ import annotations

import datetime
import html as htmlmod
import pathlib
import re
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _common import RAW_ROOT, fetch_text, slugify, write_source_json  # noqa: E402
sys.path.insert(1, str(HERE.parent))
import regions  # noqa: E402

SOURCE = "websiteservice_sk"
URL = "https://www.websiteservice.ca/firetowers_page4.htm"
CACHE_REL = "www.websiteservice.ca/firetowers_page4.htm"
SURVEY_COPY = RAW_ROOT / "expansion" / "prairies-north" / "ws_firetowers_page4.htm"
OUT = HERE.parent.parent / "data" / "sources" / f"{SOURCE}.json"
LICENSE = ("No licence stated; facts only (name, position, legal land description, height, material, build year, "
           "a dated cupola change, photos with credit, a link to the page). Towermen's names and notes are not stored.")
CREDIT = "Firetowers of Saskatchewan (websiteservice.ca), Chris Rule, from the work of Maurice Bourassa"

DMS_RE = re.compile(r"(?P<la>\d{1,4})\s*-+\s*(?P<lm>\d{1,2})\s*-+\s*(?P<ls>\d{1,2}(?:\.\d+)?)\s*X\s*"
                    r"(?P<oa>\d{2,3})\s*-+\s*(?P<om>\d{1,2})\s*-+\s*(?P<os>\d{1,2}(?:\.\d+)?)", re.I)
DM_RE = re.compile(r"(?P<la>\d{1,4})\s*-\s*(?P<lm>\d{1,2}[.,]\d+)\s*X\s*(?P<oa>\d{2,3})\s*[-.]\s*(?P<om>\d{1,2}[.,]\d+)", re.I)
LSD_RE = re.compile(r"\b(?:LSD\s*)?(\d{1,2}\s*[-=]\s*\d{1,2}\s*-\s*\d{1,3}\s*-\s*\d{1,2}\s*-\s*W\s*[23])\b", re.I)
HEIGHT_RE = re.compile(r"(\d{2,3})\s*'")
MATERIAL_RE = re.compile(r"\b(steel|wood|wooden|timber)\b", re.I)
CUPOLA_RE = re.compile(r"\bnew cupola\s+(1[89]\d\d|20[0-2]\d)\b", re.I)
PHOTO_RE = re.compile(r'<a\s+href="(towerstuff/[^"]+\.(?:jpe?g|png|gif))"', re.I)
CELL_RE = re.compile(r'<td[^>]*valign="top"[^>]*>(.*?)</td>', re.S | re.I)
LABELS = ("LOCATION", "HEIGHT", "YEAR of CONSTRUCTION", "NAMES of TOWERMEN", "NOTES")


def page_html() -> str:
    dest = RAW_ROOT / SOURCE / CACHE_REL
    if not dest.exists() and SURVEY_COPY.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SURVEY_COPY, dest)
    return fetch_text(URL, SOURCE, CACHE_REL, encoding="latin-1")


def text_of(fragment: str) -> str:
    t = re.sub(r"<!--.*?-->|<!\[if[^>]*>|<!\[endif\]>", " ", fragment, flags=re.S)
    t = re.sub(r"<(?:p|br|div|tr)[^>]*>", "\n", t, flags=re.I)
    t = htmlmod.unescape(re.sub(r"<[^>]+>", " ", t)).replace("\xa0", " ")
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in t.split("\n") if line.strip())


def fields(cell_text: str) -> dict:
    """{"name", "LOCATION", "HEIGHT", ...} from a tower's cell: the name is the text before LOCATION,
    each label's value the text up to the next label."""
    flat = re.sub(r"\s+", " ", cell_text)
    pat = r"(LOCATION(?:\s*\(\s*\d+\s*locations over the years\))?|HEIGHT:?|YEAR\s+of\s+CONSTRUCTION|NAMES\s+of\s+TOWERMEN|NOTES\s*-?)"
    parts = re.split(pat, flat, flags=re.I)
    out = {"name": parts[0].strip()}
    for i in range(1, len(parts) - 1, 2):
        label = parts[i].upper()
        key = next(lb for lb in LABELS if label.startswith(lb.upper().split()[0]) and
                   (lb != "NAMES of TOWERMEN" or "TOWERMEN" in label) and (lb != "NOTES" or label.startswith("NOTES")))
        out[key] = (out.get(key, "") + " " + parts[i + 1]).strip()
    return out


def parse_position(text: str) -> tuple[float | None, float | None, str | None, str | None]:
    """(lat, lon, the printed text, why it was not used). Longitudes are west."""
    t = re.sub(r"^(\d)\s+(?=\d-)", r"\1", (text or "").strip())   # "5 / 5-07-08.9": a degree split over two lines
    m = DMS_RE.search(t)
    if m:
        la, lm, ls, oa, om, os_ = (float(m.group(k)) for k in ("la", "lm", "ls", "oa", "om", "os"))
        raw = m.group(0)
        if lm >= 60 or ls >= 60 or om >= 60 or os_ >= 60 or not (49 <= la <= 60) or not (101 <= oa <= 110):
            return None, None, raw, "printed with impossible degrees, minutes or seconds"
        return round(la + lm / 60 + ls / 3600, 5), -round(oa + om / 60 + os_ / 3600, 5), raw, None
    m = DM_RE.search(t)
    if m:
        la, oa = float(m.group("la")), float(m.group("oa"))
        lm, om = float(m.group("lm").replace(",", ".")), float(m.group("om").replace(",", "."))
        raw = m.group(0)
        if lm >= 60 or om >= 60 or not (49 <= la <= 60) or not (101 <= oa <= 110):
            return None, None, raw, "printed with impossible degrees or minutes"
        return round(la + lm / 60, 5), -round(oa + om / 60, 5), raw, None
    if re.search(r"\d{2,4}\s*-\s*\d{1,2}[-.,]\d+\s*X", t, re.I):
        return None, None, t.strip()[:60], "not a readable position as printed"
    return None, None, None, None


def tidy_name(name: str) -> str:
    n = re.sub(r"\s+", " ", name).strip(" -:")
    n = re.sub(r"\b([A-Z])([A-Z'’]+)\b", lambda m: m.group(1) + m.group(2).lower(), n)
    return n


def records_from(html: str, admin1=None) -> list[dict]:
    cells = [(m.start(), m.end(), m.group(1)) for m in CELL_RE.finditer(html)]
    towers = [(s, e, c) for s, e, c in cells if "LOCATION" in c.upper() and "TOWERMEN" in c.upper()]
    out: list[dict] = []
    for n, (s, e, cell) in enumerate(towers):
        nxt = towers[n + 1][0] if n + 1 < len(towers) else len(html)
        f = fields(text_of(cell))
        raw_name = f.get("name") or ""
        if not re.search(r"[A-Za-z]", raw_name):
            continue
        name = tidy_name(raw_name)
        lat, lon, coords_raw, why = parse_position(f.get("LOCATION", ""))
        region = "SK"
        if lat is not None and admin1 is not None:
            region = admin1.nearest_region(lat, lon) or "SK"
        if lat is not None and region not in ("SK", "MB", "AB"):
            why, lat, lon = f"the position falls outside the prairie provinces ({region})", None, None
            region = "SK"
        lsd = LSD_RE.search(f.get("LOCATION", ""))
        height = HEIGHT_RE.search(f.get("HEIGHT", ""))
        mat = MATERIAL_RE.search(f.get("HEIGHT", ""))
        year = re.search(r"\b(1[89]\d\d|20[0-2]\d)\b", f.get("YEAR of CONSTRUCTION", ""))
        events = []
        if year:
            events.append({"year": int(year.group(1)), "event": "built", "note": None, "from": SOURCE})
        for cy in sorted({int(y) for y in CUPOLA_RE.findall(f.get("NOTES", "") + " " + f.get("HEIGHT", ""))}):
            events.append({"year": cy, "event": "modified", "note": "A new cupola was put on the tower this year.",
                           "from": SOURCE, "source_url": URL})
        extra: dict = {}
        if coords_raw:
            extra["coords_raw"] = coords_raw
        if why:
            extra["position_note"] = f"The page's position ({coords_raw}) is not used: {why}."
        if lsd:
            extra["legal_land_description"] = re.sub(r"\s+", "", lsd.group(1)).replace("=", "-").upper()
        loc_text = re.sub(r"\s+", " ", f.get("LOCATION", "")).strip()
        if lat is None and not coords_raw and loc_text:
            # no position, only a land description or a place ("Macdowel Block, North of Duck Lake"):
            # kept for people, never converted into a position here
            extra["location_text"] = re.sub(r"\s*\d{4}\s*-\s*\d{4}.*$", "", loc_text)[:80]
        if height:
            extra["height_ft"] = int(height.group(1))
        if mat:
            extra["material_text"] = mat.group(1).lower()
        if re.search(r"prince albert national park|\bPANP\b", html[max(0, s - 4000):s], re.I):
            pass
        photos = []
        for href in dict.fromkeys(PHOTO_RE.findall(html[e:nxt])):
            photos.append({"url": "https://www.websiteservice.ca/" + href, "credit": CREDIT, "caption": None,
                           "year": None, "source_url": URL})
        out.append({
            "key": None, "url": URL, "name": f"{name} Fire Tower" if not re.search(r"\btower\b", name, re.I) else name,
            "country": "CA", "region": region, "county": None, "lat": lat, "lon": lon, "elevation_m": None,
            "type_raw": None, "kind": "tower", "status_raw": None, "status": "unknown", "registers": [],
            "built": int(year.group(1)) if year else None, "agency": None, "events": events, "photos": photos,
            "links": [{"label": f"Firetowers of Saskatchewan (websiteservice.ca): {name}", "url": URL, "kind": "site"}],
            "rental": None, "extra": extra,
        })
    return merge_repeats(out)


def merge_repeats(recs: list[dict]) -> list[dict]:
    """The page lists three Prince Albert National Park towers twice (in the provincial list and in the
    park's section): one record each, positions and photos combined. Keys are fixed afterwards."""
    out: list[dict] = []
    def core(n: str) -> str:
        return slugify(re.sub(r"\b(?:fire\s+)?tower\b", " ", n, flags=re.I))
    for r in recs:
        k = core(r["name"])
        twin = next((o for o in out if core(o["name"]) == k and o["region"] == r["region"] and (
            o["lat"] is None or r["lat"] is None or (abs(o["lat"] - r["lat"]) < 0.01 and abs(o["lon"] - r["lon"]) < 0.01))), None)
        if twin is None:
            out.append(r)
            continue
        for f in ("lat", "lon", "built"):
            if twin[f] is None and r[f] is not None:
                twin[f] = r[f]
        twin["photos"] += [p for p in r["photos"] if p["url"] not in {q["url"] for q in twin["photos"]}]
        for k2, v in r["extra"].items():
            twin["extra"].setdefault(k2, v)
        twin["events"] += [e for e in r["events"] if (e["event"], e["year"]) not in {(x["event"], x["year"]) for x in twin["events"]}]
        twin["extra"]["listed_twice"] = True
    counts: dict[str, int] = {}
    for r in out:
        base = f"{SOURCE}:{r['region'].lower()}:{slugify(r['name'])}"
        counts[base] = counts.get(base, 0) + 1
        r["key"] = base + (f"-{counts[base]}" if counts[base] > 1 else "")
        if r["lat"] is not None and "position_note" in r["extra"]:
            r["extra"].pop("position_note")
    return sorted(out, key=lambda r: r["key"])


def main() -> int:
    html = page_html()
    admin1 = regions.admin1_lookup(RAW_ROOT)
    records = records_from(html, admin1)
    page = RAW_ROOT / SOURCE / CACHE_REL
    write_source_json(OUT, source=SOURCE, title="Firetowers of Saskatchewan (websiteservice.ca)", url=URL,
                      retrieved=datetime.date.fromtimestamp(page.stat().st_mtime).isoformat(),
                      license_=LICENSE, records=records, header_extra={"credit": CREDIT})
    from collections import Counter
    print(f"wrote {len(records)} records -> {OUT}; by region {dict(Counter(r['region'] for r in records))}; "
          f"with a position {sum(1 for r in records if r['lat'] is not None)}; not used "
          f"{[r['name'] for r in records if r['extra'].get('position_note')]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
