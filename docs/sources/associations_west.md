# Lookout associations of the West and the Rockies: who keeps project records

Survey of 2026-10-08 by the chapters-west agent. Scope: AK, AZ, CA, CO, HI, ID, MT, NV, NM, OR, UT, WA, WY and
the Black Hills of SD. The Northwest Montana Lookout Association is covered by `nwmt_projects`; this file
covers everyone else. Starting points were the FFLA "Communities and Links" page
(`firelookout.org/resources/links/`), FFLA's own chapter list (`/about-us/ffla-structure/`) and chapter reports
(`/about-us/current-reports/`, `/resources/archives/annual-reports/`), then a few searches for groups the FFLA
pages do not list.

What counts as a record: dated statements about work on, or the fate of, a particular lookout (restored,
repaired, assessed, rebuilt, lost to fire, staffed again). The framework for turning them into timeline
entries is `pipeline/regional/_projects.py` (DESIGN.md 3.7); the small sources use the driver in
`pipeline/regional/_assoc_site.py`. "Robots" means robots.txt was read before any page was fetched and
FirefinderBot is not excluded from the pages used. Every page used was fetched once, 2 s or more apart, and cached
under `data/raw/`. Two sites ask for a 10 s crawl delay (anffla.org and preservewa.org): the survey read their handful
of pages once each in a quick burst, closer together than that, and nothing more will be requested from them.

## 1. The big one: FFLA chapter reports

| | |
|---|---|
| Group | Forest Fire Lookout Association, chapter and division annual reports (plus the national Restoration Grants report) |
| URL | `https://firelookout.org/about-us/current-reports/` (latest year) and `https://firelookout.org/resources/archives/annual-reports/<year>-reports/` (2003 to 2024) |
| Robots | OK (disallows only `/wp-admin/` and WooCommerce/WPForms paths) |
| Records | One PDF per chapter per year: membership and money (ignored), then "projects and activities": which lookouts were repaired, repainted, reroofed, assessed, lost, reopened or staffed, with the forest. Some years' PDFs are compilations of every chapter's report. The Restoration Grants report lists each grant awarded (lookout, amount, purpose) |
| Years | 2003 to 2025 (2025 reports posted January 2026) |
| West volume | 212 PDFs from 28 chapters and local groups (list in section 6), about 710 KB of text. Six are image-only scans with no text layer: California Sierra-Nevada 2016, 2017, 2018 and 2019, Arizona-New Mexico 2004 and Oregon 2004 (read from page images; 2016 holds no project facts) |
| Lookouts | Several hundred named lookouts across all 14 states |
| Captured | `ffla_west_reports`: 248 lookouts, 491 dated events from 146 of the reports (section 6) |

This is by far the richest dated source: it spans two decades and every western chapter, and it names the
forest and the work. It is also the only record at all for the many chapters with no website.

## 2. Groups with their own websites, and what they hold

| Group | URL | Robots | Records and years | Lookouts | Captured |
|---|---|---|---|---|---|
| Sand Mountain Society (OR, FFLA affiliate) | `sandmountain.org/projects/` | OK | One page per project with a "Quick Facts" box and a list of major work by year, 1989 to 2026 | 8 (plus Whisky Peak and Mt. Scott mentioned) | `sand_mountain`: 10 lookouts, 45 events |
| Mountaineers, Everett Branch (WA) | `mountaineers.org/locations-lodges/everett-branch/committees/everett-lookout-trail-maintenance-committee/` | OK | One history page for Three Fingers, Pilchuck and Heybrook, 1980s to 2025 | 3 | `mountaineers_everett`: 3, 9 |
| Snoqualmie Fire Lookouts Association (WA, affiliate) | `snoqualmielookouts.org` | OK (Squarespace file; bots named, ours is not) | One page per lookout, build and restoration years | 3 (Suntop, Kelly Butte, Granite Mountain) | `snoqualmie_lookouts`: 3, 9 |
| Methow Valley FFLA (WA, sub-chapter formed 2023) | `mvffla.org` | OK (same Squarespace file) | Five news posts, 2023 to 2026 (some years inferred, see the module) | 5 of its 8 | `mvffla`: 5, 9 |
| Buck Rock Foundation (CA, affiliate) | `buckrock.org` | OK | Three lookout pages, an origin story and a news blog (2024 to 2026; maintenance days in 2025) | 3 | `buck_rock`: 3, 17 |
| Angeles National Forest FLA (CA, affiliate) | `anffla.org` | OK, but asks for a 10 s crawl delay (five pages read once in a quick burst and cached) | Statistics and history on four lookouts | 4 | `anffla`: 4, 10 |
| Southern California Mountains Foundation (CA, affiliate) | `mountainsfoundation.org/programs/fire-lookouts/` | OK | One page with a history paragraph per lookout, including two lost to fire in 2022 and 2024 | 7 | `scmf_lookouts`: 7, 17 |
| FFLA San Diego-Riverside Chapter (CA) | `ffla-sandiego.org` | OK | Two staffed-lookout pages and fourteen history pages for lost southern California towers | 16 | `ffla_sdrc`: 16, 37 |
| FFLA Monterey Chapter (CA) | `ffla-monterey.org` | OK | Chews Ridge history page (Cone Peak page has no dates) | 1 of 2 | `ffla_monterey`: 1, 5 |
| FFLA California South Division (CA) | `firelookouthost.org` (Wix) | OK | Bald Mountain page (2024 return to service); a roster table of 29 standing towers (a list, left to the lookout-list sources) | 1 | `ffla_ca_south`: 1, 2 |
| Hi Mountain Lookout Project (CA, affiliate) | `condorlookout.org` (Wix) | OK | One project history page | 1 | `hi_mountain`: 1, 3 |
| Siskiyou Mountain Club (OR) | `siskiyoumountainclub.org` | OK | Project post and a Forest Service story about rebuilding Bolan Mountain Lookout after the 2020 Slater Fire | 1 | `siskiyou_mountain_club`: 1, 4 |
| HistoriCorps (national, volunteer preservation crews) | `historicorps.org` | OK | Project pages: history, sessions and planned scope of work (announcements, not outcomes) | 4 western lookouts (Alder Ridge, Bunker Hill, Cement Ridge, Thorp Mountain) | `historicorps_west`: 4, 12 |
| Washington Trust for Historic Preservation and Washington Trails Association: Green Mountain Lookout (WA) | `preservewa.org/most_endangered/green-mountain-lookout/`, `wta.org/news/signpost/saving-green-mountain-lookout-a-retrospective` | OK (Trust asks for a 10 s delay; one page, cached; see the note above) | The 1987 to 2014 story of rehabilitation, a Wilderness Act lawsuit and the 2014 Act of Congress | 1 | `green_mountain_wa`: 1, 10 |

