"""Azure Mountain Friends: the history and yearly newsletters of the Azure Mountain tower.

  https://www.azuremountain.org/   (AMF, a volunteer group formed in 2001 to save the tower)

AMF restored the 1918 Aermotor fire tower on Azure Mountain (Santa Clara, Franklin County, NY) in 2002-03
with NYSDEC and AmeriCorps, and keeps it up (stairs, fencing, painting). Its site has a chronology page and
a yearly newsletter (PDF).

What is read (2026-10-08, Squarespace robots.txt: general crawlers allowed, AI-training bots by name
disallowed; FirefinderBot is not one of them, and this is a facts register, not model training): /history
and the newsletters for 2002/03, 2017-2024 (2005 and 2010 are image-only or not used: 2005 has no text layer).
Not read: store, scholarship, volunteer and event pages, and the 2010 issue's school-programme news.

Prose, curated by hand in our own words and checked against the text of what is cited. No coordinates are
published: the position is copied from the NHLR record.

Licence: none stated; facts only, notes are ours.

Output: data/sources/azure_mountain_friends.json
Re-run: python3 pipeline/regional/azure_mountain_friends.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_east import E, doc, run  # noqa: E402

SOURCE = "azure_mountain_friends"
BASE = "https://www.azuremountain.org"
ASSOCIATION = {"name": "Azure Mountain Friends", "url": f"{BASE}/"}
CREDIT = "Azure Mountain Friends (azuremountain.org)"
LICENSE = (
    "No licence stated; facts only (dates, names, the kind of work done). Every note is our own wording and "
    "every event links to the AMF page or newsletter it comes from. The position is copied from the NHLR "
    "record (AMF publishes none)."
)

DOCS = [
    doc("history", f"{BASE}/history", "AMF: Azure Mountain chronology", None, cache="history.html"),
    doc("n2024", f"{BASE}/s/AMF-Newsletter2024.pdf", "AMF newsletter 2024", 2024, cache="pdf/2024.pdf"),
    doc("n2023", f"{BASE}/s/AMF-Newsletter2023-Final-dc65.pdf", "AMF newsletter 2023", 2023, cache="pdf/2023.pdf"),
    doc("n2022", f"{BASE}/s/AMF-Newsletter2022FINAL.pdf", "AMF newsletter 2022", 2022, cache="pdf/2022.pdf"),
    doc("n2021", f"{BASE}/s/AzureNews2021final.pdf", "AMF newsletter 2021", 2021, cache="pdf/2021.pdf"),
    doc("n2020", f"{BASE}/s/AzureNews2020.pdf", "AMF newsletter 2020", 2020, cache="pdf/2020.pdf"),
    doc("n2019", f"{BASE}/s/AzureNews2019.pdf", "AMF newsletter 2019", 2019, cache="pdf/2019.pdf"),
    doc("n2018", f"{BASE}/s/AzureNews2018.pdf", "AMF newsletter 2018", 2018, cache="pdf/2018.pdf"),
    doc("n2017", f"{BASE}/s/AzureNews2017.pdf", "AMF newsletter 2017", 2017, cache="pdf/2017.pdf"),
    doc("n2003", f"{BASE}/s/azurenews2003.pdf", "AMF newsletter 2002-03", 2003, cache="pdf/2003.pdf"),
]

LOOKOUTS: list[dict] = [
    dict(slug="azure-mountain", name="Azure Mountain Fire Tower", tower="us-ny-azure-mountain", pos="nhlr:US 520",
         find=["Azure"], status="standing", agency="NYS DEC", ownership="state", staffing="volunteer",
         page=f"{BASE}/history",
         events=[
             E(1914, "built", "A wooden fire observation station was built on the summit, the first lookout structure on the mountain.", "history"),
             E(1918, "built", "The present 35-foot galvanized steel Aermotor tower was put up in summer 1918.", "history", "n2003"),
             E(1936, "other", "The observer's cabin at the foot of the mountain was built.", "history"),
             E(1978, "closed", "DEC closed the tower after the fire season and took off the lowest two flights of stairs; it stayed closed to the public for over 24 years.", "history", "n2003"),
             E(1995, "other", "DEC tore down the neglected observer's cabin near the foot of the mountain.", "history", "n2003"),
             E(2001, "other", "The tower was named to the National Register of Historic Places with six other fire towers; the state announced plans to remove it, which led to Azure Mountain Friends forming.", "history", "n2003"),
             E(2002, "restored", "Rangers, AmeriCorps members and volunteers replaced the wooden stairs, landings and cab floor, fitted new cab windows and railing and painted the whole tower.", "n2003", "history"),
             E(2003, "other", "After DEC approval, the restored tower was officially reopened to the public at an observance on 27 September.", "history", "n2003"),
             E(2017, "restored", "A Student Conservation Association crew gave the steel a fresh coat of paint in August.", "n2018"),
             E(2018, "modified", "Wire safety fencing along the tower stairs and landings was repaired or replaced by a fire-tower restoration contractor's crew.", "n2018", "n2019"),
         ]),
]


def main() -> None:
    run(source=SOURCE, association=ASSOCIATION, credit=CREDIT, license_=LICENSE, region="NY", specs=DOCS,
        lookouts=LOOKOUTS, description=__doc__.split("\n")[0])


if __name__ == "__main__":
    main()
