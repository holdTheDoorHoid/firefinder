"""Green Mountain Lookout (Washington): the long fight to save it, as told by the Washington Trust for Historic Preservation and the Washington Trails Association.

  https://preservewa.org/most_endangered/green-mountain-lookout/
  https://www.wta.org/news/signpost/saving-green-mountain-lookout-a-retrospective

Green Mountain Lookout, in the Glacier Peak Wilderness, was adopted by a "Friends of Green Mountain
Lookout" group, rehabilitated by the Darrington Historical Society and volunteers, taken to court
by a wilderness group, ordered removed in 2012 and saved by an Act of Congress in 2014. The Trust's
"Most Endangered Places" page and the Trails Association's 2014 retrospective give the dates. This
source turns those two pages into dated events on the lookout's timeline, linked to the pages.
Built on the shared association-project shape (_projects.py, DESIGN.md 3.7) and the driver in
_assoc_site.py.

What is read (2026-10-08; preservewa.org's robots.txt asks for a 10-second crawl delay, so its
one page was fetched once and cached; wta.org's allows everything but its search and forms): the
two pages above. The Trust's "40 for 40" feature and the Forest Service page are not read.

Licence: no licence stated. Dates and what happened are facts; the notes are ours; each event links
to the page it comes from.

Output: data/sources/green_mountain_wa.json
Re-run: python3 pipeline/regional/green_mountain_wa.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_site import E, doc, run  # noqa: E402

SOURCE = "green_mountain_wa"
ASSOCIATION = {"name": "Washington Trust for Historic Preservation", "url": "https://preservewa.org/most_endangered/green-mountain-lookout/"}
CREDIT = "Washington Trust for Historic Preservation (preservewa.org); Washington Trails Association (wta.org)"
LICENSE = (
    "No licence stated; facts only (dates, what happened). Every note is our own wording and every "
    "event links to the page it comes from. The position is copied from the NHLR record."
)
DOCS = [
    doc("trust", "https://preservewa.org/most_endangered/green-mountain-lookout/", "Green Mountain Lookout, Most Endangered Places (Washington Trust)"),
    doc("wta", "https://www.wta.org/news/signpost/saving-green-mountain-lookout-a-retrospective", "Saving Green Mountain Lookout, A Brief Retrospective (WTA, 2014)", 2014),
]

LOOKOUTS = [
    dict(slug="green-mountain", name="Green Mountain Lookout", region="WA", tower="us-wa-green-mountain", pos="nhlr:US 22", find=["Green Mountain"],
         forest="Mount Baker-Snoqualmie National Forest (Glacier Peak Wilderness)", agency="U.S. Forest Service", ownership="federal", status="standing",
         events=[
             E(1933, "built", "Built by the Civilian Conservation Corps as part of the North Cascades detection system.", "wta", "trust"),
             E(1968, "other", "The Glacier Peak Wilderness was enlarged to take in the lookout, which later made its upkeep controversial.", "wta"),
             E(1987, "nrhp_listed", "Added to the National Register of Historic Places with five other wilderness lookouts on the forest.", "wta"),
             E(1994, "closed", "Closed to the public because of structural deterioration and threatened with removal.", "trust"),
             E(1999, "other", "Listed among the state's Most Endangered Places; a Trust grant and a $50,000 federal Save America's Treasures award went toward rehabilitation.", "trust"),
             E(2000, "restored", "First rehabilitation work, which did not allow for snow load; the lookout was later taken apart and flown out for repair off site.", "trust"),
             E(2003, "restored", "Hundreds of volunteer hours went into rehabilitating the dismantled lookout between 2003 and 2008.", "trust"),
             E(2009, "restored", "National Park Service crews repaired the foundation and the pieces were flown back and reassembled.", "trust"),
             E(2012, "other", "A federal judge, ruling in a Wilderness Act suit, ordered the Forest Service to remove the lookout.", "trust", "wta"),
             E(2014, "other", "Congress passed the Green Mountain Lookout Heritage Protection Act in April, ending the threat of removal.", "wta", "trust"),
         ]),
]

if __name__ == "__main__":
    run(__doc__, SOURCE, ASSOCIATION, DOCS, LOOKOUTS, credit=CREDIT, license_=LICENSE)
