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
FirefinderBot is not excluded from the pages used. Every page used was fetched once, 2 s or more apart (10 s
where the site asks for it), and cached under `data/raw/`.

## 1. The big one: FFLA chapter reports

| | |
|---|---|
| Group | Forest Fire Lookout Association, chapter and division annual reports (plus the national Restoration Grants report) |
| URL | `https://firelookout.org/about-us/current-reports/` (latest year) and `https://firelookout.org/resources/archives/annual-reports/<year>-reports/` (2003 to 2024) |
| Robots | OK (disallows only `/wp-admin/` and WooCommerce/WPForms paths) |
| Records | One PDF per chapter per year: membership and money (ignored), then "projects and activities": which lookouts were repaired, repainted, reroofed, assessed, lost, reopened or staffed, with the forest. Some years' PDFs are compilations of every chapter's report. The Restoration Grants report lists each grant awarded (lookout, amount, purpose) |
| Years | 2003 to 2025 (2025 reports posted January 2026) |
| West volume | 212 PDFs from 28 chapters and local groups (list in section 5), about 710 KB of text. Eight are image-only scans with no text layer: California Sierra-Nevada 2016, 2017, 2018 and 2019, Arizona-New Mexico 2004, Oregon 2004, and two or three short New Mexico and Angeles NF scans |
| Lookouts | Several hundred named lookouts across all 14 states |
| Captured | `ffla_west_reports` (see section 6 for numbers) |

This is by far the richest dated source: it spans two decades and every western chapter, and it names the
forest and the work. It is also the only record at all for the many chapters with no website.

## 2. Groups with their own websites, and what they hold

| Group | URL | Robots | Records and years | Lookouts | Captured |
|---|---|---|---|---|---|
| Sand Mountain Society (OR, FFLA affiliate) | `sandmountain.org/projects/` | OK | One page per project with a "Quick Facts" box and a list of major work by year, 1987 to 2026 | 8 (plus Whisky Peak and Mt. Scott mentioned) | `sand_mountain`: 10 lookouts, 45 events |
| Mountaineers, Everett Branch (WA) | `mountaineers.org/locations-lodges/everett-branch/committees/everett-lookout-trail-maintenance-committee/` | OK | One history page for Three Fingers, Pilchuck and Heybrook, 1980s to 2026 | 3 | `mountaineers_everett`: 3, 9 |
| Snoqualmie Fire Lookouts Association (WA, affiliate) | `snoqualmielookouts.org` | OK (Squarespace file; bots named, ours is not) | One page per lookout, build and restoration years | 3 (Suntop, Kelly Butte, Granite Mountain) | `snoqualmie_lookouts`: 3, 9 |
| Methow Valley FFLA (WA, sub-chapter formed 2023) | `mvffla.org` | OK (same Squarespace file) | Five news posts, 2021 to 2026 (year inferred, see the module) | 5 of its 8 | `mvffla`: 5, 9 |
| Buck Rock Foundation (CA, affiliate) | `buckrock.org` | OK | Three lookout pages, an origin story and a news blog (2024 to 2026; maintenance days in 2025) | 3 | `buck_rock`: 3, 17 |
| Angeles National Forest FLA (CA, affiliate) | `anffla.org` | OK, but asks for a 10 s crawl delay (pages read once and cached) | Statistics and history on four lookouts | 4 | `anffla`: 4, 10 |
| Southern California Mountains Foundation (CA, affiliate) | `mountainsfoundation.org/programs/fire-lookouts/` | OK | One page with a history paragraph per lookout, including two lost to fire in 2022 and 2024 | 7 | `scmf_lookouts`: 7, 17 |
| FFLA San Diego-Riverside Chapter (CA) | `ffla-sandiego.org` | OK | Two staffed-lookout pages and fourteen history pages for lost southern California towers | 16 | `ffla_sdrc`: 16, 37 |
| FFLA Monterey Chapter (CA) | `ffla-monterey.org` | OK | Chews Ridge history page (Cone Peak page has no dates) | 1 of 2 | `ffla_monterey`: 1, 5 |
| FFLA California South Division (CA) | `firelookouthost.org` (Wix) | OK | Bald Mountain page (2024 return to service); a roster table of 29 standing towers (a list, left to the lookout-list sources) | 1 | `ffla_ca_south`: 1, 2 |
| Hi Mountain Lookout Project (CA, affiliate) | `condorlookout.org` (Wix) | OK | One project history page | 1 | `hi_mountain`: 1, 3 |
| Siskiyou Mountain Club (OR) | `siskiyoumountainclub.org` | OK | Project post and a Forest Service story about rebuilding Bolan Mountain Lookout after the 2020 Slater Fire | 1 | `siskiyou_mountain_club`: 1, 4 |
| HistoriCorps (national, volunteer preservation crews) | `historicorps.org` | OK | Project pages: history, sessions and planned scope of work (announcements, not outcomes) | 4 western lookouts (Alder Ridge, Bunker Hill, Cement Ridge, Thorp Mountain) | `historicorps_west`: 4, 12 |
| Washington Trust for Historic Preservation and Washington Trails Association: Green Mountain Lookout (WA) | `preservewa.org/most_endangered/green-mountain-lookout/`, `wta.org/news/signpost/saving-green-mountain-lookout-a-retrospective` | OK (Trust asks for a 10 s delay; one page, cached) | The 1987 to 2014 story of rehabilitation, a Wilderness Act lawsuit and the 2014 Act of Congress | 1 | `green_mountain_wa`: 1, 10 |

Total of the captured website sources: 14 sources, 61 lookouts, about 190 dated events, every record placed on
the tower it names (checked after a merge run; see section 6).

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
* **Scanned reports** (listed in section 1): readable only with OCR (not installed).

## 5. Leads for later

* The brief called the Argentine chapter "(CO)"; FFLA's structure page puts it in California-North (Argentine
  Rock Lookout, Plumas NF). There is no Colorado Argentine group.
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

## 6. FFLA chapter reports read (west), by chapter

(See the final section for what was extracted.)

