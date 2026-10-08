# Lookout associations in the East, South and Midwest: survey for dated project records

Surveyed 2026-10-08 by the chapters-east agent. Region: every state not in the West or the Rockies (the
West covers AK, AZ, CA, CO, HI, ID, MT, NV, NM, OR, UT, WA, WY and the Black Hills of SD), so this covers
New England, the Mid-Atlantic, the South, the Midwest and the Plains (rest of SD, ND, NE, KS, OK, TX). The
western half is `associations_west.md`.

The question asked of each group: does it keep **dated records of work on particular lookouts** (project
posts, annual reports, newsletters, restoration logs), the way the Northwest Montana Lookout Association
does? Groups that do were turned into association-project sources (DESIGN.md 3.7); the rest are listed
with the reason. robots.txt was read for every host before any page was fetched (2 s between requests to a
host, longer where `Crawl-delay` asks); nothing behind a login, bot check, 403 or robots rule was read.

**Result.** The East has no regional lookout association with a project archive like NMLA's. The records
are in three places: one state chapter that publishes a monthly newsletter (New York, 2016 to 2026); a score
of single-tower "Friends of" groups, almost all in the Adirondacks and Catskills, of which nine keep a log
or yearly newsletters that could be read; and the FFLA's own archive of yearly chapter reports (2003 to
2025), which is the only written record of the chapters that otherwise exist only on Facebook. Eleven
sources are built from them: 206 lookout records on 163 towers, 514 dated events, every record matched to
the tower intended (0 mismatches, 0 unplaced).

## A. Captured: association-project sources (modules in `pipeline/regional/`, extracts in `data/sources/`)

| Source id | Group and URL | Robots | What it publishes | Events span | Lookouts / events | Notes |
|---|---|---|---|---|---|---|
| `nysffla_projects` | FFLA New York State Chapter, https://www.nysffla.org/ | no robots.txt | monthly newsletter PDFs with an "Updates" paragraph per tower, project reports and history features (121 issues, January 2016 to July 2026); a projects page listing 18 work weekends (photo pages carry no text) | 1887 to 2026 | 75 / 227 | read by agents, curated, and every cited issue re-checked for the tower's name and the year. Towers outside NY, undated work, plans and trail closures left out. Two issue files are filed under the wrong month, the March 2026 file repeats April's, and there are no issues for September 2016, December 2023, December 2024 or October-December 2021 |
| `ffla_east_reports` | FFLA chapter and restoration-grant reports, https://firelookout.org/resources/archives/annual-reports/ | allows all but WooCommerce paths | one PDF per chapter per year: staffing, site visits, repairs, losses; the Restoration Grants report lists each grant | 1928 to 2025 | 122 / 217 | 236 PDFs for the eastern chapters read, 96 cited; see C |
| `st_regis_friends` | Friends of St. Regis Mountain Fire Tower, http://www.friendsofstregis.org/ | allows all but /wp-admin/ | one dated work log (`/restoration/`, a section per year) | 2014 to 2026 | 1 / 13 | stairs and floor (2015), roof and reopening (2016), 24 new braces (2018-19), view panels, painting, fence replacement under way |
| `mt_arab_friends` | Friends of Mount Arab, https://friendsofmtarab.org/ | `Crawl-delay: 10`, honoured | one newsletter a year (PDF) and a history page | 1918 to 2024 | 1 / 17 | 2010 is an image-only PDF; 2013 and 2016 lost their body text in conversion (no OCR here) |
| `azure_mountain_friends` | Azure Mountain Friends, https://www.azuremountain.org/ | Squarespace robots.txt: general bots allowed, named AI-training bots disallowed (FirefinderBot is not one of them) | chronology page and yearly newsletters | 1914 to 2018 | 1 / 10 | the 2005 newsletter has no text layer |
| `bald_mountain_friends` | Friends of Bald (Rondaxe) Mountain, https://www.masterpieces.com/bald.htm | no robots.txt | hand-made progress-report pages, one per season | 1990 to 2023 | 1 / 10 | the 2010-2021 report pages named on the index return "not found" |
| `hurricane_friends` | Friends of Hurricane Mountain, https://www.hurricanefiretower.org/ | allows all but /wp-admin/ | tower history and restoration timeline pages | 1919 to 2015 | 1 / 5 | the 2019 centennial post gives work without dates and is not used |
| `bramley_friends` | Friends of Bramley Mountain Fire Tower, https://bramleymountainfiretower.org/ | allows all but /wp-admin/ | tower history, project news posts | 1950 to 2025 | 1 / 6 | a tower dismantled in 1975 and rebuilt on its summit in 2024 |
| `stillwater_friends` | Friends of Stillwater Fire Tower, http://www.friendsofstillwaterfiretower.com/ | no robots.txt | a 2018 brochure with the tower's dates; the rest is photos and donors | 1882 to 2017 | 1 / 5 | the 2016 work itself is in the NYS FFLA source |
| `kent_conservation_foundation` | Kent Conservation Foundation (for the Town of Kent Conservation Advisory Committee), https://thekcf.org/ | no robots.txt | two project posts on the Mount Nimham tower | 2015 to 2017 | 1 / 2 | the CAC's own site (kentcac.info) dates none of the tower work |
| `smokies_friends` | Friends of the Smokies, https://friendsofthesmokies.org/ | `Crawl-delay: 3`, honoured | a 2016 blog post (the Cammerer tower was its first project, 1995) and Smoky Mountain News's 2023 report on the Forever Places repairs | 1995 to 2023 | 1 / 2 | the group's own Forever Places page names no tower, so 2023 is cited to the news report |

