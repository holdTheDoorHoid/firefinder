"""Buck Rock Foundation (California): the three Sierra lookouts it staffs and maintains.

  https://buckrock.org/   (a volunteer non-profit working with the Sequoia National Forest and
                           Sequoia and Kings Canyon National Parks; an FFLA affiliate)

The foundation was formed after the 1997 Choke Fire to save Buck Rock Lookout and now also
staffs Delilah (Sequoia NF) and Park Ridge (Kings Canyon NP). Each lookout has a page with its
history; the news blog records maintenance work days. This source turns those into dated
events on the three lookouts' timelines, each linked to the page. Built on the shared
association-project shape (_projects.py, DESIGN.md 3.7) and the driver in _assoc_site.py.

What is read (2026-10-08; robots.txt allows everything): the three lookout pages, /history/
(the foundation's origin story), /restoration-team/ (what the facility team does) and the
2025 maintenance posts for Buck Rock (Aug 11) and Park Ridge (Aug 19). The news blog goes back to
2024 and is mostly staffing, education and fire reports; no older work log exists.

Licence: no licence stated. Dates, names and the kind of work done are facts; the notes are
ours; each event links to the foundation's page.

Output: data/sources/buck_rock.json
Re-run: python3 pipeline/regional/buck_rock.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_site import E, doc, run  # noqa: E402

SOURCE = "buck_rock"
BASE = "https://buckrock.org"
ASSOCIATION = {"name": "Buck Rock Foundation", "url": f"{BASE}/"}
CREDIT = "Buck Rock Foundation (buckrock.org)"
LICENSE = (
    "No licence stated; facts only (dates, names, the kind of work done). Every note is our own "
    "wording and every event links to the foundation's page it comes from. Positions are copied "
    "from the NHLR records."
)
DOCS = [
    doc("buck", f"{BASE}/buck-rock-lookout/", "Buck Rock Lookout (Buck Rock Foundation)"),
    doc("delilah", f"{BASE}/delilah-lookout/", "Delilah Lookout (Buck Rock Foundation)"),
    doc("park", f"{BASE}/park-ridge-lookout/", "Park Ridge Lookout (Buck Rock Foundation)"),
    doc("history", f"{BASE}/history/", "Our origin story (Buck Rock Foundation)"),
    doc("buck25", f"{BASE}/2025/08/11/preserving-our-historic-treasure-maintenance-update-at-buck-rock-lookout/",
        "Maintenance update at Buck Rock Lookout, Aug 2025", 2025),
    doc("park25", f"{BASE}/2025/08/19/improvements-at-park-ridge-fire-lookout-new-equipment-and-clearer-views/",
        "Improvements at Park Ridge Fire Lookout, Aug 2025", 2025),
]

LOOKOUTS = [
    dict(slug="buck-rock", name="Buck Rock Lookout", region="CA", tower="us-ca-buck-rock", pos="nhlr:US 284", find=["Buck Rock"],
         forest="Sequoia National Forest", agency="U.S. Forest Service", ownership="federal", staffing="volunteer", status="standing",
         design="4-A style live-in cab on a granite dome, reached by 172 steps",
         events=[
             E(1923, "built", "The present building went up, one of the earliest live-in 4-A style cabs; earlier watchers sat on an open platform.", "history"),
             E(1987, "closed", "Shut and left to decay until 1998, used only in emergencies.", "history"),
             E(1997, "other", "Reopened briefly to track a thunderstorm; the lookout spotted the Choke Fire, and the busy six weeks led locals to form the Buck Rock Foundation.", "history"),
             E(2000, "staffed", "The Foundation and the Forest Service reopened it for good after raising grants and volunteers.", "history"),
             E(2025, "restored", "Facility team began repainting the cab exterior, fitted a new stove, strengthened the top stair platform and put in a new water pump.", "buck25"),
         ]),
    dict(slug="delilah", name="Delilah Lookout", region="CA", tower="us-ca-delilah", pos="nhlr:US 379", find=["Delilah"],
         forest="Sequoia National Forest (Hume Lake Ranger District)", agency="U.S. Forest Service", ownership="federal",
         staffing="volunteer", status="standing", design="15x15-ft cab on a 67-ft former air traffic control tower",
         events=[
             E(1916, "built", "Established as a detection site; the first structure is thought to have been a 7x7-ft cab on a metal tower.", "delilah"),
             E(1960, "replaced", "Replaced by a decommissioned Lemoore Naval Air Station air traffic control tower, flown in and rebuilt as the lookout.", "delilah"),
             E(1999, "staffed_last", "Last regular season; closed for good and used only briefly in 2001 and 2002.", "delilah"),
             E(2005, "staffed", "Reopened through a partnership of the Buck Rock Foundation and the Forest Service; staffed by its volunteers since.", "delilah"),
             E(2015, "fire", "Directly threatened by the Rough Fire, which firefighters stopped along the ridge it stands on.", "delilah"),
         ]),
    dict(slug="park-ridge", name="Park Ridge Lookout", region="CA", tower="us-ca-park-ridge", pos="nhlr:US 892", find=["Park Ridge"],
         forest="Kings Canyon National Park", agency="National Park Service", ownership="federal", staffing="volunteer", status="standing",
         design="14x14-ft cab on a 20-ft steel tower",
         events=[
             E(1916, "built", "Established as an open-air lookout with a lean-to and tent platform.", "park"),
             E(1940, "other", "The Park Service took sole charge from the Forest Service, which had shared it.", "park"),
             E(1964, "replaced", "Replaced by the present 20-ft steel tower, moved a quarter mile southwest of the old site.", "park"),
             E(1974, "other", "Longtime lookout Mattie Simms retired after 18 seasons; staffing became sporadic.", "park"),
             E(1996, "staffed_last", "Closed permanently until the Foundation's agreement.", "park"),
             E(2004, "staffed", "Reopened under a cooperative agreement with the Park Service; staffed by Buck Rock Foundation volunteers since.", "park"),
             E(2025, "modified", "New stove, a custom outhouse step and a friendlier catwalk gate; trees around it were cleared to widen the view.", "park25"),
         ]),
]

if __name__ == "__main__":
    run(__doc__, SOURCE, ASSOCIATION, DOCS, LOOKOUTS, credit=CREDIT, license_=LICENSE)
