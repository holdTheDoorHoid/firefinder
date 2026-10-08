"""Southern California Mountains Foundation (San Bernardino National Forest): its seven lookouts.

  https://mountainsfoundation.org/programs/fire-lookouts/   (non-profit partner of the San
                                                            Bernardino National Forest; an FFLA affiliate)

The foundation's Fire Lookouts program preserves and staffs (with volunteers) the seven lookouts
of the San Bernardino National Forest. One page, "Our Seven Lookouts", gives each lookout a
short history: when it was built, rebuilt, reopened or lost to fire (Red Mountain 2022 and
Keller Peak 2024). This source turns that page into dated events on the lookouts' timelines,
each linked to the page. Built on the shared association-project shape (_projects.py,
DESIGN.md 3.7) and the driver in _assoc_site.py.

What is read (2026-10-08; robots.txt blocks only the calendar views): /programs/fire-lookouts/fl-seven-lookouts/.
The program page and the news list say nothing further about the lookouts. A brochure PDF is
linked but not read.

Licence: no licence stated. Dates and what happened are facts; the notes are ours; each event
links to the foundation's page.

Output: data/sources/scmf_lookouts.json
Re-run: python3 pipeline/regional/scmf_lookouts.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_site import E, doc, run  # noqa: E402

SOURCE = "scmf_lookouts"
PAGE = "https://mountainsfoundation.org/programs/fire-lookouts/fl-seven-lookouts/"
ASSOCIATION = {"name": "Southern California Mountains Foundation", "url": "https://mountainsfoundation.org/programs/fire-lookouts/"}
CREDIT = "Southern California Mountains Foundation (mountainsfoundation.org)"
LICENSE = (
    "No licence stated; facts only (dates, names, what happened). Every note is our own wording "
    "and every event links to the foundation's page it comes from. Positions are copied from the "
    "NHLR records."
)
DOCS = [doc("seven", PAGE, "Our Seven Lookouts (Southern California Mountains Foundation)")]
SBNF = "San Bernardino National Forest"
COMMON = dict(forest=SBNF, agency="U.S. Forest Service", ownership="federal")

LOOKOUTS = [
    dict(slug="black-mountain", name="Black Mountain Lookout", region="CA", tower="us-ca-black-mountain-san-bernadino-nf", pos="nhlr:US 289",
         find=["Black Mountain"], **COMMON, status="standing",
         events=[
             E(1926, "built", "Third lookout built on the San Bernardino National Forest.", "seven"),
             E(1935, "relocated", "The original lookout was taken down and rebuilt on Barton Peak.", "seven"),
             E(1962, "replaced", "The lookout standing today was completed.", "seven"),
         ]),
    dict(slug="butler-peak", name="Butler Peak Lookout", region="CA", tower="us-ca-butler-peak", pos="nhlr:US 292",
         find=["Butler Peak"], **COMMON, status="standing",
         events=[
             E(1970, "other", "Lookout staffer Eileen McMahon spotted the Bear Fire, which burned 49 homes and 53,000 acres.", "seven"),
         ]),
    dict(slug="keller-peak", name="Keller Peak Lookout", region="CA", tower="us-ca-keller-peak", pos="nhlr:US 28",
         find=["Keller Peak"], **COMMON, status="gone",
         events=[
             E(1926, "built", "Built in 1926; the oldest original tower left on the forest, with a historic-landmark plaque.", "seven"),
             E(2024, "burned", "Destroyed by the Line Fire in September.", "seven"),
         ]),
    dict(slug="morton-peak", name="Morton Peak Lookout", region="CA", tower="us-ca-morton-peak", pos="nhlr:US 673",
         find=["Morton Peak"], **COMMON, staffing="volunteer", status="standing",
         events=[
             E(1934, "built", "Built; the lookout was destroyed in 1959.", "seven"),
             E(1959, "burned", "Destroyed by the Morton fire; the lookout on duty, Aleta Johnson, was airlifted out.", "seven"),
             E(1961, "rebuilt", "Rebuilt; it closed again in the 1970s.", "seven"),
             E(2001, "restored", "Refurbished and put back in service.", "seven"),
         ]),
    dict(slug="red-mountain", name="Red Mountain Lookout", region="CA", tower="us-ca-red-mountain-san-bernadino-nf", pos="nhlr:US 290",
         find=["Red Mountain"], **COMMON, status="gone",
         events=[
             E(1937, "built", "Built by the Civilian Conservation Corps.", "seven"),
             E(1999, "staffed", "Reopened by the foundation's volunteers.", "seven"),
             E(2022, "burned", "Destroyed by the Fairview Fire in September.", "seven"),
         ]),
    dict(slug="strawberry-peak", name="Strawberry Peak Lookout", region="CA", tower="us-ca-strawberry-peak", pos="nhlr:US 293",
         find=["Strawberry Peak"], **COMMON, status="standing", design="30-ft tower", height_ft=30,
         events=[
             E(1922, "built", "First tower: 80 ft tall, put up with railings donated by the Santa Fe railway.", "seven"),
             E(1934, "replaced", "The old tower, damaged by lightning and heavy snow, was replaced by the present 30-ft tower.", "seven"),
         ]),
    dict(slug="tahquitz-peak", name="Tahquitz Peak Lookout", region="CA", tower="us-ca-tahquitz-peak", pos="nhlr:US 291",
         find=["Tahquitz"], **COMMON, status="standing",
         events=[
             E(1993, "staffed_last", "End of its run as a working station of some 77 years, the forest's longest.", "seven"),
             E(1998, "staffed", "Reopened in October with volunteer staffing.", "seven"),
         ]),
]

if __name__ == "__main__":
    run(__doc__, SOURCE, ASSOCIATION, DOCS, LOOKOUTS, credit=CREDIT, license_=LICENSE)
