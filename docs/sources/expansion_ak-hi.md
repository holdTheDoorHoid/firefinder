# Expansion survey: Alaska and Hawaii (key `ak-hi`)

Surveyed 2026-10-20. Rules: `/tmp/.../scratchpad/survey_rules.md` (politeness, robots, no edits to existing files).
Candidates: `data/raw/expansion/ak-hi_candidates.json`. Raw pulls: `data/raw/expansion/ak-hi/`.

## 1. Summary

**Hawaii: no fire lookout found. Alaska: six named sites, all BLM towers from about 1970, and no bulk source for any of them.**

Neither state has a lookout network the way the lower 48 do, and the evidence says so directly:

* **Alaska had no lookout network.** The standard history of Alaska fire control (Todd & Jewkes, UAF Bulletin 114,
  2006) says the roads, firebreaks, lookout towers and ranger stations that served the contiguous states were
  missing in Alaska, and that detection was by aircraft from 1939. Three federal papers say it outright: USFS 1963
  (Hardy & Franks, *Forest fires in Alaska*: "no fixed lookouts exist in Interior Alaska"), BLM 1966 ("There are
  no lookouts in the state") and BLM 1967 (no lookout towers in Alaska; the cost of an adequate network would be
  prohibitive). Rakestraw's 1981 *A History of the United States Forest Service in Alaska* never mentions a
  lookout in chapters 1-8 (the only ones I could fetch), and the USFS CCC history (FS-395, ch. 11) lists no lookout
  work in either territory.
* **The one exception is in the BLM's 1970 *Alaska Fire Report*:** "the Bureau used lookout towers as available
  during 1970. Two were in use near Fairbanks ... one at Murphy Dome and another at Birch Hill. Two others were
  used in outlying areas on the east, near the U.S.-Canadian border. Still others were manned at Bald Mountain,
  Lazy Mountain, Gordon Lyon Peak, and Jean Lake in the Anchorage-Palmer Area." That is 8 sites; 6 have names
  and are the candidates. A 1979 UAF bulletin confirms a BLM fire tower still stood on Birch Hill and says it was one of only two
  such towers in the Fairbanks Fire District. This also explains the FFLA's one line on Alaska (it says there may
  have been two near Fairbanks).
* **Total ever existing in Alaska, from sources: 8 (6 named, 2 unnamed).** Standing: unknown for all (no source
  after 1979). Staffed now: none found; the Alaska Fire Service now relies on aircraft, the Alaska Lightning
  Detection Network and public reports (AICC / fire.ak.blm.gov). Candidates: 6, none with a tower position.
* **Hawaii: 0.** FFLA, NHLR, FFLOS, OSM, Wikidata, Commons, the NPS NRHP layer and the 1972 NPS *Administrative
  History of Hawaii Volcanoes and Haleakala National Parks* hold or mention none; the Hawaiian Forester /
  Territorial Board reports for 1904-1920 mention lookouts only on the US mainland; DLNR DOFAW's fire pages
  mention none. Every "lookout" in Hawaii found is a scenic overlook (Kalalau, Kilohana, Kalahaku, Kipuka Ahiu),
  a military post, or the name of a public-awareness campaign. I cannot prove a negative: a 1930s CCC-era
  Territorial Forestry fire lookout would be in reports for 1930-1945 that I could not full-text search (see
  open questions).

## 2. Sources