Total of the 14 website sources: 60 lookouts, 189 dated events. With `ffla_west_reports` the western set is 15
sources, 308 lookout records on 279 towers, 680 dated events; after a merge run every record sits on the tower it
names (checked by script) and 521 of the events show on tower timelines (the rest repeat an event and year another
source already gave).

## 3. Facebook-only or website-less groups (listed, not captured; no logins used)

| Group | What exists | Where its work shows up instead |
|---|---|---|
| Friends of Three Fingers Lookout (WA) | Facebook group, about 1,000 members | its own FFLA report (2024, 2025) and the Mountaineers page |
| Friends of Pilchuck Lookout, Friends of North Mountain, Snoqualmie group (WA) | Facebook | Mountaineers page (Pilchuck); FFLA Washington reports |
| Friends of Red Top (WA, FFLA sub-chapter forming 2025) | none | FFLA Washington report 2025 |
| Friends of Blue Mountains Lookouts (OR/WA; formed about 2019) | Facebook; a museum talk (2022) | FFLA Washington-East reports |
| Orleans Mountain Lookout group (CA, Six Rivers NF) | Facebook | FFLA California-North reports |
| Argentine Chapter and Friends of Argentine Rock Lookout (CA, Plumas NF) | Facebook; `argentinelookout.org` does not resolve | FFLA California-North reports; Plumas News articles |
| Konocti chapter (CA, Lake County; CAL FIRE tower) | Facebook | 2018 FFLA restoration grant for its floor; local news 2020 |
| Huckleberry Mountain Lookout (OR) | Facebook | Sand Mountain Society page (the "Friends of Huckleberry" group wound up in the 1990s) |
| FFLA Colorado-Utah chapter | Facebook; no site found | its yearly reports, 2007 to 2025 |
| FFLA California Pacific chapter | `ffla-ccwr.org` does not resolve | its reports 2010 to 2021 |
| FFLA Eastern Sierra and Yosemite-High Sierra chapters (CA) | none | reports (Yosemite-High Sierra 2011 to 2016; Sierra-Nevada scans unreadable) |
| Pechuck Look Outs (Molalla, OR) | none found | BLM's page for Pechuck; Sand Mountain Society page |
| Idaho Fire Lookouts | `idahofirelookouts.com` is already a Firefinder source (`idaho_fl`); its blog posts may record repairs | not read here |
| Lookouts R Us, Fire Tower Explorers, Oregon Fire Lookouts and the other Facebook groups on the FFLA page | discussion groups, no project logs | none |

## 4. Not captured, and why

