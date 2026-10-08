"""Kent Conservation Foundation (for the Town of Kent Conservation Advisory Committee): the Mount Nimham tower.

  https://thekcf.org/   (a nonprofit formed in 2014 to carry out the Kent CAC's preservation projects)

The Town of Kent's Conservation Advisory Committee holds the stewardship agreement with NYS DEC for the 1940
CCC fire tower on Mount Nimham (Putnam County, NY), and its volunteers paint and maintain it. The Foundation
was formed to fund and run the larger repairs the town and state will not: the cab floor in 2015 and the
stair landings from 2017. Its blog is short (two posts about the tower, 2017); the CAC's own site
(kentcac.info) describes the mountain but dates none of the tower work.

What is read (2026-10-08; thekcf.org has no robots.txt): the posts "A Big Project" (27 June 2017) and
"Landing Replacement Project" (11 July 2017). Not read: the Hawk Rock and Mead Farm pages.

Prose, curated by hand in our own words and checked against the posts' text. No coordinates: the
position is copied from the NHLR record.

Licence: none stated; facts only, notes are ours.

Output: data/sources/kent_conservation_foundation.json
Re-run: python3 pipeline/regional/kent_conservation_foundation.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_east import E, doc, run  # noqa: E402

SOURCE = "kent_conservation_foundation"
BASE = "https://thekcf.org"
ASSOCIATION = {"name": "Kent Conservation Foundation", "url": f"{BASE}/"}
CREDIT = "Kent Conservation Foundation (thekcf.org)"
LICENSE = (
    "No licence stated; facts only (dates, names, the kind of work done). Every note is our own wording and "
    "every event links to the Foundation's post it comes from. The position is copied from the NHLR record "
    "(the Foundation publishes none)."
)

DOCS = [
    doc("bigproject", f"{BASE}/index.php/2017/06/27/a-big-project/", "KCF: A Big Project", 2017, cache="a-big-project.html"),
    doc("landing", f"{BASE}/index.php/2017/07/11/landing-replacement-project/", "KCF: Landing Replacement Project", 2017,
        cache="landing-replacement-project.html"),
]

LOOKOUTS: list[dict] = [
    dict(region="NY", slug="mount-nimham", name="Mount Nimham Fire Tower", tower="us-ny-mount-nimham", pos="nhlr:US 314",
         find=["Nimham"], status="standing", agency="NYS DEC", ownership="state",
         url=f"{BASE}/index.php/2017/06/27/a-big-project/",
         events=[
             E(2015, "restored", "The spongy 1940 plank cab floor and the railing round the trap door were replaced in two days in early May, with the tower closed briefly, at a cost under $800.", "bigproject"),
             E(2017, "restored", "A volunteer crew replaced stair landing 3, the one 20 feet above the treetops, on 10 July and repainted the inside of the cab; the other landings were to follow one at a time.", "landing"),
         ]),
]


def main() -> None:
    run(__doc__, SOURCE, ASSOCIATION, DOCS, LOOKOUTS, credit=CREDIT, license_=LICENSE, folded=True)


if __name__ == "__main__":
    main()
