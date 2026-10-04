#!/usr/bin/env python3
"""Fetch and parse the Forest Fire Lookout Association (firelookout.org) registry.

Writes data/sources/ffla.json (see DESIGN.md section 3.2 for the record shape).
Resumable: every page fetched is cached under
/home/hoid/Desktop/firefinder/data/raw/ffla/ and a re-run reads from that cache
instead of refetching.

Usage:
    python3 pipeline/fetch_ffla.py
"""
from __future__ import annotations

import html as html_mod
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RateLimiter, RobotsCache, STATE_ABBR, fetch, slugify, write_log  # noqa: E402
from state_bbox import flag_coordinate  # noqa: E402

SOURCE = "ffla"
BASE = "https://firelookout.org"
INDEX_URL = f"{BASE}/lookouts/us/"

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "sources" / "ffla.json"
# Logs/reports are crawl artifacts, not deliverables -- keep them in the shared,
# git-ignored raw-cache tree rather than inside the committed worktree.
from common import RAW_ROOT  # noqa: E402

LOG_PATH = RAW_ROOT / "_logs" / "fetch_ffla.log"
REPORT_PATH = RAW_ROOT / "_logs" / "fetch_ffla_report.json"

TAG_RE = re.compile(r"<[^>]+>")
A_HREF_RE = re.compile(r'<a\s+[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.S | re.I)


def strip_tags(s: str) -> str:
    s = TAG_RE.sub(" ", s)
    s = html_mod.unescape(s)
    s = s.replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def log(msg: str) -> None:
    print(msg, flush=True)
    write_log(LOG_PATH, msg)


# ---------------------------------------------------------------------------
# Index page: which states have a master table, an "-add" page, NHLR/FFLOS links
# ---------------------------------------------------------------------------

def parse_index(html: str) -> list[dict]:
    idx = html.find("<table")
    end = html.find("</table>", idx) + len("</table>")
    table = html[idx:end]
    rows = re.findall(r"<tr>(.*?)</tr>", table, re.S)
    out = []
    for r in rows[1:]:  # skip header row
        tds = re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)
        if len(tds) < 3:
            continue
        name_cell = tds[0]
        m = A_HREF_RE.search(name_cell)
        table_url = None
        if m:
            table_url = m.group(1)
            if table_url.startswith("/"):
                table_url = BASE + table_url
            if table_url.startswith("http://"):
                table_url = "https://" + table_url[len("http://"):]
        state_name = strip_tags(name_cell)
        total = strip_tags(tds[1]) or None
        standing = strip_tags(tds[2]) or None
        add_url = None
        for extra_cell in tds[3:]:
            m2 = A_HREF_RE.search(extra_cell)
            if m2 and "add" in m2.group(1):
                add_url = m2.group(1)
                if add_url.startswith("http://"):
                    add_url = "https://" + add_url[len("http://"):]
        abbr = STATE_ABBR.get(state_name)
        if not abbr:
            log(f"WARN: unrecognized state name in index: {state_name!r}")
            continue
        out.append(
            {
                "state": state_name,
                "abbr": abbr,
                "table_url": table_url,
                "add_url": add_url,
                "total": total,
                "standing": standing,
            }
        )
    return out


# ---------------------------------------------------------------------------
# State table page -> source records
# ---------------------------------------------------------------------------

HEADER_SYNONYMS = {
    "name": "name",
    "tower name": "name",
    "lookout name": "name",
    "county": "county",
    "lat": "lat",
    "latitude": "lat",
    "long": "lon",
    "lon": "lon",
    "longitude": "lon",
    "type": "type",
    "status": "status",
    "nhlr/fflos": "register",
    "nhlr / fflos": "register",
    "nhlr": "register",
    "fflos": "register",
    "register": "register",
    "elevation": "elevation",
    "elev": "elevation",
}

REGISTER_CELL_RE = re.compile(
    r"(NHLR|FFLOS)\s+(US\s*#?\s*\d+)\s*,?\s*([A-Za-z]{2}\s*#?\s*\d+)?", re.I
)

