#!/usr/bin/env python3
"""Story-research queue: unresearched lookouts in priority order, and a compact brief for each.

  research/queue.py --summary            counts by priority tier
  research/queue.py --next 30            ids of the next 30 towers
  research/queue.py --briefs ID [ID...]  compact JSON briefs (what a researcher needs, nothing else)

Priority: 1 rentable, 2 standing + on the National Historic Lookout Register, 3 other standing;
within a tier, towers with more independent sources and links first (more to work with)."""
import argparse, glob, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def towers():
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "towers", "*", "*.json"))):
        t = json.load(open(f))
        if not t.get("hidden"):
            yield t


def researched(tid):
    return os.path.exists(os.path.join(ROOT, "data", "research", f"{tid}.json"))


def tier(t):
    if (t.get("rental") or {}).get("available"):
        return 1
    if t.get("status") == "standing" and any(r.get("register") == "NHLR" for r in t.get("registers") or []):
        return 2
    if t.get("status") == "standing":
        return 3
    return None


def queue():
    q = []
    for t in towers():
        k = tier(t)
        if k and not researched(t["id"]):
            q.append((k, -len(t.get("sources") or []), -len(t.get("links") or []), t["id"]))
    return [x[3] for x in sorted(q)], q


def brief(t):
    loc = t.get("location") or {}
    b = {
        "id": t["id"], "name": t["name"], "other_names": t.get("other_names") or None,
        "state": t.get("region"), "county": t.get("county"),
        "lat": loc.get("lat"), "lon": loc.get("lon"),
        "status": t.get("status"), "status_note": t.get("status_note"), "kind": t.get("kind"),
        "design": t.get("design"), "height_m": t.get("height_m"), "elevation_m": t.get("elevation_m"),
        "agency": t.get("agency"), "access": (t.get("access") or {}).get("level"),
        "registers": [f'{r.get("register")} {r.get("number")}' + (f' ({r["url"]})' if r.get("url") else "") for r in t.get("registers") or []] or None,
        "events": [f'{e.get("year")} {e.get("event")}' + (f' ({e["note"]})' if e.get("note") else "") for e in t.get("events") or []] or None,
        "source_pages": [l["url"] for l in t.get("links") or [] if l.get("url")][:12] or None,
        "conflicts": [c.get("note") or f'{c.get("field")}: ' + ", ".join(f'{v.get("source")}={v.get("value")}' for v in c.get("values") or []) for c in t.get("conflicts") or []] or None,
    }
    r = t.get("rental") or {}
    if r.get("available") is not None:
        b["rental"] = {k: r.get(k) for k in ("available", "url", "season", "max_occupancy", "warning") if r.get(k) is not None}
    return {k: v for k, v in b.items() if v not in (None, [], {})}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--next", type=int)
    ap.add_argument("--briefs", nargs="+")
    a = ap.parse_args()
    if a.briefs and not (a.summary or a.next):
        # fast path: read only the requested records
        out = []
        for i in a.briefs:
            hits = glob.glob(os.path.join(ROOT, "data", "towers", "*", f"{i}.json"))
            if hits:
                out.append(brief(json.load(open(hits[0]))))
        print(json.dumps(out, ensure_ascii=False))
        return
    ids, q = queue()
    if a.summary:
        from collections import Counter
        c = Counter(x[0] for x in q)
        print({"rentable": c[1], "standing+NHLR": c[2], "other standing": c[3], "total": len(ids)})
    if a.next:
        print("\n".join(ids[: a.next]))
    if a.briefs:
        by = {t["id"]: t for t in towers() if t["id"] in set(a.briefs)}
        print(json.dumps([brief(by[i]) for i in a.briefs if i in by], ensure_ascii=False))


if __name__ == "__main__":
    main()
