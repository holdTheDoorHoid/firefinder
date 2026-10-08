"""Sand Mountain Society (Oregon): the lookouts it has restored and maintained, with the years of work.

  https://sandmountain.org/   (a volunteer 501(c)(3) historic-preservation group; an FFLA affiliate)

The Society restores and maintains historic fire lookouts in Oregon and Washington with the
Forest Service and the Park Service, and gives each of its projects a page with a "Quick Facts"
box (agency, year built, style, "Major SMS Work Efforts" by year) and a prose history. This
source turns those eight project pages into dated events on the lookouts' timelines, each
linked to the page that gives it, plus the few facts the pages state (agency, design, who staffs
it). Built on the shared association-project shape (_projects.py, DESIGN.md 3.7) and the
driver in _assoc_site.py.

What is read (2026-10-08; robots.txt allows everything but /wp-admin): the eight pages under
/projects/ (Gold Butte, High Rock, Huckleberry Mountain, Pearsoll Peak, Pechuk, Sand Mountain,
The Watchman, Wildhorse). Nothing else on the site records work on a lookout.

The pages are prose, so the facts are curated by hand below (our own words, each citing its
page) and the driver checks each citation against the page text. Where a page gives only a
span ("2020-2025 major maintenance") or an approximate date ("early 1970s") the event is dated
to a year the page does state, or left out.

Licence: no licence stated. Dates, names, dimensions and the kind of work done are facts; the
notes are ours; each event links to the SMS page it comes from.

Output: data/sources/sand_mountain.json
Re-run: python3 pipeline/regional/sand_mountain.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_site import E, doc, run  # noqa: E402

SOURCE = "sand_mountain"
BASE = "https://sandmountain.org/projects"
ASSOCIATION = {"name": "Sand Mountain Society", "url": "https://sandmountain.org/"}
CREDIT = "Sand Mountain Society (sandmountain.org)"
LICENSE = (
    "No licence stated; facts only (dates, names, dimensions, the kind of work done). Every note is "
    "our own wording and every event links to the Sand Mountain Society page it comes from. "
    "Positions are copied from the NHLR and FFLOS records."
)

DOCS = [
    doc("gold", f"{BASE}/gold-butte-lookout/", "Gold Butte Lookout (Sand Mountain Society)", 2025),
    doc("high", f"{BASE}/high-rock-lookout/", "High Rock Lookout (Sand Mountain Society)", 2025),
    doc("huck", f"{BASE}/huckleberry-mountain-lookout/", "Huckleberry Mountain Lookout (Sand Mountain Society)", 2025),
    doc("pears", f"{BASE}/pearsoll-peak/", "Pearsoll Peak Lookout (Sand Mountain Society)", 2018),
    doc("pechuk", f"{BASE}/pechuk-lookout/", "Pechuck Lookout (Sand Mountain Society)", 1991),
    doc("sand", f"{BASE}/sand-mountain-lookout/", "Sand Mountain Lookout (Sand Mountain Society)", 1990),
    doc("watch", f"{BASE}/the-watchman-lookout/", "The Watchman Lookout (Sand Mountain Society)", 2010),
    doc("wild", f"{BASE}/wildhorse-lookout/", "Wildhorse Lookout (Sand Mountain Society)", 2014),
]

WNF = "Willamette National Forest"
RRSNF = "Rogue River-Siskiyou National Forest"

LOOKOUTS = [
    dict(slug="gold-butte", name="Gold Butte Lookout", region="OR", tower="us-or-gold-butte", pos="nhlr:US 134",
         find=["Gold Butte"], forest=f"{WNF} (Detroit Ranger District)", agency="U.S. Forest Service", ownership="federal",
         design="Hip-roofed L-4 cab with shutter props (1932 plan)", status="standing",
         events=[
             E(1934, "built", "Built by the Civilian Conservation Corps as a hip-roofed L-4 cab.", "gold"),
             E(1942, "staffed", "Served as a wartime Aircraft Warning Service post, watched around the clock through the winter.", "gold"),
             E(2007, "restored", "Dedicated after a full rebuild begun in 1998-99: volunteers catalogued, dismantled and reassembled it with the Forest Service.", "gold"),
             E(2008, "modified", "Replica woodshed and outhouse built from salvaged materials, finishing the restoration.", "gold"),
             E(2020, "restored", "Major maintenance began (shutters repaired and refitted) as the Lionshead and Beachie Creek fires blew up nearby.", "gold"),
             E(2020, "fire", "Survived the Beachie Creek and Lionshead fires; fire closures kept crews out until 2024.", "gold"),
             E(2024, "restored", "New shingle roof on two sides, more repairs, and the building and floor repainted.", "gold"),
             E(2025, "restored", "Whole exterior repainted in July; the lookout returned to the rental program after the fire-related break.", "gold"),
         ]),
    dict(slug="high-rock", name="High Rock Lookout", region="WA", tower="us-wa-high-rock-2", pos="nhlr:US 387",
         find=["High Rock"], forest=f"Gifford Pinchot National Forest (Cowlitz Valley Ranger District)",
         agency="U.S. Forest Service", ownership="federal", design="14x14-ft gable-roof L-4 cab on an enclosed timber platform",
         events=[
             E(1931, "built", "Built 1930-31 as an L-4 cab for the Mineral Ranger District's detection network.", "high"),
             E(2003, "staffed_last", "Last season the lookout was occupied; neglect and vandalism followed.", "high"),
             E(2015, "restored", "Volunteers stabilized the south wall as a Historical Society campaign to save the lookout began.", "high"),
             E(2020, "assessed", "Condition inspection found serious rot in load-bearing parts; SMS wrote the historic property plan and the windows came out for restoration.", "high"),
             E(2021, "restored", "Cabin taken apart over three weeks and its lumber flown out for repair at the ranger station.", "high"),
             E(2025, "restored", "Refurbished parts flown back on July 8 and rebuilding began; the cabin was weathertight before the trail reopened Nov 1.", "high"),
         ]),
    dict(slug="huckleberry-mountain", name="Huckleberry Mountain Lookout", region="OR", tower="us-or-huckleberry-mountain",
         pos="nhlr:US 26", find=["Huckleberry"], forest=f"{WNF} (Middle Fork Ranger District)", agency="U.S. Forest Service",
         ownership="federal", design="Hip-roofed L-4 with outriggers", staffing="staffed", status="standing",
         events=[
             E(1938, "built", "Built as a hip-roofed L-4 with outriggers.", "huck"),
             E(1992, "restored", "Restored in place, with structural repairs, by the Friends of Huckleberry and SMS after the district weighed replacing it.", "huck"),
             E(1995, "restored", "Plywood replacement ceiling swapped for in-kind rustic bevel boards supplied by SMS.", "huck"),
             E(1996, "restored", "Fir floor refurbished.", "huck"),
             E(1998, "restored", "Another of SMS's major maintenance visits.", "huck"),
             E(2008, "restored", "Major maintenance; SMS took on the lookout's continuing upkeep after Friends founder Roxie Metzler died that year.", "huck"),
             E(2017, "restored", "Rotted outrigger framing and the original shutters replaced.", "huck"),
             E(2025, "restored", "Broken panes of glass replaced.", "huck"),
         ]),
    dict(slug="pearsoll-peak", name="Pearsoll Peak Lookout", region="OR", tower="us-or-pearsoll-peak", pos="nhlr:US 51",
         find=["Pearsoll"], forest=f"{RRSNF} (Wild Rivers Ranger District)", agency="U.S. Forest Service", ownership="federal",
         design="L-4 with outriggers", status="standing",
         events=[
             E(1954, "replaced", "The present L-4 replaced an earlier cupola-style lookout, built from a kit.", "pears"),
             E(1991, "restored", "SMS and district staff re-framed the west and south walls, rebuilt their shutters and put on a new roof.", "pears"),
             E(2001, "restored", "Rotted outriggers replaced over the summer, roofing and lower sheathing taken off to do it; attic insulation removed.", "pears"),
             E(2002, "fire", "Freshly repaired and painted, it survived the Biscuit Fire although trees within 50 ft burned.", "pears"),
             E(2008, "modified", "North deck, which failed over the winter, was taken apart for safety and documented for reuse.", "pears"),
             E(2011, "restored", "West wall re-framed after wind tore out a window sill; original floor lifted and stripped over the winter.", "pears"),
             E(2012, "restored", "Original fir floor relaid the right way round and varnished clear as in 1954.", "pears"),
         ]),
    dict(slug="pechuck-mountain", name="Pechuck Lookout", region="OR", tower="us-or-pechuck-mountain", pos="nhlr:US 2",
         find=["Pechuck", "Pechuk"], forest="Table Rock Wilderness area", agency="Bureau of Land Management", ownership="federal",
         design="Stone base with a wood-frame cupola on top", aliases=["Pechuk Lookout"], status="standing",
         events=[
             E(1932, "built", "Built as a state forestry lookout: locally quarried stone base with a wooden cupola.", "pechuk"),
             E(1963, "staffed_last", "Last year it was staffed, under the Oregon Department of Forestry.", "pechuk"),
             E(1991, "restored", "SMS helped local volunteers re-roof it to start its restoration, which the Friends of Pechuck took over.", "pechuk"),
         ]),
    dict(slug="sand-mountain", name="Sand Mountain Lookout", region="OR", tower="us-or-sand-mountain", pos="nhlr:US 1",
         find=["Sand Mountain"], forest=f"{WNF} (McKenzie River Ranger District)", agency="U.S. Forest Service", ownership="federal",
         design="Grange-hall style L-4 cab", staffing="staffed", status="standing",
         events=[
             E(1933, "built", "A grange-hall style L-4 cab went up on the south peak after a road reached the saddle.", "sand"),
             E(1967, "fire", "Survived the Big Lake Airstrip Fire, which swept over the summit.", "sand"),
             E(1968, "burned", "Burned down accidentally the next season while the lookout was away; a trailer with a pop-up cupola stood in for two years.", "sand", inferred="the page says the season after the 1967 fire"),
             E(1989, "rebuilt", "SMS moved the abandoned Whisky Peak lookout here and rebuilt it, with materials from several forests; dedicated in 1990.", "sand"),
         ]),
    dict(slug="watchman", name="The Watchman Lookout", region="OR", tower="us-or-watchman", pos="nhlr:US 401",
         find=["Watchman"], forest="Crater Lake National Park", agency="National Park Service", ownership="federal",
         design="Park Service design with a stone base", aliases=["Watchman Lookout"], status="standing",
         events=[
             E(1932, "built", "Park Service lookout with a stone base on the west rim of Crater Lake.", "watch"),
             E(2010, "restored", "SMS volunteers carried in new plate glass, restored the cracked windows and milled a replica ceiling to replace plywood.", "watch"),
         ]),
    dict(slug="mount-scott", name="Mount Scott Lookout", region="OR", tower="us-or-mount-scott", pos="nhlr:US 402",
         find=["Mt. Scott", "Mount Scott", "Mt Scott"], forest="Crater Lake National Park", agency="National Park Service",
         ownership="federal", status="standing",
         events=[
             E(2010, "assessed", "SMS visited with the Park historian to assess the building; no time was left for work.", "watch"),
         ]),
    dict(slug="wildhorse-mountain", name="Wildhorse Lookout", region="OR", tower="us-or-wildhorse-mountain", pos="nhlr:US 509",
         find=["Wildhorse"], forest=f"{RRSNF} (Gold Beach Ranger District)", agency="U.S. Forest Service", ownership="federal",
         design="Hip-roofed L-4 with outriggers on a 40-ft tower", height_ft=40,
         events=[
             E(1942, "staffed", "The original structure served as a wartime Aircraft Warning Service post, watched around the clock that winter.", "wild"),
             E(1947, "replaced", "Present tower and cabin built after snow crushed the first lookout in 1946-47.", "wild"),
             E(2008, "other", "Cab collapsed under heavy snow over the winter and hung off the tower; SMS salvaged its parts and helped clean up.", "wild"),
             E(2009, "restored", "Tower parts damaged in the collapse were refurbished by contractors, with SMS help.", "wild"),
             E(2014, "modified", "Footing dug and set for a replica outhouse beside the lookout.", "wild"),
         ]),
    dict(slug="whisky-peak", name="Whisky Peak Lookout", region="OR", tower="us-or-whiskey-peak", pos="fflos:US 935",
         find=["Whisky Peak"], forest="Rogue River National Forest", agency="U.S. Forest Service", ownership="federal",
         aliases=["Whiskey Peak Lookout"], status="gone", moved_to="Sand Mountain Lookout (Willamette National Forest)",
         events=[
             E(1989, "relocated", "The long-abandoned grange-hall style L-4 cabin was taken apart and flown out to be rebuilt as the Sand Mountain Lookout.", "sand", "pears"),
         ]),
]

if __name__ == "__main__":
    run(__doc__, SOURCE, ASSOCIATION, DOCS, LOOKOUTS, credit=CREDIT, license_=LICENSE)
