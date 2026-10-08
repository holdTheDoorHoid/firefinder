"""Friends of Mount Arab: the yearly newsletters, 2006-2025, and the history of the Mount Arab tower.

  https://friendsofmtarab.org/   (FOMA, a volunteer 501(c)(3) working with NYS DEC since 1997)

FOMA restores and looks after the 1918 fire tower and observer's cabin on Mount Arab (Piercefield, St.
Lawrence County, NY). It publishes one newsletter a year (PDF), each with a project report; the home page
has a short history. This source turns them into dated events: replacing the tower's wooden steps and
landings (2006), the safety mesh, map table and horizon displays, new anchor bolts and footers (2015), new
cab windows (2020), the cabin's roof, windows, shutters and floor.

What is read (2026-10-08): the newsletters for 2006-2009 and 2011-2025 and /FOMA-5-history.htm.
robots.txt asks for a 10 second crawl delay on every request, so this module waits 10 s between requests
(CRAWL_DELAY below). Not read: the 2010 newsletter (an image-only PDF, no text layer; there is
no OCR here), and the 2013 and 2016 issues, whose text layer lost the body letters in conversion, so only
their headings read; the stewards page.

The newsletters are prose, so the facts are curated in our own words and every citation is checked
against the issue's text. FOMA publishes no coordinates: the position is copied from the NHLR record.

Licence: none stated; facts only (dates, names, the kind of work done), notes are ours.

Output: data/sources/mt_arab_friends.json
Re-run: python3 pipeline/regional/mt_arab_friends.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import _common  # noqa: E402
from _assoc_east import E, doc, run  # noqa: E402

CRAWL_DELAY = 10.0   # robots.txt: Crawl-delay: 10

SOURCE = "mt_arab_friends"
BASE = "https://friendsofmtarab.org"
ASSOCIATION = {"name": "Friends of Mount Arab", "url": f"{BASE}/"}
CREDIT = "Friends of Mount Arab (friendsofmtarab.org)"
LICENSE = (
    "No licence stated; facts only (dates, names, the kind of work done). Every note is our own wording and "
    "every event links to the FOMA newsletter or page it comes from. The position is copied from the NHLR "
    "record (FOMA publishes none)."
)

# 2010 (image-only PDF), 2013 and 2016 (garbled text layer) are not usable; see the docstring.
YEARS = [y for y in range(2025, 2005, -1) if y not in (2010, 2013, 2016)]
DOCS = [doc(f"n{y}", f"{BASE}/FOMAnewsletter{y}.pdf", f"FOMA newsletter {y}", y, cache=f"pdf/{y}.pdf") for y in YEARS]
DOCS.append(doc("history", f"{BASE}/FOMA-5-history.htm", "FOMA: History of Mount Arab", None, cache="history.html"))

LOOKOUTS: list[dict] = [
    dict(region="NY", slug="mount-arab", name="Mount Arab Fire Tower", tower="us-ny-mount-arab", pos="nhlr:US 108",
         find=["Arab"], status="standing", agency="NYS DEC", ownership="state", staffing="volunteer",
         url=f"{BASE}/FOMA-4-newsletters.htm",
         events=[
             E(1918, "built", "The steel tower went up on the summit and the first observer's cabin was built the same year; before that observers lived in tents.", "n2018", "history"),
             E(1997, "other", "On Earth Day citizens and DEC officials met on the summit and resolved to restore the tower and cabin; FOMA was then incorporated as DEC's partner.", "n2011"),
             E(2006, "restored", "The last wooden steps and landings were replaced in September, completing replacement of the tower's wooden parts, and the wire safety screen was partly repaired.", "n2006"),
             E(2008, "restored", "Volunteers repaired the leaking roof of the observer's cabin in September.", "n2008"),
             E(2009, "modified", "New plastic-coated steel mesh replaced the old wire mesh along the stairs and landings, and a new alidade and map table were installed in the cab.", "n2009"),
             E(2009, "restored", "Sparks Masonry repaired the observer's cabin chimney, its door and a window broken by vandals.", "n2009"),
             E(2011, "modified", "Horizon display panels naming distant landmarks were mounted above the tower cab windows.", "n2011"),
             E(2011, "restored", "After an October break-in volunteers repaired the observer's cabin windows, stove and lock.", "n2011"),
             E(2012, "modified", "Six lockable wooden shutters were fitted over the observer's cabin windows.", "n2012"),
             E(2015, "restored", "David Vana replaced the corroded tower anchor bolts and footers in September with stainless bolts set in bedrock and new concrete (about $18,000); a rotted cabin window was also replaced.", "n2015"),
             E(2018, "restored", "A new laminate floor was laid in the observer's cabin, which serves as the summit museum.", "n2018"),
             E(2020, "restored", "A Student Conservation Association crew painted the tower (31 August-3 September) and volunteers fitted new aluminum cab windows, finished 4 October.", "n2020", "n2021"),
             E(2021, "restored", "Volunteers repaired the observer's cabin porch rails, siding and a gutter and painted the whole tower cab interior; self-latching catches were added to the new cab windows.", "n2021"),
             E(2022, "restored", "A cracked part of the tower roof was patched and some new bolts were fitted.", "n2022"),
             E(2022, "modified", "The horizon display panels above the cab windows were taken down and stored after vandalism and cracked plexiglass covers.", "n2022"),
             E(2023, "modified", "Horizon displays were re-mounted on aluminum frames over the cab windows because the wooden backing was failing.", "n2023"),
             E(2024, "restored", "Two cracked Plexiglas cab windows were replaced in spring, the horizon-display bolts above the roof sealed and the cabin's porch rails stained.", "n2024"),
         ]),
]


def main() -> None:
    _common.MIN_INTERVAL_S = CRAWL_DELAY   # robots.txt asks for it
    run(__doc__, SOURCE, ASSOCIATION, DOCS, LOOKOUTS, credit=CREDIT, license_=LICENSE, folded=True)


if __name__ == "__main__":
    main()