KIND_MAP = {
    "tower": "tower",
    "ground": "ground",
    "2-story cab": "two_story",
    "2 story cab": "two_story",
    "2-storycab": "two_story",
    "two-story cab": "two_story",
    "3-story cab": "three_story",
    "3 story cab": "three_story",
    "3-storycab": "three_story",
    "three-story cab": "three_story",
    "encl. tower": "enclosed_tower",
    "enclosed tower": "enclosed_tower",
    "platform": "platform",
    "tree": "tree",
    "tree platform": "tree",
    "camp": "camp",
    "beacon tower": "tower",
    "unknown": "unknown",
    # confident additional variants seen across state tables (DESIGN: "do not assume
    # every state uses identical columns" -- these are still clearly one of the vocab
    # kinds once the qualifier is read off)
    "enclosed tower": "enclosed_tower",
    "open tower": "tower",
    "obs tower": "tower",
    "obs. tower": "tower",
    "observation tower": "tower",
    "stone tower": "tower",
    "stone obs tower": "tower",
    "radio tower": "tower",
    "windmill tower": "tower",
    "clock tower": "tower",
    "security tower": "tower",
    "rooftop tower": "tower",
    "non-fire tower": "tower",
    "log tower": "tower",
    "aws tower": "tower",
    "wooden tower": "tower",
    "tower (unk)": "tower",
    "tower?": "tower",
    "tower/ground": "tower",
    "tower/ground*": "tower",
    "crowsnest": "platform",
    "crows nest": "platform",
    "platform tower": "platform",
    "platforms": "platform",
    "platfrom": "platform",  # typo seen on source pages
    "tree cab": "tree",
    "tree platform": "tree",
    "3-story stone": "three_story",
    "2-story": "two_story",
    "3-story": "three_story",
    "stone hut": "ground",
}

# DESIGN vocab status is {standing, gone, relocated, ruins, replica, unknown}. Several
# state tables fold a status *and* a year into one cell (e.g. "Burned 2026"); that year
# is pulled out into an `events` entry by extract_status_year() below rather than lost.
STATUS_MAP = {
    "standing": "standing",
    "gone": "gone",
    "abandoned": "gone",
    "removed": "gone",
    "burned": "gone",
    "relocated": "relocated",
    "replica": "replica",
    "ruins": "ruins",
    "standing (ruins)": "ruins",
    "unknown": "unknown",
    "new": "standing",
}

STATUS_YEAR_RE = re.compile(r"^(standing|gone|new|removed|burned)\s+(\d{4})$", re.I)
STATUS_YEAR_EVENT = {"new": "built", "removed": "removed", "burned": "burned"}


def map_kind(raw: str, stats: Counter) -> str:
    key = raw.strip().lower().rstrip("*").strip()
    stats[raw.strip()] += 1
    return KIND_MAP.get(key, "unknown")


def map_status(raw: str, stats: Counter) -> tuple[str, bool, dict | None]:
    stats[raw.strip()] += 1
    key = raw.strip().lower().rstrip("*").strip()
    has_star = key == "standing" and "*" in raw  # the FFLA "Standing*" legend specifically
    event = None
    ym = STATUS_YEAR_RE.match(key)
    if ym:
        word, year = ym.group(1).lower(), int(ym.group(2))
        base_status = STATUS_MAP.get(word, "unknown")
        ev_name = STATUS_YEAR_EVENT.get(word)
        if ev_name:
            event = {
                "year": year,
                "event": ev_name,
                "note": f"From FFLA status column value {raw.strip()!r}",
                "from": "ffla",
            }
        return base_status, False, event
    return STATUS_MAP.get(key, "unknown"), has_star, None


def parse_register_cell(cell_html: str) -> tuple[list[dict], list[dict]]:
    """Returns (registers, links) parsed from a NHLR/FFLOS register table cell."""
    text = strip_tags(cell_html)
    if not text or text in ("&nbsp;",):
        return [], []
    registers = []
    links = []
    m = REGISTER_CELL_RE.search(text)
    if m:
        register, us_num, st_num = m.groups()
        registers.append(
            {
                "register": register.upper(),
                "number": re.sub(r"\s+", " ", us_num.replace("#", "")).strip(),
                "state_number": (
                    re.sub(r"\s+", " ", st_num.replace("#", "")).strip() if st_num else None
                ),
            }
        )
    href_m = A_HREF_RE.search(cell_html)
    if href_m:
        url = href_m.group(1)
        if url.startswith("http://"):
            # keep as-is: nhlr.org/firetower.org HTTPS resets in this environment,
            # but the canonical public URL is worth recording as given by the source
            pass
        label = "NHLR register entry" if registers and registers[0]["register"] == "NHLR" else "FFLOS register entry"
        links.append({"label": label, "url": url, "kind": "register"})
    return registers, links


