"""Methow Valley Forest Fire Lookout Association (Washington): the eight lookouts of the Methow Valley Ranger District.

  https://www.mvffla.org/   (an FFLA sub-chapter formed in 2023, with the Methow Valley Ranger District)

The association supports eight historic lookouts in north-central Washington (North Twentymile,
Monument 83, Mebee Pass, Lookout Mountain, First Butte, Goat Peak, Mount Leecher, Slate Peak) and
posts short news items on its work and on the lookouts' fate. This source turns those items into
dated events on the lookouts' timelines, each linked to its post. Built on the shared
association-project shape (_projects.py, DESIGN.md 3.7) and the driver in _assoc_site.py.

What is read (2026-10-08): the five posts under /news/ (welcome, Filson donation, Mebee Pass
shutters, North Twentymile supply drop, Slate Peak collapse). The posts print a month and day but
no year; the year is worked out from what they say (the 1923 cupola's centennial "this year", a
tower built in 1956 and 70 years old) and from the 2023 dates on /events. robots.txt (Squarespace's
standard file) disallows AI-training crawlers by name and a few query-string patterns; FirefinderBot
is none of those. The /lookouts page lists the eight names but has no per-lookout pages.

Licence: no licence stated. Dates and the kind of work done are facts; the notes are ours; each
event links to the association's post.

Output: data/sources/mvffla.json
Re-run: python3 pipeline/regional/mvffla.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_site import E, doc, run  # noqa: E402

SOURCE = "mvffla"
BASE = "https://www.mvffla.org"
ASSOCIATION = {"name": "Methow Valley Forest Fire Lookout Association", "url": f"{BASE}/"}
CREDIT = "Methow Valley Forest Fire Lookout Association (mvffla.org)"
LICENSE = (
    "No licence stated; facts only (dates, the kind of work done). Every note is our own wording "
    "and every event links to the association's post it comes from. Positions are copied from the "
    "NHLR records."
)
DOCS = [
    doc("welcome", f"{BASE}/news/welcome-to-the-mvffla", "Welcome to the MVFFLA"),
    doc("filson", f"{BASE}/news/thank-you-filson", "Thank you Filson!"),
    doc("mebee", f"{BASE}/news/mebee-pass-shutter-restoration", "Mebee Pass shutter restoration"),
    doc("n20", f"{BASE}/news/n20-paracargo", "North Twentymile paracargo drop"),
    doc("slate", f"{BASE}/news/collapse-of-the-slate-peak-fire-lookout", "Collapse of the Slate Peak fire lookout"),
]
OWNF = "Okanogan-Wenatchee National Forest (Methow Valley Ranger District)"
YEAR23 = "the post prints no year; it is 2023, the centennial year of the 1923 cupola, and the events page dates the work parties 2023"

LOOKOUTS = [
    dict(slug="north-twentymile", name="North Twentymile Lookout", region="WA", tower="us-wa-north-twentymile-peak", pos="nhlr:US 161",
         find=["North Twentymile", "North 20", "N20"], forest=OWNF, agency="U.S. Forest Service", ownership="federal", status="standing",
         design="1923 D-6 cupola beside an L-4 tower",
         discrepancies=["The L-4 tower is dated 1942 in one post and 1947 in another."],
         events=[
             E(1923, "built", "A D-6 cupola, the last intact one in Washington, was built; its centennial was celebrated in 2023.", "n20", "welcome"),
             E(2015, "restored", "The D-6 cupola was restored by volunteers led by the late Bob Pfeifer.", "welcome"),
             E(2023, "restored", "A smokejumper plane dropped paint, cedar shingles and supplies on the summit for the planned reroof and repaint of the L-4 tower.", "n20", inferred=YEAR23),
         ]),
    dict(slug="mebee-pass", name="Mebee Pass Lookout", region="WA", tower="us-wa-mebee-pass", pos="nhlr:US 1551",
         find=["Mebee"], forest=OWNF, agency="U.S. Forest Service", ownership="federal", status="standing", design="L-5 cab, one of the last standing",
         events=[
             E(2013, "restored", "The Friends of Mebee Pass completed the last restoration work.", "mebee"),
             E(2023, "restored", "A volunteer carpenter rebuilt the shutters from historical blueprints to replace temporary plywood ones, with an airlift to the summit planned.", "mebee", inferred=YEAR23),
         ]),
    dict(slug="first-butte", name="First Butte Lookout", region="WA", tower="us-wa-first-butte", pos="nhlr:US 358",
         find=["First Butte"], forest=OWNF, agency="U.S. Forest Service", ownership="federal", status="standing",
         events=[
             E(2021, "restored", "Filson employees and National Forest Foundation volunteers spent a weekend painting and restoring the tower, just before the Cub Creek 2 fire.", "filson"),
         ]),
    dict(slug="goat-peak", name="Goat Peak Lookout", region="WA", tower="us-wa-goat-peak", pos="nhlr:US 357",
         find=["Goat Peak"], forest=OWNF, agency="U.S. Forest Service", ownership="federal", staffing="volunteer", status="standing",
         events=[
             E(2020, "staffed", "Volunteer staffing by chapter chair Christine Estrada began.", "welcome"),
         ]),
    dict(slug="slate-peak", name="Slate Peak Lookout", region="WA", tower="us-wa-slate-peak", pos="nhlr:US 359",
         find=["Slate Peak"], forest=OWNF, agency="U.S. Forest Service", ownership="federal", status="gone", height_ft=40,
         design="40-ft tower, 7,440 ft, built 1956",
         events=[
             E(1956, "built", "A 40-ft tower built as a fire detection site in the Pasayten Wilderness; Washington's second-highest standing lookout.", "slate"),
             E(2026, "destroyed", "Collapsed over the winter after 70 years; the association is helping document and salvage what remains.", "slate", inferred="built 1956 and described as 70 years old"),
         ]),
]

if __name__ == "__main__":
    run(__doc__, SOURCE, ASSOCIATION, DOCS, LOOKOUTS, credit=CREDIT, license_=LICENSE)
