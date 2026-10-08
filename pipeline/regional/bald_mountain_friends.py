"""Friends of Bald (Rondaxe) Mountain: the restoration reports for the Bald Mountain tower, 2003-2023.

  https://www.masterpieces.com/bald.htm   (FoBM, volunteers working with NYS DEC out of Old Forge)

FoBM restored the 1917 steel tower on Bald (Rondaxe) Mountain (Webb, Herkimer County, NY), shut since
1990, in 2003-05 with DEC (helicopter supply drop, new steps, platforms, windows, fencing, dedication on
18 June 2005) and has kept it up since. Their hand-made site (masterpieces.com, no robots.txt) has a
"progress report" page for most seasons.

What is read (2026-10-08): the project index page, the 2003, 2004 (June, August, helicopter drop, work
weekend, reopening, November), 2005 (dedication), 2006, 2007, 2008 and 2009 reports and the 2022-2023 notes.
Not read: the 2010-2021 report pages the index lists, which return "not found" on the server (their links
are broken), the donor, mailbag, patch, vintage-photo, observer-story and book pages.

Prose, curated by hand in our own words and checked against the pages' text. No coordinates: the position
is copied from the NHLR record.

Licence: none stated; facts only, notes are ours.

Output: data/sources/bald_mountain_friends.json
Re-run: python3 pipeline/regional/bald_mountain_friends.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_east import E, doc, run  # noqa: E402

SOURCE = "bald_mountain_friends"
BASE = "http://www.masterpieces.com"
ASSOCIATION = {"name": "Friends of Bald (Rondaxe) Mountain", "url": f"{BASE}/bald.htm"}
CREDIT = "Friends of Bald (Rondaxe) Mountain (masterpieces.com/bald.htm)"
LICENSE = (
    "No licence stated; facts only (dates, names, the kind of work done). Every note is our own wording and "
    "every event links to the FoBM page it comes from. The position is copied from the NHLR record (FoBM "
    "publishes none)."
)

DOCS = [
    doc("index", "https://www.masterpieces.com/bald.htm", "FoBM: Bald (Rondaxe) Mountain Preservation Project", None, cache="index.html"),
    doc("r2003", f"{BASE}/bald2.htm", "FoBM: 2003 progress report", 2003, cache="r2003.html"),
    doc("r2004s", f"{BASE}/bald2004.htm", "FoBM: summer 2004 projects", 2004, cache="r2004s.html"),
    doc("r2004jun", f"{BASE}/bald13a.htm", "FoBM: June 2004 progress report", 2004, cache="r2004jun.html"),
    doc("r2004aug", f"{BASE}/bald13.htm", "FoBM: August 2004 progress report", 2004, cache="r2004aug.html"),
    doc("r2004heli", f"{BASE}/bald12.htm", "FoBM: helicopter supply drop, September 2004", 2004, cache="r2004heli.html"),
    doc("r2004reopen", f"{BASE}/bald14.htm", "FoBM: tower reopens, 18 September 2004", 2004, cache="r2004reopen.html"),
    doc("r2004nov", f"{BASE}/bald17.htm", "FoBM: November 2004 projects", 2004, cache="r2004nov.html"),
    doc("r2005", f"{BASE}/bald18.htm", "FoBM: dedication ceremony, 18 June 2005", 2005, cache="r2005.html"),
    doc("r2006", f"{BASE}/bald9a.htm", "FoBM: 2006 progress report", 2006, cache="r2006.html"),
    doc("r2007", f"{BASE}/bald9x.htm", "FoBM: 2007 progress report", 2007, cache="r2007.html"),
    doc("r2009", f"{BASE}/bald9z.htm", "FoBM: 2009 progress report", 2009, cache="r2009.html"),
    doc("r2023", "https://www.masterpieces.com/2022-2023%20FoBM.htm", "FoBM: notes from 2022-2023", 2023, cache="r2023.html"),
]

LOOKOUTS: list[dict] = [
    dict(region="NY", slug="rondaxe-bald-mountain", name="Bald (Rondaxe) Mountain Fire Tower", tower="us-ny-rondaxe-bald-mountain",
         pos="nhlr:US 112", find=["Bald"], status="standing", agency="NYS DEC", ownership="state", staffing="volunteer",
         url=f"{BASE}/bald.htm",
         events=[
             E(1990, "closed", "DEC officially closed the tower and padlocked the cab; it deteriorated for about 13 years.", "index", "r2004reopen"),
             E(2003, "restored", "Volunteers scraped rust, removed worn fencing and the lower steps, painted the tower in July and August, and on 20 September began fitting new treated steps.", "r2003"),
             E(2004, "restored", "A helicopter flew in materials on 15 September; volunteers replaced the platforms, poured a new footer, fitted new steel window frames, repainted, reinstalled the stairs and laid a new cab floor.", "r2004s", "r2004heli", "r2004reopen"),
             E(2004, "modified", "Security fencing went in along the stairs and platforms, and a steel safety railing inside the cab in November, the season's last big job.", "r2004reopen", "r2004nov"),
             E(2005, "other", "The restored tower was formally reopened at a dedication with a ribbon cutting on 18 June; a new map table with an alidade was in the cab.", "r2005"),
             E(2006, "modified", "A new all-weather composite map table was installed in the cab on work days in late June and early July.", "r2006"),
             E(2007, "restored", "A volunteer re-stained all the tower's steps, cab floor and landings.", "r2007"),
             E(2009, "restored", "Volunteers re-stained the wooden steps, landings and other wood parts at a September work weekend, and hung a new swing safety door at the cab entrance.", "r2009"),
             E(2023, "modified", "A new safety door into the cab went in during July, and a new map table recreated from the original design in late summer.", "r2023"),
             E(2023, "restored", "A DEC crew from Boonville repaired the worn tower steps, some missing bolts, in November.", "r2023"),
         ]),
]


def main() -> None:
    run(__doc__, SOURCE, ASSOCIATION, DOCS, LOOKOUTS, credit=CREDIT, license_=LICENSE, folded=True)


if __name__ == "__main__":
    main()