def parse_header(row_html: str) -> dict | None:
    cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)
    if not cells:
        return None
    texts = [strip_tags(c).lower().rstrip("*").strip() for c in cells]
    mapping = {}
    unmapped = []
    for i, t in enumerate(texts):
        mapped = HEADER_SYNONYMS.get(t)
        if mapped:
            mapping[mapped] = i
        elif t:
            unmapped.append(t)
    if "name" not in mapping:
        return None
    # Some state pages (e.g. VA) leave the register column header blank. If the last
    # column has no header text and nothing else claimed the "register" slot, assume
    # it holds the NHLR/FFLOS cell per the site-wide table convention.
    if "register" not in mapping and len(texts) >= 2 and not texts[-1]:
        mapping["register"] = len(texts) - 1
    return {"mapping": mapping, "unmapped": unmapped, "ncols": len(cells)}


def parse_state_table(
    html: str, abbr: str, url: str, kind_stats: Counter, status_stats: Counter, coord_stats: Counter
) -> list[dict]:
    records = []
    seen_keys: dict[str, int] = {}
    tables = re.findall(r"<table[^>]*>.*?</table>", html, re.S)
    for table in tables:
        rows = re.findall(r"<tr>(.*?)</tr>", table, re.S)
        section = None
        header = None
        for row in rows:
            cells_raw = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            if len(cells_raw) == 1:
                txt = strip_tags(cells_raw[0])
                if "<strong>" in cells_raw[0] or txt:
                    if txt and txt.lower() not in ("name", ""):
                        section = txt
                        header = None
                        continue
            maybe_header = parse_header(row)
            if maybe_header is not None:
                header = maybe_header
                continue
            if header is None:
                continue  # data row before any header seen; skip defensively
            mapping = header["mapping"]
            if "name" not in mapping or len(cells_raw) < 2:
                continue

            def cell(field):
                i = mapping.get(field)
                if i is None or i >= len(cells_raw):
                    return ""
                return cells_raw[i]

            name = strip_tags(cell("name"))
            if not name:
                continue
            county = strip_tags(cell("county")) or None
            lat_raw = strip_tags(cell("lat"))
            lon_raw = strip_tags(cell("lon"))
            type_raw = strip_tags(cell("type")) or None
            status_raw = strip_tags(cell("status")) or None
            register_cell_html = cell("register")

            lat = lon = None
            coord_problem = None
            if not lat_raw or not lon_raw:
                coord_stats["missing"] += 1
            else:
                try:
                    lat = round(float(lat_raw), 5)
                    lon = round(float(lon_raw), 5)
                except ValueError:
                    coord_stats["invalid"] += 1
                    lat = lon = None
                else:
                    problem = flag_coordinate(abbr, lat, lon)
                    if problem:
                        coord_stats[problem] += 1
                        coord_problem = problem
                    else:
                        coord_stats["ok"] += 1

            kind = map_kind(type_raw, kind_stats) if type_raw else "unknown"
            status, has_star, status_event = ("unknown", False, None)
            if status_raw:
                status, has_star, status_event = map_status(status_raw, status_stats)

            registers, links = ([], [])
            if register_cell_html:
                registers, links = parse_register_cell(register_cell_html)

            slug = slugify(name)
            lat_key = f"{lat:.4f}" if lat is not None else "null"
            lon_key = f"{lon:.4f}" if lon is not None else "null"
            base_key = f"ffla:{abbr.lower()}:{slug}:{lat_key}:{lon_key}"
            key = base_key
            if key in seen_keys:
                seen_keys[key] += 1
                key = f"{base_key}:{seen_keys[base_key] if base_key in seen_keys else 1}"
                # ensure true uniqueness even on repeated collisions
                while key in seen_keys:
                    seen_keys[base_key] += 1
                    key = f"{base_key}:{seen_keys[base_key]}"
            seen_keys.setdefault(base_key, 0)
            seen_keys[key] = 0

            extra = {"section": section}
            if has_star:
                extra["standing_asterisk"] = True
                extra["standing_asterisk_note"] = (
                    "FFLA legend (firelookout.org/lookouts/): 'Standing*' = retains tower "
                    "structure/support even though the cab is no longer in place."
                )
            if coord_problem:
                extra["coordinate_problem"] = coord_problem
            if header["unmapped"]:
                extra["unmapped_columns"] = header["unmapped"]

            rec = {
                "key": key,
                "url": url,
                "name": name,
                "country": "US",
                "region": abbr,
                "county": county,
                "lat": lat,
                "lon": lon,
                "elevation_m": None,
                "type_raw": type_raw,
                "kind": kind,
                "status_raw": status_raw,
                "status": status,
                "registers": registers,
                "built": None,
                "agency": None,
                "events": [status_event] if status_event else [],
                "photos": [],
                "links": links,
                "rental": None,
                "extra": extra,
            }
            records.append(rec)
    return records


