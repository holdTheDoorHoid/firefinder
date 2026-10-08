# Survey: the sites FFLA's links page points to

Surveyed 2026-10-08 from <https://firelookout.org/resources/links/> ("Communities and Links"). The page
lists about 40 Facebook pages and groups (skipped: login-only), 19 FFLA chapters and affiliates, and 30
"other lookout and lookout-related sites". Every non-Facebook site was opened, with `robots.txt` read
first (our user agent `FirefinderBot/0.1`, one request per 2 s per host, or the host's `Crawl-delay` when
it asks for more). Nothing was fetched from a site that blocked us, and no bot check was got round.

Skipped by instruction: firelookout.org's own tables (ffla-refresh agent), nwmt-ffla.org (nwmt-projects
agent), andyarthur.org (Cloudflare challenge), mdc.mo.gov (robots disallows us; it is not on the links
page anyway).

## Headline

* **Most of what these sites list was already in Firefinder.** Compared by name and position with the
  towers on main (8,137 before this work): Rex Kamstra's firelookout.com and idahofirelookouts.com were
  already ingested whole; the chapter and Friends sites list ~80 lookouts between them and every one is
  a tower we have (all but a few NHLR-registered); the Oregon and Washington hobby sites match 95%+ by
  name; Indiana Fire Towers (39 sites) matches 35 by name and position once the weebly fix below is in.
* **The biggest finding is a bug in our own fetcher, not a missing site.** Ron Kemnow's index
  (`ronkemnow.weebly.com`, "Ron Kemnow U. S. Forest Fire Lookouts") fronts nine near-identical weebly
  sites. We read two of them (eastern, central) and only for 17 "gap" states. Their sidebar menus have
  slips that hid towers: a "Delaware" menu header that is really the second half of Michigan (178
  lookouts, none of them ever read), a "Texas" header that is really the second half of Missouri (27), and
  a "Georgia" header that is really the second half of Indiana (30, which we had filed under Georgia). All
  fixed; the two sites are now read for every state they cover (~1,000 more pages). The six western sites
  were not read at all; they are now (`west_us_lookouts`, 3,731 pages).
* **236 towers are new** (8,373 now; 8,332 visible): 181 from the western weebly sites (Oregon 75, Idaho
  33, Montana 27, Washington 20, California 19, Wyoming 6...), 28 from the eastern site (Michigan 22), 24
  from the central site (Missouri 16, Illinois 4), 3 from TrailChick. All are Unverified single-source
  towers except where a second source's pin agrees.
* **What the survey could not fix:** 2,172 lookouts that sources list by name and county but with no
  coordinates (`unplaced` in `data/merge_report.json`; 1,628 of them from the sites in this
  survey: eastern 735, western 406, WillhiteWeb 256, central 223, and 4 each from Oregon and Indiana). They are the largest
  remaining gap in "every lookout listed". See *Left over*.

## What was added

Every record of every source below with a position is now held by a tower (`python3 pipeline/coverage.py
--strict` exits 0 for each). All merge numbers are from a full `merge.py` run on the merged tree.

| Source id | From | Records | With coordinates | On an existing tower | New towers | Unplaced | Notes |
|---|---|---|---|---|---|---|---|
| `west_us_lookouts` | Ron Kemnow's six western weebly sites | 3,731 | 3,325 | 3,303 (+22 on hidden towers) | 181 | 406 | links, county, agency, township-range-section, status word; STRONG radius 3 km |
| `eastern_us_lookouts` | easternuslookouts.weebly.com, all 24 states (was 13) | 2,135 (was 1,319) | 834 | 1,398 | 28 | 735 | nav fixes; Michigan, Indiana, Virginia/West Virginia, Maine, New York... |
| `central_us_lookouts` | centraluslookouts.weebly.com, all 10 states (was 4) | 878 (was 460) | 528 | 655 | 24 | 223 | Missouri's second half, Texas, Wisconsin, Minnesota, Illinois |
| `trailchick_wa` | TrailChick Washington guide | 93 | 93 | 93 | 3 | 0 | coordinates, elevation, years, design, a card photo with credit |
| `cherylhill_oregon` | Every Lookout in Oregon | 160 | 0 | 156 | 0 | 4 | 53 joined by register number, 103 by name (hand-written county hints for 23 ambiguous names) |
| `ffla_groups` | FFLA chapters and Friends groups | 79 | 0 | 79 | 0 | 0 | 99 links; 34 register numbers from the California-South table |
| `willhiteweb_wa` | WillhiteWeb.com Washington lists | 766 | 0 | 510 | 0 | 256 | links only; unplaced = names that are not unique in Washington or not ours |
| `indiana_fire_towers` | indianafiretowers.com (lead from chapters-east) | 39 | 11 | 35 | 0 | 4 | status from each page's condition line; the other 28 positions are only on the author's Google map |

