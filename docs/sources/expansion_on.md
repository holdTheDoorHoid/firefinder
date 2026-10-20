# Expansion survey: Ontario (key `on`)

Surveyed 2026-10-20. Nothing in the repo was edited; the raw pulls are under `data/raw/expansion/on/` and the
candidate list is `data/raw/expansion/on_candidates.json`. Every site below was read with our user agent, at most
one request per 2 s per host (10 s for data.ontario.ca, which asks for it). One site (the Southern Ontario map on
yolasite) showed a Cloudflare challenge and was left alone; the Facebook groups are login-only and were not opened.

## 1. Summary

**How many sites existed.** The best total is **325 manned towers at the peak** (about 1963), from Clay's
*Ontario's Fire Tower Lookouts* (forestrangers.github.io, "there were a total of 325 manned towers, and over 80 were
located in Southern Ontario alone"; the same site says "320 other towermen" elsewhere, so 321-325). The Department of
Lands and Forests' own 1963 map, *Tower Detection System* (the map the site hosts as a PDF and a JPG), shows three dot
classes: 100 ft steel, 80 ft or less steel, and wood (one yellow dot in the whole province). A rough colour-blob count of the
image found about 305 dots, which fits 325 once overlapping dots are allowed for. The network was split into 22 fire
districts (17 in 1922). Algonquin Park alone had at least 23 towers over time; the Pembroke district had 15. These
count the 1963 network. Wooden towers before the steel era, and towers pulled out before 1963, are in addition, so the
all-time number of sites is somewhat higher than 325 and nobody has published it.

**How many are standing.** Nobody has a current count. Clay's "still standing" list (c. 2009-2013) names **159**
towers and says "half of them remain"; the same page says the Ministry of Natural Resources (MNR) began removing standing towers in
2013. Examples reported gone since: Ogidaki (removed May 2016, per ontariohighpoints.com, seen in a search snippet), Hazelwood (2011), Big Crow Lake (cab burned 2010-11, steel
frame left), Thessalon, Pickle Lake, Bamoos. The Land Information Ontario (LIO) layer holds 95 fire-tower points, but it has
no status field and its checks date from 1998-2000.

**Staffed now: none confirmed.** Ontario ended tower detection in the 1960s-70s (aircraft, then public reports). Two towers at
the Petawawa Research Forest, Malone and Wylie, are called "active" on firelookout.ca and "manned and fully operational" on
Clay's page (c. 2013). The forest's own StoryMap calls them "fire rating towers" (the place where Canada's fire-danger rating system was
built), and Natural Resources Canada buys wildfire-camera support for the forest (a 2026 procurement notice that
the fetcher could not open, read from search snippets only). I could not confirm any person watching from either tower
in 2026. Recorded as `staffed_now: null` for those two.

**Open to visitors** (the "can I climb it" set, all non-staffed): Temagami (restored 1998), Dorset (1967 tower, Township of
Algonquin Highlands), Parry Sound (Tower Hill), Elliot Lake (a replica), Fort Frances and Ignace (towers moved to town;
both are in the candidates), Red Lake (Forestry Point), plus relocated pieces at Tweed, Port Hope, Tobermory, Pembroke and Field.

**What my candidates cover.** The approach is "bulk sources hold most; candidates only for what they miss":

* Bulk 1: **firelookout.ca**, 142 Ontario rows with coordinates (20 of them are town-centre placeholders, see below).
* Bulk 2: **LIO Tower layer**, 95 fire towers with coordinates good to 10-500 m. 61 of the 95 are NOT in firelookout.ca
  (30 with names, 31 with none). This is the biggest finding: the two bulk sources overlap on only 34 sites.
