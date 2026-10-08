"""Friends of St. Regis Mountain Fire Tower: the restoration log of the St. Regis Mountain tower.

  http://www.friendsofstregis.org/   (a volunteer 501(c)(3) working with NYS DEC since 2015)

The Friends restore the 1918 Aermotor tower on St. Regis Mountain (Franklin County, NY) with the
state's Department of Environmental Conservation and keep a dated work log on one page,
/restoration/ (WordPress; a heading per year, newest first, 2015 to 2026). This source turns that
log into events on the tower's timeline: the 2015 rebuild of the stairs, the 2016 new roof and
reopening, the 2018-19 replacement of all 24 diagonal braces, the repainting, the view panels
and the safety-fence replacement still under way in 2026.

What is read (2026-10-08): the /restoration/ page; robots.txt only disallows /wp-admin/. Not read:
the news, newsletters and annual reports (PDFs on the news page), the observers' histories and
the nature pages, which are people and wildlife rather than work on the structure.

The log is prose, so the facts are curated by hand below (our own words, each citing a year of
the log by its #anchor) and this script checks them against the page text. The Friends publish no
coordinates: the position is copied from the NHLR record (extra.position_from).

Licence: none stated; facts only (dates, names, the kind of work done), notes are ours.

Output: data/sources/st_regis_friends.json
Re-run: python3 pipeline/regional/st_regis_friends.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_east import E, doc, run  # noqa: E402

SOURCE = "st_regis_friends"
BASE = "http://www.friendsofstregis.org"
ASSOCIATION = {"name": "Friends of St. Regis Mountain Fire Tower", "url": f"{BASE}/"}
CREDIT = "Friends of St. Regis Mountain Fire Tower (friendsofstregis.org)"
LICENSE = (
    "No licence stated; facts only (dates, names, the kind of work done). Every note is our own wording "
    "and every event links to the year of the Friends' restoration log it comes from. The position is "
    "copied from the NHLR record (the Friends publish none)."
)

LOG = f"{BASE}/restoration/"


def _year(y: int) -> dict:
    # Every year is a section of the one /restoration/ page (one cached copy); the link goes to its anchor.
    return doc(f"r{y}", LOG, f"Friends of St. Regis restoration log, {y}", y, page=f"{LOG}#{y}", cache="restoration.html")


DOCS = [_year(y) for y in range(2026, 2014, -1)]

LOOKOUTS: list[dict] = [
    dict(slug="st-regis-mountain", name="St. Regis Mountain Fire Tower", tower="us-ny-st-regis-mountain",
         pos="nhlr:US 117", find=["St. Regis", "St Regis"], status="standing", agency="NYS DEC", ownership="state", staffing="volunteer",
         page=LOG,
         events=[
             E(2014, "other", "The state's final unit management plan for the fire tower area was issued on 7 November, which allowed the tower to be restored.", "r2015"),
             E(2015, "restored", "Restoration began: DEC flew in lumber and steel, then a Student Conservation Association crew and Friends volunteers rebuilt the stairs, rails, landings and cab floor in late September.", "r2015", "r2016"),
             E(2016, "restored", "A new roof was flown in by state police helicopter (21 July) and fitted in July; the cab was repainted, window frames and a cab safety rail added, and the tower reopened on 1 September.", "r2016"),
             E(2018, "restored", "Replacement of the 24 diagonal braces began: the new galvanized steel braces were flown to the summit on 31 October and the first set fitted on 4 November before weather stopped work.", "r2018"),
             E(2019, "restored", "All the cross braces were replaced by 12 May; stairs and landings were then primed and the footings repaired through October.", "r2019"),
             E(2020, "restored", "After the spring COVID closure, volunteers galvanized the drilled window frames and primed the cab floor and the metal under the treated boards (August and September).", "r2020"),
             E(2021, "modified", "Labeled panoramic photo panels for the east and south views were installed in the cab on 2 September.", "r2021"),
             E(2021, "restored", "Volunteers began repainting the tower's stringers and railings through the summer.", "r2021"),
             E(2022, "restored", "The repainting begun in 2021 was carried on and was nearly complete by the end of the season.", "r2022"),
             E(2024, "modified", "A west-view panel went up on 27 August and a north-view panel on 18 September, the third and fourth cab panels.", "r2024"),
             E(2024, "restored", "Replacement of the stair and landing safety fencing began on 15 June.", "r2024"),
             E(2025, "restored", "Fence replacement continued: in September most of the new fence sections were cut for fitting in 2026.", "r2025"),
             E(2026, "restored", "New safety fence was fitted: all stair flights were done by mid-September and the landings were under way.", "r2026"),
         ]),
]


def main() -> None:
    run(source=SOURCE, association=ASSOCIATION, credit=CREDIT, license_=LICENSE, region="NY", specs=DOCS,
        lookouts=LOOKOUTS, description=__doc__.split("\n")[0])


if __name__ == "__main__":
    main()