| Name | URL | What it gives | Count in AK/HI | Coordinates? | Form | Licence / terms | robots / blocked | Recommended fetch | Priority |
|---|---|---|---|---|---|---|---|---|---|
| BLM *Alaska Fire Report* (1970) | https://archive.org/details/alaskafirereportunit | **The only list of Alaska lookouts**: Murphy Dome, Birch Hill, Bald Mountain, Lazy Mountain, Gordon Lyon Peak, Jean Lake + 2 unnamed | 8 sites (6 named) | No | Internet Archive OCR text, 57 KB (`ia/alaskafirereportunit_djvu.txt`) | US government work | archive.org robots allow | `curl https://archive.org/download/alaskafirereportunit/alaskafirereportunit_djvu.txt` | **Bulk (it is the whole list)**; story research for the 6 |
| UAF AFES Bulletin 51, *Birch Hill Park: a case study* (1979) | https://www.uaf.edu/afes/publications/database/bulletin/files/pdfs/Bulletin_51.pdf | A BLM fire tower still on the Birch Hill summit in 1979, one of only two in the Fairbanks Fire District; summit road under military control | 1 | No (bench mark location only in text) | PDF | University publication, cite | none seen | `fetch_text.py URL --grep "fire tower"` | Supplement |
| Todd & Jewkes, UAF Bulletin 114, *Wildland Fire in Alaska* (2006) | https://www.uaf.edu/afes/publications/database/bulletin/files/pdfs/Bulletin_114.pdf | Why Alaska had no towers; agency history (Alaska Fire Control Service 1939, BLM, State Division of Forestry takeover of the Kenai and Anchorage areas in 1976) | context | No | PDF 310 KB text | University publication | none seen | `fetch_text.py` | Story research (context) |
| Hardy & Franks, *Forest fires in Alaska* (USFS PNW, 1963) | https://archive.org/details/forestfiresinala05hard | "no fixed lookouts exist in Interior Alaska" | context | No | IA OCR | US gov work | ok | `curl .../forestfiresinala05hard_djvu.txt` | Story research |
| BLM *B.L.M. in Alaska, 1966* and *Your public lands with BLM in Alaska* (1967) | https://archive.org/details/BLMinAlaska1966 , https://archive.org/details/YourPublicLandswithBLMinAlaska | "no lookouts in the state" / "no lookout towers in Alaska" (dates the towers to after 1967) | context | No | IA OCR | US gov work | ok | curl `_djvu.txt` | Story research |
| Rakestraw (1981), *A History of the United States Forest Service in Alaska* | https://npshistory.com/publications/usfs/region/10/history/chap1.htm (to chap8) | No lookout in ch. 1-8 (chapters 9-11 are not at the URL pattern I tried) | negative evidence | No | HTML | Public domain | ok | `fetch_text.py --grep lookout` | Negative evidence |
| USFS FS-395, *The Forest Service and the CCC* ch. 11 | https://www.npshistory.com/publications/usfs/FS-395/chap11.htm | CCC work in Alaska (transport, recreation, buildings) and Hawaii (Territorial Forestry Commission 675 enrollees, Hawaii National Park 225); no lookout work named | negative evidence | No | HTML | Public domain | ok | `fetch_text.py` | Negative evidence |
| NPS *Administrative History of Hawaii Volcanoes and Haleakala NPs* (Jackson, 1972) | https://npshistory.com/publications/havo/adhi.pdf | 611,000 characters; only scenic lookouts (Kipuka Ahiu, Kalahaku, Volcano House), no fire lookout | negative evidence | No | PDF | Public domain | ok | `fetch_text.py --grep "lookout|fire tower"` | Negative evidence |
| NPS NRHP points layer | https://mapservices.nps.gov/arcgis/rest/services/cultural_resources/nrhp_locations/MapServer/0 | 324 Alaska (`State='ALASKA'`) and 267 Hawaii (`'HAWAII'`) listings, with positions; **none is a fire lookout**. Alaska hits that look relevant: Curry Lookout (hotel shelter), 14 CCC "Shelter Cabin" listings on Admiralty Island | 0 | Yes (point) | ArcGIS REST query, JSON (`nrhp_ALASKA.json`, `nrhp_HAWAII.json`) | Public domain | no robots.txt (404) | `...MapServer/0/query?where=State='ALASKA'&outFields=*&f=json` | Supplement (re-run before launch: new listings) |
| USGS GNIS Domestic Names | cached `data/raw/gnis/DomesticNames_AllStates_Text.zip` | **Natural features only** (no Tower or Building class; AK 29,783 rows, HI 7,334): 10 AK summits/ridges named Lookout Hill/Mountain/Ridge, none in HI. Used here only to point at the six BLM sites' named hills | 0 as lookouts | Yes (feature, not tower) | pipe-delimited text | Public domain | n/a | already cached | Supplement (approximate-location rule) |
| FFLA / NHLR / FFLOS | https://firelookout.org/lookouts/us/ak/ , http://nhlr.org/lookouts/us/ak/ , http://firetower.org/lookouts/us/AK (and `/hi/`) | AK: FFLA page is "Under Construction" and says only that there may have been two lookouts near Fairbanks; NHLR and FFLOS each say they register none for AK and HI. FFLA's HI page is a mis-linked firefinder-history page | 0 | n/a | HTML | as DESIGN §2 | ok | already crawled | None |
| Ron Kemnow's weebly sites | https://westlookouts.weebly.com/alaska.html | An empty "ALASKA" heading (no entries); no Hawaii page (404) | 0 | n/a | HTML | none stated | ok | `fetch_text.py` | None |
| OSM snapshot | `data/raw/osm/overpass_ca_ak_hi.json` | 0 in AK/HI (as the rules state) | 0 | n/a | JSON | ODbL | n/a | cached | None |
| Wikidata | `data/raw/expansion/ak-hi/wikidata_all_firetowers.json` | All Q748998 items with coordinates (328 worldwide): **none** inside Alaska or Hawaii bounding boxes. (2 of 3 allowed queries used; the first, a recursive P131 query, timed out) | 0 | n/a | SPARQL JSON | CC0 | ok | cached | None |
| Wikimedia Commons categories | https://commons.wikimedia.org/wiki/Category:Fire_lookout_towers_in_the_United_States_by_state | 39 states listed; no Alaska or Hawaii category | 0 | n/a | MediaWiki API | CC | ok | n/a | None |
| Library of Congress, Chronicling America (Alaska, Hawaii papers to 1963) | https://www.loc.gov/collections/chronicling-america/ (JSON with `fo=json&fa=location_state:alaska`) | Tried 4 queries per state (2 of the 8 returned an error page instead of JSON and were not retried): the search is fuzzy, not a phrase match, and returned mostly noise (a 1913 ship lookout; nothing about fire towers). Saved in `ca/` | 0 useful | n/a | JSON (OCR snippets) | public domain | `/search` is disallowed; `/collections/` path is not; Crawl-delay 5 honoured | not recommended | Dropped |
| Hawaiian Forester & Agriculturist (1904-1920) and Board of Commissioners of Agriculture and Forestry reports (to 1919) | Internet Archive, e.g. https://archive.org/details/hawaiianforester1112hawa | Grepped 11 volumes for lookout / fire tower / fire watch: only mainland items, plus Kilohana "lookout" on Kauai (a rain-gauge overlook) | 0 | n/a | IA OCR | public domain | ok | curl `_djvu.txt` | Negative evidence; **the 1930-1945 reports are the gap** |
| Alaska Heritage Resources Survey (AHRS) | https://dnr.alaska.gov/parks/oha/ahrs/ahrs.htm | Inventory of 45,000 sites that would record any lookout structure | unknown | yes | restricted database | access agreement and fees | not opened (needs a user agreement; not for us to sign) | ask OHA | Story research, owner decision |
| Alaska Guide Co / *Glacier Lookout* | https://alaska.guide/glacier-lookout | A private cabin above Valdez Glacier sold as "Alaska's only traditional fire lookout" | 1 (excluded, see §4) | no | HTML | n/a | **Blocked: Sucuri JavaScript challenge** ("Javascript is required"). Stopped; nothing else fetched from alaska.guide | search snippets + alaskalodgeguide.com only | Excluded |
| JBER Nike Site Summit page | https://www.jber.jb.mil/Services-Resources/Environmental/Nike/NSS/ | Mount Gordon Lyon carries the Nike Site Summit complex (used in the Gordon Lyon Peak candidate's access note) | context | no | HTML | gov | 403 to our fetcher; claim taken from the search snippet only | n/a | Context |

