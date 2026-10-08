"""The curated facts for pipeline/regional/nwmt_projects.py.

The Northwest Montana Lookout Association (NMLA) reports its work in prose: yearly "Completed
Projects" PDFs (printed from its old website), the 2025 and 2026 project posts, and a yearly
newsletter. Nobody can parse a sentence like "the first lookout was constructed in 1929 and
was destroyed by fire two weeks after completion" into data by machine, so each fact was read
from the report and written down once here, in our own words, citing the report(s) by the
ids in DOCS. nwmt_projects.py then checks every cited report's text (it must name the lookout,
and the year unless it is that year's own report), builds the records, and flags new project
posts nobody has curated yet.

Reading notes. The PDFs are print-outs of a Wix page and carry every word twice and some
digits doubled ("7 miles" reads "77 miles"), so anything numeric that mattered was checked
against the page image. NMLA's reports sometimes disagree with each other (build years above
all); each such case is kept in the lookout's ``discrepancies`` instead of being settled by
guesswork, and the event that carries the more recent or more detailed statement names the
other in its note.

Conventions: ``E(year, event, note, *cite)``; ``built`` is the first structure on the site,
``replaced`` every later one; ``restored`` is repair, rehabilitation, re-roofing and
repainting; ``modified`` is something added; ``assessed`` is a condition assessment; a year of
None means the report gives no usable year (the note says what it does give).
"""

from __future__ import annotations

BASE = "https://nwmt-ffla.org"
PDF_BASE = f"{BASE}/wp-content/uploads"

# id, year (the season the report covers), the document's own URL, the web page that carries it.
# "post" documents are HTML; "pdf" documents are read with pdftotext. Newsletters are published
# each November; the 2024 PDF is mostly a list of project titles whose detail pages are gone, so
# the 2024 season is read from the fall 2024 newsletter.
DOCS: list[dict] = []


def _doc(doc_id: str, kind: str, year: int, url: str, page: str, label: str) -> None:
    DOCS.append({"id": doc_id, "kind": kind, "year": year, "url": url, "page": page, "label": label})


_doc("p2026", "post", 2026, f"{BASE}/2026/03/07/2026-projects/", f"{BASE}/2026/03/07/2026-projects/", "NMLA 2026 projects")
_doc("p2025", "post", 2025, f"{BASE}/2025/03/04/2025-projects/", f"{BASE}/2025/03/04/2025-projects/", "NMLA 2025 projects")
for _y in range(2024, 2013, -1):
    _doc(f"pdf{_y}", "pdf", _y, f"{PDF_BASE}/2025/09/{_y}-completed-projects.pdf", f"{BASE}/{_y}/09/01/{_y}-projects/",
         f"NMLA {_y} completed projects (PDF)")
_NL = [
    ("nl2025", 2025, "2025/11/2025-newsletter-final2.pdf", "2025/11/12/2025-newsletter/", "NMLA 2025 newsletter"),
    ("nl2024", 2024, "2025/11/2024-newsletter.pdf", "2024/11/12/2024-newsletter/", "NMLA fall 2024 newsletter"),
    ("nl2023", 2023, "2025/11/2023-newsletter.pdf", "2023/11/12/2023-newsletter/", "NMLA fall 2023 newsletter"),
    ("nl2022", 2022, "2025/11/2022-newsletter.pdf", "2022/11/12/2022-newsletter/", "NMLA fall 2022 newsletter"),
    ("nl2021w", 2021, "2025/11/2021winter.pdf", "2021/11/12/2021-newsletter/", "NMLA winter 2021 newsletter"),
    ("nl2020f", 2020, "2025/11/2020fall.pdf", "2020/11/12/2020-newsletter/", "NMLA fall 2020 newsletter"),
    ("nl2019f", 2019, "2025/11/2019-fall-newsletter.pdf", "2019/11/12/2019-newsletter/", "NMLA fall 2019 newsletter"),
    ("nl2018s", 2018, "2025/11/2018spring.pdf", "2018/11/12/2018-newsletter/", "NMLA spring 2018 newsletter"),
    ("nl2017f", 2017, "2025/11/2017fall.pdf", "2017/11/12/2017-newsletters/", "NMLA fall 2017 newsletter"),
    ("nl2017s", 2017, "2025/11/2017-spring.pdf", "2017/11/12/2017-newsletters/", "NMLA spring 2017 newsletter"),
    ("nl2016f", 2016, "2025/11/2016fallnewsletter.pdf", "2016/11/12/2016-newsletters/", "NMLA fall 2016 newsletter"),
    ("nl2016s", 2016, "2025/11/2016-spring-newsletter.pdf", "2016/11/12/2016-newsletters/", "NMLA spring 2016 newsletter"),
    ("nl2015", 2015, "2025/11/2015-newsletter.pdf", "2015/11/12/2015-newsletter/", "NMLA 2015 newsletter"),
]
for _id, _y, _pdf, _page, _label in _NL:
    _doc(_id, "pdf", _y, f"{PDF_BASE}/{_pdf}", f"{BASE}/{_page}", _label)

# Pages that are not reports but are part of the crawl (checked against the sitemap).
CATEGORY_PAGES = [
    f"{BASE}/category/projects/",
    f"{BASE}/category/projects/completed/",
    f"{BASE}/category/projects/completed/page/2/",
    f"{BASE}/category/projects/in-progress/",
]

# Section titles in the 2025/2026 posts that are not lookouts.
IGNORED_HEADINGS = (
    "assessments", "projects", "glacier national park", "kootenai national forest", "flathead national forest",
    "learn more about our", "stillwater", "share this", "thank you to our",
)


