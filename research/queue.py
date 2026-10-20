#!/usr/bin/env python3
"""Story-research queue: unresearched lookouts in priority order, and a compact brief for each.

  research/queue.py --summary            counts by priority tier, then per country and region
  research/queue.py --next 30            ids of the next 30 towers
  research/queue.py --briefs ID [ID...]  compact JSON briefs (what a researcher needs, nothing else)

Select by country and region (combine with any option above; --briefs ignores them):

  research/queue.py --country CA --summary         Canada only
  research/queue.py --region ON --next 30          Ontario only (a region code implies its country)
  research/queue.py --region ON,QC --region BC     several regions: repeat the option or use commas
  research/queue.py --country US --region AK,HI    a country with regions: they must belong to it

Region codes are unique across countries ("CA" the region is California; "CA" the country is Canada),
so --region needs no --country; naming both with a region of the other country is an error.
Names work too (--region Ontario, --region Québec). Without either option all countries are queued,
in one list; the priority order below decides who comes first, not the country.

Priority: 1 rentable, 2 standing + on a register, 3 other standing; within a tier, towers with more
independent sources and links first (more to work with). "A register" is the National Historic Lookout
Register for a US tower, and any register entry for a Canadian one (the Canadian Register of Historic
Places, historicplaces.ca, or a provincial or territorial heritage register).
With --gone (owner-approved batches only, DESIGN 1): 4 relocated, ruins or replica structures on a
lookout register, 5 gone structures on a register (US: NHLR or FFLOS; Canada: any register).
With --gone-all as well (owner: "keep going until I tell you to stop", 2026-10-09): 6 gone, moved
or ruined structures with no register page, 7 structures whose status no source settles.
Sites with no structure (camps, lookout trees, bare points) are never queued."""
import argparse, glob, json, os, sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(ROOT, "pipeline"))  # appended, never first: a module here must not shadow the standard library
import regions  # noqa: E402  (the one table of countries and regions; DESIGN.md 3.3)


def tower_country(t):
    """"US" or "CA": the record's country, else the country its region code belongs to, else US
    (records from before countries existed)."""
    return str(t.get("country") or regions.country_of(t.get("region")) or "US").upper()


def towers(country=None, region_codes=None):
    """Every visible tower record, optionally only those of one country and/or some regions."""
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "towers", "*", "*.json"))):
        with open(f, encoding="utf-8") as fh:
            t = json.load(fh)
        if t.get("hidden"):
            continue
        if country and tower_country(t) != country:
            continue
        if region_codes and str(t.get("region") or "").upper() not in region_codes:
            continue
        yield t


def tower_path(tid):
    """The record file of a tower id, wherever it lives (data/towers/or/, data/towers/ca-on/ ...)."""
    hits = glob.glob(os.path.join(ROOT, "data", "towers", "**", glob.escape(f"{tid}.json")), recursive=True)
    return hits[0] if hits else None


def researched(tid):
    return os.path.exists(os.path.join(ROOT, "data", "research", f"{tid}.json"))


NO_STRUCTURE = {"camp", "tree", "point"}
# US registers that raise a tower's priority. NRHP and the state lists do not, as before.
US_LOOKOUT_REGISTERS = {"NHLR"}
US_GONE_REGISTERS = {"NHLR", "FFLOS"}


def on_register(t, us_names):
    """Is the tower on a register that earns priority? A US tower: one of `us_names`. A Canadian
    one: any register entry, or a linked historicplaces.ca / heritage-register page (links of
    kind "register"), since those registers are the documented ones there."""
    regs = {r.get("register") for r in t.get("registers") or []}
    if regs & us_names:
        return True
    if tower_country(t) != "US":
        return bool(regs) or any(l.get("kind") == "register" for l in t.get("links") or [])
    return False


def tier(t, gone=False, gone_all=False):
    if (t.get("rental") or {}).get("available"):
        return 1
    if t.get("status") == "standing" and on_register(t, US_LOOKOUT_REGISTERS):
        return 2
    if t.get("status") == "standing":
        return 3
    if gone and t.get("kind") not in NO_STRUCTURE and on_register(t, US_GONE_REGISTERS):
        if t.get("status") in ("relocated", "ruins", "replica"):
            return 4
        if t.get("status") == "gone":
            return 5
    if gone_all and t.get("kind") not in NO_STRUCTURE and not (t.get("location") or {}).get("approximate"):
        if t.get("status") in ("gone", "relocated", "ruins", "replica"):
            return 6
        if t.get("status") in (None, "unknown"):
            return 7
    return None


