"""New York State Chapter of the Forest Fire Lookout Association: its monthly newsletters, 2016-2026.

  https://www.nysffla.org/   (the New York chapter of the FFLA)

The chapter looks after a dozen fire towers itself (Berry Hill, Snowy, Wakely, Kane, Lyon, Stillwater,
Pillsbury, Blue, Owls Head...), runs volunteer work weekends with Team Rubicon, NYSDEC and the "Friends of"
groups, and reports on every tower in the state each month. Its newsletter has an "Updates" column with a
paragraph per tower (closures, repairs, painting, new roofs, rebuilds, moves), project reports, and
history features. This source turns them into dated events on the towers' timelines.

What is read (2026-10-08; nysffla.org has no robots.txt): the chapter's projects page (/projects.html, a
list of 18 work weekends 2017-2025; its photo pages carry no text), and the monthly newsletter PDFs from
the newsletter pages (/Newsletters/News<year>.html): 121 issues, January 2016 to July 2026. Not read: the
history pages (observer history, "Historian's Corner") and the alphalist page, which is a tower list.

The newsletters are prose, so the facts are curated in nysffla_projects_data.py (our own words, each citing
its issues) and this script checks every citation against the issue's text. The chapter publishes no
coordinates: each position is copied from the NHLR (or FFLA, for relocated towers) record of the tower the
lookout joins (extra.position_from, extra.tower_hint). Facts about towers outside New York are not included.

Licence: no licence stated; facts only (dates, names, the kind of work done), notes are ours, each event
links to the issue it comes from.

Output: data/sources/nysffla_projects.json
Re-run: python3 pipeline/regional/nysffla_projects.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_east import run  # noqa: E402
import nysffla_projects_data as D  # noqa: E402


SOURCE = "nysffla_projects"
ASSOCIATION = {"name": "Forest Fire Lookout Association, New York State Chapter", "url": f"{D.BASE}/"}
CREDIT = "Forest Fire Lookout Association, New York State Chapter (nysffla.org)"
LICENSE = (
    "No licence stated; facts only (dates, names, the kind of work done). Every note is our own wording and "
    "every event links to the chapter newsletter it comes from. Positions are copied from the NHLR and FFLA "
    "records (the chapter publishes none)."
)


def main() -> None:
    run(__doc__, SOURCE, ASSOCIATION, D.DOCS, D.LOOKOUTS, credit=CREDIT, license_=LICENSE, folded=True)


if __name__ == "__main__":
    main()