## Chapters and affiliates (19)

| Site | Run by | robots.txt | What it lists | Lookouts | Missing from Firefinder | Terms | Action |
|---|---|---|---|---|---|---|---|
| nysffla.org | FFLA New York State Chapter | none (404) | One page of every known NY tower (county, status, history prose) plus lists of Friends and affiliate groups | 149 | 0 real: "Alander Mt" is the MA/NY-line tower we hold as Alander Mountain (MA), "Knightower" is an NHLR entry with no coordinates | none stated | None for towers (no coordinates, no per-tower URLs, NY is complete at 175). Its Friends list gave `ffla_groups` the NY groups |
| mountainsfoundation.org/programs/fire-lookouts/ | Southern California Mountains Foundation | allows (calendar paths only) | The seven San Bernardino NF lookouts on one page, with directions and opening times | 7 | 0 | none stated | **Ingested** as links (`ffla_groups`) |
| firelookouthost.org | FFLA California-South chapter | allows | Bald Mountain (Inyo NF) page, and a table of Southern California towers with NHLR/FFLOS page, operator and current condition | 34 (+Bald Mountain) | 0 (every row is NHLR/FFLOS-registered) | none stated | **Ingested** (`ffla_groups`): register numbers, operator, condition. Two conditions say "destroyed" (Keller Peak 2024 Line Fire, Red Mtn Riverside 2022) |
| buckrock.org | Buck Rock Foundation (CA) | allows all | Buck Rock, Delilah and Park Ridge lookouts, one page each | 3 | 0 | none stated | **Ingested** as links |
| ffla-ccwr.org | FFLA California Pacific Chapter | no DNS record | none (the domain no longer resolves) | n/a | n/a | n/a | **Dead link**: FFLA should update it |
| anffla.org | Angeles NF Fire Lookout Association | `Crawl-delay: 10` (honoured) | Slide Mountain and Vetter Mountain pages, an inactive-towers page (South Mt. Hawkins, Warm Springs) | 4 | 0 | none stated | **Ingested** as links |
| ffla-sandiego.org | FFLA San Diego-Riverside chapter | allows (member area only) | Boucher Hill and High Point sections; fourteen history pages for San Diego/Riverside/Orange County towers (most gone) | 16 | 0 | none stated | **Ingested** as links |
| snoqualmielookouts.org | Snoqualmie Fire Lookouts Association (WA) | Squarespace file (blocks named AI crawlers, not us) | Suntop, Kelly Butte and Granite Mountain pages | 3 | 0 | none stated | **Ingested** as links |
| ffla-monterey.org | FFLA Monterey chapter | allows all | Chews Ridge and Cone Peak pages | 2 | 0 | none stated | **Ingested** as links |
| sandmountain.org | Sand Mountain Society (OR) | allows all | Eight restoration projects: Gold Butte, High Rock, Huckleberry Mountain, Pearsoll Peak, Pechuck, Sand Mountain, The Watchman, Wildhorse | 8 | 0 | none stated | **Ingested** as links |
| nwmt-ffla.org | Northwest Montana Lookout Association | n/a | n/a | n/a | n/a | n/a | Skipped (nwmt-projects agent) |
| friendsofstregis.org | Friends of St. Regis Mountain Fire Tower (NY) | allows all | The one tower | 1 | 0 | none stated | **Ingested** as a link |
| mvffla.org | Methow Valley Forest Fire Lookout Association (WA) | Squarespace file (as above) | Eight lookout pages (North Twentymile, Monument 83, Mebee Pass, Lookout Mountain, First Butte, Goat Peak, Mount Leecher, Slate Peak) and an ArcGIS StoryMap | 8 | 0 | none stated | **Ingested** as links. The StoryMap was not read |
| stissingfiretower.org | Friends of Stissing Landmarks (NY) | allows all | The one tower | 1 | 0 | none stated | **Ingested** as a link |
| argentinelookout.org | FFLA Argentine Chapter | no DNS record | none | n/a | n/a | n/a | **Dead link** |
| friendsofsterlingforest.org | (was) Friends of Sterling Forest (NY) | serves an HTML page | **The domain has been taken over: it now serves an Indonesian online-gambling site.** Not opened beyond the first response; nothing used | n/a | n/a | n/a | **Do not link.** FFLA should remove it; its own NY chapter page also lists it |
| azuremountain.org | Azure Mountain Friends (NY) | Squarespace file | The one tower | 1 | 0 | none stated | **Ingested** as a link |
| townofkentny.gov | Kent Conservation Advisory Committee (NY) | allows | (Nimham fire tower) | 1 | 0 | none stated | **Dead link** (404); Mount Nimham is already a tower |
| condorlookout.org | Hi Mountain Lookout Project (CA) | allows | The one lookout | 1 | 0 | none stated | **Ingested** as a link |

