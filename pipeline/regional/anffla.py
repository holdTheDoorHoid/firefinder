"""Angeles National Forest Fire Lookout Association (California): its lookouts and the lost ones.

  https://www.anffla.org/   (volunteer non-profit partnering with the Angeles National Forest;
                             an FFLA affiliate)

ANFFLA restores, maintains and staffs the lookouts of the Angeles National Forest. Each lookout
page carries a "Statistics" box and a short history; an "Inactive Towers" page notes two that
burned. This source turns those four pages into dated events on the lookouts' timelines, each
linked to its page. Built on the shared association-project shape (_projects.py, DESIGN.md 3.7)
and the driver in _assoc_site.py.

What is read (2026-10-08): /towers/slide-mountain/, /towers/vetter-mountain/ and
/towers/inactive-towers/ (South Mount Hawkins, Warm Springs). robots.txt asks for a 10-second
crawl delay; the four pages were fetched once each and cached, and no further request is made
by this module. The site has no news or project posts.

Licence: no licence stated. Dates, names and the kind of work done are facts; the notes are
ours; each event links to the association's page.

Output: data/sources/anffla.json
Re-run: python3 pipeline/regional/anffla.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_site import E, doc, run  # noqa: E402

SOURCE = "anffla"
BASE = "https://www.anffla.org/towers"
ASSOCIATION = {"name": "Angeles National Forest Fire Lookout Association", "url": "https://www.anffla.org/"}
CREDIT = "Angeles National Forest Fire Lookout Association (anffla.org)"
LICENSE = (
    "No licence stated; facts only (dates, names, the kind of work done). Every note is our own "
    "wording and every event links to the association's page it comes from. Positions are copied "
    "from the NHLR and FFLOS records."
)
DOCS = [
    doc("slide", f"{BASE}/slide-mountain/", "Slide Mountain Lookout (ANFFLA)"),
    doc("vetter", f"{BASE}/vetter-mountain/", "Vetter Mountain Lookout (ANFFLA)"),
    doc("inactive", f"{BASE}/inactive-towers/", "Inactive towers (ANFFLA)"),
]
ANF = "Angeles National Forest"

LOOKOUTS = [
    dict(slug="slide-mountain", name="Slide Mountain Lookout", region="CA", tower="us-ca-slide-mountain", pos="nhlr:US 1045",
         find=["Slide Mountain"], forest=f"{ANF} (Los Angeles Gateway Ranger District)", agency="U.S. Forest Service",
         ownership="federal", staffing="volunteer", status="standing", design="Two-story metal tower with a 365 sq ft cab",
         events=[
             E(1969, "built", "Built with the construction of Pyramid Reservoir: a two-story metal tower with the cab on top.", "slide"),
             E(2003, "restored", "Rededicated on 4 October (the page gives no detail of the work).", "slide", inferred="the page prints the date as 10/04/03"),
         ]),
    dict(slug="vetter-mountain", name="Vetter Mountain Lookout", region="CA", tower="us-ca-vetter-mountain", pos="nhlr:US 294",
         find=["Vetter Mountain"], forest=f"{ANF} (San Gabriel Mountains National Monument)", agency="U.S. Forest Service",
         ownership="federal", staffing="volunteer", status="standing", design="14x14-ft BC-3 cab on the ground, no tower",
         discrepancies=["The page's prose says built 1937; its statistics box says 1935."],
         events=[
             E(1937, "built", "Built as a ground-level 14x14-ft cab (the page's statistics box says 1935).", "vetter"),
             E(1998, "restored", "Reopened to the public by volunteers on 30 May.", "vetter"),
             E(2009, "burned", "The original lookout was lost in the Station Fire in August; volunteers kept lookout service going from a temporary structure for ten years.", "vetter"),
             E(2019, "rebuilt", "Rebuild began in September in a partnership with Southern California Edison.", "vetter"),
             E(2020, "staffed", "Rebuild finished in April; first staffed over the July 4 weekend.", "vetter"),
         ]),
    dict(slug="south-mount-hawkins", name="South Mount Hawkins Lookout", region="CA", tower="us-ca-south-mount-hawkins", pos="nhlr:US 295",
         find=["South Mt. Hawkins", "South Mount Hawkins"], forest=ANF, agency="U.S. Forest Service", ownership="federal", status="gone",
         events=[
             E(1999, "staffed", "Opened (restored) in September by volunteers.", "inactive"),
             E(2002, "burned", "Destroyed by the Curve Fire on 1 September; rebuilding was dropped because the access road was too poor.", "inactive"),
         ]),
    dict(slug="warm-springs", name="Warm Springs Lookout", region="CA", tower="us-ca-warm-springs-mountain", pos="fflos:US 1790",
         find=["Warm Springs"], forest=ANF, agency="U.S. Forest Service", ownership="federal", status="ruins",
         events=[
             E(1987, "burned", "The cab was lost in the Ruby Ridge Fire; only the metal tower platform remains.", "inactive"),
         ]),
]

if __name__ == "__main__":
    run(__doc__, SOURCE, ASSOCIATION, DOCS, LOOKOUTS, credit=CREDIT, license_=LICENSE)
