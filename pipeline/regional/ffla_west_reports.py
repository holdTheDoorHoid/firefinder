"""Forest Fire Lookout Association chapter reports, West and the Rockies: what the chapters did to which lookouts, year by year.

  https://firelookout.org/about-us/current-reports/   (latest year)
  https://firelookout.org/resources/archives/annual-reports/<year>-reports/   (2003 to 2024)

Every active FFLA chapter files a yearly report: members and money, then the "projects and
activities" that matter here: which lookouts were repaired, repainted, reroofed, assessed, lost to
fire, put back in service. The national Restoration Grants report adds each grant awarded, to which
lookout and for what. For the 14 western states (AK, AZ, CA, CO, HI, ID, MT, NV, NM, OR, UT, WA, WY and
the Black Hills of SD) the archive holds about 210 readable PDFs from 2003 to 2025, from the Arizona,
California (North, Pacific, Central/Nevada, Sierra/Nevada, South and its local groups), Colorado-Utah,
Idaho, New Mexico, Oregon, Washington and Wyoming chapters, plus the Western Deputy and Northwestern
Region reports and the Restoration Grants reports. (The Northwest Montana Lookout Association has its
own source, nwmt_projects.) This source turns what those reports say into dated events on the lookouts'
timelines, each linked to the PDF that gives it. Built on the shared association-project shape
(_projects.py, DESIGN.md 3.7) and the driver in _assoc_site.py.

How it was made: the reports are prose, so they were read by agents (one batch per chapter family) who wrote
each dated fact once as a record with the lookout's name, forest, year, event and a short note in our own
words, plus a short verbatim run of the report's text as evidence. A script then checked every record against
the PDF's text (the lookout's name, the year, the evidence), dropped what was uncertain, trivial or only a
nomination or a funding amount, and matched each lookout to one of our towers by state, name and forest
(ambiguous ones by hand); positions are copied from that tower's register record. The result is the curated
data in ffla_west_reports_data.py, which this script re-checks against the cached PDFs on every run.

What is read (2026-10-08; robots.txt disallows only /wp-admin/ and shop paths): the PDFs listed in
ffla_west_reports_data.REPORTS. Not readable: image-only scans (California Sierra-Nevada 2016 to 2019, Arizona-New
Mexico 2004, Oregon 2004) are not text-checked; their few facts are marked in the data. The FFLA Facebook groups and
the east's reports are out of scope.

PDF text from these files loses the letters of "ti", "tt", "ft" and "fi" ("Kelly Bu e"), so names are compared in a
folded form (_assoc_site.fold).

Licence: no licence stated. Dates, names and the kind of work done are facts; the notes are ours; each event links to
the PDF it comes from.

Output: data/sources/ffla_west_reports.json
Re-run: python3 pipeline/regional/ffla_west_reports.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_site import doc, run  # noqa: E402
import ffla_west_reports_data as D  # noqa: E402

SOURCE = "ffla_west_reports"
ASSOCIATION = {"name": "Forest Fire Lookout Association chapter reports", "url": "https://firelookout.org/about-us/current-reports/"}
CREDIT = "Forest Fire Lookout Association, chapter and restoration-grant reports (firelookout.org)"
LICENSE = (
    "No licence stated; facts only (dates, names, the kind of work done). Every note is our own wording and "
    "every event links to the FFLA report it comes from. Positions are copied from the NHLR, FFLOS and FFLA records."
)
DOCS = [doc(i, url, label, year, kind="pdf", cache=f"pdf/{url.rsplit('/', 1)[-1]}") for i, url, label, year in D.REPORTS]
LOOKOUTS = D.LOOKOUTS

if __name__ == "__main__":
    run(__doc__, SOURCE, ASSOCIATION, DOCS, LOOKOUTS, credit=CREDIT, license_=LICENSE, folded=True)