## 3. State notes

### Alaska

* **Administrative units.** Boroughs and census areas, not counties. The candidates use the borough names GNIS gives
  (Fairbanks North Star, Matanuska-Susitna, Anchorage municipality). `region` AK.
* **Agencies over time.** USFS manages the Chugach and Tongass National Forests and fought fires there from 1907
  (rarely needed, high rainfall) but never built a lookout system. The Territorial General Land Office started
  the Alaska Fire Control Service in 1939 (aircraft detection), which became the BLM Alaska Fire Control Service /
  Alaska Fire Service; the State Division of Forestry took over fire management for the Kenai and Anchorage areas
  in 1976. The 1970 towers are BLM ("the Bureau"). Today's Alaska Fire Service works from Fort Wainwright (AICC).
* **No still-staffed programme found.** None of the documents after 1979 names a lookout; the current agency sites
  describe aircraft, the lightning network and public reports.
* **Names to avoid being fooled by.** (1) **Tongass CCC "Shelter Lookout/Cabin"**: the Forest Service's recreation
  listings call the 1930s CCC three-sided log shelters on Admiralty Island's canoe route, and others such as Pinta
  Cove, "Shelter Lookout/cabin". They are camp shelters, built 1933-37; 14 are on the NRHP (e.g. Lake Guerin West,
  NRHP 95001301). A name match on "lookout" in a Forest Service or campflare feed would wrongly import them.
  (2) **RIDB activity "FIRE LOOKOUTS/CABINS OVERNIGHT"** is attached to BLM Alaska trail shelters (Ptarmigan Creek
  and North Fork) and Wolf Run Cabin; the pipeline already rejects the first two in
  `ridb_excluded.json`. (3) **Curry Lookout** (NRHP 92000424, Mat-Su) is a 1920s Alaska Railroad hotel shelter on
  Curry Ridge for guests to view Denali (per a web search summary; the NRHP layer lists it as a building). (4) GNIS has ten summits and ridges named Lookout Hill, Lookout Mountain
  or Lookout Ridge: these are place names, not evidence of structures.