## B. FFLA chapters and affiliates from https://firelookout.org/resources/links/

| Group | Real website? | Dated records? | What was done |
|---|---|---|---|
| FFLA New York State Chapter | https://www.nysffla.org/ | yes: newsletters, projects, friends list | `nysffla_projects` |
| Friends of St. Regis Mountain Fire Tower (NY) | http://www.friendsofstregis.org/ | yes: yearly work log; newsletters and annual reports (PDFs on its news page, not read) | `st_regis_friends` |
| Friends of Stissing Landmarks (NY) | https://stissingfiretower.org/ | the history page is built by JavaScript and its text is in neither the page nor the WordPress REST data; news is on Instagram | not captured. Third party: the New Pine Plains Herald ("FOSL Completes Major Project at Stissing Mountain Fire Tower") |
| Friends of Sterling Forest (NY) | friendsofsterlingforest.org is now a **hijacked domain** serving online-gambling spam (checked 2026-10-08); the real group is on Facebook only | no | not captured. Sterling's work is in the NYS FFLA newsletters and in Team Rubicon's write-up (teamrubiconusa.org, July and November 2017) |
| Azure Mountain Friends (NY) | https://www.azuremountain.org/ | yes: chronology, newsletters | `azure_mountain_friends` |
| Kent Conservation Advisory Committee (Nimham, NY) | the town page 404s; kentcac.info is the committee's information site | no dated tower work there | the Kent Conservation Foundation (thekcf.org) does: `kent_conservation_foundation` |
| Friends of Poke-O-Moonshine (NY) | https://www.pokeomoonshine.org/ | the site is a JavaScript site builder; its pages (history, news) arrive empty without scripts, although the sitemap lists news posts from 2016 to 2023 | not captured. The readable third-party records: AARCH's 2005 reopening PDF (aarch.org/wp-content/uploads/2014/09/050617VLPPokeOopening1.pdf) and the Cloudsplitter Foundation project page |
| Friends of Hurricane Mountain (NY) | https://www.hurricanefiretower.org/ | yes | `hurricane_friends` |
| Friends of Mount Arab (NY) | https://friendsofmtarab.org/ | yes | `mt_arab_friends` |
| Friends of Bald Mountain (NY) | https://www.masterpieces.com/bald.htm | yes | `bald_mountain_friends` |
| Friends of Bramley Mountain (NY) | https://bramleymountainfiretower.org/ | yes | `bramley_friends` |
| Hadley Mountain Fire Tower Committee (NY) | https://hadleymtfiretower.org/ | JavaScript site (committee, gallery, events, hike information), no history | not captured. Third party: Adirondack Almanack, "20 Years of the Hadley Mountain Fire Tower Committee" |
| Friends of Stillwater Fire Tower (NY) | http://www.friendsofstillwaterfiretower.com/ | one brochure | `stillwater_friends` |
| Cornell Hill Fire Tower (Town of Wilton, NY) | https://townofwilton.com/visitors/cornell-hill-fire-tower/ | a visitor page, no history | the tower's move and restoration are in the NYS FFLA source |
| Balsam Lake Mountain (viewsandbrews.com) | one person's page for the FFLA chapter | patches and schedule only | not captured |
| Friends of Mount Beacon | Facebook only | | skipped (never logged in) |
| Catskill Center, Catskill Fire Tower Project | https://www.catskillcenter.org/firetowers | six towers (Balsam Lake, Red Hill, Tremper, Overlook, Hunter, Upper Esopus) with built years and a 2019 rebuild; no project history, news or reports page for the towers | not captured. robots.txt carries a Cloudflare "Content-Signal: ai-train=no" and disallows ClaudeBot and other AI crawlers by name; FirefinderBot is not named and only the one page was read for facts, but the owner may prefer not to use the site further. The Catskill reopenings 1999 to 2001 are dated in the NYS FFLA newsletters instead |
| Adirondack Mountain Club, Fire Tower Challenge | https://adk.org/adk-fire-tower-challenge/ | the challenge list and rules; no restoration log | not captured (robots.txt has content signals) |
| Adirondack Architectural Heritage (AARCH) | https://aarch.org/preserve/fire-towers/ | a regional list of every Adirondack tower with who restored it (no years) | not captured: no dates |
| Indiana, Maine, Massachusetts, North Carolina, Pennsylvania, Southern Region, Tennessee, Virginia-West Virginia chapters | **Facebook only** | no | their only written record is the FFLA yearly chapter report (section C) |
| NH Fire Towers, North Carolina Fire Towers, WV fire lookouts, Save the Deer Mt. Fire Tower (Facebook groups) | Facebook only | | skipped |
| New Hampshire Fire Towers (state Division of Forests and Lands) | https://www.nhdfl.dncr.nh.gov/forest-protection/fire-towers | answers **403 Forbidden** to the bot, so not read | not captured. The NH chapter's yearly report says which of the 15 state towers were staffed |
| Indiana Lookout Towers (Hoosier National Forest) | https://www.fs.usda.gov/detail/hoosier/landmanagement/resourcemanagement/?cid=fsbdev3_017555 | a national-forest history page, not an association | not captured |
| Lookout Tower Challenge (Carolina Mountain Club, NC) | https://carolinamountainclub.org/ | the challenge checklist; the old "LTC Preservation" page is gone | not captured. The NC chapter's reports (section C) cover its towers |