def E(year: int | None, event: str, note: str, *cite: str) -> dict:
    return {"year": year, "event": event, "note": note, "cite": list(cite)}


# Units, as NMLA groups its lookouts, with the agency and ownership that follows from them.
GNP = dict(unit="Glacier National Park", agency="National Park Service (Glacier National Park)", ownership="federal")
FNF = dict(unit="Flathead National Forest", agency="U.S. Forest Service (Flathead National Forest)", ownership="federal")
KNF = dict(unit="Kootenai National Forest", agency="U.S. Forest Service (Kootenai National Forest)", ownership="federal")
DNRC = dict(unit="Montana DNRC", agency="Montana Department of Natural Resources and Conservation", ownership="state")

LOOKOUTS: list[dict] = [
    # ------------------------------------------------------------------ Glacier National Park
    dict(slug="apgar", name="Apgar Lookout", tower="us-mt-apgar", pos="nhlr:US 33", find=["Apgar"], **GNP,
         design="Two-story wood frame: 14x14-ft cab on an enclosed 10-ft tower (one of two basic designs in Glacier)", height_ft=10,
         events=[
             E(1929, "destroyed", "The first lookout on the site, finished that year, burned about two weeks after completion.", "p2025"),
             E(1930, "rebuilt", "An identical lookout was built on the site: the one standing today.", "p2025"),
             E(2015, "assessed", "Condition assessment by volunteers, to plan maintenance.", "pdf2015", "nl2015"),
             E(2016, "restored", "Volunteers scraped and repainted the exterior, replaced one broken window, reglazed others and replaced two door shutter boards.", "pdf2016", "nl2016f"),
             E(2016, "assessed", "Condition assessment, part of NMLA's 2016 push to assess lookouts.", "pdf2016", "nl2016f"),
             E(2019, "assessed", "June assessment, also a training trip for future assessors; the 2016 paint was still in very good shape.", "pdf2019", "nl2019f"),
             E(2022, "assessed", "Repeat assessment (done every three years): structurally sound, already needing fresh paint.", "pdf2022", "nl2022"),
             E(2025, "assessed", "Repeat assessment: good shape; minor cosmetic repairs, possible rodent entry points, graffiti and window gaps noted.", "p2025", "nl2025"),
         ]),
    dict(slug="huckleberry", name="Huckleberry Lookout", tower="us-mt-huckleberry", pos="nhlr:US 35", find=["Huckleberry"], **GNP,
         design="14x14-ft wood frame cab with the hip roof extended over the catwalk and removable (not folding) shutters",
         events=[
             E(1933, "replaced", "The present structure replaced an original cupola lookout on the site.", "pdf2021"),
             E(2015, "restored", "With Park maintenance: exterior painted, the many cab windows reglazed and painted, guy wires secured.", "pdf2015", "nl2015"),
             E(2018, "restored", "Park crew re-roofed the lookout; a volunteer re-roofed and braced the outhouse and replaced latches on the vent doors.", "pdf2018"),
             E(2021, "assessed", "Needs assessment: dry rot, window reglazing, cracked boards, failing catwalk railing and painting.", "pdf2021", "nl2021w"),
             E(2024, "assessed", "August assessment: some rot, rodent access to the cab and a paint touch-up needed.", "nl2024", "pdf2024"),
         ]),
    dict(slug="scalplock", name="Scalplock Mountain Lookout", tower="us-mt-scalplock-mountain", pos="nhlr:US 39", find=["Scalplock"], **GNP,
         staffing="staffed", aliases=["Scalplock Lookout"],
         events=[
             E(1931, "built", "Built 1931, above the Middle Fork of the Flathead.", "nl2024"),
             E(2018, "restored", "Under Park supervision, a volunteer helped scrape and paint siding, replace skirt boards and decking, and paint stringers and stairs.", "pdf2018"),
             E(2021, "assessed", "Assessment: good condition and minor maintenance only; the lookout is staffed through fire season.", "pdf2021", "nl2021w"),
             E(2024, "assessed", "September assessment found several concerns to fix before winter; assessed every three years under a cooperative agreement.", "nl2024", "pdf2024"),
         ]),
    dict(slug="loneman", name="Loneman Lookout", tower="us-mt-loneman", pos="nhlr:US 36", find=["Loneman"], **GNP,
         design="Standard wood frame: 14x14-ft cabin on a 10-ft enclosed tower with catwalk", height_ft=10,
         events=[
             E(1929, "built", "Built 1929.", "nl2017f"),
             E(2017, "assessed", "Assessment for the Park after fording the Middle Fork and Nyack Creek; the lookout was staffed that season.", "pdf2017", "nl2017f"),
             E(2021, "assessed", "Two-day assessment: good condition, minor maintenance only.", "pdf2021", "nl2021w"),
             E(2024, "assessed", "August assessment: interior good, catwalk weakened and rotting, paint worn.", "nl2024", "pdf2024"),
         ]),
    dict(slug="porcupine-ridge", name="Porcupine Ridge Lookout", tower="us-mt-porcupine-ridge", pos="nhlr:US 1459", find=["Porcupine"], **GNP,
         design="Classic two-story National Park Service frame cab",
         discrepancies=["Built 1939 (2023 newsletter) or between 1939 and 1940 (2026 post)."],
         events=[
             E(1939, "built", "Two-story Park Service frame cab above the Waterton Valley.", "nl2023", "p2026"),
             E(1972, "abandoned", "Regular fire-detection use ended about this time; it still supports backcountry rangers.", "nl2023", "p2026"),
             E(2003, "restored", "Last rehabilitated; bears and other animals have tried to get in since.", "pdf2017", "nl2017f"),
             E(2017, "assessed", "Remote assessment reached by boat to Goat Haunt and a hike with creek fords.", "pdf2017", "nl2017f"),
             E(2023, "assessed", "Assessment: good condition; routine painting and a few shutters to replace.", "pdf2023", "nl2023"),
         ]),
    dict(slug="heavens-peak", name="Heavens Peak Lookout", tower="us-mt-heavens-peak", pos="nhlr:US 34", find=["Heaven"], **GNP,
         staffing="unstaffed",
         design="Stone-and-wood cab, 12x12 ft, flat roof, on a stone foundation with a stone-walled catwalk",
         discrepancies=["Stabilization work in 2012, 2014 and 2016 (2020 report) or 2013-14 (2023 newsletter)."],
         events=[
             E(1945, "built", "Built by conscientious objectors in the Civilian Public Service during World War II.", "p2026", "nl2023"),
             E(1953, "staffed_last", "In operation from 1945 until 1953.", "nl2023"),
             E(2012, "restored", "Park and Mennonite crews stabilized the structure in rounds (2012, 2014, 2016); a 2023 newsletter dates it 2013-14.", "pdf2020"),
             E(2020, "assessed", "Overnight assessment after a trailless 3,000-ft bushwhack through the 2003 Trapper Fire burn; unstaffed for decades.", "pdf2020", "nl2020f"),
             E(2023, "assessed", "Assessment: generally good shape but in need of extensive painting and other repairs.", "pdf2023", "nl2023"),
         ]),
    dict(slug="mount-brown", name="Mount Brown Lookout", tower="us-mt-mount-brown", pos="nhlr:US 37", find=["Mount Brown", "Mt Brown", "Mt. Brown"], **GNP,
         design="Two-story cab with a short hip roof",
         discrepancies=["Built 1929 (2026 post) or constructed 1928 (fall 2019 newsletter)."],
         events=[
             E(1929, "built", "One of the oldest lookouts left in Glacier; a 2019 newsletter says 1928.", "p2026"),
             E(2015, "assessed", "Condition assessment by volunteers, to plan maintenance.", "pdf2015", "nl2015"),
             E(2017, "assessed", "Assessment for the Park ahead of a maintenance project.", "pdf2017", "nl2017f"),
             E(2017, "fire", "Wrapped in protective covering during the Sprague Fire, which burned nearly 17,000 acres around it; the lookout survived and the project was postponed.", "nl2017f", "pdf2017"),
             E(2019, "assessed", "Condition assessment earlier in the summer, before the work project.", "nl2019f"),
             E(2019, "restored", "Volunteers scraped and painted much of the interior, worked on the windows and made the stairs to the catwalk safer.", "pdf2019", "nl2019f"),
             E(2020, "restored", "Volunteers painted the whole exterior and touched up the interior.", "pdf2020", "nl2020f"),
             E(2022, "restored", "August work: major stair repairs, cracked windows replaced, painting.", "pdf2022", "nl2022"),
             E(2023, "restored", "Cracked windows, failed storage-area siding and catwalk deck boards replaced; interior and exterior painted.", "pdf2023", "nl2023"),
             E(2026, "assessed", "Assessment: interior fine; exterior needs caulking and paint, new shutters and south catwalk railing, stair railings and privy repair.", "p2026"),
         ]),
    dict(slug="swiftcurrent", name="Swiftcurrent Lookout", tower="us-mt-swiftcurrent", pos="nhlr:US 40", find=["Swiftcurrent"], **GNP,
         staffing="staffed", design="The only lookout in Glacier without a catwalk",
         events=[
             E(1936, "built", "Built on the Continental Divide above Granite Park Chalet.", "p2025", "nl2025", "nl2019f"),
             E(2019, "assessed", "Overnight assessment from the Loop; the lookout is staffed.", "pdf2019", "nl2019f"),
             E(2022, "assessed", "Assessment: staffed and very well maintained.", "pdf2022", "nl2022"),
             E(2025, "assessed", "Repeat assessment: generally good, no major defects; scraping and painting needed.", "p2025", "nl2025"),
         ]),
    dict(slug="numa-ridge", name="Numa Ridge Lookout", tower="us-mt-numa-ridge", pos="nhlr:US 38", find=["Numa"], **GNP,
         staffing="staffed", design="Standard wood frame: 14x14-ft house on a 10-ft tower with catwalk", height_ft=10,
         events=[
             E(1934, "built", "Built 1934 as the Park's northernmost lookout, nine miles from the Canadian border.", "p2025", "nl2025", "nl2019f"),
             E(2019, "assessed", "Condition assessment of the staffed lookout (about 11.5 miles round trip).", "pdf2019", "nl2019f"),
             E(2022, "assessed", "Assessment: good condition; the outhouse was flattened by the winter's snow.", "pdf2022", "nl2022"),
             E(2025, "assessed", "Assessment: foundation, catwalk, stairs and some siding need repair, the exterior needs paint; interior good.", "p2025", "nl2025"),
         ]),
    # ------------------------------------------------------------------ Flathead National Forest
    dict(slug="spotted-bear", name="Spotted Bear Lookout", tower="us-mt-spotted-bear-mountain", pos="nhlr:US 1495", find=["Spotted Bear"], **FNF,
         aliases=["Spotted Bear Mountain Lookout"], design="R-6 treated-timber tower (1963)",
         discrepancies=["2014 report: built 1914, current tower 1933. 2025 report: built 1916, current R-6 tower 1963."],
         events=[
             E(1916, "other", "First lookout on the site: a two-story log structure (the 2014 report says 1914).", "p2025", "nl2025"),
             E(1933, "replaced", "A second lookout replaced the log one (the 2014 report calls it the current tower).", "pdf2014"),
             E(1963, "replaced", "The present treated-timber R-6 tower replaced the earlier lookout.", "p2025", "nl2025"),
             E(2014, "restored", "Four volunteers, 160 hours in July: roof repair, soffits and windows painted, screen door, trap-door gate, shutters, stair treads.", "pdf2014", "nl2020f"),
             E(2025, "assessed", "Assessment: glazing, paint, flooring and the outhouse need work; two broken panes to replace, new panes delivered.", "p2025", "nl2025"),
         ]),
    dict(slug="moran-patrol-cabin", name="Moran Patrol Cabin", tower="us-mt-coal-ridge-moran-lookout-cabin", pos="nhlr:US 1498", find=["Moran"], **FNF,
         aliases=["Coal Ridge Cabin"], design="Patrol cabin on Coal Ridge (a ground structure, not a tower)",
         events=[
             E(1928, "built", "First of three lookouts within two miles on Coal Ridge; now the only structure left on the ridge.", "pdf2014"),
             E(2014, "restored", "Rehabilitation begun in 2012 finished in September; NMLA bought siding and trim and the Forest Service installed them.", "pdf2014"),
             E(2016, "restored", "Volunteers gave the cabin a fresh coat of paint.", "pdf2016", "nl2016f"),
             E(2017, "restored", "Gable end, south wall and rafter tails scraped and painted, finishing the tune-up begun the year before.", "pdf2017", "nl2017f"),
         ]),
    dict(slug="firefighter", name="Firefighter Lookout", tower="us-mt-firefighter", pos="nhlr:US 926", find=["Firefighter"], **FNF, height_ft=41,
         design="41-ft tower; NMLA describes an R-6 flat-top base with an L-4 style tower on it, the only one of its kind, its hip roof later made flat",
         events=[
             E(1923, "other", "The original D-6 cupola lookout (12x12 cabin) was built on the mountain's southeast ridge, a different spot from today's tower; it burned between 1948 and 1952.", "nl2023"),
             E(1953, "built", "The present 41-foot tower was built by the Bureau of Reclamation, replacing Riverside Lookout, which the reservoir covered.", "nl2023"),
             E(None, "staffed_last", "Paid Forest Service staffing ended about 1997 or 1998.", "nl2023"),
             E(2012, "staffed", "One of the first three lookouts in the Flathead's volunteer lookout program, with Baptiste and Cyclone.", "nl2023"),
             E(2014, "modified", "NMLA bought an 8-ft picnic table for visitors.", "pdf2014"),
             E(2016, "restored", "Three days of scraping and two coats of paint on the cab, catwalk and stair railings; tower oiled, brass threshold polished.", "pdf2016", "nl2016f"),
             E(2018, "restored", "Kalispell Daybreak Rotary volunteers scraped and painted the cab, catwalk and stair railings.", "pdf2018", "nl2023"),
         ]),
    dict(slug="cyclone", name="Cyclone Lookout", tower="us-mt-cyclone-peak", pos="nhlr:US 1499", find=["Cyclone"], **FNF,
         aliases=["Cyclone Peak Lookout"],
         events=[
             E(2012, "staffed", "One of the first three lookouts in the Flathead's volunteer lookout program, with Baptiste and Firefighter.", "nl2023"),
             E(2018, "restored", "Multi-day project scraping and painting the cab exterior, catwalk and stair railings.", "pdf2018"),
         ]),
    dict(slug="mud-lake", name="Mud Lake Lookout", tower="us-mt-mud-lake", pos="nhlr:US 1496", find=["Mud Lake"], **FNF,
         design="Early L-4 ground cab in the Bob Marshall Wilderness; NMLA calls it the only original lookout left in the Bob",
         events=[
             E(1932, "built", "L-4 lookout in the Bob Marshall Wilderness, a 23-mile hike in from Meadow Creek.", "nl2015", "nl2016f", "nl2025"),
             E(2015, "restored", "First phase: cabin repaired, new shutters hung, structure scraped and painted, interior readied.", "pdf2015", "nl2015"),
             E(2015, "modified", "A wood stove was installed.", "pdf2015", "nl2015"),
             E(2016, "restored", "Second phase: lookout levelled and squared on a new loose-stack rock foundation, windows removed for repair, radio repeater and solar panel moved off the building.", "pdf2016", "nl2016f"),
             E(2017, "restored", "Third phase: the failed west wall was rebuilt from the ground up on the new foundation.", "pdf2017", "nl2017f"),
             E(2018, "restored", "A badly damaged window replaced; windows on three sides reglazed, painted and reset.", "pdf2018"),
             E(2020, "restored", "Final phase of the multi-year restoration finished, with Salmon Forks Outfitters packing the crew in.", "pdf2020", "nl2020f"),
             E(2025, "assessed", "Five-day backpacking assessment with no stock support; the crew also painted the window glazing.", "p2025", "nl2025"),
         ]),
    dict(slug="jumbo", name="Jumbo Lookout", tower="us-mt-jumbo-mountain", pos="nhlr:US 1497", find=["Jumbo"], **FNF,
         aliases=["Jumbo Mountain Lookout"],
         events=[
             E(2015, "restored", "Three-day volunteer project with the Spotted Bear District: new privy hole and hitching rail, stone wall rebuilt, trim and shutters painted, roof patched.", "pdf2015", "nl2015"),
         ]),
    dict(slug="baptiste", name="Baptiste Lookout", tower="us-mt-baptiste", pos="nhlr:US 995", find=["Baptiste"], **FNF,
         events=[
             E(2012, "staffed", "After renovation, one of the first three lookouts in the Flathead's volunteer lookout program.", "nl2023"),
             E(2015, "modified", "Backcountry Horsemen packed up a 6-ft picnic table donated by NMLA; volunteers stained and assembled it.", "pdf2015", "nl2015"),
         ]),
    dict(slug="cooney", name="Cooney Lookout", tower="us-mt-cooney", pos="nhlr:US 1492", find=["Cooney"], **FNF,
         events=[
             E(2023, "other", "NMLA trained assessment team leaders here (Swan Lake Ranger District) in mid-June.", "pdf2023", "nl2023"),
         ]),
    dict(slug="hornet-mountain", name="Hornet Mountain Lookout", tower="us-mt-hornet-peak", pos="nhlr:US 1154", find=["Hornet"], **FNF,
         aliases=["Hornet Peak Lookout"], design="D-1 cupola house of logs cut on site, an unusual design in the Northern Region",
         events=[
             E(1922, "built", "Standard D-1 cupola cabin of on-site logs, built for about $719 to a design by Dwight Beatty.", "nl2022"),
             E(2022, "other", "Centennial celebration on September 10, hosted by the Forest Service with NMLA board members helping; more preservation work planned.", "nl2022", "nl2023"),
         ]),
    # ------------------------------------------------------------------ Kootenai National Forest
    dict(slug="meadow-peak", name="Meadow Peak Lookout", tower="us-mt-meadow-peak", pos="nhlr:US 344", find=["Meadow Peak"], **KNF,
         design="L-4 cab on a 10-ft treated-timber frame with a wrap-around catwalk", height_ft=10,
         discrepancies=["Rentals: 'can now be rented' in the 2021 report, but the 2022 newsletter expects the cabin rental in 2023."],
         events=[
             E(1936, "replaced", "A 15-ft timber tower with an L-4 cab replaced the original cupola cabin.", "p2026"),
             E(1957, "replaced", "The current L-4 lookout on a 10-ft treated-timber frame.", "p2026", "pdf2022"),
             E(2015, "assessed", "Collaborative condition assessment with the Kootenai NF, which planned the restoration.", "pdf2015", "nl2015"),
             E(2016, "assessed", "Condition assessment (May), before the first phase.", "nl2016f", "pdf2016"),
             E(2016, "restored", "Phase 1: tower bracing and supports replaced, shutters taken to the Regional Historic Preservation Shop, attic cleaned of pack-rat litter, header and soffit replaced.", "pdf2016", "nl2016f"),
             E(2017, "restored", "Phase 2: ceiling boards, soffit, fascia and west wall below the windows replaced; new shutters painted; exterior scraped and painted.", "pdf2017", "nl2017f"),
             E(2018, "restored", "Phase 3: shutters installed and painted, stairs rebuilt, other maintenance, ending the three-year project.", "pdf2018"),
             E(2020, "restored", "Finishing touches for the rental program: handrails extended to meet OSHA rules and a way to secure the shutters in winter.", "pdf2020", "nl2020f"),
             E(2021, "modified", "Safety screen on the railing, windows made to open, and a privy vault installed.", "pdf2021", "nl2021w"),
             E(2021, "rental_opened", "The Libby District added it to the Recreation.gov rental program (a 2022 NMLA newsletter says 2023).", "pdf2021", "nl2021w"),
             E(2022, "restored", "Final scraping and painting to make it look as it did in 1957, closing the project begun in 2015.", "pdf2022", "nl2022"),
             E(2026, "restored", "Volunteers repaired shutter hardware bent by high winds.", "p2026"),
         ]),
    dict(slug="northwest-peak", name="Northwest Peak Lookout", tower="us-mt-northwest-peak", pos="nhlr:US 347", find=["Northwest Peak", "NW Peak", "North West Peak"], **KNF,
         design="Prototype gable-roof L-4 ground house; one of few surviving gabled L-4s",
         events=[
             E(1921, "other", "The site was first used as a patrol camp.", "p2025", "p2026"),
             E(1929, "built", "Prototype gable-roof L-4 ground house, forerunner of the classic L-4.", "p2025", "pdf2016"),
             E(1955, "abandoned", "Abandoned for fire detection.", "p2025", "p2026"),
             E(None, "restored", "Restored in the 1980s as a historic site.", "p2025", "p2026"),
             E(2016, "assessed", "Field condition assessment and a little project work on a Montana Wilderness Association trip.", "pdf2016", "nl2016f"),
             E(2017, "restored", "First phase of a multi-year restoration: ceiling boards removed, collar ties installed and ceiling joists secured to them.", "pdf2017", "nl2017f"),
             E(2018, "restored", "Second year: new shutters built and painted for later installation.", "pdf2018"),
             E(2022, "assessed", "Assessment: in very good shape overall, needing a lot of paint.", "pdf2022", "nl2022"),
             E(2024, "restored", "Windows removed and flown out by helicopter, plywood panels fitted; a pre-project assessment planned the next phase.", "nl2024", "pdf2024"),
             E(2025, "restored", "Windows flown back in June; volunteers stabilized all four walls and began installing the ceiling.", "p2025", "nl2025"),
         ]),
    dict(slug="sex-peak", name="Sex Peak Lookout", tower="us-mt-sex-peak", pos="nhlr:US 179", find=["Sex Peak"], **KNF,
         events=[
             E(2015, "restored", "NMLA's first renovation on the Kootenai NF: two walls repaired, cab ceiling cleaned, 76 window panes reglazed and painted, door and vent windows repaired.", "pdf2015", "nl2015"),
         ]),
    dict(slug="mcguire", name="McGuire Mountain Lookout", tower="us-mt-mcguire-mountain", pos="nhlr:US 345", find=["McGuire"], **KNF,
         aliases=["McGuire Lookout"], design="D-6 cupola cabin",
         discrepancies=["Built 1923 (2020 report) or 1924 (2026 post; the 2024 newsletter marks its 100th year).",
                        "Restored 1982 (2026 post) or renovated between 1983 and 1998 (2020 report)."],
         events=[
             E(1924, "built", "D-6 cupola lookout (the 2020 report says 1923).", "p2026"),
             E(1944, "abandoned", "Abandoned around this time.", "pdf2020", "nl2020f"),
             E(1982, "restored", "Restored after 35 years of abandonment and added to the rental system.", "p2026"),
             E(2016, "assessed", "First on-site condition assessment, the start of the long restoration project.", "pdf2016", "nl2023"),
             E(2020, "assessed", "In-depth assessment to prepare the next summer's restoration.", "pdf2020", "nl2020f"),
             E(2021, "restored", "Windows reglazed off-site at Murphy Lake Ranger Station, building squared and levelled, siding and trim repaired, painted inside and out, new shutters.", "pdf2021", "nl2021w"),
             E(2022, "restored", "With the rental closed for a week, final touches on the shutters for the cabin and cupola windows; outhouse pit started.", "pdf2022", "nl2022"),
             E(2023, "restored", "Outhouse moved onto a new vault and the lookout and both support structures re-roofed, completing the project.", "pdf2023", "nl2023"),
             E(2024, "restored", "Storage shed repaired and painted and a summer shutter-storage cover built, in the lookout's 100th year.", "nl2024", "pdf2024"),
             E(2026, "restored", "Cupola shutters converted back to the original hinged system, spot painting and ventilation screens.", "p2026"),
         ]),
    dict(slug="mount-wam", name="Mount Wam Lookout", tower="us-mt-wam-mountain", pos="nhlr:US 350", find=["Wam"], **KNF,
         aliases=["Wam Mountain Lookout", "Wam Lookout"], staffing="unstaffed",
         design="Gable-roof L-4 ground house, one of the last gabled L-4s",
         events=[
             E(1931, "built", "Built by the Forest Service on a 7,121-ft peak; last used for fire detection in the 1950s.", "p2025", "p2026", "nl2025"),
             E(2016, "assessed", "Condition assessment (April).", "pdf2016", "nl2016f"),
             E(2017, "restored", "Two-day assessment and maintenance trip: shutters repaired to last the winter.", "pdf2017", "nl2017f"),
             E(2018, "restored", "Building levelled, painted and new shutters installed, the start of a multi-year rehabilitation.", "pdf2018", "nl2023"),
             E(2019, "restored", "Fifteen days of major work: all windows removed and flown off for restoration, and the lookout boarded up in late September.", "pdf2019", "nl2019f"),
             E(2020, "restored", "Nineteen refurbished windows (171 panes) reinstalled, three window sills and headers and all siding replaced.", "pdf2020", "nl2020f"),
             E(2022, "fire", "Wrapped in protective structure wrap during the Weasel Fire.", "pdf2023", "nl2023"),
             E(2022, "restored", "Door reinstalled and the exterior painted; a new outhouse hole started.", "pdf2022", "nl2022"),
             E(2023, "restored", "Interior windows and exterior trim painted; the outhouse moved to a new vault dug into rock.", "pdf2023", "nl2023"),
             E(2024, "restored", "Pre-project assessment and repairs to the shutter braces.", "nl2024", "pdf2024"),
             E(2025, "restored", "New cedar-shingle roof, paid for through the Great American Outdoors Act.", "p2025", "nl2025"),
             E(2026, "restored", "Damaged shutters repaired and secured, and a new shutter built for the entry door.", "p2026"),
         ]),
    dict(slug="berray-mountain", name="Berray Mountain Lookout", tower="us-mt-berray-mountain", pos="nhlr:US 181", find=["Berray"], **KNF,
         events=[
             E(2017, "assessed", "Assessment before restoration planning; the lookout had been unstaffed for years.", "pdf2017", "nl2017f"),
             E(2017, "restored", "The Cabinet District installed a new roof to stop water damage (a Forest Service project).", "pdf2017", "nl2017f"),
         ]),
    dict(slug="star-peak", name="Star Peak Lookout", tower="us-mt-star-peak", pos="nhlr:US 178", find=["Star Peak", "Star Lookout", "Star Condition"], **KNF,
         design="L-4 hip-roof cab on a stone base; the 1910 stone cabin still stands below it",
         discrepancies=["L-4 cab built 1930 (2022 newsletter) or 1957 (2024 newsletter)."],
         events=[
             E(1910, "built", "Stone cabin built for the lookout; NMLA calls the site the first recorded lookout in Montana.", "nl2022", "pdf2023", "nl2023"),
             E(1933, "staffed", "Staffed by Wag Dodge, later the foreman of the Mann Gulch fire.", "nl2023"),
             E(2003, "staffed_last", "Staffed and maintained until 2003.", "nl2024"),
             E(2022, "assessed", "Assessment to document restoration needs for the Cabinet District.", "pdf2022", "nl2022"),
             E(2023, "restored", "Windows flown out; re-roofed with cedar shingles and the exterior scraped and painted, with Great American Outdoors Act funding.", "pdf2023", "nl2023"),
             E(2024, "restored", "Windows restored at spring workshops and helicoptered back in June; new shutters, interior and exterior painted, leaving it in restored condition.", "nl2024", "pdf2024"),
         ]),
    dict(slug="mount-henry", name="Mount Henry Lookout", tower="us-mt-mount-henry", pos="nhlr:US 346", find=["Mount Henry", "Mt Henry"], **KNF,
         staffing="emergency", design="L-4 with a 14x14-ft cab and catwalk on a 10-ft log tower", height_ft=10,
         discrepancies=["Abandoned 1973 (2026 post) or out of use since 1978 (2023 newsletter)."],
         events=[
             E(1925, "other", "First lookout on the site: a stone-and-frame cupola lookout built by the Kootenai NF.", "p2026"),
             E(1942, "replaced", "The current L-4 cab on a log tower replaced it.", "p2026", "nl2023"),
             E(1973, "abandoned", "Abandoned (a 2023 newsletter says out of use since 1978); now used only in emergencies.", "p2026"),
             E(None, "restored", "Partly restored in the 1990s.", "p2026"),
             E(2016, "assessed", "Condition assessment (August).", "pdf2016", "nl2016f"),
             E(2023, "assessed", "Assessment: pretty good shape but needs a major paint job and a few panes; the outhouse is propped up after being flattened.", "pdf2023", "nl2023"),
             E(2026, "assessed", "Assessment, aiming at a major restoration in coming years.", "p2026"),
         ]),
    dict(slug="lost-horse", name="Lost Horse Lookout", tower="us-mt-lost-horse", pos="nhlr:US 1510", find=["Lost Horse"], **KNF,
         design="L-4 cab on a wooden tower, with a ventilation 'butter box'",
         events=[
             E(1934, "built", "Built 1934.", "pdf2023"),
             E(1994, "fire", "Wrapped in protective covering during the Yaak-Red Dragon Complex Fire.", "pdf2023"),
             E(2023, "assessed", "Assessment by a re-flagged route: catwalk, steps, railings and shutters need repair and the roof has holes; the cab interior is intact.", "pdf2023"),
         ]),
    dict(slug="stahl-peak", name="Stahl Peak Lookout", tower="us-mt-stahl-peak", pos="nhlr:US 1501", find=["Stahl"], **KNF,
         design="D-6 cupola-style cabin",
         discrepancies=["Built 1926 (2026 post) or finished in spring 1927 (2024 newsletter)."],
         events=[
             E(1926, "built", "Cabin kit packed in by mule in fall 1926 (finished spring 1927, says a 2024 newsletter); used for fire detection into the 1960s.", "p2026", "nl2024"),
             E(2023, "assessed", "Assessment: in disrepair, needing paint and basic carpentry; a common shelter for Continental Divide hikers.", "pdf2023", "nl2023"),
             E(2024, "restored", "Five-day project: cab and cupola cleaned, exterior scraped and painted twice, two repaired cupola windows reinstalled, shutters repaired, rodent-proofing.", "nl2024", "pdf2024"),
             E(2026, "assessed", "Pre-project assessment for planned window, shutter and south-wall restoration.", "p2026"),
         ]),
    dict(slug="big-creek-baldy", name="Big Creek Baldy Lookout", tower="us-mt-big-creek-baldy", pos="nhlr:US 341", find=["Big Creek Baldy"], **KNF,
         design="15x15-ft flat-top cab on a 41-ft tower", height_ft=41,
         events=[
             E(1929, "built", "There has been a lookout on the mountain since 1929.", "nl2025"),
             E(1966, "replaced", "The current 15x15-ft flat-top cab on a 41-ft base was built.", "nl2025"),
             E(2020, "assessed", "One of four Libby District assessments that set the 2021 priorities.", "pdf2020", "nl2020f"),
             E(2022, "restored", "New rubber-membrane roof installed by a specialist crew with an NMLA board member; lightning protection made functional.", "pdf2022", "nl2022"),
             E(2023, "modified", "A heater was installed with the Forest Service for the rental; roof and hatch fine-tuned.", "pdf2023", "nl2023"),
             E(2025, "restored", "Landings secured with new handrails, wire mesh on the catwalk and a new catwalk railing.", "nl2025"),
         ]),
    dict(slug="swede-mountain", name="Swede Mountain Lookout", tower="us-mt-swede-mountain", pos="nhlr:US 1508", find=["Swede"], **KNF,
         aliases=["Big Swede Lookout", "Big Swede"], staffing="staffed",
         events=[
             E(2019, "restored", "New roof installed in early October by a roofing firm and an NMLA board member, between staffing seasons.", "pdf2019"),
             E(2020, "assessed", "One of four Libby District assessments that set the 2021 priorities.", "pdf2020", "nl2020f"),
             E(2020, "restored", "Further stabilizing work on the roof.", "pdf2021", "nl2021w"),
             E(2021, "restored", "Two projects: 52 windows glazed and catwalk and landing posts and railings replaced; then the lookout scraped, sanded and painted.", "pdf2021", "nl2021w"),
         ]),
    dict(slug="robinson", name="Robinson Lookout", tower="us-mt-robinson-mountain", pos="nhlr:US 348", find=["Robinson"], **KNF,
         aliases=["Robinson Mountain Lookout"], design="Gable-roof cupola cabin, 12x14 ft, shake and frame",
         discrepancies=["The 2022 reports give about 7,600 ft and a 1921 site date, which match Northwest Peak; the 2026 post gives 7,404 ft."],
         events=[
             E(1929, "built", "One of the few remaining gable-roof cupola lookouts in the region.", "p2026"),
             E(1948, "abandoned", "Abandoned.", "p2026"),
             E(1983, "restored", "Restored to serviceable condition by the Kootenai NF.", "p2026"),
             E(2022, "assessed", "Restoration assessment: needs a little help.", "pdf2022", "nl2022"),
             E(2026, "assessed", "Assessment: good condition; future structural work needed alongside regular maintenance.", "p2026"),
         ]),
    dict(slug="keeler-mountain", name="Keeler Mountain Lookout", tower="us-mt-keeler-mountain", pos="nhlr:US 1114",
         find=["Keeler"], **KNF, staffing="unstaffed", design="R-6 flat cab on a 53-ft treated-lumber tower, the third lookout on the site", height_ft=53,
         position_note="Copied from NHLR like the rest. NMLA puts it about 10 miles south of Troy, which fits FFLA's coordinates (48.3204, -115.8947) and not NHLR's, 30 km away.",
         events=[
             E(1924, "other", "First structures on the site: a 50-ft platform tower and a log cabin (the cabin still stands).", "p2026"),
             E(1934, "replaced", "A 50-ft pole tower with an L-4 cab replaced the platform tower.", "p2026"),
             E(1963, "replaced", "The present 53-ft treated-lumber R-6 tower, the third lookout on the site.", "p2026"),
             E(2026, "assessed", "Assessment with the Forest Service on reactivating it as a staffed lookout; lightning protection is the top upgrade; access is closed to protect grizzly habitat.", "p2026"),
         ]),
    dict(slug="zeigler-mountain", name="Zeigler Mountain Lookout", tower="us-mt-ziegler-mountain", pos="nhlr:US 351", find=["Ziegler", "Zeigler"], **KNF,
         aliases=["Ziegler Mountain Lookout"], staffing="unstaffed",
         design="R-6 flat-top cab on a 32-ft treated-timber tower with catwalk", height_ft=32,
         events=[
             E(1915, "other", "First structures on the site: a log cabin and a three-legged platform tower.", "p2026"),
             E(1928, "replaced", "A second platform tower.", "p2026"),
             E(1933, "replaced", "A 30-ft pole L-4 tower.", "p2026"),
             E(1959, "replaced", "The present 32-ft treated-timber R-6 flat-top tower with catwalk.", "p2026"),
             E(2020, "assessed", "One of four Libby District assessments that set the 2021 priorities.", "pdf2020", "nl2020f"),
             E(2026, "assessed", "Assessment for restaffing: tower, catwalk and cab exterior good; photos through two removed shutters show a good interior with basic restaffing equipment.", "p2026"),
         ]),
    dict(slug="blue-mountain", name="Blue Mountain Lookout", tower="us-mt-blue-mountain-kootenai-nf", pos="nhlr:US 342", find=["Blue Mountain"], **KNF,
         events=[
             E(2020, "assessed", "One of four Libby District assessments that set the 2021 priorities.", "pdf2020", "nl2020f"),
         ]),
    # NMLA writes "Robert's Lookout"; the tower is already "Roberts Mountain Lookout (now at ...)", so
    # the record uses that name (NMLA's spelling is an alias) rather than renaming the tower.
    dict(slug="roberts", name="Roberts Mountain Lookout", aliases=["Robert's Lookout"], tower="us-mt-roberts-mountain-at-tobacco-valley-historical-village",
         pos="ffla:mt:tobacco-valley-historical-village-relocated-roberts-mountain:48.8768:-115.0521", find=["Robert"],
         unit="Tobacco Valley Historical Village, Eureka", agency=None, ownership=None,
         events=[
             E(2024, "other", "NMLA helped make an interpretive sign telling the story of the lookout, now at the Tobacco Valley Historical Village in Eureka.", "nl2024", "pdf2024"),
         ]),
    # ------------------------------------------------------------------ Montana DNRC
    dict(slug="little-napa", name="Little Napa Lookout", tower="us-mt-little-napa-point", pos="nhlr:US 1493", find=["Little Napa"], **DNRC,
         aliases=["Little Napa Point Lookout"],
         events=[
             E(2016, "assessed", "Condition assessment before the stair project.", "pdf2016", "nl2016f"),
             E(2016, "restored", "Stairs rebuilt for safety to a volunteer architect's plan: new stringers, two tiers of stairs and railings; DNRC supplied the materials.", "pdf2016", "nl2016f"),
             E(2017, "restored", "New larger weighted trap door and replaced catwalk decking and handrails, finishing the two-year project.", "pdf2017", "nl2017f"),
             E(2025, "assessed", "June assessment with DNRC: stairs, catwalk, cab and outhouse in good condition; small maintenance items and some follow-up on the tower.", "p2025", "nl2025"),
         ]),
    dict(slug="werner-peak", name="Werner Peak Lookout", tower="us-mt-werner-peak", pos="nhlr:US 1500", find=["Werner"], **DNRC,
         events=[
             E(2020, "restored", "First project under a new partnership with Stillwater State Forest: volunteers scraped and painted the exterior.", "pdf2020", "nl2020f"),
             E(2021, "restored", "Catwalk, railing and window trim painted and touched up; a new pit-toilet vault was installed by a board member's construction firm.", "pdf2021", "nl2021w"),
         ]),
]