* **Military neighbours.** Murphy Dome (Air Force radar, then communications) and Mount Gordon Lyon (Nike Site
  Summit) were military sites; the BLM lookouts, if on those hills, would sit beside them. Birch Hill's summit road
  was military-controlled in 1979.
* **Where more could be found** (not reachable by us): BLM Alaska Fire Service and State Division of Forestry
  records (a records request or a call), Fairbanks and Anchorage newspapers after 1963 (paywalled), the AHRS, and
  the 1969-1980 BLM Alaska annual fire reports (IA has only the 1970 one that I found).

### Hawaii

* **Administrative units.** Counties (Hawaii, Maui, Kauai, Honolulu; Kalawao is tiny). `region` HI.
* **Agencies.** Territorial Board of Commissioners of Agriculture and Forestry (1903) -> Territorial Division of
  Forestry -> State DLNR Division of Forestry and Wildlife (DOFAW). CCC 1933-42 had 675 enrollees under the
  Territorial Forestry Commission and 225 in Hawaii National Park (FS-395). DOFAW responds to wildfire on about 26%
  of the state's land and co-responds with county fire departments and federal agencies; its pages mention
  nothing like a lookout.
* **What the sources show.** No lookout network, and no plantation "fire watch" or ranch tower is mentioned by
  any source I could read.
* **Name traps.** (1) **"Wildfire LOOKOUT!"** is the Hawaii Wildfire Management Organization / DOFAW public
  awareness campaign (10th year in 2025) and floods search results. (2) **Scenic overlooks**: Kalalau Lookout and
  Kilohana Lookout (Kauai; Kilohana Lookout had a rain gauge in 1916), Kalahaku Lookout (Haleakala), Kipuka
  Ahiu lookout (Hawaii Volcanoes). (3) **Military**: Puu o Lokuana "lookout" (Army radar/ship-and-plane
  watch, Kahuku Ranch on Hawaii Island), Pohakuloa Training Area fire stations (firefighting, not detection
  towers), Aloha Tower (harbour pilots), and the WWII coastal-artillery fire-control stations on Oahu (see §4).

## 4. Excluded / considered and rejected