## C. FFLA's own chapter reports (the archive behind the chapters)

The FFLA publishes every chapter director's yearly report, with the national officers' reports, at
https://firelookout.org/resources/archives/annual-reports/ (2003 to 2024) and
https://firelookout.org/about-us/current-reports/ (2025): 493 PDFs. 236 are for chapters in this region or
national reports about it (Restoration Grants, Historian, Archivist, SHPO, Eastern and Southern Deputy).
They are one to three pages: membership and money, then which towers were staffed, repaired, moved, lost.
The Facebook-only chapters appear nowhere else in writing. All 236 were fetched (2 s apart) and read in six
batches; `ffla_east_reports` holds 217 events on 122 lookouts (ME 23, NY 36, NH 14, VT 11, MA 9, IN 6, NC 5,
RI 4, IL 2, OH 2, TN 2, and one each in AR, KY, LA, MN, NJ, SC, WI, WV). What is left out, by rule, as in
`ffla_west_reports`: the registers' own dates (no `nhlr_registered` or National Register events), plans and
hopes, bare site visits, "closed as of this report" without a start year, status events whose year the report
only approximates, observation towers, and towers our lists cannot place (the two Missouri towers moved to
Indiana, a Minnesota fairgrounds tower, the Crane Navy towers). The grants are kept as `other`.

