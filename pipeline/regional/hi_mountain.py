"""Hi Mountain Lookout Project (California): the lookout restored as a biological field station.

  https://www.condorlookout.org/   (a project of the Morro Coast Audubon Society with the Forest
                                    Service; an FFLA affiliate)

Hi Mountain Lookout, in the Los Padres National Forest above San Luis Obispo County, was restored
from the late 1990s as a condor and peregrine falcon monitoring station and education centre.
The project's history page gives the lookout's dates. This source turns that page into dated
events on the lookout's timeline, linked to the page. Built on the shared association-project
shape (_projects.py, DESIGN.md 3.7) and the driver in _assoc_site.py.

What is read (2026-10-08; robots.txt allows everything but a gallery lightbox): /project-history.
The other pages are volunteer, internship and research information.

Licence: no licence stated. Dates and the kind of work done are facts; the notes are ours; the
events link to the project's page.

Output: data/sources/hi_mountain.json
Re-run: python3 pipeline/regional/hi_mountain.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_site import E, doc, run  # noqa: E402

SOURCE = "hi_mountain"
ASSOCIATION = {"name": "Hi Mountain Lookout Project", "url": "https://www.condorlookout.org/"}
CREDIT = "Hi Mountain Lookout Project (condorlookout.org)"
LICENSE = (
    "No licence stated; facts only (dates, the kind of work done). Every note is our own wording "
    "and the events link to the project's page. The position is copied from the NHLR record."
)
DOCS = [doc("history", "https://www.condorlookout.org/project-history", "Project history (Hi Mountain Lookout Project)")]

LOOKOUTS = [
    dict(slug="hi-mountain", name="Hi Mountain Lookout", region="CA", tower="us-ca-hi-mountain", pos="nhlr:US 522", find=["Hi Mountain"],
         forest="Los Padres National Forest", agency="U.S. Forest Service", ownership="federal", status="standing",
         events=[
             E(1926, "built", "First lookout built and put in service by the Forest Service.", "history"),
             E(1961, "replaced", "The original lookout was replaced and improved.", "history"),
             E(1996, "restored", "Morro Coast Audubon and the Forest Service began restoring it as a biological field station and education centre, after some 15 years of neglect and vandalism.", "history"),
         ]),
]

if __name__ == "__main__":
    run(__doc__, SOURCE, ASSOCIATION, DOCS, LOOKOUTS, credit=CREDIT, license_=LICENSE)
