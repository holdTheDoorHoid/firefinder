"""FFLA Monterey Chapter (California): Chews Ridge Lookout.

  https://ffla-monterey.org/   (the Forest Fire Lookout Association's Monterey chapter, formed 2019)

The chapter's volunteers renovated and staff Chews Ridge Lookout in the Los Padres National Forest,
and the site has a short history of the lookout. This source turns that page into dated events on
the lookout's timeline, linked to the page. (The Cone Peak page has no dated history.) Built on the
shared association-project shape (_projects.py, DESIGN.md 3.7) and the driver in _assoc_site.py.

What is read (2026-10-08; robots.txt disallows only /wp-admin): /chews-ridge-lookout/. The chapter
also keeps an In The News page of press clippings, which are not a work log.

Licence: no licence stated. Dates and the kind of work done are facts; the notes are ours; the
events link to the chapter's page.

Output: data/sources/ffla_monterey.json
Re-run: python3 pipeline/regional/ffla_monterey.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_site import E, doc, run  # noqa: E402

SOURCE = "ffla_monterey"
BASE = "https://ffla-monterey.org"
ASSOCIATION = {"name": "FFLA Monterey Chapter", "url": f"{BASE}/"}
CREDIT = "Forest Fire Lookout Association, Monterey Chapter (ffla-monterey.org)"
LICENSE = (
    "No licence stated; facts only (dates, the kind of work done). Every note is our own wording "
    "and the events link to the chapter's page. The position is copied from the NHLR record."
)
DOCS = [doc("chews", f"{BASE}/chews-ridge-lookout/", "Chews Ridge Lookout (FFLA Monterey)")]

LOOKOUTS = [
    dict(slug="chews-ridge", name="Chews Ridge Lookout", region="CA", tower="us-ca-chews-ridge", pos="nhlr:US 751", find=["Chews Ridge"],
         forest="Los Padres National Forest (Monterey Ranger District)", agency="U.S. Forest Service", ownership="federal",
         staffing="volunteer", status="standing", design="R-6 flat cab on a 12-ft metal tower",
         events=[
             E(1978, "rebuilt", "The cab was rebuilt after a fire.", "chews"),
             E(1984, "replaced", "The cab was renovated and the present R-6 flat cab built.", "chews"),
             E(1990, "staffed_last", "Taken out of service about this time; the Forest Service then used it for radio equipment.", "chews"),
             E(2019, "restored", "Volunteers of the new Monterey chapter, working with the Forest Service, replaced floor boards, fitted new flooring and drywall and installed equipment.", "chews"),
             E(2019, "staffed", "Volunteer lookouts were certified and began shifts in August.", "chews"),
         ]),
]

if __name__ == "__main__":
    run(__doc__, SOURCE, ASSOCIATION, DOCS, LOOKOUTS, credit=CREDIT, license_=LICENSE)
