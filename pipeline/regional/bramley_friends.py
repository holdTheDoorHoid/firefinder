"""Friends of Bramley Mountain Fire Tower: the project that rebuilt the Bramley Mountain tower, 2016-2025.

  https://bramleymountainfiretower.org/   (formed in 2020 by the Catskill Mountain Club)

DEC built an 80-foot Aermotor LS40 on Bramley Mountain (Delhi, Delaware County, NY) in 1950 and closed it in
1970; a Delhi farmer bought the tower for $50 in 1975, took it down and kept the parts. The Catskill Mountain
Club's loop trail (2016) led the family to offer the tower back, and the Friends, with Delaware County and the
NYC Department of Environmental Protection, rebuilt it on the summit in 2024; it opened on 4 January 2025.

What is read (2026-10-08, robots.txt only disallows /wp-admin/): the tower history page, the project
posts for the groundbreaking (August 2024), completion (November 2024) and first season (November 2025), the
Delaware County post (August 2023) and the About page. Not read: fundraising, merchandise and steward pages.

Prose, curated by hand in our own words and checked against the pages' text. No coordinates: the position
is copied from the NHLR record.

Licence: none stated; facts only, notes are ours.

Output: data/sources/bramley_friends.json
Re-run: python3 pipeline/regional/bramley_friends.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_east import E, doc, run  # noqa: E402

SOURCE = "bramley_friends"
BASE = "https://bramleymountainfiretower.org"
ASSOCIATION = {"name": "Friends of Bramley Mountain Fire Tower", "url": f"{BASE}/"}
CREDIT = "Friends of Bramley Mountain Fire Tower (bramleymountainfiretower.org)"
LICENSE = (
    "No licence stated; facts only (dates, names, the kind of work done). Every note is our own wording and "
    "every event links to the Friends' page it comes from. The position is copied from the NHLR record (the "
    "Friends publish none)."
)

DOCS = [
    doc("history", f"{BASE}/bramleys-towers-history/", "Friends of Bramley Mountain: tower history", 2025, cache="history.html"),
    doc("ground", f"{BASE}/ground-broken-for-the-restored-fire-tower/", "Ground broken for the restored fire tower", 2024, cache="ground.html"),
    doc("completed", f"{BASE}/construction-completed-not-yet-open-to-the-public/", "Construction completed, not yet open", 2024, cache="completed.html"),
    doc("season", f"{BASE}/great-first-season/", "Great first season", 2025, cache="season.html"),
    doc("county", f"{BASE}/we-are-excited-to-report-that-delaware-county-officials-have-been-working-to-help-the-bramley-mountain-fire-tower-project-move-forward/",
        "Delaware County officials help move the project forward", 2023, cache="county.html"),
    doc("about", f"{BASE}/about/", "About the Friends of Bramley Mountain Fire Tower", None, cache="about.html"),
]

LOOKOUTS: list[dict] = [
    dict(region="NY", slug="bramley-mountain", name="Bramley Mountain Fire Tower", tower="us-ny-bramley-mountain", pos="nhlr:US 1808",
         find=["Bramley"], status="standing", agency="NYC Department of Environmental Protection", ownership="local", staffing="volunteer",
         url=f"{BASE}/bramleys-towers-history/",
         events=[
             E(1950, "built", "DEC erected the 80-foot Aermotor LS40 steel tower on the summit, with a three-room observer's cabin.", "history"),
             E(1970, "closed", "DEC closed the tower as aerial surveillance replaced observers.", "history"),
             E(1975, "removed", "DEC offered the tower for sale with the buyer to remove it; a Delhi dairy farmer paid $50 and the family took it down, marking the parts, and stored it.", "history", "about"),
             E(2023, "other", "Delaware County officials agreed to partner with the Friends and take the lead as permit holder, reviving the stalled rebuilding project.", "county"),
             E(2024, "rebuilt", "The stored tower was rebuilt on its original summit: footers were dug from August and construction was completed on 19 November.", "ground", "completed", "history"),
             E(2025, "other", "A Certificate of Completion was issued in early January and the rebuilt tower had its first public opening on 4 January.", "completed", "season"),
         ]),
]


def main() -> None:
    run(__doc__, SOURCE, ASSOCIATION, DOCS, LOOKOUTS, credit=CREDIT, license_=LICENSE, folded=True)


if __name__ == "__main__":
    main()