* **Agency pages** (Forest Service, BLM, NPS) and hobby sites (`willhiteweb.com`, `trailchick.com`,
  `cherylhill.net` "Every Lookout in Oregon", `leslieromer.com`, Placer County's lookout page): histories and
  photos, not an association's work log, and several are other agents' lists.
* **`firelookouts.com` (the Historic Lookout Project)**: its home page carries a spam link to a marketplace
  site; treated as compromised and not read further.
* **Friends of Heybrook Ridge** (Index, WA): supports a county park, not the lookout (the lookout work is in
  the Mountaineers page).
* **Alaska and Hawaii**: no group, no register entry found.
* **Utah, Nevada, Wyoming, the Black Hills**: no association site; the only records are the FFLA chapter
  reports (Colorado-Utah; Wyoming 2007 to 2014; South Dakota-Wyoming 2025) and HistoriCorps at Cement Ridge.
* **Scanned reports** (listed in section 1): no OCR is installed, so the six image-only PDFs were read from page
  images instead and are not text-checked.

## 5. Leads for later

* FFLA's links page lists an "Argentine Chapter"; FFLA's structure page puts it in California-North (Argentine Rock
  Lookout, Plumas NF). It is not a Colorado group.
* FFLA's California South site has a roster of the chapter's 29 standing towers with NHLR numbers, operator
  and status (operational, closed, private). It is a list; hand it to the lookout-list agent.
* HistoriCorps runs lookout projects every year; only four western pages exist now, and they are announcements.
  Re-check `historicorps.org/project-sitemap.xml` each spring.
* High Rock Lookout (WA) was damaged in a deliberate attack in June 2026 (FFLA press release of 2026-06-12,
  reported by Outside, OPB and the Nisqually Valley News). Not yet in any source here; worth an event once the
  FFLA posts its report.
* Pechuck Look Outs, Friends of Hager Mountain and similar Oregon groups appear in news but have no site.
* FFLA's Lookout Network magazine archive (`/resources/archives/`) is not a project log, but its older issues
  could be read for pre-2003 history if the FFLA agrees.

## 6. FFLA chapter reports: what was read and what came out

Reports read (count, years): Arizona 18 (2007 to 2025) and Arizona-New Mexico 2 (2004, 2005); California North 19
(2004 to 2025), Pacific 8 (2010 to 2021), Central-Nevada 4 (2004 to 2009), Sierra-Nevada 8 (2010 to 2019),
Yosemite-High Sierra 3 (2011 to 2016), South 10 (2007 to 2025) with its local groups: Angeles NF 5 (2010 to 2017),
San Bernardino NF 4 (2010 to 2014), Southern California Mountains Foundation 1 (2017), San Diego-Riverside 8 (2009 to
2025), Monterey 4 (2019 to 2025), Bald Mountain 1 (2025); Colorado-Utah(-Wyoming) 14 (2007 to 2025); Idaho
North-Montana 23 (2003 to 2025) and Idaho South 6 (2006 to 2022); New Mexico 14 (2007 to 2025); Oregon 9 (2004 to
2017); Washington East 15 (2004 to 2018), West 1 (2004), Washington 2 (2024, 2025) and Friends of Three Fingers 2
(2024, 2025); Wyoming 6 (2007 to 2014), South Dakota-Wyoming 1 (2025); Western Deputy 5 (2004 to 2008) and
Northwestern Region 1 (2025); Restoration Grants 18 (2006 to 2025, the western lookouts only).

Method (details in `DESIGN.md` 3.7 and the `ffla_west_reports.py` docstring): eight agents read the reports by chapter
family and wrote one record per dated fact (lookout, forest, year, event, note in our words, a short verbatim run of
the report as evidence); a script checked each record against the PDF text, dropped plans, funding, site visits,
register nominations and uncertain years on status events, matched lookouts to towers, and the 30
ambiguous or unmatched names were settled by hand. 890 records were read in; 556 passed the filter; 491 events on 248 towers were kept after
joining duplicates.

By state (lookouts / events): CA 71 / 140, ID 41 / 70, NM 39 / 91, WA 38 / 77, MT 19 / 44, OR 19 / 23, CO 7 / 25,
WY 6 / 12, NV 5 / 6, AZ 1 / 1, SD 1 / 1, UT 1 / 1. By event: restored 195, other 53 (grants and agreements), built 51
(New Mexico's 2020 compendium gives most), assessed 35, staffed 22, modified 21, fire 18, burned 17, nrhp_listed 15,
replaced 14, removed 13, rental_opened 10, relocated 9, staffed_last 6, destroyed 5, abandoned 4, closed 2, rebuilt 1.
Years run from 1921 to 2025.

Not captured from the reports: 13 names that matched no tower or several (examples: Falls Point (Lolo NF, MT), Hughes
Ridge (WA), Tillamook Forest Interpretive Center, the museum replica of an L-4 near Missoula, Sid Ormsby and the
Moran Patrol Cabin); the Northwest Montana Lookout Association items (covered by
`nwmt_projects`); non-western chapters, including the eastern sections of the combined 2009 PDF (a matching reading of
the eastern chapters' reports belongs to the east survey); and anything in plans or hopes.
