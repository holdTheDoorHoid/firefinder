"""HistoriCorps (national): its volunteer projects on western fire lookouts.

  https://historicorps.org/   (a non-profit whose volunteer crews do traditional preservation work
                               on historic buildings for the Forest Service and other agencies)

HistoriCorps runs week-long volunteer sessions on historic structures, and a handful of its
project pages are lookouts. Each page gives the building's history, the sessions and the scope of
work. This source turns the four western lookout project pages into dated events on those
lookouts' timelines, each linked to its page. The pages are announcements, so a project event
says "sessions scheduled" and describes the planned scope; it does not claim the work was
finished. Built on the shared association-project shape (_projects.py, DESIGN.md 3.7) and the
driver in _assoc_site.py.

What is read (2026-10-08; robots.txt allows everything): the lookout project pages found in the
site's project sitemap: Alder Ridge (CA, 2024), Bunker Hill (CA, 2024), Cement Ridge (WY, 2026)
and Thorp Mountain (WA, 2026). A fifth, Grandview (AZ, 2024), is the lookout's ground cabin, not
the tower, and is left out. The sitemap shows no eastern lookout projects.

Licence: no licence stated. Dates and the kind of work done are facts; the notes are ours; each
event links to the HistoriCorps page.

Output: data/sources/historicorps_west.json
Re-run: python3 pipeline/regional/historicorps_west.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_site import E, doc, run  # noqa: E402

SOURCE = "historicorps_west"
BASE = "https://historicorps.org"
ASSOCIATION = {"name": "HistoriCorps", "url": f"{BASE}/"}
CREDIT = "HistoriCorps (historicorps.org)"
LICENSE = (
    "No licence stated; facts only (dates, the kind of work planned). Every note is our own wording "
    "and every event links to the HistoriCorps page it comes from. Positions are copied from the NHLR "
    "records."
)
DOCS = [
    doc("alder", f"{BASE}/alder-ridge-lookout-cabin-ca-2024/", "Alder Ridge Lookout Cabin, CA 2024", 2024),
    doc("bunker", f"{BASE}/bunker-hill-lookout-tower-ca-2024/", "Bunker Hill Lookout, CA 2024", 2024),
    doc("cement", f"{BASE}/cement-ridge-fire-lookout-wy-2026/", "Cement Ridge Fire Lookout, WY 2026", 2026),
    doc("thorp", f"{BASE}/hardcorps-thorp-mountain-lookout-wa-2026/", "HardCorps: Thorp Mountain Lookout, WA 2026", 2026),
]

LOOKOUTS = [
    dict(slug="alder-ridge", name="Alder Ridge Lookout", region="CA", tower="us-ca-alder-ridge", pos="nhlr:US 592", find=["Alder Ridge"],
         forest="Eldorado National Forest", agency="U.S. Forest Service", ownership="federal", status="standing",
         design="60-ft observation tower with a ranger cabin and garage",
         events=[
             E(1937, "built", "Built by the Placerville Ranger District with the Civilian Conservation Corps: a 60-ft tower, ranger cabin and garage.", "alder"),
             E(2023, "restored", "HistoriCorps volunteers worked on restoring the ranger cabin.", "alder", inferred="the 2024 page says 'last season'"),
             E(2024, "restored", "HistoriCorps scheduled three volunteer sessions (June 16 to July 5) to finish the cabin's windows, interior finishes, exterior paint and floor boards.", "alder"),
         ]),
    dict(slug="bunker-hill", name="Bunker Hill Lookout", region="CA", tower="us-ca-bunker-hill", pos="nhlr:US 593", find=["Bunker Hill"],
         forest="Eldorado National Forest (Pacific Ranger District)", agency="U.S. Forest Service", ownership="federal", status="standing",
         design="20-ft stone live-in tower topped with a 14x14-ft wooden cab (Kepler Johnson design)",
         events=[
             E(1939, "built", "Designed by Region 5 architect Kepler Johnson; construction began with the Civilian Conservation Corps, the stone base finishing by 1942.", "bunker"),
             E(1949, "modified", "The wooden observation cab was added on top of the stone tower.", "bunker"),
             E(2024, "restored", "HistoriCorps scheduled volunteer sessions (July 14 to September 6) to repair the roof, take down the brick chimney and prepare for repointing and painting.", "bunker"),
         ]),
    dict(slug="cement-ridge", name="Cement Ridge Lookout", region="WY", tower="us-wy-cement-ridge", pos="nhlr:US 74", find=["Cement Ridge"],
         forest="Black Hills National Forest", agency="U.S. Forest Service", ownership="federal", status="standing",
         design="CCC stone base about 15 ft tall with a 14x14-ft wood cab",
         events=[
             E(1913, "built", "A log cabin lookout built between 1911 and 1913; a glassed-in crow's nest followed in 1921.", "cement"),
             E(1941, "replaced", "The present CCC stone-and-wood lookout was built between 1940 and 1941.", "cement"),
             E(1974, "restored", "Cab siding, catwalk planks, steps and wall studs replaced; interior repainted and siding restained.", "cement"),
             E(2026, "restored", "HistoriCorps scheduled a volunteer session (August 9 to 14) to repair the garage door and entrance door in kind.", "cement"),
         ]),
    dict(slug="thorp-mountain", name="Thorp Mountain Lookout", region="WA", tower="us-wa-thorp-mountain", pos="nhlr:US 389", find=["Thorp Mountain"],
         forest="Okanogan-Wenatchee National Forest", agency="U.S. Forest Service", ownership="federal", status="standing",
         design="14x14-ft gable-roof L-4 ground house",
         events=[
             E(1930, "built", "Built as a gable-roofed L-4 cab, one of the last such left in the Northwest.", "thorp"),
             E(2026, "restored", "HistoriCorps scheduled two volunteer sessions in September, hiking in, to rebuild the shutters in kind and repair the catwalk, door and paint.", "thorp"),
         ]),
]

if __name__ == "__main__":
    run(__doc__, SOURCE, ASSOCIATION, DOCS, LOOKOUTS, credit=CREDIT, license_=LICENSE)
