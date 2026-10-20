# Expansion survey: the Prairies and the North (key `prairies-north`)

Area: Alberta, Saskatchewan, Manitoba, the Northwest Territories and Nunavut, including the national parks there
(Banff, Jasper, Waterton Lakes, Elk Island, Wood Buffalo, Prince Albert, Riding Mountain).

Surveyed 2026-10-20. Nothing in the repo was edited. Raw pulls are under `data/raw/expansion/prairies-north/`
(236 files, 58 MB) and the candidate list is `data/raw/expansion/prairies-north_candidates.json`. Pages were read with our
user agent at most once per 2 s per host (10 s for open.alberta.ca, which asks for it). Nothing was blocked and no
challenge was met. A few things were not tried: the Alberta Register of Historic Places search form (`hermis.alberta.ca`,
an interactive form), the Wayback Machine (it returned 429 on the first request, so I stopped) and the old FFLA Alberta
page (`w.firelookout.org/lookouts/ca-alb/ca-alb.htm`, a host that no longer resolves).

**Approach to the candidate list.** Alberta has a government layer with all 124 current towers and their positions, so the
active Alberta towers are **not copied** into the candidates; the candidates hold the Alberta lookouts the layer
misses (closed and historic ones, the national-park ones). Saskatchewan has no machine-readable bulk source, so the
hobbyist list (`websiteservice.ca`) is parsed into the candidates in full. Manitoba, the Northwest Territories and the
rest are small and are listed in full. Of the 280 candidate records, 78 have a position (AB 8, SK 56, MB 14); the other
202 are names with a province and a source, which is what the "can't place yet" list needs.

## 1. Summary

**How many sites existed.** Nobody has published an all-time count for Alberta or Saskatchewan.

| Area | Best figure | Source |
|---|---|---|
| Alberta | 127 wildfire lookout sites in 2009 and in a 2016 fact sheet; 124 points in the current government layer; **about 200 distinct names** across the layer and Ron Kemnow's Alberta index (121 match the layer, 74 are historic or closed) | open.alberta.ca; WF_WILDFIRE_LOOKOUT layer; canada-lookouts.weebly.com |
| Saskatchewan | **77 tower sites** on the Firetowers of Saskatchewan list (5 of them Prince Albert National Park towers), plus Blue Bell from the park museum; 111 names in Ron Kemnow's index before merging spelling variants (about 38 not matched to the first list) | websiteservice.ca; canada-lookouts.weebly.com |
| Manitoba | **about 66 towers built in all**, per the Manitoba Historical Society's head researcher; Ron Kemnow's Manitoba index has 67 names | The Carillon 2025-11-29 (quoting Gordon Goldsborough); canada-lookouts.weebly.com |
| Northwest Territories | 17 names; the territorial government says it has five lookout stations today | GNWT ECC; canada-lookouts.weebly.com |
| Nunavut | **none found** (see section 3) | |

**Standing.**

* Alberta: the 124 layer towers (101 "Steel", 23 "Cabin") are all flagged active in the layer. Beyond them a handful of old
  structures are known to stand: Black Rock, Cameron (Mount Burke), Grizzly Tower and the old Baseline ground house (all
  NHLR-registered), the memorial tower at Medicine Lodge, and the foundation of Castle Mountain.
* Saskatchewan: 42 detection towers in service in 2026, all camera-equipped (SPSA, Prince Albert Daily Herald). Which 42 is not published.
* Manitoba: "roughly 10" towers left standing in the province (the province, Nov 2025). The Woodridge tower came down on 12 Nov 2025. Five Riding Mountain National Park towers were still up in 2018.
* Northwest Territories: five working lookout stations; Angus closed in 2006.

**Staffed now (people living in the tower or cabin).**

* **Alberta: about 100.** Alberta Wildfire says it has 127 sites "each staffed by a lookout observer"; the job postings and the
  FRIAA service description say 100 active (a 2024-era posting snippet said 104). The 2026 season postings are still seeking lookout observers.
  Of the 124 layer rows, 74 are drive-in and 50 are fly-in.