| Item | Where | Why |
|---|---|---|
| WWII coastal-artillery **fire-control stations** (Harbor Defenses of Honolulu and Pearl Harbor: observation towers and pillboxes at Diamond Head, Koko Head, Makapuu, Kaena and others) | Oahu, plus a few on the other islands | They aimed guns (fire control = artillery). **Category only; not enumerated.** Refs: https://www.army.mil/article/192041/ring_of_steel_protected_oahu_from_invasion_but_not_from_attack_by_air , https://cdsg.org/list-of-american-military-reservations-and-concrete-gun-batteries-hawaii/ |
| Pohakuloa Training Area, Schofield Barracks, Kahuku, Makua | HI | Army ranges; fire stations and observation posts, not fire lookouts, per every source read |
| Puu o Lokuana | Kahuku, Hawaii Island | WWII Army lookout for ships and aircraft (radar), then cinder quarry |
| Kalalau Lookout, Kilohana Lookout, Kalahaku Lookout, Kipuka Ahiu lookout | Kauai, Maui, Hawaii | Scenic overlooks built for visitors |
| Aloha Tower | Honolulu | Harbour landmark; observation deck and pilot lookout |
| Kokee, South Point, Koko Crater, Punamano and Bellows Air Force stations; Barbers Point and Kaneohe air stations | Hawaii | Air Force radar and military sites in GNIS "Military" class, not fire lookouts |
| **Glacier Lookout** | Valdez, AK (West Peak above Valdez Glacier, about 3,600 ft per a Dwell listing) | Private rental cabin run by Alaska Guide Co. The operator's tour page calls it "Alaska's only traditional fire lookout", but the operator's lodge listing says it was built mainly to watch the retreat of Valdez Glacier. No evidence it ever did fire detection. **Owner call**, see §5. alaska.guide is behind a bot challenge, so it was not fetched. |
| 14 CCC shelter-cabin NRHP listings ("Shelter Lookout/Cabin") on Admiralty Island | Tongass NF, AK | Backcountry camp shelters for the canoe route (NRHP 95001294-95001309), not fire lookouts |
| Curry Lookout | Mat-Su, AK (NRHP 92000424) | 1920s railroad hotel shelter for tourists |
| Ptarmigan Creek and North Fork trail shelters, Wolf Run Cabin | BLM Alaska | Emergency or recreation shelters tagged "FIRE LOOKOUTS/CABINS OVERNIGHT" in RIDB |
| Murphy Dome AFS, Fire Island AFS, Ohlson Mountain AFS and other Alaska AC&W radar stations | AK | Air defence radar |
| 10 summits and ridges named Lookout Hill/Mountain/Ridge | AK (GNIS) | Place names only, no source ties any to fire detection |
| 2 unnamed BLM lookouts "in outlying areas on the east, near the U.S.-Canadian border" (1970) | AK | Real but unnamed, so cannot be a site record; the report text is in the evidence file |

## 5. Open questions

1. **Glacier Lookout (Valdez).** Keep out (my recommendation: built as a glacier observatory, never fire
   detection) or show it as a `point`/`ground` tourist lookout with a "never a fire lookout" note?
2. **Six BLM sites with no position.** The report names each hill but gives no tower position, and the GNIS
   name matches are mine (Jean Lake has no unique match and Bald Mountain is ambiguous). Should they appear on the
   "Lookouts we can't place yet" list until a real position turns up, or should the pipeline accept the DESIGN
   3.5 approximate-location rule for the ones with one GNIS match (Birch Hill, Murphy Dome, Lazy Mountain, Gordon
   Lyon)?
3. **Should the site say plainly that Hawaii has none?** A one-line state note ("no fire lookouts documented in
   Hawaii or Alaska before about 1970") could save visitors from the scenic "Lookout" overlooks. I recommend it.
4. **Is a records request worth it?** The AHRS, the State Division of Forestry and the Alaska Fire Service could
   settle the unnamed east-Alaska pair, the dates and the current state of the six towers. These need a person to
   write, sign an AHRS user agreement, or call; I did not attempt any of them.
5. **Hawaii 1930-1945.** The territorial forestry and CCC reports are not full-text searchable by us (HathiTrust
   and the UH eVols repository were not tried). If the owner wants Hawaii closed with confidence, a person with
   library access should search those years for "fire lookout".
