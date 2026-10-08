"""Friends of Stillwater Fire Tower: the restoration of the Stillwater Mountain tower, 2009-2016.

  http://www.friendsofstillwaterfiretower.com/   (a volunteer 501(c)(3) working with NYS DEC)

The Friends and DEC restored the 1919 steel tower on Stillwater Mountain (Webb, Herkimer County, NY), closed
in 1988, with about 125 volunteers between 2009 and its reopening on 2 July 2016. The site (Weebly) is small:
a home page, photo and donor pages and a 2018 brochure (PDF) with the tower's dates, which is the one dated
record here.

What is read (2026-10-08; the site has no robots.txt): the 2018 brochure PDF. Not read: the donor and
news page (thanks and donations), the photo pages, the history book page.

Prose, curated by hand in our own words and checked against the brochure's text. No coordinates: the
position is copied from the NHLR record.

Licence: none stated; facts only, notes are ours.

Output: data/sources/stillwater_friends.json
Re-run: python3 pipeline/regional/stillwater_friends.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_east import E, doc, run  # noqa: E402

SOURCE = "stillwater_friends"
BASE = "http://www.friendsofstillwaterfiretower.com"
ASSOCIATION = {"name": "Friends of Stillwater Fire Tower", "url": f"{BASE}/"}
CREDIT = "Friends of Stillwater Fire Tower (friendsofstillwaterfiretower.com)"
LICENSE = (
    "No licence stated; facts only (dates, names, the kind of work done). Every note is our own wording and "
    "every event links to the Friends' brochure it comes from. The position is copied from the NHLR record "
    "(the Friends publish none)."
)

BROCHURE = f"{BASE}/uploads/7/0/5/9/7059738/fsft-brochure-2018.pdf"
DOCS = [doc("brochure", BROCHURE, "Friends of Stillwater Fire Tower: 2018 brochure", 2018, cache="brochure.pdf")]

LOOKOUTS: list[dict] = [
    dict(region="NY", slug="stillwater-mountain", name="Stillwater Fire Tower", tower="us-ny-stillwater-mountain", pos="nhlr:US 904",
         find=["Stillwater"], status="standing", agency="NYS DEC", ownership="state",
         url=f"{BASE}/",
         events=[
             E(1882, "other", "Verplanck Colvin's state Adirondack Survey built a signal tower on the summit, making it a primary triangulation station.", "brochure"),
             E(1988, "closed", "The 1919 tower was closed.", "brochure"),
             E(2009, "restored", "Restoration began as a partnership between NYS DEC and the volunteer Friends group.", "brochure"),
             E(2016, "restored", "The restored tower reopened.", "brochure"),
             E(2017, "nrhp_listed", "The tower was listed on the New York State and National Registers of Historic Places.", "brochure"),
         ]),
]


def main() -> None:
    run(__doc__, SOURCE, ASSOCIATION, DOCS, LOOKOUTS, credit=CREDIT, license_=LICENSE, folded=True)


if __name__ == "__main__":
    main()
