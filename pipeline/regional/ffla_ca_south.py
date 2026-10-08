"""FFLA California South Division (California): the return of Bald Mountain Lookout to service.

  https://www.firelookouthost.org/   (the Forest Fire Lookout Association's California South chapter)

The division's Wix site lists the 29 standing towers of southern California and has a page for Bald
Mountain Lookout, the only standing lookout on the Inyo National Forest, which the association
returned to volunteer service in 2024. This source puts that on the lookout's timeline, linked to
the page. (The site's roster table of the chapter's towers is a list, not a work log, and is left to
the lookout-list sources.) Built on the shared association-project shape (_projects.py, DESIGN.md 3.7)
and the driver in _assoc_site.py.

What is read (2026-10-08; robots.txt allows everything but a gallery lightbox): /bald-mountain.

Licence: no licence stated. Dates and what happened are facts; the notes are ours; the events link to
the division's page.

Output: data/sources/ffla_ca_south.json
Re-run: python3 pipeline/regional/ffla_ca_south.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_site import E, doc, run  # noqa: E402

SOURCE = "ffla_ca_south"
ASSOCIATION = {"name": "FFLA California South Division", "url": "https://www.firelookouthost.org/"}
CREDIT = "Forest Fire Lookout Association, California South Division (firelookouthost.org)"
LICENSE = (
    "No licence stated; facts only (dates, what happened). Every note is our own wording and the events "
    "link to the division's page. The position is copied from the NHLR record."
)
DOCS = [doc("bald", "https://www.firelookouthost.org/bald-mountain", "Bald Mountain Lookout (FFLA California South)")]

LOOKOUTS = [
    dict(slug="bald-mountain-inyo", name="Bald Mountain Lookout (Inyo NF)", region="CA", tower="us-ca-bald-mountain-inyo-nf", pos="nhlr:US 279",
         find=["Bald Mountain"], forest="Inyo National Forest (Mono Lake Ranger District)", agency="U.S. Forest Service", ownership="federal",
         staffing="volunteer", status="standing",
         events=[
             E(1963, "built", "Built; the only standing and operating lookout on the Inyo National Forest.", "bald"),
             E(2024, "staffed", "Back in service: the FFLA and the Mono Lake Ranger District started staffing it with trained volunteers, including visiting volunteers from other forests.", "bald"),
         ]),
]

if __name__ == "__main__":
    run(__doc__, SOURCE, ASSOCIATION, DOCS, LOOKOUTS, credit=CREDIT, license_=LICENSE)
