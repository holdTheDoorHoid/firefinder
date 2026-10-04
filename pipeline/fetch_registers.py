#!/usr/bin/env python3
"""Fetch and parse the NHLR (nhlr.org, standing lookouts) and FFLOS (firetower.org,
former lookout sites) registers. They share one site template/operator (DESIGN.md
section 2: "treat nhlr.org and firetower.org as ONE host" for the 2s/request limit).

Writes data/sources/nhlr.json and data/sources/fflos.json.

NOTE: both hosts reset the TLS handshake for every client tried from this environment
(curl, python urllib, with or without a browser User-Agent) but serve plain HTTP (port
80) normally. We fetch over http:// for these two hosts only and say so in the report;
this is a network-layer issue in this environment, not a bot block (robots.txt is a
plain 404 on both, i.e. no restrictions stated).

Usage:
    python3 pipeline/fetch_registers.py                 # both registers, full crawl
    python3 pipeline/fetch_registers.py --only nhlr      # one register only
    python3 pipeline/fetch_registers.py --states or,wa   # limit states (debugging)

Resumable: every page fetched is cached under
/home/hoid/Desktop/firefinder/data/raw/<nhlr|fflos>/ ; a re-run reads from that cache
instead of refetching, so it's safe to re-run after an interruption.
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RAW_ROOT, RateLimiter, RobotsCache, STATE_ABBR, fetch, write_log  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = RAW_ROOT / "_logs" / "fetch_registers.log"
PROGRESS_PATH = RAW_ROOT / "_logs" / "fetch_registers_progress.json"
REPORT_PATH = RAW_ROOT / "_logs" / "fetch_registers_report.json"

SITES = {
    "nhlr": {
        "base": "http://nhlr.org",
        "default_status": "standing",
        "register_name": "NHLR",
        "registered_event": "nhlr_registered",
        "out": REPO_ROOT / "data" / "sources" / "nhlr.json",
        "title": "National Historic Lookout Register (NHLR)",
    },
    "fflos": {
        "base": "http://firetower.org",
        "default_status": "gone",
        "register_name": "FFLOS",
        "registered_event": "fflos_registered",
        "out": REPO_ROOT / "data" / "sources" / "fflos.json",
        "title": "Former Fire Lookout Sites Register (FFLOS)",
    },
}

TAG_RE = re.compile(r"<[^>]+>")
A_HREF_RE = re.compile(r'<a\s+[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.S | re.I)
REGNUM_RE = re.compile(r"US\s*#?\s*(\d+)(?:\s*,\s*([A-Za-z]{2})\s*#?\s*(\d+))?", re.I)
MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|november|december"
)
DATE_RE = re.compile(rf"({MONTHS})\s+\d{{1,2}},\s*(\d{{4}})", re.I)
COUNTY_RE = re.compile(r"(.+?)\s+County,\s*(.+)", re.I)
ELEV_RE = re.compile(r"([\d,]+)\s*ft\s*\(([\d,]+)\s*m\)", re.I)
DECDEG_RE = re.compile(r"([NS])\s*(\d+\.\d+)\s*\xb0\s*([EW])\s*(\d+\.\d+)\s*\xb0")
YEAR_RE = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")


def strip_tags(s: str) -> str:
    s = TAG_RE.sub(" ", s)
    s = html_mod.unescape(s)
    s = s.replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def log(msg: str) -> None:
    print(msg, flush=True)
    write_log(LOG_PATH, msg)


def abs_url(base: str, url: str) -> str:
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/"):
        return base + url
    return base + "/" + url


# ---------------------------------------------------------------------------
# State list page
# ---------------------------------------------------------------------------

LIST_HEADER_SYNONYMS = {
    "lookout name": "name",
    "name": "name",
    "nhlr registry number": "registry",
    "registry number": "registry",
    "available for rental": "rental",
    "visit reports": "visit",
}


def parse_list_page(html: str, base: str) -> list[dict]:
    idx = html.find("<table")
    if idx == -1:
        return []
    end = html.find("</table>", idx) + len("</table>")
    table = html[idx:end]
    rows = re.findall(r"<tr>(.*?)</tr>", table, re.S)
    if not rows:
        return []
    header_cells = re.findall(r"<td[^>]*>(.*?)</td>", rows[0], re.S)
    header_texts = [strip_tags(c).lower() for c in header_cells]
    mapping = {}
    for i, t in enumerate(header_texts):
        mapped = LIST_HEADER_SYNONYMS.get(t)
        if mapped:
            mapping[mapped] = i
    out = []
    for row in rows[1:]:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if "name" not in mapping or mapping["name"] >= len(cells):
            continue
        name_cell = cells[mapping["name"]]
        m = A_HREF_RE.search(name_cell)
        if not m:
            continue
        detail_url = abs_url(base, m.group(1))
        name = strip_tags(m.group(2))
        registry_text = (
            strip_tags(cells[mapping["registry"]]) if "registry" in mapping and mapping["registry"] < len(cells) else ""
        )
        rental_text = (
            strip_tags(cells[mapping["rental"]]) if "rental" in mapping and mapping["rental"] < len(cells) else ""
        )
        out.append(
            {
                "name": name,
                "detail_url": detail_url,
                "registry_text": registry_text,
                "rental_available": "rent" in rental_text.lower(),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Detail page
# ---------------------------------------------------------------------------

def parse_about_table(html: str) -> dict:
    idx = html.find('id="tabs-about"')
    if idx == -1:
        return {}
    t_idx = html.find("<table", idx)
    t_end = html.find("</table>", t_idx) + len("</table>")
    table = html[t_idx:t_end]
    fields = {}
    for row in re.findall(r"<tr>(.*?)</tr>", table, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) != 2:
            continue
        label = strip_tags(cells[0]).lower().rstrip(":").strip()
        if label:
            fields[label] = cells[1]
    return fields


def parse_photos(html: str, base: str) -> list[dict]:
    photos = []
    seen = set()
    # the single photo shown above the tabs, and every photo in the Photos tab
    for block_m in re.finditer(
        r'<div class="lookoutPhoto">\s*<img[^>]*src="([^"]+)"[^>]*alt="([^"]*)"[^>]*/?>\s*(?:<p>\s*(.*?)\s*</p>)?',
        html,
        re.S,
    ):
        src, alt, caption_html = block_m.groups()
        url = abs_url(base, src.split("?")[0])
        if url in seen:
            continue
        seen.add(url)
        caption = strip_tags(caption_html) if caption_html else (strip_tags(alt) if alt else None)
        year = None
        if caption:
            ym = YEAR_RE.search(caption)
            if ym:
                year = int(ym.group(1))
        credit = None
        if caption:
            cm = re.search(r"\s*[-,]?\s*(?:photo\s+by|courtesy\s+of|credit:?)\s+(.+?)\s*$", caption, re.I)
            if cm:
                credit = re.sub(r"^the\s+", "", cm.group(1).strip(), flags=re.I)
                if credit.count(")") > credit.count("("):
                    credit = credit[:-1].rstrip()
                caption = caption[: cm.start()].strip(" -,(") or None
                if caption and caption.lower() in ("photo", "photo of", "picture"):
                    caption = None
        photos.append({"url": url, "credit": credit, "caption": caption, "year": year})
    return photos


def parse_links_tab(html: str, base: str) -> list[dict]:
    idx = html.find('id="tabs-links"')
    if idx == -1:
        return []
    end = html.find("</div>", idx)
    body = html[idx:end]
    out = []
    for m in A_HREF_RE.finditer(body):
        url, label = m.group(1), strip_tags(m.group(2))
        if label:
            out.append({"label": label, "url": abs_url(base, url)})
    return out


def parse_detail_page(html: str, base: str, source: str, default_status: str) -> dict:
    result: dict = {
        "name": None,
        "registers": [],
        "county": None,
        "elevation_m": None,
        "built": None,
        "agency": None,
        "status": default_status,
        "events": [],
        "photos": [],
        "links": [],
        "extra": {},
        "lat": None,
        "lon": None,
    }

    title_idx = html.find('id="pageTitle"')
    if title_idx != -1:
        t_start = html.find(">", title_idx) + 1
        t_end = html.find("</div>", t_start)
        result["name"] = strip_tags(html[t_start:t_end])

    sub_idx = html.find('id="pageSubtitle"')
    subtitle = ""
    if sub_idx != -1:
        s_start = html.find(">", sub_idx) + 1
        s_end = html.find("</div>", s_start)
        subtitle = strip_tags(html[s_start:s_end])

    fields = parse_about_table(html)

    reg_text = fields.get("registry numbers")
    reg_text = strip_tags(reg_text) if reg_text else subtitle
    rm = REGNUM_RE.search(reg_text or "")
    if rm:
        us_num, st_abbr, st_num = rm.groups()
        register = {
            "register": source.upper() if source != "fflos" else "FFLOS",
            "number": f"US {us_num}",
            "state_number": f"{st_abbr.upper()} {st_num}" if st_abbr and st_num else None,
        }
        result["registers"].append(register)

    if "date registered" in fields:
        date_text = strip_tags(fields["date registered"])
        dm = DATE_RE.search(date_text)
        if dm:
            year = int(dm.group(2))
            result["events"].append(
                {
                    "year": year,
                    "event": "nhlr_registered" if source == "nhlr" else "fflos_registered",
                    "note": f"Date registered per {source.upper()} detail page: {date_text}",
                    "from": source,
                }
            )
            result["extra"]["date_registered"] = date_text

    if "nominated by" in fields:
        result["extra"]["nominated_by"] = strip_tags(fields["nominated by"])

    if "location" in fields:
        lines = [strip_tags(l) for l in re.split(r"<br\s*/?>", fields["location"])]
        lines = [l for l in lines if l]
        if lines:
            last = lines[-1]
            cm = COUNTY_RE.match(last)
            if cm:
                result["county"] = cm.group(1).strip()
                result["extra"]["location_state_text"] = cm.group(2).strip()
                forest = " ".join(lines[:-1]).strip()
                if forest:
                    result["extra"]["forest_or_area"] = forest
            else:
                result["extra"]["location_text"] = " ".join(lines)

    if "coordinates" in fields:
        coord_text = strip_tags(fields["coordinates"])
        dm2 = DECDEG_RE.search(coord_text)
        if dm2:
            ns, lat_v, ew, lon_v = dm2.groups()
            lat = float(lat_v) * (1 if ns.upper() == "N" else -1)
            lon = float(lon_v) * (-1 if ew.upper() == "W" else 1)
            result["lat"] = round(lat, 6)
            result["lon"] = round(lon, 6)

    if "elevation" in fields:
        elev_text = strip_tags(fields["elevation"])
        em = ELEV_RE.search(elev_text)
        if em:
            feet = float(em.group(1).replace(",", ""))
            result["elevation_m"] = round(feet * 0.3048, 1)
            result["extra"]["elevation_ft"] = feet

    if "built" in fields:
        built_text = strip_tags(fields["built"])
        ym = YEAR_RE.search(built_text)
        if ym:
            year = int(ym.group(1))
            result["built"] = year
            result["events"].append(
                {"year": year, "event": "built", "note": f"'Built' field on {source.upper()} detail page", "from": source}
            )

    if "administered by" in fields:
        result["agency"] = strip_tags(fields["administered by"])

    if "cooperators" in fields:
        result["extra"]["cooperators"] = strip_tags(fields["cooperators"])

    KNOWN_LABELS = {
        "registry numbers", "date registered", "nominated by", "location", "coordinates",
        "elevation", "built", "administered by", "cooperators", "available for rental",
    }
    other = {lbl: strip_tags(v) for lbl, v in fields.items() if lbl not in KNOWN_LABELS}
    if other:
        result["extra"]["other_fields"] = other

    # Description prose is used in-memory only, for a "replica" signal -- never persisted.
    desc_idx = html.find("<h2>Description</h2>")
    if desc_idx != -1:
        d_end = html.find("</div>", desc_idx)
        desc_text = strip_tags(html[desc_idx:d_end])
        if re.search(r"\breplica\b", desc_text, re.I):
            result["status"] = "replica"
            result["extra"]["status_override_reason"] = "description text mentions 'replica'"
        if re.search(r"\brelocated\b|\bmoved to\b", desc_text, re.I):
            result["extra"]["possible_relocation"] = True

    result["photos"] = parse_photos(html, base)
    result["links"] = parse_links_tab(html, base)
    return result


# ---------------------------------------------------------------------------
# Main crawl
# ---------------------------------------------------------------------------

def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def build_source(source: str, states: list[str], rl: RateLimiter, robots: RobotsCache, progress: dict) -> dict:
    conf = SITES[source]
    base = conf["base"]
    all_records = []
    seen_keys: dict[str, int] = {}
    zero_states = []
    list_counts = {}
    fetch_fail = []

    worklist = []
    for abbr in states:
        list_url = f"{base}/lookouts/us/{abbr.lower()}/"
        status, body, cached = fetch(source, list_url, rl, robots, log=log)
        if status != 200:
            log(f"{source} {abbr}: list page status={status}")
            fetch_fail.append(list_url)
            continue
        entries = parse_list_page(body, base)
        list_counts[abbr] = len(entries)
        if not entries:
            zero_states.append(abbr)
        for e in entries:
            worklist.append((abbr, e))

    total = len(worklist)
    log(f"{source}: {total} detail pages to process across {len(states)} states")
    progress[source] = {"total": total, "done": 0, "started": time.time()}
    _save_progress(progress)

    done = 0
    for abbr, entry in worklist:
        status, body, cached = fetch(source, entry["detail_url"], rl, robots, log=None)
        done += 1
        if status != 200:
            log(f"{source} {abbr} DETAIL FAIL status={status} {entry['detail_url']}")
            fetch_fail.append(entry["detail_url"])
        else:
            parsed = parse_detail_page(body, base, source, conf["default_status"])
            name = parsed["name"] or entry["name"]
            registers = parsed["registers"]
            if not registers:
                # fall back to the registry number shown on the state list page
                rm = REGNUM_RE.search(entry["registry_text"])
                if rm:
                    us_num, st_abbr, st_num = rm.groups()
                    registers = [{
                        "register": conf["register_name"],
                        "number": f"US {us_num}",
                        "state_number": f"{st_abbr.upper()} {st_num}" if st_abbr and st_num else None,
                    }]
            if registers:
                key = f"{source}:{registers[0]['number']}"
            else:
                key = f"{source}:{abbr.lower()}:{slugify(name)}"
            base_key = key
            if base_key in seen_keys:
                seen_keys[base_key] += 1
                key = f"{base_key}:{seen_keys[base_key]}"
            else:
                seen_keys[base_key] = 0

            rental = {"available": True} if entry["rental_available"] else None

            rec = {
                "key": key,
                "url": entry["detail_url"],
                "name": name,
                "country": "US",
                "region": abbr,
                "county": parsed["county"],
                "lat": parsed["lat"],
                "lon": parsed["lon"],
                "elevation_m": parsed["elevation_m"],
                "type_raw": None,
                "kind": "unknown",
                "status_raw": None,
                "status": parsed["status"],
                "registers": registers,
                "built": parsed["built"],
                "agency": parsed["agency"],
                "events": parsed["events"],
                "photos": parsed["photos"],
                "links": parsed["links"],
                "rental": rental,
                "extra": parsed["extra"],
            }
            all_records.append(rec)

        if done % 25 == 0 or done == total:
            progress[source]["done"] = done
            _save_progress(progress)
            log(f"{source}: {done}/{total} detail pages processed")

    report = {
        "list_counts": list_counts,
        "zero_states": zero_states,
        "fetch_failures": fetch_fail,
        "total_records": len(all_records),
    }
    return {
        "source": source,
        "title": conf["title"],
        "url": f"{base}/lookouts/",
        "retrieved": __import__("datetime").date.today().isoformat(),
        "license": "All rights reserved (American Resources, Inc.); facts extracted only, no prose copied.",
        "records": all_records,
    }, report


def _save_progress(progress: dict) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_PATH.write_text(json.dumps(progress, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["nhlr", "fflos"], default=None)
    ap.add_argument("--states", default=None, help="comma-separated state abbrs, for debugging")
    args = ap.parse_args()

    rl = RateLimiter()
    robots = RobotsCache(rl)
    states = [s.strip().upper() for s in args.states.split(",")] if args.states else sorted(STATE_ABBR.values())

    sources = [args.only] if args.only else ["nhlr", "fflos"]
    progress = {}
    if PROGRESS_PATH.exists():
        try:
            progress = json.loads(PROGRESS_PATH.read_text())
        except Exception:
            progress = {}

    log(f"=== fetch_registers.py starting: sources={sources} states={len(states)} ===")
    full_report = {}
    for source in sources:
        out, report = build_source(source, states, rl, robots, progress)
        SITES[source]["out"].parent.mkdir(parents=True, exist_ok=True)
        SITES[source]["out"].write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        log(f"Wrote {len(out['records'])} records to {SITES[source]['out']}")
        full_report[source] = report

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(full_report, indent=2), encoding="utf-8")
    log("=== fetch_registers.py done ===")


if __name__ == "__main__":
    main()