def queue(gone=False, gone_all=False, country=None, region_codes=None):
    """(ids in priority order, rows). A row is (tier, -sources, -links, id, region); the first four
    sort the queue, exactly as before countries existed."""
    q = []
    for t in towers(country, region_codes):
        k = tier(t, gone or gone_all, gone_all)
        if k and not researched(t["id"]):
            q.append((k, -len(t.get("sources") or []), -len(t.get("links") or []), t["id"], str(t.get("region") or "").upper()))
    q.sort()
    return [x[3] for x in q], q


def source_pages(t, cap=12):
    """The tower's linked pages, at most `cap` of them, but never without the association
    project reports (links of kind "association" other than the FFLA state list): those pages
    carry the dated work on the lookout, which a story should cite."""
    links = [l for l in t.get("links") or [] if l.get("url")]
    urls = [l["url"] for l in links][:cap]
    for l in links:
        if l.get("kind") == "association" and "firelookout.org" not in l["url"] and l["url"] not in urls:
            urls.append(l["url"])
    return urls


def register_label(r):
    s = " ".join(str(x) for x in (r.get("register"), r.get("number")) if x)
    return s + (f' ({r["url"]})' if r.get("url") else "")


def brief(t):
    loc = t.get("location") or {}
    country = tower_country(t)
    region = str(t.get("region") or "").upper()
    fr_name = regions.CA_FRENCH.get(region) if country == "CA" else None
    if fr_name == regions.region_name(region):
        fr_name = None
    b = {
        "id": t["id"], "name": t["name"], "other_names": t.get("other_names") or None,
        "country": regions.COUNTRY_NAMES.get(country, country),
        # region is the state, province or territory; local_unit the county, district, borough...
        "region": region or None, "region_name": regions.region_name(region) or None,
        "region_name_fr": fr_name,  # Canada only, when it differs from the English name: for searching French sources
        "local_unit": regions.local_unit_label(country, region, t.get("county")),
        "lat": loc.get("lat"), "lon": loc.get("lon"),
        "status": t.get("status"), "status_note": t.get("status_note"), "kind": t.get("kind"),
        "design": t.get("design"), "height_m": t.get("height_m"), "elevation_m": t.get("elevation_m"),
        "agency": t.get("agency"), "access": (t.get("access") or {}).get("level"),
        "registers": [register_label(r) for r in t.get("registers") or []] or None,
        "events": [f'{e.get("year")} {e.get("event")}' + (f' ({e["note"]})' if e.get("note") else "") for e in t.get("events") or []] or None,
        "source_pages": source_pages(t) or None,
        "conflicts": [c.get("note") or f'{c.get("field")}: ' + ", ".join(f'{v.get("source")}={v.get("value")}' for v in c.get("values") or []) for c in t.get("conflicts") or []] or None,
    }
    r = t.get("rental") or {}
    if r.get("available") is not None:
        b["rental"] = {k: r.get(k) for k in ("available", "url", "season", "max_occupancy", "warning") if r.get(k) is not None}
    return {k: v for k, v in b.items() if v not in (None, [], {})}


def briefs_for(ids):
    """Briefs for the requested ids, in the order asked; unknown ids are skipped. Reads only those files."""
    out = []
    for i in ids:
        p = tower_path(i)
        if p:
            with open(p, encoding="utf-8") as fh:
                out.append(brief(json.load(fh)))
    return out


# ---- selection by country / region ---------------------------------------------------------------

def parse_country(text):
    """"CA", "ca", "Canada", "United States" -> "CA" / "US"; ValueError otherwise."""
    t = regions.fold(text)
    for code, name in regions.COUNTRY_NAMES.items():
        if t in (code.lower(), regions.fold(name)):
            return code
    if t in ("usa", "u.s.", "u.s.a."):
        return "US"
    raise ValueError(f"unknown country {text!r}; use {' or '.join(regions.COUNTRY_NAMES)}")


