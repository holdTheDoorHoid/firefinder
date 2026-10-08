"""Friends of the Smokies: the Mount Cammerer fire tower, 1995 and 2023.

  https://friendsofthesmokies.org/   (the Great Smoky Mountains National Park's nonprofit partner, formed 1993)

Friends of the Smokies exists because of a fire tower: the group was founded in 1993 to raise money to
restore the dilapidated 1939 CCC tower on Mount Cammerer (Cocke County, TN, on the North Carolina line), and
that restoration (1995, finished a few years later) was its first project. In 2023 its "Forever Places"
endowment paid for a second round of repairs. The group is not a lookout association, but it is a nonprofit
that restored a lookout and kept a dated record.

What is read (2026-10-08; robots.txt asks for a 3 s crawl delay, which CRAWL_DELAY below sets): the group's 2016
blog post about the Classic Hike to the tower (it states the 1995 restoration) and Smoky Mountain News's
2023 report on the Forever Places repairs (smokymountainnews.com, whose robots.txt allows it). The group's
own Forever Places page names no tower; the 2023 work is therefore cited to the news report. Not read: the
rest of the blog, donor and event pages.

Prose, curated by hand in our own words and checked against the pages' text. No coordinates: the
position is copied from the NHLR record.

Licence: none stated; facts only, notes are ours.

Output: data/sources/smokies_friends.json
Re-run: python3 pipeline/regional/smokies_friends.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_east import E, doc, run  # noqa: E402

CRAWL_DELAY = 3.0   # robots.txt: Crawl-delay: 3

SOURCE = "smokies_friends"
BASE = "https://friendsofthesmokies.org"
ASSOCIATION = {"name": "Friends of the Smokies", "url": f"{BASE}/"}
CREDIT = "Friends of the Smokies (friendsofthesmokies.org)"
LICENSE = (
    "No licence stated; facts only (dates, names, the kind of work done). Every note is our own wording and "
    "every event links to the page it comes from. The position is copied from the NHLR record (the group "
    "publishes none)."
)

DOCS = [
    doc("classic", f"{BASE}/blog/mt-cammerer-classic-hike-sept2016/", "Friends of the Smokies: Classic Hike to Mt. Cammerer", 2016,
        cache="classic-hike.html"),
    doc("smn2023", "https://smokymountainnews.com/archived/archived-outdoors/keeping-watch-mt-cammerer-fire-tower-restoration-marks-friends-of-the-smokies-30th-birthday/",
        "Smoky Mountain News: Mt. Cammerer fire tower restoration marks Friends of the Smokies' 30th birthday", 2023,
        cache="smn-2023.html"),
]

LOOKOUTS: list[dict] = [
    dict(slug="mount-cammerer", name="Mount Cammerer Fire Tower", tower="us-tn-mount-cammerer", pos="nhlr:US 82",
         find=["Cammerer"], status="standing", agency="National Park Service (Great Smoky Mountains National Park)",
         ownership="federal", page=f"{BASE}/blog/mt-cammerer-classic-hike-sept2016/",
         events=[
             E(1995, "restored", "Restoration of the tower began, the first project of the new Friends of the Smokies; the work finished a few years later.", "classic", "smn2023"),
             E(2023, "restored", "A Forever Places crew spent a week in September repairing steps and railings, replacing blown-out windows and rotted rafter tails, and repainting the door.", "smn2023"),
         ]),
]


def main() -> None:
    run(source=SOURCE, association=ASSOCIATION, credit=CREDIT, license_=LICENSE, region="TN", specs=DOCS,
        lookouts=LOOKOUTS, description=__doc__.split("\n")[0], crawl_delay=CRAWL_DELAY)


if __name__ == "__main__":
    main()