* **Saskatchewan: none.** The province began replacing tower observers with cameras in 2013 (about 38 seasonal posts lost; Wildfire Today, NHLR); in 2026 SPSA reports 42 towers, "cameras on all of them", watched by detection staff. The brief assumed Saskatchewan still staffs towers; it does not, and Firefinder should say "camera-equipped, not staffed".
* **Manitoba: none found.** Woodridge had not operated since 2010; the province says new technology took over.
* **Northwest Territories:** the ECC page says lookouts are "manned by a lookout observer" (undated). Which of the five are in use is not stated.
* **Nunavut:** none.

**How many the candidates cover.** 280 records: SK 115, AB 75, MB 73, NT 17, NU 0. 61 carry a build year,
14 are marked standing, 8 gone, 1 ruins, 1 replica. Alberta's 124 current towers come from the layer, not the candidates.

## 2. Sources

| Name | URL | What it gives | How many in this area | Coordinates? | Form | Licence / terms | robots / blocked | Recommended fetch | Priority |
|---|---|---|---|---|---|---|---|---|---|
| **Alberta WF_WILDFIRE_LOOKOUT** (in the FRIAA FireSmart service) | https://geospatial.alberta.ca/titan/rest/services/friaa/friaa_firesmart_vector_data/MapServer/0 | Name, 2-letter id, type (Steel / Cabin), year constructed, tower height m, elevation m, map sheet, location verified (Y/N and by GPS), active flag, access mode (drive / fly), weather station flag, declination | **124** (101 Steel, 23 Cabin; 106 positions verified Y; years 1953-2019) | **Yes**, attribute fields LATITUDE / LONGITUDE (WGS84) | ArcGIS REST MapServer layer, max 1000 per query | The portal item says "Open Government Licence - Alberta", **but the layer's own description says Security Classification "Protected" and "not to be displayed on maps with a scale larger than 1:1,000,000 or on maps that show local roads, that are going to be seen by the general public"** (extract dated April 2018). See open question 1. | `robots.txt` 404 (none); no challenge | `GET .../MapServer/0/query?where=1%3D1&outFields=*&returnGeometry=false&f=json&resultRecordCount=1000` (one request). Note `f=geojson` and `returnCountOnly` returned HTTP 500 on this server; plain `f=json` works. Saved as `ab_wf_wildfire_lookout_attrs.json`. | **bulk** (hold until question 1 is answered) |
| **Open Alberta "Fire lookouts" map** | https://open.alberta.ca/publications/fire-lookouts | One-page PDF map (2009) of the 127 sites, labelled; the dataset note and a 2016 BearSmart fact sheet repeat "127" | 127 labels; 7 are not in the current layer: Bitumont, Buckton, Cambrian, Christina Basin, Keane, Richardson, Winefred. The layer has 3 the map lacks (Kirby Lake, Petitot, Steen; built after 2009) | No (labels on a map) | PDF, text via `pdftotext -raw` | Open Government Licence - Alberta | Crawl-Delay 10 honoured; `/api/` not used | One PDF fetch | supplement |
| **websiteservice.ca "Firetowers of Saskatchewan"** (Chris Rule, from Maurice Bourassa's work) | https://www.websiteservice.ca/firetowers_page4.htm | Directory of provincial and Prince Albert NP towers: location as deg-min-sec or deg-decimal-minutes, many with a legal land description (LSD), height and tower class (80 ft light or heavy steel, 60 ft, 40 ft wood), notes such as "new cupola 1957", towermen, photos | **80 entries**: 75 provincial + 5 PANP (3 of the PANP ones repeat a provincial row) = 77 distinct sites, plus a tower map PDF | **58 with a usable position** (SK 56, MB 2); 3 have impossible digits (Dube lon "197", Molonosa seconds "98.9", Piwei minutes "99"), 1 has a typo'd degree field (Ridge "5353"); 15 have only a land description (LSD) or nothing | Hand-made HTML, one long page | None stated; facts only | `robots.txt` 404; no challenge | One page fetch, then parse (`ws_page4_lines.txt` is the cleaned text). Needs a tolerant parser: formats vary and several entries break across lines | **bulk** for Saskatchewan |
| **Ron Kemnow "Canada's Fire Lookouts"** | https://canada-lookouts.weebly.com/ | Same author and template as the US weebly sites already in Firefinder. Per-province index pages (names) plus a page per lookout with dated quotes from annual reports and newspapers: years erected, replaced, closed, place line (forest, division, park) | AB index 196 names (109 with pages); SK 111 names (49 pages); MB 67 names (31 pages); NT 17 names (6 pages); no Nunavut | Only 13 pages embed a map widget (AB 3: Ansell, Castle Mountain, Kimiwan; MB 10) | Weebly HTML, 195 pages fetched | No licence; facts only (the quoted prose is not copied) | `Disallow: /ajax/` only; a Crawl-delay is set for one bot, not `*`; I used 2.2 s | Reuse `pipeline/regional/weebly_lookouts.py` page reader (nav parse in `canada_weebly_nav.json`); sitemap at /sitemap.xml | **supplement** (history; the only list of Alberta's historic names) |
| **National Historic Lookout Register, Canada** | http://nhlr.org/lookouts/can/ (use `/lookouts/can/<prov>/`, plain http) | Register number, date registered, coordinates, elevation, agency, short history | **AB 5** (Baseline, Black Rock, Cameron, Grizzly Tower, Medicine Lodge), **SK 1** (North Cabin, CAN 18; URL is `/lookouts/can/saskatchewan/north-cabin-fire-tower/`, no `/sk/` list page); none in MB, NT, NU | **Yes**, deg-min, DMS and decimal | HTML, one page each | "All rights reserved"; facts only (as DESIGN §2) | `robots.txt` 404 | Six page fetches | supplement (registers, coordinates) |
| **FFLOS** (former sites) | http://firetower.org/lookouts/can/ | Canadian former sites | 3 in Canada (Fort Frances, Jesmond, Rogersville); **none in this area** | n/a | HTML | as NHLR | none | n/a | none |
| **FFLA Canada page** | https://firelookout.org/lookouts/ca/ | Stub, "Under Construction": a row per province (Alberta has an NHLR link; Manitoba, NWT, Nunavut, Saskatchewan rows are empty) | 0 | No | HTML | none stated | allows | n/a | none |
| **firelookout.ca** | https://firelookout.ca/ (per tower `/lookouts/?slug=<slug>`) | 206 rows in a JS array (`rawTowers`); the per-tower page adds elevation, type, year built, free text | **14** Saskatchewan (13 "Saskatchewan" + Rabbit Hill filed under "Unorganized Division No. 18"); **0** Alberta, Manitoba, NWT or Nunavut. The cached home page and a fresh fetch on 2026-10-20 both show 206 rows | Yes, but 2 of the 14 are placeholders (below) | HTML + JS array | CC BY-NC-SA 4.0 | `/robots.txt` returns the home page with HTTP 200 (no real robots file); no challenge. `www.` has a certificate mismatch; use the bare host | Already cached; 14 slug fetches done | supplement; **not independent**: 7 of the 12 rows I could compare sit exactly on the websiteservice.ca position (0.0 km), 4 within 0.6-2.2 km, so the SK rows derive from that list |
| **Manitoba Historical Society, Historic Sites of Manitoba** | http://www.mhs.mb.ca/docs/sites/ | Woodridge Fire Tower (N49.28968 W96.14726) and Sasaginnigak Fire Tower (N51.60048 W95.67231), each with photos | 2 | Yes (5 decimals) | HTML | "Free public service for non-commercial purposes"; facts only | read through `fetch_text.py` | Search the collection for "fire tower" for more | supplement / story research |
| **Jasper Yellowhead Historical Society** | https://jaspermuseum.org/jasper-fire-towers/ | Five-line timeline: Signal 1939, Devona steel tower 1942, Palisade 1945, Geraldine 1950, Bald Hills 1955; all decommissioned by 1978 | 5 | No | HTML | none stated | n/a | one fetch | supplement |
| **Canadian Rockies peak database** | https://www.cdnrockiesdatabases.ca/peaks/1251 | Signal Mountain summit position (52.8594 N 117.967 W) and "first mountain-parks fire lookout 1941" | 1 | Yes, summit not lookout | HTML | not stated | n/a | n/a | story research |
| **Waskesiu Heritage Museum** | https://waskesiuheritagemuseum.org/fire-towers | Prince Albert NP: six towers (Blue Bell, Summit, Wabeno, Sanctuary, Rabbit Creek built 1938; Boundary 1940), decommissioned 2001 | 6 | No | HTML | not stated | n/a | one fetch | supplement |
| **Riding Mountain tower note** | https://everybodyhastobesomewhere.blogspot.com/2018/09/fire-lookout-towers.html | RMNP: about ten towers built 1938-39; Rolling River and Heron Creek 1949; five left in 2018 (Baldy, Clear Lake, Sugarloaf, Heron Creek, Rolling River) | 5 named | No | Blog post | not stated | n/a | one fetch | story research (a hobbyist; confirm with Parks Canada) |
| **OSM snapshot** (`data/raw/osm/overpass_ca_ak_hi.json`) | cached | 86 elements in Canada | AB ~32: 31 sit within 3 km of a layer point, 1 is new (Rock Lake, abandoned); MB 2 (Griffiths Hill Lookout Tower, Lonnie's Lookout: unclear what they are); SK 0; NT 0 | Yes | JSON | ODbL | not queried | already cached | supplement |
| **Wikidata** (query saved) | `wikidata_ca_fire_lookouts.json` | 11 Canadian items, of which 5 are in Alberta (Baseline, Black Rock, Cameron, Grizzly Tower, Medicine Lodge) | 5 | None of the five has a position | SPARQL JSON | CC0 | n/a | 1 of the 3 allowed queries used | none beyond NHLR ids |
| **GNWT Environment and Climate Change** | https://www.gov.nt.ca/ecc/en/services/wildfire-operations/detecting-wildfire | "A network of five lookout stations are spread throughout the NWT"; observers named; no list | 5 (unnamed) | No | HTML | GNWT | n/a | n/a | status evidence |
| **SPSA / press on Saskatchewan** | https://paherald.sk.ca/saskatchewan-has-42-wildfire-detection-towers-but-no-ai-camera-system-spsa-says/ ; https://wildfiretoday.com/saskatchewan-replacing-fire-lookouts-with-cameras/ ; https://www.sgeu.org/news/sgeu-news/save-our-fire-tower-observers | 42 camera towers in 2026; 2013 decision to phase out observers; union campaign page | n/a | No | HTML | n/a | n/a | n/a | status evidence |
| **Manitoba press on Woodridge** | https://www.thecarillon.com/local/2025/11/29/province-removes-woodridge-fire-lookout-tower-residents-sad-to-see-it-go ; Steinbach Online; CTV | Removal on 12 Nov 2025; "roughly 10" towers left; ~66 built; 1913 first detection from towers | n/a | No | HTML | n/a | n/a | n/a | status evidence |
| **Alberta Culture "Lonely Lookouts"** | https://albertashistoricplaces.com/2014/04/24/lonely-lookouts/ | History of the Alberta system; Cameron/Burke 1929 (the highest in Canada), Black Rock; in a comment the author says the government "does not have a list of abandoned lookouts" | n/a | A comment gives DMS for Black Rock and Cameron | HTML | n/a | n/a | n/a | story research |
| **Federal Heritage Designations (DFHD)** | https://open.canada.ca/data/en/dataset/49d5ba7d-d860-40d9-9183-892979e4acbe (CSV saved) | 3,890 designations | 1 fire lookout in all of Canada (Summit Fire Lookout, Mount Revelstoke, BC), **none in this area** | n/a | CSV, 14 MB | Open Government Licence - Canada | none | done | none |
| **CGNDB** | https://geogratis.gc.ca/services/geoname/en/geonames.json?q=lookout&province=48 (47, 46, 61, 62) | Place names containing "lookout" | AB 5, SK 5, MB 4, NT 2, NU 2; all are summits, creeks or islands with a "Lookout" name, **none a fire-tower feature class** (Adams Lookout, AB, 53.7258 -118.5681 sits at the Adams Creek tower, a hint, not a source) | Yes | JSON | Open Government Licence - Canada | `robots.txt` now a 404 page (site redesigned); no challenge | n/a | none (rejected as bulk) |

**Placeholder or doubtful positions in this area (flagged as asked).**

* firelookout.ca **Cumberland House Fire Tower** 53.9523 -102.2624: the address is only "Cumberland House, SK, Canada", a geocoded town pin. Not adopted; the candidate has no position and keeps the pin in `extra.placeholder_position`.
* firelookout.ca **Clear Lake Fire Tower** 52.93992 -106.45086: the address is "Saskatchewan, Canada" and the submitter's note says "unknown location and coordinates" and that a weather-station tower may stand in its place. Not adopted.
* firelookout.ca **Cypress Fire Tower** 49.631 -109.3159 says it is in the "West Block", but websiteservice.ca puts the West Block tower at 49.6013 -109.9217 (44 km west) and the Centre Block tower at 49.6624 -109.4829 (closer to the pin). Both ws positions are kept; the disagreement is noted on the record.
* websiteservice.ca **Duck Mountain** (51.626 -101.659) and **Porcupine** (52.62 -101.828): listed on the Saskatchewan list but east of 102 deg W, so they are in Manitoba; filed under MB with a note.
* websiteservice.ca **Kingsmere** (54.0456 -108.4389) is far from Kingsmere Lake in Prince Albert NP; kept as published.
* NHLR **Black Rock** 51.336015 -115.167342 versus a position given in an Alberta Culture comment (51 20 30 N, 115 11 34 W = 51.3417 -115.1928): about 1.9 km apart. NHLR's is used, the other kept in `extra.coord_conflict`.
* The Alberta layer marks 18 of its 124 points "Location Verified = N".
* Ron Kemnow's map-widget positions (Castle Mountain, Baldy Mountain, 10 Manitoba pages) are the author's own placements; precision is unknown.

## 3. Province and territory notes

**Alberta.** Every current lookout is an Alberta Wildfire (Ministry of Forestry and Parks) site, a government
workplace with a live-in observer, generally April to October. Layer ids are two letters (AD = Adair). The layer's
types are "Steel" (a 30 m tower is the usual height; a few are 18 or 24 m) and "Cabin" (alpine cabins, 2 or 5 m tall); 23 cabins sit on mountain tops in
the Rockies and Kananaskis (Baldy 1953, Copton 1955, Blackstone 1961, Torrens 1962, Limestone 1963, Moberly 1967, Mockingbird Hill 1972, Kananaskis 1976 ...). Most steel towers are 2003-2019 rebuilds on older sites, so the layer's
"year constructed" is the present structure, not the first lookout there (Alberta Culture says many sit "on the location of the first generation"). The government's
bear-safety page says permanent electric fences enclose "residences, lookout towers, outhouses and generator buildings"
at priority sites; the FRIAA service text calls them "private residences, often protected by electric fences". OSM mappers tag several as `access=private` (Cline, Baldy, Kananaskis, Falls, Grave Flats). I found no public-access policy. Sites with a public face: Medicine Lodge (a 20 ft memorial tower in Cypress Hills Provincial Park, with the Tom Trott Forestry Museum), and a few cabins reachable on public trails (Kananaskis, Hailstone Butte, Cline) that are still staffed.

* Naming: most are place names plus Lookout (Hailstone Butte, Moose Mountain); Ron Kemnow shows 'old' sites as "Old Baseline", "Old Falls", "Old Luscar". Alberta uses several "Forest Reserve / Division" names in older text (Edson, Whitecourt, Peace River, Grande Prairie, Slave Lake, Breton, Lac La Biche, Clearwater, Bow River).
* Administrative units to store: municipal district or county for provincial land (the layer has none; derive from the position), "Improvement District" / park name inside national parks. The layer's `MAP_NUMBER` is an NTS sheet.
* Agencies over time: Dominion Forestry Branch (to 1930, when Alberta took over the Crown lands), then the Alberta Forest Service (Lands and Mines, Lands and Forests, Energy and Natural Resources, SRD, ESRD, Agriculture and Forestry, now Forestry and Parks). Parks Canada's wardens ran the national-park lookouts.
* National parks (all gone or foundations only): **Banff** (Tunnel Mountain 1941, Castle Mountain c.1942, Aylmer c.1948, Bow Summit 1949; Mount Sarbach 1943-45 is filed under Jasper by Ron Kemnow but is normally a Banff peak: check), **Jasper** (Signal, Devona, Palisade, Geraldine, Bald Hills; none after 1978), **Waterton** (Chief Mountain Highway 40 ft tower 1958/59-1973, removed in the 1980s), **Wood Buffalo** (Pine Lake photo only; plus the NT-side towers below). **Elk Island: nothing found** in four searches. The brief's examples: Cascade and Ribbon Creek have no source (Ron Kemnow files "Cascade" only under British Columbia); Palisade, Signal Mountain and Black Rock are in the candidates.
* NHLR's five Alberta entries pre-date the current towers; Baseline shows the pattern: a late-1920s ground house and the active tower about half a mile west.

**Saskatchewan.** Provincial forest towers (Saskatchewan Dept. of Natural Resources, then Environment / SERM, and since 2017 the Saskatchewan Public Safety Agency, SPSA) were mostly 80 ft steel, with cupolas replaced in the 1950s-60s. Local names combine a lake or hill with Tower. Locations are
given by legal land description (LSD, section-township-range-meridian, "W2/W3") and by rural municipality ("Torch River No. 488") or "Unorganized Division No. 18" in the north. Towers were replaced by cameras from 2013-14; the
websiteservice.ca list is the only source with positions for the old network, and nothing says which of its towers are among the 42 in service today (Rabbit Hill is, per firelookout.ca; North Cabin stands, fenced). **Prince Albert National Park** towers (Blue Bell, Summit, Wabeno, Sanctuary, Rabbit Creek, Boundary) went out of use in 2001; one cupola (Sanctuary) is at the Waskesiu Heritage Museum. The Cypress Hills straddle the border: Medicine Lodge is Alberta's side, Centre Block and West Block towers are Saskatchewan's. No rentals or overnight stays found.

**Manitoba.** About 66 towers over time (first detections from towers in 1913), almost all removed; the province says ~10 stand, none in use. Known standing: Sasaginnigak (Atikaki Provincial Park, remote), five in Riding Mountain NP, **Baldy Mountain in Duck Mountain Provincial Park (the highest point, 831 m, a 12 m tower kept as a public viewing tower with a paved trail; a 1915 pole tower was the first lookout there)**. Woodridge (Woodridge Provincial Park, c.1960-2025) is gone: the first removal we can date precisely. Early lookouts included platforms on ranger-station roofs (Durban, Minitonas, 1914-15) and a 20 ft steel tower on the Pine Falls pulp mill (1947): those are `rooftop`/`platform` kinds. William Lake (Turtle Mountain) was a combined fire lookout and tourist tower (1959). Agencies: Dominion Forestry Branch, then Manitoba Dept. of Mines and Natural Resources and successors; Parks Canada in Riding Mountain.

**Northwest Territories.** GNWT Environment and Climate Change (ECC; earlier Environment and Natural Resources) works from regional offices (South Slave, Dehcho ...). Names recorded: Angus (Wood Buffalo NP, steel tower 1965, closed 2006, replaced by Raven's Nest, which opened in spring 2006), Blackwater and Trout Lake (two steel towers tendered 1982; Tsu Lake had a tower in 1958), Caen Lake (30 m steel tower and cabin, road deactivated 2011), Cameron Hills, Enterprise (access clearing for a tower in 2013), Hart Lake (decommissioned for structural problems), Kimble, plus sites cleared in 1958 (Kakisa Lake, Yellowknife) that may never have been built, and names with no history (Liard, Lone Mountain, Long Island, Mount Gaudet, Nahanni Butte, Parsons Lake Road). ECC counts five working lookouts, but publishes no list.

**Nunavut: no fire lookouts.** Evidence: (1) the FFLA Canada page has a Nunavut row with nothing in it; (2) Ron Kemnow's Canada index has no Nunavut page; (3) NHLR and FFLOS list none; (4) CGNDB has two "Lookout" names in Nunavut, a Lookout Island (59.58 N 69.32 W) and Balaena Lookout (69.74 N 67.15 W), neither a fire feature; (5) Nunatsiaq News (2026) says wildfires are historically uncommon since "the vast majority of the territory [is] above the treeline", and the territory only joined the Canadian Interagency Forest Fire Centre in 2026. A strip of treed land in the Kivalliq may exist, but no source mentions a tower there. Record as "none found", not "proved none".

**Licences and rights.** Government layers (Open Government Licence - Alberta / Canada) allow reuse with credit. The hobbyist sources (websiteservice.ca, Ron Kemnow, firelookout.ca at CC BY-NC-SA) carry no usable licence or a non-commercial one, so the same "facts only, our own words, link back" rule as the earlier surveys applies; firelookout.ca's NC clause in particular should be taken to the owner before any bulk copy.

## 4. Excluded, considered and rejected

| Item | Where | Why |
|---|---|---|
| Hastings Hill | Ron Kemnow's Alberta index | It is in Fundy Park, New Brunswick (page text says "Fundy Park"); misfiled. Left out of the candidates. |
| Griffiths Hill Lookout Tower (50.0274 -96.8971) and Lonnie's Lookout (49.7639 -99.5870) | OSM, Manitoba | Names only, no evidence that either detected fires; both look like viewing structures. Not in the candidates. |
| Nipigon Lookout, Fire Tower (49.4162 -91.6661) | OSM | Ontario, not this area. |
| Federal Heritage Designations | Parks Canada CSV | One fire lookout in all of Canada (Mount Revelstoke, BC); none here. |
| CGNDB "Lookout" names | geogratis | Mountain, island and creek names, not tower sites. |
| FFLOS Canada | firetower.org | 3 sites, all outside this area. |
| Wikipedia "List of fire lookout towers" | en.wikipedia.org | The "Canada" section is empty. |
| Alberta weather-station map | open.alberta.ca | Lists lookouts as weather stations only; no extra sites. |
| Military or radar sites | NWT, Nunavut | None found that were lookout towers; DEW-line sites are out of scope. |
| Kakisa Lake and Yellowknife (NWT) | Ron Kemnow | Federal report says a tower site was cleared in 1958; no evidence one was built. Kept in the candidates with `status` unknown and the note; drop if nothing better turns up. |
| Beehive Mountain, Alberta | Ron Kemnow | The page only quotes a 1941 newspaper list of points chosen for lookouts; may never have been built. Same treatment. |
| Alberta Register of Historic Places | hermis.alberta.ca | A search form; not read. Alberta Culture's author says the government keeps no list of abandoned lookouts. A future agent could search it for Cameron, Black Rock and Baseline. |

## 5. Open questions for the owner

1. **Alberta's layer: may we publish its positions?** The layer is served openly and the portal record says Open Government Licence - Alberta. But the layer's own description says "Protected", extracted in 2018, "not to be displayed on maps with a scale larger than 1:1,000,000 or on maps that show local roads, that are going to be seen by the general public", and the sites are staffed government workplaces (the service text says "private residences"). Firefinder's rule is exact location, warn rather than hide, so choices are: (a) ingest all 124 exact positions and label them staffed / restricted access; (b) ask Alberta Wildfire whether the 2018 restriction still stands, before ingesting; (c) show the active Alberta towers with a coarse pin (rounded to a few km) until (b) is answered. I have not copied the layer's positions into the candidates; the data is saved locally.
2. **Name-only records.** 202 of the 280 candidates have no position (Ron Kemnow's index names, most with no status). Do these go on the "can't place yet" list now (they are single-source and Unverified), or wait for a second source? The Alberta ones may duplicate a current tower under another name (for example Doucette vs Doucet, Old Falls vs Falls), and that cannot be settled without positions.
3. **Saskatchewan status wording.** Almost every Saskatchewan tower is "status unknown, not staffed": SPSA runs 42 camera towers but publishes no list. Is "camera-equipped, no observer" a staffing value you want (DESIGN §3.4 has `staffed`, `emergency`, `volunteer`, `unstaffed`, `unknown`), or do these go in as plain `unstaffed` with the camera in a note?