def parse_regions(values, country=None):
    """Region codes from repeated and comma-separated --region values (codes or names, English or
    French). A region of another country than `country` is an error, not an empty selection."""
    codes = []
    for v in values or []:
        for part in str(v).split(","):
            if not part.strip():
                continue
            code = regions.parse_region(part)
            if not code:
                raise ValueError(f"unknown region {part.strip()!r}; use a state, province or territory code such as OR, AK or ON")
            if country and regions.country_of(code) != country:
                raise ValueError(
                    f"region {code} ({regions.region_name(code)}) is in {regions.COUNTRY_NAMES.get(regions.country_of(code))}, "
                    f"not {regions.COUNTRY_NAMES.get(country, country)}"
                    + (" (the region code CA is California; Canada is --country CA)" if code == "CA" and country == "CA" else ""))
            if code not in codes:
                codes.append(code)
    return codes


def selection_text(country, codes):
    if codes:
        return "regions " + ", ".join(f"{c} ({regions.region_name(c)})" for c in codes)
    if country:
        return f"country {country} ({regions.COUNTRY_NAMES.get(country, country)})"
    return "all countries and regions"


def us_only(country, codes):
    return country == "US" or bool(codes and all(regions.country_of(c) == "US" for c in codes))


def tier_labels(register_word):
    return {1: "rentable", 2: f"standing+{register_word}", 3: "other standing",
            4: "moved/ruins/replica+register", 5: "gone+register", 6: "gone, no register", 7: "status unknown"}


def print_summary(q, ids, gone, gone_all, country, codes):
    labels = tier_labels("NHLR" if us_only(country, codes) else "register")
    c = Counter(x[0] for x in q)
    out = {labels[1]: c[1], labels[2]: c[2], labels[3]: c[3]}
    if gone or gone_all:
        out.update({labels[4]: c[4], labels[5]: c[5]})
    if gone_all:
        out.update({labels[6]: c[6], labels[7]: c[7]})
    print({**out, "total": len(ids)})
    # The same counts per country and region (only the tiers that have towers in them).
    by = defaultdict(lambda: defaultdict(Counter))
    for k, _s, _l, tid, region in q:
        by[regions.country_of(region) or "??"][region][k] += 1
    print(f"selection: {selection_text(country, codes)}" + ("" if q else " -- nothing left to research (all done, or none match)"))
    order = [x for x in regions.COUNTRY_ORDER if x in by] + sorted(x for x in by if x not in regions.COUNTRY_ORDER)

    def line(cnt):
        return ", ".join(f"{labels[k]} {cnt[k]}" for k in sorted(cnt))
    for ctry in order:
        total = Counter()
        for cnt in by[ctry].values():
            total.update(cnt)
        print(f"{ctry} {regions.COUNTRY_NAMES.get(ctry, ctry)}: {sum(total.values())} ({line(total)})")
        for region in sorted(by[ctry]):
            cnt = by[ctry][region]
            print(f"  {region} {regions.region_name(region)}: {sum(cnt.values())} ({line(cnt)})")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # French names in briefs, whatever the locale
    ap = argparse.ArgumentParser(description="Story-research queue (see the module docstring for the priority tiers).")
    ap.add_argument("--summary", action="store_true", help="counts by tier, then per country and region")
    ap.add_argument("--next", type=int, metavar="N", help="print the ids of the next N towers")
    ap.add_argument("--briefs", nargs="+", metavar="ID", help="compact JSON briefs for these tower ids (selection options are ignored)")
    ap.add_argument("--gone", action="store_true", help="also queue registered gone, moved and ruined structures")
    ap.add_argument("--gone-all", action="store_true", help="also queue unregistered gone structures and unknown-status ones")
    ap.add_argument("--country", metavar="US|CA", help="only this country's towers (US includes Alaska and Hawaii)")
    ap.add_argument("--region", action="append", metavar="CODE[,CODE...]",
                    help="only these states, provinces or territories, e.g. ON or OR,AK; repeatable. A region implies its "
                         "country (CA as a region is California; Canada is --country CA)")
    a = ap.parse_args()
    country = None
    try:
        if a.country:
            country = parse_country(a.country)
        codes = parse_regions(a.region, country)
    except ValueError as e:
        ap.error(str(e))
    if a.briefs and not (a.summary or a.next):
        # fast path: read only the requested records, found by id wherever their folder is
        print(json.dumps(briefs_for(a.briefs), ensure_ascii=False))
        return
    ids, q = queue(a.gone, a.gone_all, country, set(codes))
    if a.summary:
        print_summary(q, ids, a.gone, a.gone_all, country, codes)
    if a.next:
        print("\n".join(ids[: a.next]))
    if a.briefs:
        print(json.dumps(briefs_for(a.briefs), ensure_ascii=False))


if __name__ == "__main__":
    main()
