"""Forest Fire Lookout Association chapter reports, the East, the South and the Midwest: what the chapters did to which lookouts, year by year.

  https://firelookout.org/about-us/current-reports/   (latest year)
  https://firelookout.org/resources/archives/annual-reports/<year>-reports/   (2003 to 2024)

Every active FFLA chapter files a yearly report to the national board: members and money, then the projects and
activities that matter here: which lookouts were repaired, repainted, reroofed, moved, rebuilt, lost, closed. The
national Restoration Grants report adds each grant awarded, to which lookout and for what. The archive holds
about 490 PDFs from 2003 to 2025; 236 are for chapters or national reports in the East, the South and the Midwest
(New York, New England, Pennsylvania, New Jersey, Virginia and West Virginia, the Carolinas, Georgia, Tennessee,
Kentucky, Indiana and Illinois, Ohio, Wisconsin, Minnesota, the Gulf and Plains chapters, plus the Eastern and
Southern Deputy, Historian, Archivist, SHPO and Restoration Grants reports). They are the only written record of
the chapters that exist only on Facebook (Indiana, Maine, Massachusetts, North Carolina, Pennsylvania, the
Southern Region, Tennessee, Virginia-West Virginia). This source turns what they say into dated events on the
lookouts' timelines, each linked to the PDF that gives it. Built on the shared association-project shape
(_projects.py, DESIGN.md 3.7) and the driver in _assoc_site.py; the western reports are ffla_west_reports.

How it was made: the reports are prose, so they were read by agents (six batches by year) who wrote each dated fact
once as a record with the lookout's name, state, year, event, a short note in our own words and a short verbatim
run of the report's text as evidence. A script checked the evidence against the PDF text, dropped by rule what is
uncertain, trivial or not a physical fact (see below), and matched each lookout to one of our towers by state and name
(ambiguous ones by hand); positions are copied from that tower's register record. The result is the curated data in
ffla_east_reports_data.py, which this script re-checks against the cached PDFs on every run (the lookout's name and the
year must appear in the report that cites them).

What the filter drops, by rule: the register's own dates are the authority, so no National Register or NHLR listings
(`nhlr_registered`); plans and hopes; site visits that were only a look; "closed as of this report" with no start
year; status events (built, removed, relocated...) whose year the report only approximates; towers the lists do not
have or cannot place (a Minnesota fairgrounds tower, the two Missouri towers moved to Indiana, observation towers);
and the New York chapter's own towers' work after 2015 (the NYS chapter's newsletters, source nysffla_projects, give
that in more detail). Grants awarded are kept as `other` ("FFLA restoration grant awarded for ...").

What is read (2026-10-08; robots.txt disallows only /wp-admin/ and shop paths): the PDFs listed in
ffla_east_reports_data.REPORTS. Five are image-only scans (Pennsylvania 2004, 2005, 2008 and 2009, the 2009 Historian)
and one has a font that decodes to nonsense (New Hampshire 2024); no OCR is available here, so their facts are not
read. The combined 2009 PDF filed under Arizona repeats the Arkansas, Kentucky, Maine, New Hampshire, North
Carolina, Vermont and Virginia reports and the Restoration Grants report, word for word, so it adds nothing.
The FFLA Facebook groups are out of scope.

PDF text from these files loses the letters of "ti", "tt", "ft" and "fi" ("Kelly Bu e"), so names are compared in a
folded form (_assoc_site.fold).

Licence: no licence stated. Dates, names and the kind of work done are facts; the notes are ours; each event links to
the PDF it comes from.

Output: data/sources/ffla_east_reports.json
Re-run: python3 pipeline/regional/ffla_east_reports.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_site import doc, run  # noqa: E402
import ffla_east_reports_data as D  # noqa: E402

SOURCE = "ffla_east_reports"
ASSOCIATION = {"name": "Forest Fire Lookout Association chapter reports", "url": "https://firelookout.org/about-us/current-reports/"}
CREDIT = "Forest Fire Lookout Association, chapter and restoration-grant reports (firelookout.org)"
LICENSE = (
    "No licence stated; facts only (dates, names, the kind of work done). Every note is our own wording and "
    "every event links to the FFLA report it comes from. Positions are copied from the NHLR, FFLOS and FFLA records."
)
DOCS = [doc(i, url, label, year, kind="pdf", cache=f"pdf/{i}.pdf") for i, url, label, year in D.REPORTS]
LOOKOUTS = D.LOOKOUTS

if __name__ == "__main__":
    run(__doc__, SOURCE, ASSOCIATION, DOCS, LOOKOUTS, credit=CREDIT, license_=LICENSE, folded=True)