## Other lookout and lookout-related sites (30)

| Site | Run by | robots.txt | What it lists | Lookouts | Missing from Firefinder | Terms | Action |
|---|---|---|---|---|---|---|---|
| firelookout.com | Rex Kamstra | allows | Per-lookout pages for the Northwest and more; state maps | 3,266 | already ingested (`firelookout_com`) | none stated | Done earlier |
| fs.usda.gov (Indiana lookout towers, Hoosier NF) | US Forest Service | allows | The old page now returns the forest's home page | n/a | n/a | public | Dead link. Indiana has 41 towers, +30 from the weebly fix |
| ronkemnow.weebly.com | Ron Kemnow | allows | Index of the author's nine "FOREST LOOKOUTS" weebly sites (see *Ron Kemnow's sites*) | ~6,600 pages | see below | none stated | **Ingested** (eastern/central re-read for all states; western new) |
| nhdfl.dncr.nh.gov (NH fire towers) | NH Division of Forests and Lands | `robots.txt` and the page both answer HTTP 403 to our user agent | probably the state tower list | n/a | unknown | n/a | **Blocked, not retried.** NH has 78 towers from NHLR/FFLA; ask the Division for the list if wanted |
| canadafirelookouts.weebly.com | Ron Kemnow (formerly) | allows | **Taken over: a spam blog now (recipes, a speedway page).** | n/a | n/a | n/a | Do not link. Canada is out of scope until the model's `country` field is used |
| fs.usda.gov (Lincoln NF lookouts) | USFS | allows | The old page returns the forest's home page | n/a | n/a | public | Dead link |
| idahofirelookouts.com | (Idaho lookouts blog) | allows | Per-lookout posts with map pins | 998 | already ingested (`idaho_fl`) | none stated | Done earlier |
| fs.usda.gov (Mt. Baker-Snoqualmie lookouts) | USFS | allows | Home page only | n/a | n/a | public | Dead link |
| cherylhill.net/firelookouts | Cheryl Hill | allows all but /wp-admin/ | Table of Oregon's standing lookouts (agency, elevation, year, status), a post for each, and a "Destroyed Lookouts" category | 155 + 5 destroyed posts | 0 new (no coordinates); 156 of 160 now linked, 4 ambiguous names left unplaced | none stated | **Ingested** (`cherylhill_oregon`): links, elevation, year built, design, height, five destroyed lookouts |
| fs.usda.gov (Umatilla NF historic photos) | USFS | allows | Home page only | n/a | n/a | public | Dead link |
| trailchick.com | TrailChick | none (404) | Guide to 93 Washington lookouts the author has visited, each page with coordinates, elevation, type and years | 93 | 3 new (Aeneas Mountain, Whitmore Mountain, Mount Leecher Crows Nest) | none stated | **Ingested** (`trailchick_wa`): coordinates, facts, a card photo with credit, link |
| nps.gov/subjects/lookouts | National Park Service | allows (not /search, /ns) | A search page that fills in with JavaScript; no static list | n/a | n/a | public domain | None (park lookouts are in NHLR/FFLA) |
| willhiteweb.com (Washington Fire Lookouts) | A private collection (no author named on the pages) | empty (allows all) | Five list pages linking a page for every Washington place that ever had a lookout | ~770 pages | 36 names not in Firefinder (mostly trees, camps, ranger stations); no coordinates on the lists | none stated | **Ingested** as links (`willhiteweb_wa`); the lists only, not the 770 pages |
| visitrainier.com (Fire Lookouts of Mount Rainier) | Visit Rainier | allows (blocks named AI crawlers) | The page has moved (404) | n/a | n/a | n/a | Dead link; the park's lookouts are in Firefinder |
| carolinamountainclub.org (Lookout Tower Challenge) | Carolina Mountain Club | `Crawl-delay: 10` (honoured) | 23 NC towers on a PDF checklist; the old page URL is a 404 | 23 | 0 | none stated | None; list membership only (a "challenge" tag would need an owner decision) |
| viewsandbrews.com/balsamlake | Balsam Lake Mountain (Catskill Fire Tower Project) | none (404) | One tiny page | 1 | 0 | none stated | **Ingested** as a link |
| nj.gov (NJ Forest Fire Service detection) | NJ DEP | the old URL redirects to dep.nj.gov, which sits behind an Incapsula bot check | n/a | n/a | n/a | n/a | **Blocked, not automated.** NJ is covered by the Wikipedia list (23) and NHLR |
| pokeomoonshine.org | Friends of Poke-O-Moonshine (NY) | allows | One tower | 1 | 0 | none stated | **Ingested** as a link |
| firelookoutsdownunder.com | (Australian hobbyist) | allows | Australian towers | n/a | out of scope | none stated | None (not US) |
| friendsofmtarab.org | Friends of Mount Arab (NY) | `Crawl-delay: 10` (honoured) | One tower | 1 | 0 | none stated | **Ingested** as a link |
| ontarioftl.bravehost.com | (Ontario hobbyist) | n/a | 404 | n/a | n/a | n/a | Dead link; Canada anyway |
| masterpieces.com/bald.htm | Friends of Bald (Rondaxe) Mountain (NY) | none (404) | One tower | 1 | 0 | none stated | **Ingested** as a link |
| placer.ca.gov (Placer County lookout towers) | Placer County | HTTP 403 to our user agent | probably a short list | n/a | unknown | n/a | **Blocked, not retried** |
| bramleymountainfiretower.org | Bramley Mountain Fire Tower (NY) | allows | One tower | 1 | 0 | none stated | **Ingested** as a link |
| leslieromer.com | Leslie Romer | allows | A WordPress.com blog around the book *Lost Fire Lookouts*; per-lookout posts are few and scattered | n/a | n/a | none stated | None |
| hurricanefiretower.org | Friends of Hurricane Mountain (NY) | allows | One tower | 1 | 0 | none stated | **Ingested** as a link |
| firelookouts.com | Historic Lookout Project (Kresek) | allows all | About the project, the book and the Spokane museum; no lookout list. **The home page carries an injected link to a darknet marketplace** (looks hacked) | n/a | n/a | n/a | Do not link; tell FFLA |
| townofwilton.com (Cornell Hill Fire Tower) | Town of Wilton, NY | `Crawl-delay: 5` (honoured) | A page for the relocated tower | 1 | 0 | none stated | **Ingested** as a link |
| kuefler-lightning.com | Kuefler Lightning Protection | allows | A lightning-protection supplier | n/a | n/a | commercial | Not a lookout source |
| hadleymtfiretower.org | Hadley Mountain Fire Tower friends (NY) | allows | One tower | 1 | 0 | none stated | **Ingested** as a link |

