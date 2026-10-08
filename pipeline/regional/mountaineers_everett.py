"""The Mountaineers, Everett Branch (Washington): the lookouts its Lookout and Trail Maintenance Committee keeps up.

  https://www.mountaineers.org/locations-lodges/everett-branch/committees/everett-lookout-trail-maintenance-committee

The Everett branch of the Seattle-based outdoor club has restored and maintained three North
Cascades lookouts since the 1980s: Three Fingers, Mount Pilchuck and Heybrook. Its committee's
"Fire Lookouts and The Mountaineers" page gives the history of each building and of the branch's
work on it. This source turns that page into dated events on the three lookouts' timelines, each
linked to the page. Built on the shared association-project shape (_projects.py, DESIGN.md 3.7)
and the driver in _assoc_site.py.

What is read (2026-10-08; robots.txt disallows only the site search): the one page above. The
committee's other pages are trip planning and seminar templates.

Where the page's build histories disagree (Pilchuck is given three different ways) the facts are
left out and the disagreement is recorded in the record's ``extra.discrepancies``; only the work
the branch itself did is given as events.

Licence: no licence stated. Dates and the kind of work done are facts; the notes are ours; each
event links to the Mountaineers page it comes from.

Output: data/sources/mountaineers_everett.json
Re-run: python3 pipeline/regional/mountaineers_everett.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_site import E, doc, run  # noqa: E402

SOURCE = "mountaineers_everett"
PAGE = ("https://www.mountaineers.org/locations-lodges/everett-branch/committees/"
        "everett-lookout-trail-maintenance-committee/web-pages/the-mountaineers-and-fire-lookouts")
ASSOCIATION = {"name": "The Mountaineers, Everett Branch",
               "url": "https://www.mountaineers.org/locations-lodges/everett-branch/committees/everett-lookout-trail-maintenance-committee"}
CREDIT = "The Mountaineers, Everett Branch (mountaineers.org)"
LICENSE = (
    "No licence stated; facts only (dates, names, the kind of work done). Every note is our own "
    "wording and every event links to the Mountaineers page it comes from. Positions are copied "
    "from the NHLR records."
)
DOCS = [doc("page", PAGE, "Fire Lookouts and The Mountaineers (Everett Branch)", None)]
MBS = "Mount Baker-Snoqualmie National Forest"

LOOKOUTS = [
    dict(slug="three-fingers", name="Three Fingers Lookout", region="WA", tower="us-wa-three-fingers", pos="nhlr:US 68",
         find=["Three Fingers"], forest=MBS, agency="U.S. Forest Service", ownership="federal", status="standing",
         design="14x14-ft L-4 cab on the south summit (6,850 ft)",
         events=[
             E(1986, "restored", "The Everett Mountaineers restored the lookout in the mid-1980s; their first newsletter article on the repairs ran in September 1986.", "page"),
             E(2014, "restored", "Roof replaced.", "page"),
             E(2025, "restored", "Floor supports, siding and gable trim replaced.", "page"),
         ]),
    dict(slug="mount-pilchuck", name="Mount Pilchuck Lookout", region="WA", tower="us-wa-mount-pilchuck", pos="nhlr:US 62",
         find=["Pilchuck"], forest=f"{MBS} (Mount Pilchuck State Park)", agency="Washington State Parks and U.S. Forest Service",
         status="standing", discrepancies=["The page gives three histories: built 1919 and rebuilt 1942; built 1921 with a cupola and rebuilt 1938 as an L-4; built 1918."],
         events=[
             E(1989, "restored", "The Everett Mountaineers restored the building, 105 volunteers giving 10,000 hours with help from search-and-rescue and Army Reserve helicopters; it had been due to be burned.", "page"),
         ]),
    dict(slug="heybrook", name="Heybrook Lookout", region="WA", tower="us-wa-heybrook", pos="nhlr:US 1094",
         find=["Heybrook"], forest=MBS, agency="U.S. Forest Service", ownership="federal", status="standing",
         design="Hut on a 70-ft tower", height_ft=70,
         events=[
             E(1925, "built", "First building: a platform tower.", "page"),
             E(1932, "replaced", "A 45-ft L-4 lookout replaced it.", "page"),
             E(1964, "replaced", "A 67-ft \"TT flat\" lookout replaced the L-4.", "page"),
             E(1996, "restored", "The Everett Mountaineers began an eight-year restoration under a cost-share agreement with the Forest Service, starting by taking down the decayed hut.", "page"),
             E(2002, "restored", "A hut rebuilt to the original plans in a ranger-station car park was hoisted onto the tower; work finished by year end and was accepted in January 2003.", "page"),
         ]),
]

if __name__ == "__main__":
    run(__doc__, SOURCE, ASSOCIATION, DOCS, LOOKOUTS, credit=CREDIT, license_=LICENSE)