# ---------------------------------------------------------------------------
# "-add" additional information pages
# ---------------------------------------------------------------------------

def parse_add_page(html: str, state_name: str) -> dict:
    idx = html.find('class="entry-content"')
    if idx == -1:
        return {"links": [], "text_present": False}
    start = html.find(">", idx) + 1
    # find the matching close of this div by tracking the next entry-content sibling marker
    end = html.find('<!-- .entry-content -->', start)
    if end == -1:
        end = start + 6000
    body = html[start:end]
    links = []
    for m in A_HREF_RE.finditer(body):
        url = m.group(1)
        label = strip_tags(m.group(2))
        if not label:
            continue
        if label.strip().lower() == state_name.strip().lower():
            continue  # the self-referential "State: <Name>" link back to the table page
        links.append({"label": label, "url": url})
    plain_text = strip_tags(body)
    has_prose = len(plain_text) > 0 and len(links) < len(plain_text.split())
    return {"links": links, "text_present": bool(plain_text), "text_sample": plain_text[:300]}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    rl = RateLimiter()
    robots = RobotsCache(rl)

    log("=== fetch_ffla.py starting ===")
    status, body, cached = fetch(SOURCE, INDEX_URL, rl, robots, log=log)
    if status != 200:
        log(f"FATAL: index page fetch failed with status {status}")
        sys.exit(1)
    states = parse_index(body)
    log(f"Index parsed: {len(states)} states listed")

    all_records = []
    additional_info = {}
    kind_stats = Counter()
    status_stats = Counter()
    coord_stats = Counter()
    per_state_counts = {}
    states_with_table = 0
    states_without_table = []

    for st in states:
        abbr = st["abbr"]
        if st["table_url"]:
            states_with_table += 1
            status, body, cached = fetch(SOURCE, st["table_url"], rl, robots, log=log)
            if status == 200:
                recs = parse_state_table(
                    body, abbr, st["table_url"], kind_stats, status_stats, coord_stats
                )
                all_records.extend(recs)
                per_state_counts[abbr] = len(recs)
                log(f"{abbr}: {len(recs)} rows parsed ({'cache' if cached else 'fetched'})")
            else:
                log(f"{abbr}: table fetch failed status={status}")
                per_state_counts[abbr] = 0
        else:
            states_without_table.append(abbr)

        if st["add_url"]:
            status, body, cached = fetch(SOURCE, st["add_url"], rl, robots, log=log)
            if status == 200:
                info = parse_add_page(body, st["state"])
                additional_info[abbr] = {"url": st["add_url"], **info}

    out = {
        "source": SOURCE,
        "title": "Forest Fire Lookout Association (FFLA) - US lookout lists",
        "url": INDEX_URL,
        "retrieved": __import__("datetime").date.today().isoformat(),
        "license": "No licence stated; facts extracted only, no prose copied.",
        "records": all_records,
        "additional_info": additional_info,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"Wrote {len(all_records)} records to {OUT_PATH}")

    report = {
        "states_with_table": states_with_table,
        "states_without_table": states_without_table,
        "per_state_counts": per_state_counts,
        "kind_raw_counts": dict(kind_stats),
        "status_raw_counts": dict(status_stats),
        "coord_stats": dict(coord_stats),
        "additional_info_states": sorted(additional_info.keys()),
        "total_records": len(all_records),
        "registers_present": sum(1 for r in all_records if r["registers"]),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"Report written to {REPORT_PATH}")
    log("=== fetch_ffla.py done ===")


if __name__ == "__main__":
    main()