## Two leads from the chapters-east agent (not on FFLA's links page)

| Site | Run by | robots.txt | What it lists | Lookouts | Missing from Firefinder | Terms | Action |
|---|---|---|---|---|---|---|---|
| indianafiretowers.com | Mark Armantrout ("Indiana Fire Towers (by Mark A)") | `Crawl-delay: 10` (honoured: 39 pages, ~7 minutes) | A list of the 43 Indiana tower sites in four groups (13 climbable, standing but overlooked, base corners left, gone) and a page for each, with names, county, topo quad, condition, links and, on 11 pages, latitude and longitude (the rest are on his Google map, which robots.txt for google.com keeps crawlers out of) | 39 pages | 0 after the weebly fix (4 have no coordinates and no match: Indiana Dunes, Salt Creek, the State Fair replica, Crane's several towers) | none stated | **Ingested** (`indiana_fire_towers`): 35 matched, 4 unplaced, 11 positions |
| e2pm.com/pafire_tower | E2 Project Management LLC (engineer for PA DGS / DCNR) | allows | A contractor's project page for the 53 Pennsylvania fire towers it inspected, rehabilitated or replaced (no dates given): marketing text, eight photos and one map screenshot with red/green/blue/orange dots for the plan per tower. **No list of tower names anywhere on the page.** | 53 towers (unnamed) | unknown: Pennsylvania already has 245+ towers from NHLR, the StoryMap and the weebly sites | none stated | **Nothing usable.** The map is a picture with no labels; a list would come from PA DCNR's Bureau of Forestry or DGS. Worth a records request if the owner wants the rebuild dates |

## Ron Kemnow's sites

`ronkemnow.weebly.com` indexes these. All are the same template: a menu of every lookout in the state or
region, a page each, with the forest, the township-range-section and often a Weebly map widget whose
iframe URL holds the author's own latitude and longitude. Narrative is newspaper clippings (not copied).

| Site | States | Menu entries | Read before | Now |
|---|---|---|---|---|
| easternuslookouts.weebly.com | 24 states (AL CT DE FL GA IN KY MA MD ME MI MS NC NH NJ NY OH PA RI SC TN VA VT WV) | ~2,140 | 13 gap states, 1,319 pages | all, with the nav fixes below |
| centraluslookouts.weebly.com | AR IA IL KS LA MN MO OK TX WI | ~880 | 4 gap states, 460 pages | all |
| westlookouts.weebly.com | AK AZ CO NE NV NM ND SD UT WY | 381 | not read | `west_us_lookouts` |
| californialookouts.weebly.com | CA | 574 | not read | `west_us_lookouts` |
| idaholookouts.weebly.com | ID | 684 | not read | `west_us_lookouts` |
| montanalookouts.weebly.com | MT | 485 | not read | `west_us_lookouts` |
| oregonlookouts.weebly.com | OR | 930 | not read | `west_us_lookouts` |
| washingtonlookouts.weebly.com | WA | 682 | not read | `west_us_lookouts` |

The sidebar nav slips fixed in `pipeline/regional/weebly_lookouts.py`:

* `/delaware1.html` ("Delaware", after Michigan's first half) is Michigan's second half: Demond Hill to
  Yates, 178 pages. Michigan had 30 towers in Firefinder; the site lists 229.
* `/texas1.html` ("Texas", after Missouri's first half) is Missouri's T-to-Z run (27 pages).
* `/georgia1.html` ("Georgia", after Indiana's first half) is Indiana's second half (30 pages), which we
  had been filing under Georgia.
* "WEST VIRGINIA >" and "MICHIGAN. >" are state markers with arrow text; Virginia resumes after West
  Virginia with no marker at all. A page that names its own state ("West Virginia - Cabell County") now
  wins over the run it was listed in.
* Names print in capitals; they are now title-cased ("MCNAB" becomes "McNab"), which changes 272
  existing tower names (cosmetic).

## Problems with the links page itself (for FFLA)

Dead: ffla-ccwr.org, argentinelookout.org (no DNS); townofkentny.gov, visitrainier.com, ontarioftl.bravehost.com,
the Carolina Mountain Club page (404); four fs.usda.gov pages (now the forest home page); the NJ DEP page.
Taken over by someone else: friendsofsterlingforest.org (gambling), canadafirelookouts.weebly.com (spam
blog). Looks compromised: firelookouts.com (a link to a darknet market on the home page), and the old NJ
DEP page carries an injected script tag. Blocking our user agent: nhdfl.dncr.nh.gov, placer.ca.gov.

## Left over

* **2,172 lookouts with a name (usually a county) but no coordinates**, 1,628 of them from the sites
  above (the rest are FFLOS 299, FFLA 240 and a few others). A prototype against USGS GNIS (the
  committed `DomesticNames_AllStates_Text.zip`) finds exactly one same-name natural feature (summit,
  ridge, pillar, gap) in the same county for 95 of the 958 eastern and central ones, and exactly one
  populated place of that name for 279 more (town centres, a poor proxy); the other 476 match nothing.
  Using these would mean positions labelled approximate: the owner's call, so not done.
* Oregon: 4 rows are still unplaced (Bald Butte in Fremont-Winema, Bly, Silver Butte and one more whose
  names are not unique even within their county); WillhiteWeb: 256 list
  entries (names not unique in Washington, or sites we do not have; 36 look like genuinely missing sites,
  mostly trees, camps and ranger stations, with no coordinates).
* Blocked by the host and not retried: New Hampshire's tower list (HTTP 403), Placer County's list (403),
  NJ DEP (bot check).
* Not read: the 770 WillhiteWeb lookout pages themselves (the lists link them; photo-heavy), the Methow
  StoryMap, the NYS chapter's one-page list of 149 NY towers (no coordinates; NY is already complete),
  Friends of Mount Beacon and Grafton Lakes (Facebook / state park page).
* Canada and Australia (three sites) are out of scope until the model's `country` field is used.
* `ffla_groups` overlaps in concept with the `chapters-*` association sources now on main (their
  year-by-year project reports for the same chapters). Both stay: theirs link a chapter's report for
  a lookout, ours the chapter's or Friends group's page about the lookout; the merge de-duplicates
  links by URL.
