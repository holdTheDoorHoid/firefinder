"""Snoqualmie Fire Lookouts Association (Washington): the three lookouts it looks after.

  https://www.snoqualmielookouts.org/   (volunteer group working with the Snoqualmie and North
                                         Bend Ranger Districts; an FFLA affiliate)

The association staffs Suntop and Kelly Butte with volunteers each summer and is restoring
Granite Mountain. Its one page per lookout gives the build history and the restoration years.
This source turns the three pages into dated events on the lookouts' timelines, each linked to its
page. Built on the shared association-project shape (_projects.py, DESIGN.md 3.7) and the driver
in _assoc_site.py.

What is read (2026-10-08): /suntop-lookout, /kelly-butte-lookout, /granite-mountain-lookout.
robots.txt (Squarespace's standard file) disallows AI-training crawlers by name and a few
paths such as /config and /search; FirefinderBot is none of those and reads only the pages
above. The site has no news or project posts.

Licence: no licence stated. Dates and the kind of work done are facts; the notes are ours; each
event links to the association's page.

Output: data/sources/snoqualmie_lookouts.json
Re-run: python3 pipeline/regional/snoqualmie_lookouts.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_site import E, doc, run  # noqa: E402

SOURCE = "snoqualmie_lookouts"
BASE = "https://www.snoqualmielookouts.org"
ASSOCIATION = {"name": "Snoqualmie Fire Lookouts Association", "url": f"{BASE}/"}
CREDIT = "Snoqualmie Fire Lookouts Association (snoqualmielookouts.org)"
LICENSE = (
    "No licence stated; facts only (dates, names, the kind of work done). Every note is our own "
    "wording and every event links to the association's page it comes from. Positions are copied "
    "from the NHLR records."
)
DOCS = [
    doc("suntop", f"{BASE}/suntop-lookout", "Suntop Lookout (Snoqualmie Fire Lookouts Association)"),
    doc("kelly", f"{BASE}/kelly-butte-lookout", "Kelly Butte Lookout (Snoqualmie Fire Lookouts Association)"),
    doc("granite", f"{BASE}/granite-mountain-lookout", "Granite Mountain Lookout (Snoqualmie Fire Lookouts Association)"),
]
MBS = "Mount Baker-Snoqualmie National Forest"

LOOKOUTS = [
    dict(slug="suntop", name="Suntop Lookout", region="WA", tower="us-wa-suntop", pos="nhlr:US 92", find=["Suntop"],
         forest=f"{MBS} (Snoqualmie Ranger District)", agency="U.S. Forest Service", ownership="federal", staffing="volunteer",
         status="standing", design="14x14-ft L-4 cab",
         events=[
             E(1932, "built", "Built as a 14x14-ft L-4 cab; supplies came up by pack and mule until a road reached the summit in 1956.", "suntop"),
             E(1986, "restored", "Major refurbishment, after which the cab was set on the rock foundation it still sits on.", "suntop"),
         ]),
    dict(slug="kelly-butte", name="Kelly Butte Lookout", region="WA", tower="us-wa-kelly-butte", pos="nhlr:US 910", find=["Kelly Butte"],
         forest=f"{MBS} (Snoqualmie Ranger District)", agency="U.S. Forest Service", ownership="federal", staffing="volunteer",
         status="standing", design="L-4 cab",
         events=[
             E(1926, "built", "First lookout: a 12x12-ft cupola cab, supplied by mule from the Lester ranger station.", "kelly"),
             E(1950, "replaced", "The present L-4 cab replaced the cupola cab.", "kelly"),
             E(2008, "restored", "Volunteers with the FFLA and the Forest Service began a major restoration that included a new trail built with Washington Trails Association help.", "kelly"),
             E(2011, "restored", "The restoration was completed after a spell of 20 years abandoned.", "kelly"),
             E(2012, "staffed", "Put back in service by the national forest.", "kelly"),
         ]),
    dict(slug="granite-mountain", name="Granite Mountain Lookout", region="WA", tower="us-wa-granite-mountain-2", pos="nhlr:US 1068",
         find=["Granite Mountain"], forest=f"{MBS} (Snoqualmie Ranger District)", agency="U.S. Forest Service", ownership="federal",
         status="standing", design="10-ft L-4 tower",
         events=[
             E(1924, "built", "A D-6 cupola cab went up on the summit, where an earlier summit cabin had stood.", "granite"),
             E(1956, "replaced", "Upgraded to the present L-4 on a 10-ft tower after serving as a wartime Aircraft Warning post.", "granite"),
         ]),
]

if __name__ == "__main__":
    run(__doc__, SOURCE, ASSOCIATION, DOCS, LOOKOUTS, credit=CREDIT, license_=LICENSE)