Not read: five image-only scans (Pennsylvania 2004, 2005, 2008, 2009 and the 2009 Historian) and New
Hampshire 2024, whose PDF decodes to nonsense (no OCR here). The combined 2009 PDF filed under Arizona
repeats the Arkansas, Kentucky, Maine, New Hampshire, North Carolina, Vermont, Virginia and Restoration
Grants reports word for word, so it adds nothing for this region.

Thin reports: the Pennsylvania chapter's 2025 report is half a page (it runs through a Facebook group of
350 members), the Western North Carolina chapter's lists site visits and trail clearing, and the New
Hampshire chapter's says which state towers volunteers staffed and nothing else; hence the many chapters with
one or two events.

## D. Other groups found by search (no usable dated record, or not an association)

| Group | Why not captured |
|---|---|
| Loon Echo Land Trust (Pleasant Mountain, ME) | trail pages and grant news; the tower itself is not dated |
| Friends of Ouabache State Park (IN) | raised $75,000 for the 1939 CCC tower; the only account is Indiana Landmarks, "Friends Group Ignites Fire Tower Renovation" (27 July 2017: closed 2015, repairs to begin, reopening hoped for spring 2018); the FFLA Indiana reports give the 2018 reopening, which is captured in `ffla_east_reports` |
| Friends of Rib Mountain State Park (WI) | a park friends group; its site carries no tower history |
| Hickory Flats Fire Tower (Rowan County, KY) | a county government page, not an association |
| Pennsylvania Lumber Museum (Potter County, PA) | a museum re-erecting and restoring a 1922 Blaw-Knox tower (September 2026 press coverage); one event, not an association's record |
| PA DGS / DCNR fire tower program | a state programme that rehabilitated or replaced 53 Pennsylvania towers; the contractor's page (e2pm.com/pafire_tower) is the best dated record. Not an association, so not read further: a good lead for a Pennsylvania state-forests source |
| Glastenbury and Stratton towers (VT) | a U.S. Forest Service repair project (fs.usda.gov/r09/gmfl/projects/304273); the Green Mountain Club's own record was not found |
| Friends of Glastenbury, Friends of the Fire Tower (CT/MA) | Facebook only |
| Appalachian Trail Conservancy (Rich Mountain, Wayah Bald, Georgia towers) | trail club; the restorations are in the ATC magazine ("A View Worth Saving", spring 2019) and Forest Service pages |
| Appomattox fire tower (VA, 2026 press) | a private owner, not an association |
| indianafiretowers.com (Mark A.) | a hobbyist guide to 40+ Indiana towers with histories; a lookout list for links-survey, not a project record |

## E. Leads left over

* **Poke-O-Moonshine, Hadley, Stissing**: JavaScript sites with a news archive that a browser can read but
  FirefinderBot cannot. A person could copy the dates.
* **Mount Arab 2010, 2013, 2016 newsletters, Azure 2005 newsletter, five Pennsylvania FFLA reports, NH 2024**:
  image-only or garbled PDFs; an OCR pass would add some events.
* **Pennsylvania's 53-tower state programme** (above): the single richest dated record for the state.
* **Vermont**: eight state towers had cab railings, roofs or white-oak stairs in 2023 to 2025; the Vermont
  chapter's reports date some (captured), the state's own documents the rest.
* **Lookouts the newsletters mention that Firefinder lacks**: a private lookout at Foolish Farms, Mount Vision
  (NY, opened 2 July 2021); the Trout Mountain, ME rebuild; the Jackson Township, NJ replacement tower; Vermont's
  Bromley observation tower (not a fire tower). None added: no positions were stated.
* **Lookout Network** (the FFLA magazine, quarterly) is members-only in part and was not read.
* **Lists for links-survey**: indianafiretowers.com, michiganfiretower.com's tower list, the FFLA state
  "additional information" pages.
