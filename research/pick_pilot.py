#!/usr/bin/env python3
"""Pick the story-research pilot: 40 standing or rentable lookouts spread across kinds and regions.

  research/pick_pilot.py [--country US|CA|all]     (default US: the pilot the project started with)

Deterministic (sorted by a hash of the id), so re-running gives the same list. "Regions" are states
and provinces; the east / midwest / west groups below are the US ones, with Canada's
beside them (Ontario eastwards; the prairie provinces; everything else is west)."""
import argparse, glob, hashlib, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# appended, never first: a module in pipeline/ must not shadow the standard library
sys.path.append(os.path.join(ROOT, "pipeline"))
import regions  # noqa: E402

EAST = set("ME NH VT MA RI CT NY NJ PA DE MD VA WV NC SC GA FL AL MS TN KY OH IN MI".split())
MIDWEST = set("MN WI IA MO AR LA OK TX KS NE SD ND IL".split())
# Canada. Region codes are unique across countries (regions.py), so the sets can simply be joined.
EAST |= set("ON QC NB NS PE NL".split())
MIDWEST |= set("MB SK".split())

ap = argparse.ArgumentParser()
ap.add_argument("--country", default="US", help="US (default), CA or all")
COUNTRY = ap.parse_args().country.upper()
if COUNTRY not in ("US", "CA", "ALL"):
    ap.error("--country is US, CA or all")

def h(s): return hashlib.sha1(s.encode()).hexdigest()

towers = []
for f in glob.glob(os.path.join(ROOT, "data", "towers", "*", "*.json")):
    with open(f, encoding="utf-8") as fh:
        t = json.load(fh)
    if t.get("hidden") or t["id"].startswith("us-gu"):
        continue
    if COUNTRY != "ALL" and (t.get("country") or regions.country_of(t.get("region")) or "US").upper() != COUNTRY:
        continue
    towers.append(t)
towers.sort(key=lambda t: h(t["id"]))

def has_wiki(t): return any("wikipedia.org" in (l.get("url") or "") for l in t.get("links") or [])
def rentable(t): return bool((t.get("rental") or {}).get("available"))
def standing(t): return t.get("status") == "standing"

picked, seen_states = [], {}
def take(pred, n, label, state_cap=2):
    got = 0
    for t in towers:
        if got >= n: break
        if t["id"] in {p["id"] for p, _ in picked} or not pred(t): continue
        if seen_states.get(t["region"], 0) >= state_cap: continue
        picked.append((t, label)); seen_states[t["region"]] = seen_states.get(t["region"], 0) + 1; got += 1

take(rentable, 10, "rental")
take(lambda t: standing(t) and has_wiki(t), 7, "well-documented")
take(lambda t: standing(t) and not has_wiki(t) and t["region"] not in EAST | MIDWEST, 8, "obscure-west")
take(lambda t: standing(t) and t["region"] in EAST, 8, "east")
take(lambda t: standing(t) and t["region"] in MIDWEST, 4, "midwest")
take(lambda t: t.get("status") == "relocated" or any(e.get("event") == "relocated" for e in t.get("events") or []), 3, "moved", state_cap=3)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # French names
for t, label in picked:
    print(f'{t["id"]}\t{label}\t{t["name"]}\t{t["region"]}')
print(len(picked), "picked", file=sys.stderr)
