"""Friends of Hurricane Mountain: the history and restoration of the Hurricane Mountain tower.

  https://www.hurricanefiretower.org/   (volunteers under the umbrella of Adirondack Architectural Heritage)

The Friends work with NYS DEC to protect the 1919 steel fire tower on Hurricane Mountain (Essex
County, NY), the only one in the Adirondacks inside a "primitive" area. The site is small: a tower
history page and a restoration page with a short dated timeline.

What is read (2026-10-08, robots.txt only disallows /wp-admin/): /sample-page/ ("Tower History"),
/restoration/. (The 2019 "100 years" post says the stairs were new, the fencing added and the tower painted by then, without dating any of it, so it gives no event.) Not read: the observers'
and rangers' pages, hiking and lighting pages. The map table installed in the cab in September
2021 is reported by the NYS FFLA chapter (nysffla_projects), not here: the Friends' own post about
it is undated on the page.

Facts are curated by hand below (our own words) and every citation is checked against the page
text. No coordinates are published: the position is copied from the NHLR record.

Licence: none stated; facts only, notes are ours.

Output: data/sources/hurricane_friends.json
Re-run: python3 pipeline/regional/hurricane_friends.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_east import E, doc, run  # noqa: E402

SOURCE = "hurricane_friends"
BASE = "https://www.hurricanefiretower.org"
ASSOCIATION = {"name": "Friends of Hurricane Mountain", "url": f"{BASE}/"}
CREDIT = "Friends of Hurricane Mountain (hurricanefiretower.org)"
LICENSE = (
    "No licence stated; facts only (dates, names, the kind of work done). Every note is our own wording "
    "and every event links to the Friends' page it comes from. The position is copied from the NHLR "
    "record (the Friends publish none)."
)

DOCS = [
    doc("restoration", f"{BASE}/restoration/", "Friends of Hurricane Mountain: Restoration", 2017),
    doc("history", f"{BASE}/sample-page/", "Friends of Hurricane Mountain: Tower History", 2018),
]

LOOKOUTS: list[dict] = [
    dict(slug="hurricane-mountain", name="Hurricane Mountain Fire Tower", tower="us-ny-hurricane-mountain",
         pos="nhlr:US 644", find=["Hurricane"], status="standing", agency="NYS DEC", ownership="state",
         page=f"{BASE}/restoration/",
         events=[
             E(1919, "built", "A 35-foot steel tower with an observation cabin was put up; observers had used the bald summit without a structure from 1910.", "history"),
             E(1979, "staffed_last", "The tower was officially closed in November; the Conservation Department relied on air surveillance from then on.", "history"),
             E(2007, "nrhp_listed", "The tower was listed on the National Register of Historic Places in June.", "restoration"),
             E(2010, "other", "The state classified the land at the tower's base as historic, which saved the tower from removal under the wilderness rules.", "restoration", "history"),
             E(2015, "restored", "Restoration began: DEC flew in materials and volunteers carried more up to replace the stair flights, which were fenced; the tower reopened to the public.", "restoration"),
         ]),
]


def main() -> None:
    run(source=SOURCE, association=ASSOCIATION, credit=CREDIT, license_=LICENSE, region="NY", specs=DOCS,
        lookouts=LOOKOUTS, description=__doc__.split("\n")[0])


if __name__ == "__main__":
    main()
