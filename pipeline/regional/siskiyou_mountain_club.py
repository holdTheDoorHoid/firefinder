"""Siskiyou Mountain Club (Oregon): the rebuilding of Bolan Mountain Lookout.

  https://siskiyoumountainclub.org/   (a trail non-profit in southern Oregon and northern California;
                                       its Bolan Mountain project is its first building)

Bolan Mountain Lookout, on the Oregon-California line in the Rogue River-Siskiyou National Forest,
burned in the 2020 Slater Fire. The club and the Forest Service rebuilt it to the 1954 design in
2024. This source puts that history on the lookout's timeline, linked to the club's project page
and the Forest Service's account of it. Built on the shared association-project shape
(_projects.py, DESIGN.md 3.7) and the driver in _assoc_site.py.

What is read (2026-10-08; the club's Shopify robots.txt allows blog and page content; the Forest
Service robots.txt blocks only archive and image-database search paths): the club's Bolan Mountain
Lookout Project post and the Forest Service story "Hope Returns to the Forest" (4 August 2025).
Any other club project is a trail, not a lookout.

Licence: no licence stated. Dates and what happened are facts; the notes are ours; each event
links to the page it comes from.

Output: data/sources/siskiyou_mountain_club.json
Re-run: python3 pipeline/regional/siskiyou_mountain_club.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_site import E, doc, run  # noqa: E402

SOURCE = "siskiyou_mountain_club"
ASSOCIATION = {"name": "Siskiyou Mountain Club", "url": "https://siskiyoumountainclub.org/"}
CREDIT = "Siskiyou Mountain Club (siskiyoumountainclub.org); USDA Forest Service, Rogue River-Siskiyou National Forest"
LICENSE = (
    "No licence stated; facts only (dates, what happened). Every note is our own wording and every "
    "event links to the page it comes from. The position is copied from the NHLR record."
)
DOCS = [
    doc("club", "https://siskiyoumountainclub.org/blogs/siskiyou-hiker-news/bolan-mountain-lookout-project",
        "Bolan Mountain Lookout Project (Siskiyou Mountain Club)"),
    doc("fs", "https://www.fs.usda.gov/r06/rogue-siskiyou/newsroom/stories/hope-returns-forest-rebuilding-bolan-mountain-lookout",
        "Hope Returns to the Forest: Rebuilding Bolan Mountain Lookout (Rogue River-Siskiyou NF)", 2025),
]

LOOKOUTS = [
    dict(slug="bolan-mountain", name="Bolan Mountain Lookout", region="OR", tower="us-or-bolan-mountain", pos="nhlr:US 483", find=["Bolan"],
         forest="Rogue River-Siskiyou National Forest (Wild Rivers Ranger District)", agency="U.S. Forest Service", ownership="federal",
         status="standing",
         url="https://siskiyoumountainclub.org/blogs/siskiyou-hiker-news/bolan-mountain-lookout-project",
         events=[
             E(1925, "built", "Original lookout; rebuilt in 1954 and staffed by forest employees until the 2000s, then rented to the public.", "fs"),
             E(1954, "rebuilt", "The lookout was rebuilt; the 2024 reconstruction copies this version.", "fs"),
             E(2020, "burned", "Burned to the ground in the Slater Fire in September, weeks after the Forest Service finished repairs and a remodel.", "fs", "club"),
             E(2024, "rebuilt", "Rebuilt by the club, Forest Service staff and contractors in the image of the 1954 lookout with fire-resistant materials; finished in October after 2,000 hours of labor.", "fs"),
         ]),
]

if __name__ == "__main__":
    run(__doc__, SOURCE, ASSOCIATION, DOCS, LOOKOUTS, credit=CREDIT, license_=LICENSE)
