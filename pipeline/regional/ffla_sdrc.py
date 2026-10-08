"""FFLA San Diego-Riverside Chapter (California): the Palomar Mountain lookouts and the lost towers of southern California.

  https://www.ffla-sandiego.org/   (the Forest Fire Lookout Association's San Diego-Riverside chapter)

The chapter staffs Boucher Hill and High Point on Palomar Mountain with volunteers and keeps a
history page for each of the southern California towers it has researched (Cleveland National
Forest and neighbours). Those pages give the dates a tower was built, replaced, lost or taken
down, with its cab and tower design. This source turns the sixteen pages into dated events on
the towers' timelines, each linked to its page. Built on the shared association-project shape
(_projects.py, DESIGN.md 3.7) and the driver in _assoc_site.py.

What is read (2026-10-08; robots.txt disallows only /member/): /boucher-lookout/,
/highpoint-lookout/ and the fourteen pages under /fire-lookout/southern-california-towers/.
The site's history essays (Osborne firefinder, smoke chasers, 1970s stories) and press clippings
are not lookout records. A handbook PDF of the chapter's procedures is not read.

Where a page gives only a bound ("standing in 1979, gone by 1986") the event is dated to the bound
and the note says so; a page that gives only a decade is left out.

Licence: no licence stated. Dates, designs and the kind of work done are facts; the notes are
ours; each event links to the chapter's page.

Output: data/sources/ffla_sdrc.json
Re-run: python3 pipeline/regional/ffla_sdrc.py [--no-check]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_site import E, doc, run  # noqa: E402

SOURCE = "ffla_sdrc"
BASE = "https://www.ffla-sandiego.org"
T = f"{BASE}/fire-lookout/southern-california-towers"
ASSOCIATION = {"name": "FFLA San Diego-Riverside Chapter", "url": f"{BASE}/"}
CREDIT = "Forest Fire Lookout Association, San Diego-Riverside Chapter (ffla-sandiego.org)"
LICENSE = (
    "No licence stated; facts only (dates, designs, the kind of work done). Every note is our own "
    "wording and every event links to the chapter's page it comes from. Positions are copied from "
    "the NHLR, FFLOS and FFLA records."
)
DOCS = [
    doc("boucher", f"{BASE}/boucher-lookout/", "Boucher Hill Lookout (FFLA-SDRC)"),
    doc("highpoint", f"{BASE}/highpoint-lookout/", "High Point Lookout (FFLA-SDRC)"),
    doc("blackmtn", f"{T}/black-mountain/", "Black Mountain (FFLA-SDRC)"),
    doc("bottle", f"{T}/bottle-peak/", "Bottle Peak (FFLA-SDRC)"),
    doc("cuyamaca", f"{T}/cuyamaca-peak/", "Cuyamaca Peak (FFLA-SDRC)"),
    doc("estelle", f"{T}/estelle-mountain/", "Estelle Mountain (FFLA-SDRC)"),
    doc("hotsprings", f"{T}/hot-springs-mountain/", "Hot Springs Mountain (FFLA-SDRC)"),
    doc("lospinos", f"{T}/los-pinos/", "Los Pinos (FFLA-SDRC)"),
    doc("lyons", f"{T}/lyons-peak/", "Lyons Peak (FFLA-SDRC)"),
    doc("woodson", f"{T}/mount-woodson/", "Mount Woodson (FFLA-SDRC)"),
    doc("redsd", f"{T}/red-mountainsd/", "Red Mountain, San Diego County (FFLA-SDRC)"),
    doc("sanjuan", f"{T}/san-juan/", "San Juan (FFLA-SDRC)"),
    doc("margarita", f"{T}/santa-margarita-peak/", "Santa Margarita Peak (FFLA-SDRC)"),
    doc("santiago", f"{T}/santiago-peak/", "Santiago Peak (FFLA-SDRC)"),
    doc("tecate", f"{T}/tecate/", "Tecate Peak (FFLA-SDRC)"),
    doc("redriv", f"{T}/red-mountainriverside/", "Red Mountain, Riverside County (FFLA-SDRC)"),
]
CNF = "Cleveland National Forest"

LOOKOUTS = [
    dict(slug="boucher-hill", name="Boucher Hill Lookout", region="CA", tower="us-ca-boucher-hill", pos="nhlr:US 394", find=["Boucher"],
         forest="Palomar Mountain State Park", agency="California State Parks", ownership="state", staffing="volunteer", status="standing",
         design="CDF 809R design: 16x16-ft base, 30-ft tower",
         events=[
             E(1921, "built", "A tower has stood on Boucher Hill since this year, according to a 1991 state lookout survey.", "boucher"),
             E(1948, "replaced", "The present CDF 809R tower was built and put into service.", "boucher"),
             E(1983, "staffed_last", "Last year of regular state staffing.", "boucher"),
             E(2012, "staffed", "Chapter volunteers began staffing it, also serving as state park docents; they covered every fire-season day from 2014.", "boucher"),
         ]),
    dict(slug="high-point", name="High Point Lookout", region="CA", tower="us-ca-high-point", pos="nhlr:US 735", find=["High Point"],
         forest=f"{CNF} (Palomar Ranger District)", agency="U.S. Forest Service", ownership="federal", staffing="volunteer", status="standing",
         design="13x13-ft CL-30 steel cab on a 67-ft all-steel L-1600 tower", height_ft=67,
         events=[
             E(1935, "built", "First tower built on the site by the Civilian Conservation Corps.", "highpoint"),
             E(1964, "replaced", "The present 67-ft steel tower and cab replaced it; it is the tallest tower left in California Forest Service inventory.", "highpoint"),
             E(1992, "staffed_last", "Last year the Cleveland National Forest staffed it.", "highpoint"),
             E(2005, "other", "The interior was stripped out because of vandalism and a security gate fitted to the tower.", "highpoint"),
             E(2009, "restored", "Restoration with new glass, cabinets and flooring finished; chapter volunteers began staffing it that year.", "highpoint"),
         ]),
    dict(slug="black-mountain-black-hill", name="Black Mountain (Black Hill) Lookout", region="CA", tower="us-ca-black-mountain-black-hill",
         pos="fflos:US 515", find=["Black Mountain"], forest=f"{CNF} (Mesa Grande Indian Reservation edge)", status="gone",
         design="20-ft open timber tower with a Region 5 C3 14x14-ft wood cab",
         events=[E(1986, "removed", "Seen standing in 1979 and gone by 1986; demolished or removed.", "blackmtn")]),
    dict(slug="bottle-peak", name="Bottle Peak Lookout", region="CA", tower="us-ca-bottle-peak", pos="fflos:US 520", find=["Bottle Peak"],
         forest="Cleveland National Forest (boundary since redrawn)", status="ruins", design="7x7-ft hip-roofed ground cab reached by a 29-ft ladder",
         events=[
             E(1912, "built", "Built that spring by District Ranger Ed Bish, one of the first two lookouts in the new forest's detection system.", "bottle"),
             E(1938, "abandoned", "Listed as abandoned in a 1938 survey data sheet, though seen standing in 1950; the concrete foundation remains.", "bottle"),
         ]),
    dict(slug="cuyamaca-peak", name="Cuyamaca Peak Lookout", region="CA", tower="us-ca-cuyamaca-peak", pos="fflos:US 516", find=["Cuyamaca"],
         forest=f"{CNF} (Cuyamaca Rancho State Park)", status="gone", design="30-ft steel K-brace tower with a Region 5 C3 14x14-ft cab",
         events=[E(1918, "built", "A 10-ft enclosed timber tower with a 14x14-ft live-in cab went up; a 30-ft steel tower replaced it in the 1930s.", "cuyamaca")]),
    dict(slug="estelle-mountain", name="Estelle Mountain Lookout", region="CA", tower="us-ca-estelle-mountain",
         pos="ffla:ca:estelle-mountain:33.7675:-117.4219", find=["Estelle Mountain"], forest="Cleveland National Forest", status="relocated",
         design="BC-301 14x14-ft cab on a 30-ft L-1600 steel K-brace tower", moved_to="Hemet-Ryan Air Attack Base",
         events=[E(1935, "built", "Built by the Civilian Conservation Corps; later taken apart and moved to the Hemet-Ryan airbase, where it still serves as the control tower.", "estelle")]),
    dict(slug="hot-springs-mountain", name="Hot Springs Mountain Lookout", region="CA", tower="us-ca-hot-springs-mountain", pos="nhlr:US 753",
         find=["Hot Springs"], forest=f"{CNF} (Los Coyotes Indian Reservation)", ownership="tribal", status="standing",
         design="Wood 14x14-ft C-3 cab and tower",
         events=[
             E(1912, "built", "Original tower in service: the oldest in the Cleveland National Forest.", "hotsprings"),
             E(1928, "replaced", "A second structure replaced the original.", "hotsprings"),
             E(1942, "replaced", "The present cab and tower were built; its roof has since collapsed and the structure is badly weathered.", "hotsprings"),
         ]),
    dict(slug="los-pinos", name="Los Pinos Lookout", region="CA", tower="us-ca-los-pinos", pos="nhlr:US 742", find=["Los Pinos"],
         forest=CNF, agency="U.S. Forest Service", ownership="federal", staffing="staffed", status="standing",
         design="13x13-ft CL-30 steel cab on a 30-ft L-1600 steel tower", height_ft=30,
         events=[
             E(1925, "built", "Original tower.", "lospinos"),
             E(1964, "replaced", "The present steel cab and tower opened; it is the only tower on the forest still staffed by Forest Service employees.", "lospinos"),
         ]),
    dict(slug="lyons-peak", name="Lyons Peak Lookout", region="CA", tower="us-ca-lyons-peak", pos="nhlr:US 754", find=["Lyons Peak"],
         forest=CNF, status="standing", design="13x13-ft CL-30 steel cab on a 41-ft L-1600 K-brace tower (the only such combination in California)", height_ft=41,
         events=[E(1913, "built", "A tiny 5x5-ft first tower, said to look like a telephone booth; the site is now reachable only by helicopter or escort.", "lyons")]),
    dict(slug="mount-woodson", name="Mount Woodson Lookout", region="CA", tower="us-ca-mount-woodson", pos="fflos:US 519", find=["Woodson"],
         forest="Cleveland National Forest", status="gone",
         events=[
             E(1936, "built", "Likely a CCC job: a 7x7-ft Aermotor cab on an 80-ft steel tower with a ground residence cabin, the tallest known in southern California.", "woodson"),
             E(1950, "replaced", "A CDF 809R 15x15-ft cab on a 30-ft enclosed steel tower, with living space below; apparently lost to a fire later.", "woodson"),
             E(1991, "removed", "Seen standing in a 1986 survey and gone by 1991.", "woodson"),
         ]),
    dict(slug="red-mountain-san-diego", name="Red Mountain Lookout (San Diego County)", region="CA", tower="us-ca-red-mountain-san-diego-county",
         pos="nhlr:US 755", find=["Red Mountain"], forest="Fallbrook area", status="standing",
         events=[
             E(1921, "built", "A lookout has stood here since this year; no pictures of the first one survive.", "redsd"),
             E(1935, "replaced", "New CDF lookout (similar to the Forest Service 4AR 14x14 cab on a 10-ft enclosed tower), with a garage and weather station.", "redsd"),
             E(1977, "replaced", "Replaced by a plain wood cab on a 10-ft concrete block base.", "redsd"),
             E(1977, "closed", "Closed the same year; the cab was stripped and sealed but still stands among communications gear.", "redsd"),
         ]),
    dict(slug="san-juan", name="San Juan Lookout", region="CA", tower="us-ca-san-juan", pos="fflos:US 852", find=["San Juan"],
         forest="Cleveland National Forest", status="gone", design="7-ft open wood tower with an 8x8-ft hip-roofed cab",
         events=[E(1930, "built", "Built around 1930 and used for emergency staffing; it is gone and a trail still leads to the site.", "sanjuan")]),
    dict(slug="santa-margarita-peak", name="Santa Margarita Peak Lookout", region="CA", tower="us-ca-santa-margarita-margarita-peak",
         pos="fflos:US 517", find=["Santa Margarita", "Margarita Peak"], forest=f"{CNF} (Trabuco Ranger District)", status="gone",
         events=[
             E(1935, "built", "Built by the Civilian Conservation Corps: a 30-ft steel K-brace tower with a 14x14-ft live-in cab.", "margarita"),
             E(1965, "replaced", "Replaced by a Forest Service standard CL-104 lookout: a 30-ft steel tower with a 13x13-ft steel cab.", "margarita"),
             E(1986, "fire", "The lookout was burned over in a wildfire.", "margarita"),
             E(1988, "destroyed", "Destroyed when a Marine Corps helicopter struck it.", "margarita"),
         ]),
    dict(slug="santiago-peak", name="Santiago Peak Lookout", region="CA", tower="us-ca-santiago-peak", pos="fflos:US 518", find=["Santiago Peak"],
         forest=f"{CNF} (Trabuco Ranger District)", status="standing",
         events=[
             E(1914, "built", "Original 70-ft lookout tower.", "santiago"),
             E(1935, "removed", "The original tower was taken down by the Civilian Conservation Corps.", "santiago"),
             E(1951, "replaced", "A 35-ft tower with a 10-ft cab was built, now among communications facilities.", "santiago"),
         ]),
    dict(slug="tecate-peak", name="Tecate Peak Lookout", region="CA", tower="us-ca-tecate-peak", pos="fflos:US 521", find=["Tecate"],
         forest="Cleveland National Forest (US-Mexico border)", status="gone",
         design="20-ft enclosed battered timber tower with a 14x14-ft wood cab",
         events=[E(1939, "built", "Built by the Civilian Conservation Corps and used for at least 40 years before being demolished.", "tecate")]),
    dict(slug="red-mountain-riverside", name="Red Mountain Lookout (San Bernardino NF)", region="CA", tower="us-ca-red-mountain-san-bernadino-nf",
         pos="nhlr:US 290", find=["Red Mountain"], forest="San Bernardino National Forest", status="gone",
         discrepancies=["Built 1936 and returned to service in October 1998 (this chapter); 1937 and reopened 1999 (the Southern California Mountains Foundation)."],
         events=[E(2022, "burned", "Destroyed by the Fairview Fire in September.", "redriv")]),
]

if __name__ == "__main__":
    run(__doc__, SOURCE, ASSOCIATION, DOCS, LOOKOUTS, credit=CREDIT, license_=LICENSE)
