# Expansion survey: British Columbia and Yukon (key `bc-yt`)

Surveyed 2026-10-20. Raw pulls are under `data/raw/expansion/bc-yt/`; the candidate list is
`data/raw/expansion/bc-yt_candidates.json` (401 records). Nothing in the repo was edited.

**Approach taken for candidates:** a full cross-source merge, not "only what the bulk sources miss".
BC has no single clean bulk source (the biggest list, canada-lookouts.weebly.com, has coordinates for
only a third of its names), so every source below was merged by name and position into one record per
site. Each record lists all its source URLs, so the pipeline author can see which source gave what.

## 1. Summary

**How many lookouts existed.** Four published figures disagree, because they count different things:

| Figure | Source |
|---|---|
| 320 "forest fire lookout locations" in BC, 20 of them active and required by the Wildfire Management Branch | BC Gov news release, 26 Sept 2012 (<https://news.gov.bc.ca/releases/2012FOR0178-001437>) |
| "Some 300 active lookouts" at the network's peak | Canadian Geographic, 13 Sept 2024 (<https://canadiangeographic.ca/articles/last-of-the-lookouts/>) |
| "Once numbering over 200" | Heritage Canada magazine 2013 (<https://archive.nationaltrustcanada.ca/sites/www.heritagecanada.org/files/UC_Fire%20Lookouts%20only.pdf>) |
| 348 names in the author's BC index | canada-lookouts.weebly.com (this survey's count; 197 have a page, 151 are name only; about 25 names are towns or stations, and a few are listed twice) |

Our guess for the owner: about 330 to 350 distinct BC sites, which fits the 320 locations plus the
tree, ranger-station and town entries the 2012 count would have left out. Yukon: **12** towers
(canada-lookouts lists 13 pages, but "Tagish" is the same tower as "Jubilee Mountain"), all built
1954 to 1983. "Very few" would be wrong for Yukon.

**Standing.** "Fewer than one hundred structures remain" in BC (The Rainlander and Wild Bluebell,
both 2026). In our list 67 BC sites have a source saying a structure stands (or likely stands), 13
are gone (Jesmond, Lavina, Nahatlatch, Eagle Pass, Promontory, Alex Graham, Salmon, Daer, Mount
Hunter Upper, Mount Shanks, Sheep Mountain, Wardle, Wigwam) and 274 are `unknown` because no source
says. Yukon: 10 standing, 2 unknown.

**Still staffed.**
- BC: **Sinkut Mountain** (staffing began 21 May 2026; the one regularly staffed lookout, observer Bart
  Vanderlinde). **Kuyakuz** (fly-in only) has been vacant since its observer died in summer 2023; the
  CBC headline in 2026 says "B.C.'s last 2 fire lookouts", but I could not read the CBC page (it times out
  for our fetcher), so Kuyakuz is recorded `staffed_now: null`.
- Yukon: five staffed as of 2024 (Moyles' article, reposted later; no 2026 confirmation found): **Dome** (Dawson), **Ferry Hill** (Stewart Crossing), **Murray
  Mountain** (Carmacks), **Tom Creek** (Watson Lake), **Jubilee Mountain / Tagish** (Moyles, "Keeping
  Watch"). Haeckel Hill is now a radio repeater; Kusawa and Paint Mountain were shut by 2024.

**What the 401 candidate records cover.**

| | Count |
|---|---|
| BC named sites | 354 |
| BC unnamed TRIM map symbols (fire lookout tower on the 1980s-90s base map, not matched to any name) | 35 |
| Yukon sites | 12 |
| Records with a coordinate from a source | 156 (120 BC named, 35 BC unnamed, 1 Yukon) |
| Named records with no coordinate but one unique same-name BC Geographical Names summit (`extra.approx_location`) | 77 |
| Named records with no coordinate and no unique summit | 157 |
| `status` standing / gone / unknown (named) | 67 / 13 / 274 |
| `staffed_now: true` | 6 (Sinkut + 5 Yukon) |
| Rental | 1 (Hankin, via the Bulkley Backcountry Ski Society) |

Where the 156 coordinates come from: BC TRIM map symbols 47, canada-lookouts 41, firelookout.ca 27,
BC rec-site layer 17, OSM 12, NHLR 9, HistoricPlaces 2, FFLOS 1.

**National parks.** Mount Revelstoke: Summit Fire Lookout (1927, Federal Heritage Building, standing).
Yoho: Paget Lookout (standing, disused), Mount Hunter Lower (standing), Mount Hunter Upper (the
canada-lookouts page says "Removed"), Tocher Ridge ("old fire lookout"). Kootenay: Mt. Daer
(canada-lookouts says "Removed"). Glacier: no lookout in any source read. Kluane: none inside the park;
Paint Mountain (above Pine Lake, Haines Junction) and Kusawa lie outside it.

## 2. Sources

Priority: **bulk** = fetch whole; **supplement** = fills fields; **story** = research only.

| Source | URL | What it gives | In BC/YT | Coordinates? | Form | Licence / terms | robots / blocked | Recommended fetch | Priority |
|---|---|---|---|---|---|---|---|---|---|
| canada-lookouts.weebly.com ("Canada's Fire Lookouts"; same author family as the US weebly sites already ingested) | <https://canada-lookouts.weebly.com/british-columbia-index.html>, nav list on every page | Name list with regional district (some), per-site pages with lat/lon/elevation (some), "Removed" status words, and dated newspaper and annual-report clippings (Daily Colonist, Forest Branch reports) that date builds and staffing | BC: 348 index names, 198 pages (64 with coordinates, 62 with elevation); YT: 13 pages (12 sites), none with coordinates | 3 decimals (about 100 m), longitude written positive-west | HTML (Weebly). Coordinates are in a "Latitude: 49.383 Longitude: 120.407 Elevation: 1593" line | None stated; the page says lists are "not comprehensive" and a lookout may appear twice. Clippings are old newspaper text: take facts only | robots.txt allows (`Disallow: /ajax/, /apps/`); Cloudflare in front but no challenge shown | GET the home page, read every `<a href>` in the menu, fetch each page 2 s apart (212 pages took about 25 minutes). The BC index page's "go" buttons point to canadafirelookouts.weebly.com, which the earlier links survey found taken over by spam: do not follow those | **bulk** |
| firelookout.ca Open Canada Fire Lookout Index | <https://firelookout.ca/> and `/lookouts/?slug=<slug>` | 206 Canadian rows in a JS array; per-tower page adds elevation (7 BC), year (4 BC), short notes | 50 of its 206 rows are BC | 5-6 decimals when OSM/BCGNWS-derived, 3 decimals when copied from canada-lookouts. **No town-centre placeholders found in BC.** Five are doubtful (see section 3) | JS array `rawTowers` in the home page; per-tower HTML | CC BY-NC-SA 4.0 | `/robots.txt` returns the home page (no real robots file); no challenge | Parse the home-page array (id, title, slug, lat, lng, address, region), then per-tower pages | supplement (50 rows, 27 give the only coordinate we use) |
| NHLR, BC | <http://nhlr.org/lookouts/can/bc/> | 9 registered lookouts with CAN/BC numbers, 6-decimal coordinates, built and removed years, administering agency, cooperators, short description | 9 | yes, 6 decimals (nominator GPS) | HTML, plain http | FFLA register; facts with credit per DESIGN section 1 | robots 404; no block | Index page, then 9 pages (path is `/lookouts/can/`, not `/ca/`) | supplement (best quality) |
| FFLOS, BC | <http://firetower.org/lookouts/can/bc/> | 1 former site: Jesmond (CAN 3, BC 1, registered 11 Oct 2026) | 1 | yes | HTML | as above | none | one page | supplement |
| BC Geographic Warehouse WFS: TRIM landmark structures | `https://openmaps.gov.bc.ca/geo/pub/ows` layer `WHSE_BASEMAPPING.TRIM_EBM_LANDMARKSTRUCTURES`, `cql_filter=FEATURE_TYPE ILIKE '%look%'` | 68 polygons of type `fireLookoutTower` (FCODE BF10950120), no names, all the same 863 m² symbol footprint | 68 (21 matched to a named site within 0.8 km; 12 more placed on name-only sites by a same-name summit; 35 left unnamed) | yes: map-symbol position from 1:20,000 base mapping, tens of metres | WFS GeoJSON (`outputFormat=application/json`) | Licence needs confirming (see section 5) | no robots.txt on openmaps (404) | One GetFeature call, saved in `bcgw/trim_ebm_fireLookoutTower.json` | **bulk** for position |
| BC Geographic Warehouse WFS: rec sites | same host, `WHSE_FOREST_TENURE.FTEN_REC_SITE_POINTS_SVW`, filter `PROJECT_NAME ILIKE '%lookout%' OR PROJECT_DESCRIPTION ILIKE '%fire lookout%'` | 23 hits, 21 real lookouts: name, REC number, description, maintenance level, closure text, established date | 21 | yes, 8 decimals, at the site | WFS GeoJSON | Open Government Licence BC expected (confirm) | none | One GetFeature call (`bcgw/rec_site_points_lookout.json`). Trailhead layer `FTEN_REC_TRAIL_HEADS_SVW` gives 20 more lookout trails (Wigwam, Salmon, Kappan, Seymour, Eagle Eye, Two Sisters...) but at the trailhead, not the lookout | **bulk** (names, status, access text) |
| BC Geographical Names Web Service (BCGNWS) | `https://apps.gov.bc.ca/pub/bcgnws/names/search?name=<n>&exactSpelling=1&outputFormat=json&outputSRS=4326` | Official names with feature type and position. No fire-lookout feature class: the 14 "Lookout ..." names are plain summits (Lookout Mountain, Lookout Point...). Used here to find same-name summits for placing name-only lookouts | 279 queries cached in `bcgnws/q/` | yes, summit position | JSON | Open Government Licence BC | robots 404 (API gateway) | one query per name, 5 workers staggered 2.2 s apart | supplement (placement hints) |
| NHLR sibling / Wikidata | Q748998 class, SPARQL (3 used) | Canada query returned 11 items, 3 in BC (Buchanan, Windy Joe, Nahatlatch). The other two queries (label search in a bounding box, then an mwapi text search) both returned HTTP 504 | 3 | 2 with coordinates | JSON | CC0 | none | not worth more queries | supplement |
| OSM snapshot (already cached, `data/raw/osm/overpass_ca_ak_hi.json`) | n/a | 26 of its 86 elements are in BC (my hand-checked list, in `osm_all_ca_subset.json` with the rest), 1 in Yukon (Dawson) | 27 | yes | JSON | ODbL | n/a | already cached | supplement |
| Canadian Register of Historic Places | <https://www.historicplaces.ca/en/rep-reg/place-lieu.aspx?id=N> | Summit Fire Lookout (id 4691, built 1927, Parks Canada), Monument 83 (18048), Windy Joe (18052, built 1925 per OSM), Saddle Mountain Lookout Trail (25055: says the 1963 lookout had the first female lookout in Canada). Coordinates sit in `<meta name="PlaceLatitude">` tags; the visible text is thin | 4 | yes (a place coordinate, not always the building) | HTML | Parks Canada / province; facts only | robots 404 | fetch by id with curl; `fetch_text.py` drops the meta tags. No list page exists without the search form | supplement |
| Parks Canada Yoho hike page | <https://parks.canada.ca/pn-np/bc/yoho/activ/randonnee-hike/jour-day> | Paget Lookout, Mt. Hunter Lower and Upper, Tocher Ridge | 4 | no | HTML | Crown | allows | one page | story |
| Kootenay NP brochure (c.1970s) | <https://parkscanadahistory.com/publications/kootenay/brochures/banff-windermere-pkwy-e-c1970s.pdf> | "Trail to Mt. Daer Fire Lookout" | 1 | no | PDF | | | one PDF | story |
| The Rainlander | <https://therainlander.ca/bcs-historic-fire-lookout-hikes/> | About 60 named lookouts with a 2026 "structures still standing" list and 17 hike write-ups | about 60 | no | HTML | blog; facts only | allows | one page | supplement (standing status) |
| Wild Bluebell | <https://wildbluebell.ca/fire-lookouts-british-columbia> | Hankin rental, "more than 300 once, fewer than 100 standing, two staffed" | n/a | no | HTML | blog | none found | one page | story |
| BC Gov news release 2012 | <https://news.gov.bc.ca/releases/2012FOR0178-001437> | 320 locations, 20 active; five centennial restorations (Thornhill, Nahatlatch, Buchanan, Owen Hill, Mara) and six assessed (Fraser Mountain, Bickford, Woss, McBride Peaks, Lakit, Mt. Cartier) | n/a | no | HTML | OGL | allows | one page | story |
| 4WDABC news pages | <https://4wdabc.ca/2023/08/22/nahatlatch-lookout-loss/>, <https://4wdabc.ca/2026/08/03/jesmond-fire-lookout/> | Nahatlatch burned 17 Aug 2023 (original late 1950s, rebuilt 2012); Jesmond confirmed lost 27 July 2026; the club maintains Lavina, Cornwall, Greenstone, Eureka (2025) | 6 | no | HTML | blog | allows | per post | story |
| ExploreNorth, Haeckel Hill page | <https://explorenorth.com/yukon/haeckel_hill-forestry_tower.html> | All 12 Yukon towers with build years (quoting canada-lookouts), 2014 staffing, Haeckel history | 12 | no | HTML | blog | allows | one page | **bulk** for Yukon |
| Trina Moyles, "Keeping Watch" | <https://www.trinamoyles.com/field-notes/keeping-watch-dawson-fire-tower> | 2024 article reposted with a later post-script: five Yukon towers staffed; Kusawa and Paint Mountain shut; Dawson tower facts | 5 | no | HTML | blog | none found | one page | supplement |
| Canadian Geographical Names Database | `https://geogratis.gc.ca/services/geoname/en/geonames.json?q=<name>&province=60` | Positions of the named Yukon hills (Haeckel, Ferry, Jubilee, Haldane, Ross, Paint, Ptarmigan) | 7 | summit position only | JSON | Open Government Licence Canada | robots 404 | one query per name (`cgndb/`) | supplement for Yukon pins |
| Sites and Trails BC | <https://www.sitesandtrailsbc.ca/resource/REC...> | Same data as the rec-site layer, as web pages | 21 | no (map is JS) | HTML | | allows all | not needed (use the WFS) | skip |
| BC Forest Fire Lookouts (Facebook group) | <https://www.facebook.com/groups/bcforestfirelookouts/> | The community hub (posts about staffing, losses, new finds) | n/a | no | login | | login only | **not accessed** | story (owner to decide) |
| Bivouac.com | <https://bivouac.com/> | Peak pages mentioning old lookouts | few | no | HTML | | `Crawl-delay: 120` | not crawled (one page is 2 minutes; no list endpoint) | story |

**Blocked or unusable (not retried):**
- `emrlibrary.gov.yk.ca` (Yukon Fire History Atlas): HTTP 403 to our user agent.
- `cbc.ca` pages on Sinkut and Kuyakuz: the fetch times out every time.
- `catalogue.data.gov.bc.ca`: robots disallow `/api/`; the dataset pages are JavaScript only.
- Facebook group: login only.

**One slip to disclose.** In one command I fetched the BC Data Catalogue's `/api/3/action/package_search`
(to learn what lookout datasets exist) before reading its robots.txt, which disallows `/api/`. One
request, no repeat. I deleted the response and used only a hint from it: the catalogue shows the TRIM
EBM landmark layer under licence "Access Only", which is why the licence row above says "confirm".
All BC data afterwards came from `openmaps.gov.bc.ca` (no robots.txt) and the BCGNWS gateway.

## 3. Province and territory notes

**Naming.** English throughout. Sources write "X Fire Lookout", "X Lookout", "X Mountain Lookout" and
bare names ("Agate"). The candidates use "<core name> Lookout" and keep the other forms in
`other_names`. Spelling variants seen: Avery = Vavenby; Camelsfoot = Camelshoof = Camel; Horetzky =
Horetsky; Dina = Dena; Crevice = Crevise; Sinkut = Tsinkut; Wildhorse = Lakit; Mobley = Crowfoot;
Rhoderick Dhu = Roderick Dhu. Several lookouts bear the name of a hill that is not quite where the
tower is (Haeckel Hill: the tower is on the unnamed ridge next to it, per ExploreNorth). About 25 index names are towns or
stations (Terrace, Vernon, Golden, Hope, Lytton, Langford, Courtenay, Comox, Valemont, Fort Fraser,
Denman Island, White Rock, Green Timbers, Holmes Farm...): probably ranger-station or rooftop
lookouts, or mislabelled. They are kept as name-only records with `kind: unknown`.

**Administrative units.** BC "county" = regional district. canada-lookouts uses the pre-2000s names
(Fraser-Cheam, Okanogan-Similkameen, Kootenay-Boundary, Comox-Strathcona, Fraser-Fort George); the
candidates spell them with a plain hyphen and no "Regional District". A few entries give an old forest
district instead (Langford District, Chilliwack District): those are dropped from `county`. Yukon has
no counties; `county` is null and the nearest community is in `extra.yukon_community`.

**Agencies over time.** Dominion Forestry Branch built the first lookouts along the CP Railway Belt
(1921 square stone cabins at Joss Mountain, Eagle Pass, Mara and Mt. Cartier; the Belt passed to the
province in 1930). The BC Forest Branch (1912) became the BC Forest Service, then the Ministry of
Forests; the BC Wildfire Service (Wildfire Management Branch) runs the active ones. Since the 2012
centennial and a 2014 provincial project, **Recreation Sites and Trails BC** takes over abandoned
lookouts as recreation sites, often with a club: Four Wheel Drive Association of BC (Nahatlatch, Lavina,
Cornwall, Greenstone, Eureka; Jesmond with the Clinton and District Outdoor Sportsman Association), Houston
Hikers Society (Owen Hill), Revelstoke ATV Club (Sproat), Kingfisher Historical Society (Mara), the
Bulkley Backcountry Ski Society (Hankin). BC Parks holds Windy Joe, Monument 83 and Cornwall Hills; Parks
Canada holds the Mount Revelstoke, Yoho and Kootenay ones. Yukon: Yukon Wildland Fire Management
(Government of Yukon), fire districts Whitehorse, Dawson, Mayo, Watson Lake, Carmacks, Haines Junction.

**Dates.** The BC network started in the 1920s (earliest in the Vancouver district: Mt. Tucker on
Sonora Island and Mt. Benson near Nanaimo, per a Facebook post I could only see in a search snippet);
canada-lookouts clippings show Goat Mountain (Creston) and Baker Mountain (Cranbrook) lookouts already in the
1913 Forest Branch report, and Casey Mountain in 1919. Most surviving structures date from the 1920s to
1950s (Heritage Canada) or the 1970s (Jesmond 1971, Begbie early 1970s). Yukon towers: 1954 (Haeckel)
to 1983.

**Still staffed, and access.** Sinkut Mountain is a government workplace staffed May to September
(usually 14-day stints, 8 am to 8 pm). The public road reaches the summit and visitors drive up. Kuyakuz is
fly-in. Yukon's five staffed towers (as of 2024) are workplaces; Dawson's sits on the Second Dome up a gravel road
off Dome Road. Other BC sites are mostly recreation sites: Buchanan (drive-up on a 2WD gravel road,
about 12,000 visitors a year in 2012), Idaho Peak (trail open, lookout locked), Hamilton (private
land, no access), Summit Fire Lookout (summer only, no dogs, park fees), Windy Joe (open hut). Wildfire
closures hit several in 2023 to 2026: Nahatlatch, Jesmond, Lavina, Sproat, Promontory.
**Jesmond:** FFLOS says the Fiftynine Creek Fire destroyed it on 17 July 2026; 4WDABC says it was confirmed lost on 27 July in the Big Bar Complex. Both are kept in the record.

**Rentals.** Only **Hankin Lookout** (north of Smithers): a winter-ready cabin sleeping six, booked
through the Bulkley Backcountry Ski Society (<https://bbss.ca/backcountry-cabins/>); a Facebook post says
it was closed for a stove repair (date not visible). Day-use: everything else read.

**Coordinate quality, in the candidates.** `location_from` is the source URL; `extra.location_precision`
says what kind of point it is; `extra.location_alternates` lists other sources that disagree by over
0.4 km. Checked against BC Geographical Names (`extra.bcgnws_nearest_same_name_summit_km`):
- firelookout.ca: many coordinates equal the named-summit position to within 0.2 km (Horetzky 0.04,
  Deescius 0.03, Hallowell 0.13), so they are summit positions, not surveyed tower positions.
  No town-centre placeholders found in BC. Doubtful: **Fording** (25 km from Fording Mountain),
  **Brent** (16 km from Mount Brent), **Casey** (19 km from Mount Casey; the Rainlander calls it
  Casey / Plumbob), **Hunter** (it is in Yoho; unclear which of the two towers), **Bull** (name too generic to check).
- canada-lookouts: **Bickford** longitude looks wrong (55.606, -121.431 vs Mount Bickford 55.618,
  -122.422, 62 km west, near Chetwynd). **Blueberry** (49.554, -118.519) is Bluejoint's position; another
  Blueberry at 56.72, -121.77 (Peace River) is a different site. **Sugarloaf Mountain** sits 0.9 km from
  Sugar Mountain and was merged with it.
- OSM "Historic Firetower" (node 1904481832, 51.047, -118.144) is 7.6 km from the Summit Fire
  Lookout's register position and is probably a mis-pin of it; merged, flagged in `location_alternates`.
- 12 name-only records got a position from an unnamed TRIM symbol lying within 1.5 km of a same-name
  summit (e.g. Sinkut, Tacheeda, Thunder, Lolo, Kobau Mountain), recorded with
  `location_confidence: medium`.

**Yukon positions.** No source gives a tower position except OSM's Dawson node (64.0683, -139.3334, the
Second Dome). For seven others `extra.named_feature_position` holds the CGNDB position of the hill the
tower is named for. Murray Mountain, Tom Creek, Kusawa, Tagish and Transport Creek have no usable
CGNDB match.

## 4. Excluded and rejected

| Item | Reason |
|---|---|
| Coastal artillery and fire-control posts at Victoria-Esquimalt (Christopher Point, Mary Hill, Albert Head, Macaulay Point and others; <https://www.northamericanforts.com/Canada/bc2.html>) | Aimed guns, not fire spotting. None of them appears in the lookout sources, but a name search later should skip them. |
| WWII aircraft-detection posts on the BC coast | Not fire detection; none found in sources. |
| BC Geographical Names "Lookout Hill / Lake / Peak / Point / Ridge / Island / Mountain" (14 names) | Ordinary place names, not structures. |
| Rec sites "Lookout Lake" (REC3066) and "Swansea Mountain" (REC2002) | Matched the word "lookout" but are not lookouts. |
| Trailhead records (20) from `FTEN_REC_TRAIL_HEADS_SVW` | Position is the trailhead; used for names and status text only. |
| Alberta lookouts in the OSM snapshot near the border (Kananaskis, Raspberry Ridge, Sugarloaf, Porcupine, Ironstone, Hailstone Butte, Mockingbird, Limestone, and others) | In Alberta; belong to the Prairies survey. |
| Holdover Peak | The US-side half of the Monument 83 pair (Canadian Register: "one Canadian, one American"). Check whether Firefinder's Washington data already has it. |
| OSM "Historic Firetower" at 51.047, -118.144 | Merged into Summit Fire Lookout as a probable mis-pin. |
| Old Glory's weather station | A weather station on the summit; the lookout building stays. |
| Never-built sites | None identified. |
| Canada's Fire Lookouts spam domain canadafirelookouts.weebly.com | Taken over (earlier survey); not fetched. |

## 5. Open questions for the owner

1. **Approximate pins for BC.** The US rule uses county plus a single same-name GNIS summit. I had no
   regional-district polygons, so I used "exactly one same-name high-ground feature in all of BC"
   (77 records) and left the position in `extra.approx_location`, with `lat`/`lon` null. Accept this as the BC
   equivalent? The alternative is to fetch regional district boundaries and relax to "one per district".
2. **157 named records with no position and no unique summit** (96 have no same-name summit at all; 54 have
   several; 7 have names too short or numeric to look up). Should they appear on "Lookouts we can't place yet"? Many are the town and station names.
3. **35 unnamed TRIM symbols.** They look like real lookout towers from the 1980s-90s base map, but have no
   name and no second source. Include as unnamed sites, hold them back, or try matching names from
   a 1:50,000 map later?
4. **Licences.** firelookout.ca is CC BY-NC-SA 4.0; the NC and SA terms may not fit our ODbL database, so
   take facts only or ask the owner (the site takes contributions via ko-fi and a submit form, which I did
   not touch). canada-lookouts.weebly.com states no terms and quotes old newspapers. The TRIM layer's
   licence needs checking on the catalogue's dataset page (JavaScript only, so a person must look);
   the rec-site layer is expected to be Open Government Licence BC.
5. **The Facebook group "BC Forest Fire Lookouts"** is where the community reports staffing, losses and new
   finds (it was the only place I saw a 21 May 2026 Sinkut staffing note and a Kuyakuz hope). Login only, so
   nothing from it is in the candidates except those two facts, cited by URL. Do you want to approach its
   admins?
6. **Kuyakuz staffing in 2026** is unknown. The CBC "last 2 lookouts" article would settle it but I
   could not load it.
7. **Yukon positions.** Accept CGNDB named-feature positions as approximate pins, or leave the 11
   without a tower position off the map until someone supplies coordinates (Yukon Wildland Fire
   Management could, by records request)?