* `on_candidates.json`: **101 records** that neither bulk source holds: 91 names from Clay's still-standing list (names and
  nearest places only, no coordinates; 68 more list entries were matched to a bulk record and left out, see the
  `covered_by_bulk` array in the JSON), plus 10 found in single sources (Fort Frances and its original site, Parry Sound, the
  relocated Ignace tower and the first Ignace tower, two Algonquin sites, three Pembroke-district names). Only 4 have
  coordinates, and each of those comes from a source that gives them.
* Together the sources name or place about **270-300** of the ~325 sites. Some of the 91 list names may be the 31 unnamed LIO
  points (for example the six unnamed points at Kapuskasing, `Fire Tower Basemap NNNNN`, against six Kapuskasing names on the
  list), so adding candidates and LIO points double-counts a little. Matching them needs a map sheet (see OCUL topo maps below).

## 2. Sources

| Name | URL | What it gives | Count in Ontario | Coordinates? | Form | Licence / terms | robots / blocked | Recommended fetch | Priority |
|---|---|---|---|---|---|---|---|---|---|
| firelookout.ca "Open Canada Fire Lookout Index" | https://firelookout.ca/ | Name, slug, lat/lng, address, region on the home page; per-tower page adds elevation, "Tower Type", "Year Built", prose and credits | **142** of 206 (Ontario 117, Central Ontario 12, Northeastern Ontario 10, Eastern Ontario 3; one of them, Maria, has a Quebec address; Rabbit Hill in the list is Saskatchewan). After merging same-tower duplicates (Moon River x2, Skymount x2, Aldina x2, Big Crow Lake = Freswick, Anima-Nipissing = Brigstocke) about 137 distinct | Yes, but quality varies: 20 rows at 4 shared town-centre pins (Lindsay x9, Tweed x8, Pembroke x3) are placeholders; 13 pages carry a doubt note ("approximate", "best guess", "unsure", "not verified") | JS array `rawTowers` in the home page (already cached at `data/raw/web/8d0a1f2eb4fe0b34b7a23fbb4e19906b96769bf4.bin`); per-tower HTML at `/lookouts/?slug=<slug>` | Historical records CC BY-NC-SA 4.0 (volunteer-run, ko-fi). Licence is a question, see section 5 | No robots.txt (the URL returns the SPA page, HTTP 200). No challenge. The pretty URLs `/lookouts/<id>/<slug>/`, `/en/<slug>/`, `/district/<x>/` and `/sitemap.xml` all return the home page, so only the `?slug=` form is real | Parse `rawTowers`, then 142 page GETs at 2 s each (done; parsed copy `firelookout_ca_ontario_pages.json`). Per-tower KML at `export-kml.php?slug=` not fetched | **bulk** (names, pins). Pages are thin: elevation on 56 of 142, tower type on 34 (32 "Steel Tower"), year built on 3 (Temagami 1910, Preston 1922, Wilberforce 1958), height on 0, photos 0, no status, no agency field. Status has to be read from prose ("tower is gone", "blew down in a 1965 windstorm", "removed in 2011") on about 20 pages |
| **LIO "Tower" layer** (Ontario GeoHub / Land Information Ontario) | https://ws.lioservices.lrc.gov.on.ca/arcgis2/rest/services/LIO_OPEN_DATA/LIO_Open10/MapServer/14 ; hub page https://geohub.lio.gov.on.ca/datasets/mnrf::tower ; catalogue https://data.ontario.ca/en/dataset/tower | Points for 3,080 towers of all kinds; subtype `Fire Tower` = **95**. Fields: OFFICIAL_NAME (42 of 95 filled), TOWER_IDENT (12), LOCATION_ACCURACY (5 m to 500 m; 7 flagged "Data Load"), LOCATION_DESCR (23), GENERAL_COMMENTS (39: "Constructed in 1929 / 1940 / 1951 / 1956", "Tower not used", "no cabin on top", "MNR Fire Tower- no longer used"), VERIFICATION_STATUS (78 verified, 16 unverified), PURPOSE_OF_TOWER_DESCR (9). Height 1, construction date 1, no status, no agency | 95 | **Yes, good**: WGS84 via `outSR=4326`, accuracy per point | ArcGIS REST MapServer (JSON, GeoJSON, PBF), max 2,000 records per query | Open Government Licence - Ontario (compatible with our ODbL database if credited). Item notes "Maintenance: Not planned: there are no plans to update the data"; service last modified 2026-08-13 | `ws.lioservices...` has no robots.txt (404). The GeoHub site asks `Crawl-delay: 60` and data.ontario.ca `Crawl-delay: 10` and disallows `/api/`; I used one query on the service and one page each on the other two, no more | One request: `.../MapServer/14/query?where=CLASS_SUBTYPE='Fire Tower'&outFields=*&outSR=4326&f=geojson` (saved as `lio_fire_towers.geojson`). French twin "Tours" at geohub-fr.lio.gov.on.ca | **bulk** (positions, a few names). Treat status as unknown: the layer keeps towers that were later removed |
| forestrangers.github.io/ontariofiretowers (Clay, "Ontario's Fire Tower Lookouts"); old mirrors geocities.ws/ontarioftl and oocities.org/ontarioftl | https://forestrangers.github.io/ontariofiretowers/stillstanding2.html (also index.html, towermen.html, links.html, map1963.jpg, FireTowers.pdf) | **List of 159 "still standing" towers**: number, name, nearest lake or town, notes ("removed", "now dismantled", "pulled over and left to rot", "moved", "*" = cupola removed, now a communications tower). Peak total (325), 22 fire districts, how towermen worked, 1963 map | 159 names (17 southern, 68 mid-northern, 74 northern; the list skips #11) | No | Static HTML on GitHub Pages | None stated; hobbyist | No robots.txt (GitHub 404). Fetch with `fetch_text.py`; parsed copy `forestrangers_stillstanding.json` | One GET | **supplement, but the only name list for the north**: gave the 91 name-only candidates. Undated (c. 2009-2013) |
| Ontario Dept. of Lands and Forests, *Tower Detection System* map, 1963 | https://www.geocities.ws/ontarioftl/FireTowers.pdf (and `map1963.jpg` in the GitHub repo) | Dots only (no names): 100 ft steel, 80 ft or less steel, wood | ~305 dots counted (not a source count) | Dots could be georeferenced by hand; names would have to come from elsewhere | One-page scanned PDF (no text layer) | Crown publication, 1963; the copy is a fan scan | geocities.ws served it | Saved as `FireTowers_1963_map.pdf` | **story-research only** (proves the total; gives the 100 ft / 80 ft split, which a tower page can use) |
| NHLR and FFLOS, Ontario | http://nhlr.org/lookouts/can/on/ ; http://firetower.org/lookouts/can/on/ (note `can`, not `ca`; `/lookouts/ca/<prov>/` is a 404 for Ontario) | **1 lookout (Fort Frances Lookout Tower, CAN 16, ON 1) and 1 former site (Fort Frances Original Site, CAN 1, ON 1)**: coordinates, elevation, administrator, nominator | 1 + 1 | Yes (to seconds) | HTML, plain http | "All rights reserved"; facts only (DESIGN decision) | no robots.txt (404) | `fetch_text.py` (done) | **supplement** (both are in the candidates) |
| FFLA Canada page | https://firelookout.org/lookouts/ca/ | "Under Construction"; Ontario row has an NHLR link only | none | n/a | HTML | n/a | allows | none | skip |
| OpenStreetMap (cached snapshot) | `data/raw/osm/overpass_ca_ak_hi.json` | 8 Ontario fire or lookout towers: Elliot Lake "Fire Tower" (way/node 889596938), Dorset, Temagami, Ignace "Fire Tower" (6610059192), Menzies/Bailloquet, Maple Mountain, Ishpatina, and "Scenic Lookout Tower" at Parry Sound (920367477) | 8 (+2 observation towers I excluded) | Yes | cached JSON | ODbL | n/a | already cached; no new Overpass query made | **supplement** (gave Parry Sound and Ignace coordinates) |
| Wikidata | `data/raw/expansion/on/wikidata_q748998_canada.json` | Class Q748998 in Canada: 11 items, **one in Ontario** (Parry Sound Fire Tower, Q105819616, inception 1927-06-01, no coordinates) | 1 | no | SPARQL JSON | CC0 | n/a | 3 queries used (one timed out with a 504; one zero-result bounding-box query) | **story-research only** |
| Canadian Geographical Names Database (CGNDB) | https://geogratis.gc.ca/services/geoname/en/geonames.json?q=tower&province=35 (also `.csv`, `.geojson`) | Names containing "Tower" or "Lookout" in Ontario: 39 and 29. Only a few are tower-derived: Fire Tower Mountain (Algoma, 46.27089 -82.89016), Highview Tower Hill (Renfrew, 46.0064 -77.3097), Melrose Tower Hill (Sudbury, 48.38757 -82.19514), Louise Tower Mountain (Sudbury, 46.31895 -81.38872), Tower Hill and Tower Bay (Algoma, 49.2111 -85.1375), Old Tower Rocks and Old Tower Island (Parry Sound), plus 20 "Tower Lake"s and some "Lookout" points that are not fire related | ~10 useful | Yes, of the named feature (a hill), not the tower | Public JSON API | Open Government Licence - Canada | no robots.txt (404 page) | Handful of queries (done; raw `cgndb_*_on.json`) | **story-research only**. It also shows that firelookout.ca's Highview pin (45.82665 -77.11088, a Pembroke placeholder) is about 25 km from the real Highview Tower Hill |
| HMDB markers | https://www.hmdb.org/m.asp?m=243299 (Ignace), https://www.hmdb.org/m.asp?m=262093 (Fort Frances) | Marker inscriptions: years, heights, history of the two relocated towers; coordinates of the marker | 2 | Yes (marker) | HTML | Photos belong to their takers; facts only | allows (`map.asp` and full-size photo pages disallowed; `Crawl-delay: 0.1`) | `fetch_text.py` (done) | **supplement** (two candidates) |
| Algonquin Park / Friends of Algonquin Park | https://www.algonquinpark.on.ca/news/2013/2013-07-23_fire_tower_trail_announced.php | "At least 23 fire towers built in Algonquin Park"; the Smoke Lake pine-tree lookout; the "Summit tower" (about 31 m, wood, north of Brule Lake); Big Crow Lake (1956) the last standing | 23 sites, 3 named | No | HTML | none stated | allows | `fetch_text.py` | **story-research** (gave two candidates) |
| Pembroke district list | https://www.liquisearch.com/pembroke_ontario/forest_fire_protection_history (mirror of Wikipedia "Pembroke, Ontario", CC BY-SA) | The 15 towers of the Pembroke fire district (Wilberforce, Mt. Edna, Sherwood, Murchison, Preston, Clancy, Fitzgerald, Brent, Big Crow Lake, White Trout Lake, Stonecliffe, Deux Rivieres, Osler, Lauder, Skymount) | 15 names | No | HTML | CC BY-SA | n/a | done | **supplement** (3 names are in no other source) |
| Petawawa Research Forest | https://storymaps.arcgis.com/stories/3cdb9fa0b6984ec1817e94b30e387322 (JSON at arcgis.com `.../content/items/<id>/data?f=json`) | Malone and Wylie are "fire rating towers" at the forest | 2 | No | ArcGIS StoryMap | Natural Resources Canada | arcgis.com robots allows | done (saved `prf_storymap.json`) | **story-research** (staffing question) |
| Archives of Ontario, Forest History Ontario | https://www.ontarioforesthistory.ca/research-explore/archives (catalogue of other archives), https://aims.archives.gov.on.ca/ | Finding aids: RG 1-186 *Forest Fire Report Files, 1917-2006* (fire reports, not tower lists); RG 1-485 *Hundred Year History Committee records* (research for the official Lands and Forests history); Lakehead University Archives and Archeion hold a Lands and Forests "Fire Watch Tower" postcard | 0 tower lists | No | HTML finding aids; AIMS search is JavaScript (not read) | Crown; finding-aid text | allows | not worth bulk fetching; read individual finding aids when writing stories | **story-research only** |
| OCUL Historical Topographic Maps (Scholars GeoPortal) and McMaster index | https://ocul.on.ca/topomaps/collection/ ; https://library.mcmaster.ca/maps/geospatial/historical-topographic-maps-150000-index | Scanned 1:25,000 and 1:50,000 sheets that print the tower symbol; this is where firelookout.ca's contributors read most positions ("Appears on Pembroke topographic map 31F, 3rd ed., 1977") | n/a | Yes, by eye on the sheet | scans | Crown / library terms | not read | none now | **story-research / position checks** (the way to place the 31 unnamed LIO points and the 91 candidates) |
| Ontario Heritage Act Register, Canada's Historic Places | https://www.heritagetrust.on.ca/oha/oha-register ; https://www.historicplaces.ca/ | I found no fire-tower entry; the search turned up only a military tower (Fort Mississauga) | 0 | n/a | JS search | n/a | n/a | none | skip (not exhaustive: the registers could not be searched by type) |
| Southern Ontario Fire Towers Map (Clay) | http://OntFireTowersMap.yolasite.com/ | "All towers that existed from 1922 onwards" on a map, east and west, plus a Saskatchewan map | probably the best list there is | probably | web map | n/a | **BLOCKED: Cloudflare "Just a moment" challenge on `/robots.txt` and the page (HTTP 403).** Stopped after the first response | none | **blocked**. See question 5 |
| Facebook groups: *Ontario Fire Towers & Lookouts: Preserving Their History*, *Northern Ontario Information Station* | https://www.facebook.com/groups/2441468019/ | Posts, photos, the still-standing list re-posted | n/a | n/a | login | n/a | login wall | **not accessed** | skip |
| Other pages read for facts, no bulk value | blogTO 2026 article on five tower hikes; Dorset and Fort Frances town pages; lostcanada.ca (a JS photo archive: 8 fire-tower photo sets in all Canada); dankachur.com Algoma list (404; was linked from Clay's page); simplyred "Dean's Ontario Fire Tower Adventures" (dead link) | Tourist-tower facts | few | few | HTML | blogTO's robots forbids scraping and data mining; I read the one article once to see which towers are open (Temagami, Dorset, Elliot Lake, Parry Sound, Fort Frances); the access details for those in section 3 come from it and from search snippets, so check them before they go on a page, and do not crawl blogTO | | none | skip |

## 3. Notes on Ontario

* **Names.** Towers were named for a township, lake, hill or nearest village, and Ontario usage is "<Name> Tower" (Lloyd Tower, Lauder
  Tower) or "<Name> Fire Tower". Both bulk sources and the candidates use "<Name> Fire Tower"; the candidates keep the source
  spelling in `other_names` and `source_spelling`. Spellings drift (Donovan / Donovon, Stetham / Stretham, Bonheur / Bonhuer,
  Colquhuon / Colquhoun, Loch Erne / Lock Erne, Mattawan / Mattawawan, Helleyer / Hellyer), so the merge must match on position
  as well as name. A few towers have two names: Menzies / Bailloquet (Catfish Lake, Wawa), Norberg / Griffin Lake (Batchawana
  Mountain), Ellis / Ishpatina, Rorke / Maple Mountain, Val Rita / Hardy. Several names are shared with other provinces (Grassy Lake,
  Aldina). A few LIO names carry only a township ("Township 120 Fire Tower") or are generic ("Old Fire Tower", "MNR").
* **Administrative units.** For `county` use the Ontario *district* in the north (Algoma, Cochrane, Kenora, Nipissing, Parry Sound,
  Rainy River, Sudbury, Thunder Bay, Timiskaming; also Muskoka District Municipality) and the *county* in the south (Renfrew,
  Lanark, Northumberland, Bruce, Norfolk). firelookout.ca's `address` field gives it ("Nipissing District", "Renfrew County"). The
  old "fire district" (22 of them, for example Pembroke, Tweed, Parry Sound, North Bay, Sudbury) is a different unit and is not in any
  data layer; the Pembroke list above is the one example found.
* **Agencies over time.** The Forest Fire Prevention Act of 1917 gave each district forester the towers and towermen. The
  Ontario Department of Lands and Forests ran them to 1972, then the Ministry of Natural Resources (MNR, later MNRF). Petawawa Research Forest
  is federal (Natural Resources Canada); the Highview tower sits on CFB Petawawa (Department of National Defence). A few were
  Ontario Parks' or a private concern's (Richards was "sold to a private concern for scrap metal value" after it ceased to
  be manned in 1974).
* **Build history, from the sources.** First towers were wood (about 35 ft) after 1900 and after the First World War, plus
  platforms in tall trees (Smoke Lake). Steel arrived in the 1920s-30s (Mount St. Patrick may have been among the first 11); the
  usual forms are 80 ft heavy steel with an octagonal or square cupola, light guyed steel, and 100 ft towers from the 1950s;
  the Temagami tower went 1910 wood (45 ft), late 1930s 85 ft steel, 1961 100 ft steel. Towermen worked 1 May to 1 October, often
  with a cabin at the base. Aircraft detection took over through the 1960s; Bonheur was used until 1969, the Dorset original
  until 1961, Richards until 1974. MNR demolished or pulled over many in the 1960s-70s, and removed the bottom ~20 ft of ladder on
  those it left; more removals from 2013 on. Several were moved: Hungerford (Tweed Heritage Centre), Northumberland (Port Hope fire-fighters museum;
  also said to be on an island in Rice Lake), Bruce County (Northern Bruce Peninsula fire hall, Tobermory), Jamieson's Mountain
  (cupola at the Pembroke MNR office, restored 2003), Thistle (re-erected at Field), Olden (Mountain Grove to near Parry Sound),
  Middleville (moved to Clyde Forks 2004, not re-erected), Bonheur (Ignace, 1991), Pickle Lake (said to have come from Atikokan).
* **Public access and rules.** Most standing towers are on Crown land in the bush and are not maintained; Clay's page warns that
  climbing is hazardous. Access that is real: Temagami (trail in the White Bear Forest Conservation Reserve), Dorset (Township of
  Algonquin Highlands, fee), Elliot Lake (a 1.1 km trail), Parry Sound (Tower Hill Heritage Garden), Fort Frances (La Verendrye
  Parkway), Ignace (exhibit beside the library), Restoule Provincial Park (the Pinery tower is still there but its cab was removed). Highview is inside CFB Petawawa and Malone
  and Wylie inside the research forest (permission). No rentals or overnight stays were found anywhere in Ontario.
* **Positions to distrust.** (1) The 20 firelookout.ca placeholders: Lindsay 44.355 -78.73702 (7) and 44.35657 -78.74075 (2), Tweed
  44.47473 -77.31025 (8: Olden, Marmora, Limerick, Kaladar, Hungerford, Hinchinbrooke, Cashel, Ashby), Pembroke 45.82665 -77.11088 (3: Mount Martin,
  Montgomery, Highview). (2) Mount Martin and Stonecliffe are said to stand across the Ottawa River in Quebec. (3) Bonhuer's pin
  (49.486 -91.613) matches neither the original site (25 km east of Ignace) nor the Ignace exhibit (49.4162 -91.6661).
  (4) The Menzies/Bailloquet pin differs by 10 km between OSM and firelookout.ca's Catfish Lake. (5) LIO and firelookout.ca place
  Wylie 3.2 km apart. (6) Skymount appears twice, 3 km apart, both marked approximate. Recommendation: load LIO positions as the main
  position where the two disagree, drop the 20 placeholders to "can't place yet", and let a person decide on the rest.

## 4. Excluded, considered and rejected

| Item | Where seen | Reason |
|---|---|---|
| Thunder Cape Bird Observatory tower (60 ft wooden) | firelookout.ca id 35798 | Bird-observatory observation tower; its page says "Not a fire tower per se" |
| Ferndale Tower, Port Carling | firelookout.ca id 41019; Clay's list | The list says "not official tower, used on the Red Green Show" |
| Tay Marsh Lookout Tower (44.891 -76.195), Nipigon Lookout (49.017 -88.257, disused) | OSM | Observation or viewpoint towers; no fire-detection link found |
| OSM "Tour à feu" (45.5447 -75.9953), "Tour d'observation" nodes, Grand Héron | OSM | Quebec side, left to the Quebec survey (the 45.54 -75.99 "tour à feu" needs their check) |
| Algonquin Visitor Centre "Fire Tower Trail" cupola (2013) | Friends of Algonquin Park | A new cupola built for a boardwalk; an educational replica, not a lookout site |
| Fort Frances Lookout Tower and its Pal Lake original site | NHLR, FFLOS, HMDB | **Kept as BORDERLINE candidates**: built as an RCAF Pine Tree Line radar gap-filler (cancelled 1964), sold to Lands and Forests, "may have" been a short-lived lookout. Radar sites are out of scope, but the lookout registers list it |
| Elliot Lake Fire Tower | firelookout.ca id 11741 | **Kept** (in the bulk source); the page calls it "a replica of a fire ranger's lookout station", so `status: replica` |
| Kenora X-21 Tower, "Shania Twain Tower" (Timmins) | Clay's list | **Kept as candidates with a `scope_flag`**: odd names, could be radio or tourist structures |
| LIO Tower layer: 2,985 non-fire towers (communication, microwave, radio, lighthouse, beacon, lightning locator, meteorological) | LIO | Not lookouts |
| Never-built sites | none found | None of the sources lists a proposed or never-built Ontario tower |

## 5. Open questions for the owner

1. **firelookout.ca licence.** Its records are CC BY-NC-SA 4.0 (non-commercial, share-alike) and our database is ODbL.
   Facts such as a name and a pin are probably fine, as with the other registries, but this site is volunteer-run, its
   pins are hand-made, and its prose and photos are contributors' own. Do you want to ingest names and coordinates only, ask
   the operator, or treat it as story-research?
2. **The 20 placeholder pins.** Drop their coordinates and list them under "Lookouts we can't place yet", or show them as
   approximate pins? (A Pembroke pin 25 km from the real Highview is the sort of error that shows on the map.)
3. **Status of "still standing".** Clay's list is c. 2009-2013 and MNR removed towers afterwards. I set candidates to
   `standing` with a note on each. Would you rather map them to `unknown` until a person or an aerial image checks?
4. **Fort Frances / Pal Lake**: keep, or drop as a radar tower that may never have watched for smoke? The lookout registers
   list it, which DESIGN says to use.
5. **The blocked yolasite map.** It is probably the most complete list of Ontario towers. The author's address is on his
   own page; asking him for the list (or the underlying map data) is a message sent for you, so I did not.
6. **Petawawa towers.** Is a person watching from Malone or Wylie? If it is a yes the site needs its first `staffed` Ontario
   entry. Natural Resources Canada's forest office could say.
7. **Cross-border Quebec towers.** Stonecliffe is in `on_candidates.json` as `region: QC` because Clay's Ontario list names
   it; Mount Martin (firelookout.ca id 39034) is in the bulk source with a Pembroke pin. Quebec's agent may hold both.
