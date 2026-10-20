# Expansion survey: Quebec, New Brunswick, Nova Scotia, Prince Edward Island, Newfoundland and Labrador (key `qc-atl`)

Surveyed 2026-10-20. Nothing in the repo was edited. Raw pulls are under `data/raw/expansion/qc-atl/` (the weebly
province pages and 327 tower pages, the NHLR/FFLOS pages, five CGNDB province CSVs, two Wikidata results, and the two
small scripts in `build/` that turn them into the candidate list). The candidate list is
`data/raw/expansion/qc-atl_candidates.json` (364 records). Every host was read with our user agent at most once per 2 s.
Blocked, not worked round: BAnQ Advitam (Radware CAPTCHA on the second request), the Provincial Archives of New Brunswick
catalogue `search.canbarchives.ca` (redirects every page to `/challenge-inline`; `Crawl-delay: 60`) and ArchivesCanada's
AtoM (a "Verifying your browser" page). Facebook groups were not opened (login). The CBC News pages timed out twice and
were read through Yahoo's copy.

## 1. Summary

**How many sites existed.** Nobody has published an all-time count for any of the five.

* **Quebec: more than 500 towers at once, at the peak.** SOPFEU's history says the network reached its high point in the late
  1930s with "more than 500 towers" (SHFQ/SOPFEU article *Le gardien de tour*; the SHFQ Lanaudière panel says "nearly 500").
  A Quebec interpretation text quoted by Géo Plein Air gives **416 wooden and 48 steel towers in 1941** (464). A heritage
  society post (secondary, Facebook) says 503 in 1966. The hobby author of the only multi-province list guesses "1200 plus"
  lookouts over all time. First tower 1910 (south of Lac Matapédia, 518 m); one association alone, St. Maurice FPA, built 75 new
  towers in 1923-24. My guess for the all-time number of *sites* is 800-1,200; that is a guess, not a source.
* **New Brunswick: 72 sites named**, from the annual reports of the Department of Lands and Mines (1920s-1966). A Provincial
  Archives of NB finding aid mentions "a detailed list of fire towers in New Brunswick in 1960" (item P211/10229; the page is
  behind a bot challenge, so I could not read it). That list is the best lead for a full count.
* **Nova Scotia: 27 observation towers in 1960** (Canada Year Book 1961) and **33 seasonal DNR towers in 2009** (Marscan,
  CBC). 37 sites named (31 weebly + 6 more from Marscan). Half were closed in 1970 (Facebook memory, snippet only).
* **Newfoundland: 21 government lookout towers in 1960** (Canada Year Book 1961), plus the paper companies' and railway's own
  (counted by nobody). The government's first four were begun in 1935. 35 sites named on the island. Labrador: none found.
* **Prince Edward Island: none found**, and a reason to think there were none (section 3).

**How many are standing.** A handful. Quebec has 4 confirmed standing (Luskville, Saint-Rémi-d'Amherst, Mont Gaudet as a frame
without its cab, Mont Morisette) plus two towers whose state nobody states (Maniwaki rue Comeau, listed by a heritage inventory;
Valcartier) and two replicas; New Brunswick 2 (Mount Carleton summit tower,
Blackville moved to a private yard) and an OSM "Fire Tower" on Mount Champlain whose status nobody states; Nova Scotia
**0 confirmed** (the DNR closed its network in 2013 and, per CBC, dismantled the towers by 2015; the Parks Canada tower in
Kejimkujik is unverified); Newfoundland 1 (Ochre Hill, Terra Nova NP, climbable).

**Staffed now: none found in any of the five.** Quebec's last tower in use was on the Valcartier base until 1981
(SOPFEU). New Brunswick stopped in 1968 at Mount Carleton (park sign) and early 1970s at Blackville. Nova Scotia ended in
2013-15. Newfoundland's government site describes aircraft and ground crews only; Ochre Hill is "historically" a fire-watch
station.

**What my candidates cover (approach).** No bulk source with coordinates exists for these provinces: firelookout.ca holds
**0 rows** in the five (its 206 rows are BC, ON, SK; its NS and PEI region pages are empty) and no open-data layer lists
fire towers. So I did the opposite of the Ontario approach: the candidates file carries **every site I found, 364
records**, mostly name-only:

| | records | with coordinates | standing / replica | gone | from the weebly list | not on it |
|---|---|---|---|---|---|---|
| Quebec | 219 | 6 | 4 / 2 | 1 | 208 | 11 |
| New Brunswick | 73 | 4 | 2 / 0 | 6 | 72 | 1 |
| Nova Scotia | 37 | 0 | 0 / 0 | 33 | 31 | 6 |
| Newfoundland and Labrador | 35 | 1 | 1 / 0 | 0 | 35 | 0 |
| PEI | 0 | 0 | 0 | 0 | 0 | 0 |

Only **11 of 364 have a position from a source.** The other 353 have a name, a county or an association, sometimes
a year, and nothing to put on a map. 52 of them carry an `approx_hint` (the one CGNDB relief feature of that name in the
same county: a place-name match, not a tower position, for the owner's "approximate location" rule). The statuses in the
Nova Scotia block are `gone` for 33 of 37 (the sites in Marscan's 2009 list, on the strength of the province-wide closure); each says so in
`status_note`.

## 2. Sources

| Name | URL | What it gives | How many in my area | Coordinates? | Form | Licence / terms | Robots / blocked | Recommended fetch | Priority |
|---|---|---|---|---|---|---|---|---|---|
| **Canada's Fire Lookouts** (weebly; same hobby family as the US weebly sites already ingested) | `https://canada-lookouts.weebly.com/` and `/quebec.html`, `/new-brunswick.html`, `/nova-scotia.html`, `/newfoundland.html` | Per province: an index page with one `<h2>` per site and, under it, the county or protective association (and division) and sometimes dated clips from annual reports and newspapers; a page per tower in the sidebar menu | QC 210 index entries (178 with their own page), NB 72, NS 31, NL 35 (six more NWT rows sit under the Newfoundland header, for the NT survey) | **None** | HTML (weebly) | none stated; names, places, years only (the clips are quotes, not copied) | allows (`Disallow: /ajax/`; named bots blocked, not us) | GET the four index pages and parse `<h2>`; read the per-tower page only where the sidebar has one (327 pages = 12 min at 2.2 s). Scripts: `data/raw/expansion/qc-atl/build/parse_index.py`, `build_candidates.py` | **bulk** (names, associations, years) |
| NHLR Canada pages | `http://nhlr.org/lookouts/can/<prov>/` (`qc`, `ns`, `new-brunswick`; `/lookouts/ca/` redirects) | Register number, date registered, location, coordinates, elevation, built, agency, short text | QC 3, NB 2, NS 2 (no coordinates) | yes, 6 of 7 (to 0.001 arc-minute) | HTML | "All rights reserved"; facts only | no robots.txt (404) | plain GET, follow the redirect | **supplement** (already the owner's NHLR path) |
| FFLOS Canada pages | `http://firetower.org/lookouts/can/` | former sites | NB 1 (Rogersville, with coordinates) | yes | HTML | as NHLR | no robots.txt | plain GET | supplement |
| RPCQ, *Répertoire du patrimoine culturel du Québec* | `https://www.patrimoine-culturel.gouv.qc.ca/rpcq/detail.do?methode=consulter&id=<n>&type=bien` | Heritage-inventory fiches with latitude/longitude, year, structure; found: 173551 (Pontiac/Luskville), 173368 (Blue Sea), 173366 (Maniwaki), 196596 (Amherst) | 4 | **yes**, to the second | HTML | © Gouvernement du Québec; facts only | `/rpcq/robots.txt` is a 404; the site runs an Incapsula script but did not challenge us | fetch known ids; ids found only by web search (the site's search is a form, not used). Not in Données Québec: that open data holds protected sites only | story-research / supplement |
| Quebec SOPFEU and SHFQ documents | `https://shfq.ca/wp-content/uploads/2021/07/gardien-tour-EB.pdf`; `.../AFFPAN_lanaudiere2-br.pdf`; `https://sopfeu.blogspot.com/2015/09/le-metier-de-gardien-de-tour.html` | History, counts, the first tower, last tower in use (1981), tower no. 5 at lac Carotte | n/a (history) | no | PDF, blog | © authors; facts only | allow | read once | story-research |
| CGNDB (place names) | `https://ftp.maps.canada.ca/pub/nrcan_rncan/vector/geobase_cgn_toponyme/prov_csv_eng/cgn_<prov>_csv_eng.zip` | Official spelling of French names; relief features for `approx_hint`; 5 zips = 12 MB, cached | not a lookout list | place names only | CSV in a zip | Open Government Licence - Canada | none | one GET per province | supplement (spelling, approximate positions) |
| OSM snapshot already in the repo | `data/raw/osm/overpass_ca_ak_hi.json` | 5 matches: Luskville, NB Mount Champlain "Fire Tower", Ochre Hill, an unnamed `fire_lookout` at Mont du Général-Allard, plus tourist towers (excluded) | 4 used | yes | JSON | ODbL | n/a | already cached; I did not query Overpass | supplement. A name-regex query (`tour à feu`, `fire tower`, `Tour d'observation`) over the four provinces was not allowed to me and may add a few |
| Marscan, Nova Scotia DNR fire towers | `http://marscan.com/nsdnrfiretowers.htm` | 33 towers by county with rough locations (2009, scanner-hobby, some names tentative) | 33 listed (27 matched a weebly site, 6 new) | no | HTML | none stated | allows | one GET | supplement (NS) |
| Canada Year Book 1961, p. 481 | `https://www66.statcan.gc.ca/eng/1961/196104990481_p.%20481.pdf` | NL 21 lookout towers; NS 27 observation towers; PEI: fire protection "not too great a problem" (road network) | counts only | no | PDF | Statistics Canada | allows | read once | story-research (counts) |
| Newfoundland fire-patrol history | `https://www.gov.nl.ca/fal/public-education/forestry/forest-fires/ffpc/anniversary/`; `https://www.portblandford.org/wp-content/uploads/2017/08/fire_patrol.pdf` | First four towers (1935): Mount Peyton, Lowell Hills, Mount Blandford, Powderhorn; agencies | 4 sites | no | HTML, PDF | Gov't of NL; facts only | allow | read once | story-research |
| Hiking NB, NB Parks and Parks Canada pages | e.g. `https://www.hikingnb.ca/Trails/AppalachianRegion/MountCarletonPark/MountCarletonTrail.html` | Mount Carleton: 1923 cabin lookout, unstaffed after 1968; Kejimkujik Fire Tower Trail | 2 | no | HTML | per site | allow | read once | story-research |
| Wikidata | cached `wikidata_q1_ca_fire_lookouts.json`, `wikidata_q2_atl_towers.json` (2 of 3 queries used) | class Q748998 in Canada: 12 items, only Barr Settlement (Q86927230) and Johnson Hill (Q86927236) in my area, no coordinates; a 5-province tower query returned only tourist observation towers | 2 | no | JSON | CC0 | n/a | n/a | not worth a pipeline |
| firelookout.ca ("Open Canada Fire Lookout Index") | `https://firelookout.ca/` and `/region/<province>/` | 206 rows: BC, SK, ON only | **0** | n/a | JS array | CC BY-NC-SA 4.0 | `robots.txt` serves the app page (no rules) | n/a | check again later: it accepts submissions |
| BAnQ Numérique, *Fonds James Maclaren Company* | `https://numerique.banq.qc.ca/patrimoine/details/52327/45031xx` | Photo files "Tour de guet pour les incendies de forêt": Iroquois, Devil Mountain, Ferme Tapanee, Lac Doré ([192-?], Mitchinamekus River area) | 4 | no | HTML | BAnQ: free of known restrictions | numérique opened; Advitam is CAPTCHA'd | do not crawl further | story-research |
| Considered, not usable | Données Québec (no tower dataset; its `robots.txt` disallows `/api/`), NS NSTDB `UTTO60 TOWER point` (one generic code for every kind of tower; no type field; not downloaded), GeoNB catalogue (nothing about towers), Provincial Archives of NB (challenge) | | | | | | | | |

## 3. Notes by province

**Quebec (`QC`).** French is the working language, so records keep the official French form and put the English in
`other_names`. The weebly list prints names in English style without accents ("Lac a Ange", "Riviere a Mars"). Where a name
is unique in CGNDB I used its spelling and kept the source form in `other_names` (about a dozen names changed, plus a few
plain "à" and "Rivière" fixes; the rest keep the source spelling). Words: *tour à feu* (the common one, also *tour de feu* in the heritage register),
*tour d'observation* (the official and SOPFEU term), *tour de guet*, *poste de vigie*, *garde-feu* (the person or the
patrol, and in the Aiguebelle park the tower). Agencies in time: the timber licensees' own patrols; the St. Maurice FPA
(1912, the first tower association), Ottawa River FPA, Lower Ottawa FPA, Laurentian FPA (1917; Côte-Nord and
Saguenay-Lac-Saint-Jean), Southern St. Lawrence FPA (south shore and Gaspésie); the Quebec Forest Protective Association (1918,
the umbrella); then the ministry (Terres et Forêts, Ressources naturelles, now MFFP/MRNF), SOPFEU since 1994. The
Laurentian FPA's entries carry a "division" and "section" (stored in `division`); those are the local administrative unit of
the time, not a municipality. County: the modern unit is the MRC, which the source never gives; I filled it only where a
heritage fiche or the NHLR names it. The tower network faded from the mid-1960s; the last in use was on CFB Valcartier
(Mont du Général-Allard, 60 ft, used to 1981) because aircraft could not patrol there. Public access: the standing
ones are on trails (Amherst: ~1.5 km from chemin Saint-Louis, climbing forbidden per NHLR; Luskville: Gatineau Park;
Mont Morisette: regional park). Valcartier is a military base. No rentals found. Watch for replicas: Maniwaki's
interpretation centre rebuilt a tower; the Parc national d'Aiguebelle's summit tower is a reconstruction; a new "Tour du
Garde-Feu" opened at the Parc régional de la Montagne du Diable. All three are recorded or noted, not counted as originals.
The weebly list repeats some sites under variant names (it says so itself); 23 records carry `possible_duplicate_of`.
Leads not yet turned into records: CGNDB has 32 "Montagne de la Tour", 60 "Lac de la Tour", one "Mont de la Tour à Feu"
(Trois-Rives, 46.8999, -72.8140), one "Lac de la Tour à Feu" (Sept-Rivières) and a "Belvédère de la Tour" (Sainte-Irène). The
Amherst "Montagne de la Tour" is exactly the tower's spot, so some of these names may mark tower hills; I did not verify
that with the Commission de toponymie's name-origin pages.

**New Brunswick (`NB`).** Provincial towers from the 1920s under the Department of Lands and Mines (the weebly notes cite
its annual reports from 1923); some were built with the Geodetic Survey or paper companies (International Paper, Restigouche
Company). Counties are the old ones (Northumberland, Restigouche, ...); three weebly entries print something that is not
a county ("St. Quenton County", "Charlton County", "Kings / Queens County line") and I left `county` null for those.
Eight are marked "secondary" in the source. The NHLR/FFLOS text for Rogersville claims all NB towers but Blackville were
sold for steel in the early 1980s; Mount Carleton's still stands, so that claim is wrong as written. Access: Mount Carleton
is inside the provincial park (park fee; 9.3 km loop trail); Blackville's tower is in a private yard.

**Nova Scotia (`NS`).** Department of Lands and Forests, later Natural Resources (DNR). Counties as given; "CBRM" (Cape
Breton Regional Municipality) is not a county but is the source's unit. Barr Settlement (1937, second in the province) and
Johnson Hill (1962) are NHLR-registered 100-ft steel towers with fibreglass cabs; the NHLR text from 1998 says "staffed each
summer", which is out of date. New Yarmouth (Cape Chignecto Provincial Park) was built by Minas Basin Pulp & Paper in the
1940s, taken over by the DNR, closed 2013 and demolished June 2015 (Wikipedia); an RCAF radar-and-fire-tower combination
proposed there in 1960 was never built. Kejimkujik's tower and cabin are Parks Canada's; a hiking guide says the tower is not
to be climbed and mentions a cabin booked through the park, which the current Parks Canada accommodation page does not list;
no rental recorded.

**Prince Edward Island (`PE`).** No lookout found. The evidence: the 1961 Canada Year Book says fire protection on the
Island "does not constitute too great a problem" because woodlots are in patches and roads reach all of them; the FFLA's
Canada table has an empty PEI row and NHLR/FFLOS have no PEI page; the weebly list has no PEI section; firelookout.ca's PEI
page has no PEI rows; CGNDB has no name with "tower", "fire" or "watch"; web searches in English and French returned nothing.
I would record PEI as having no known fire lookouts.

**Newfoundland and Labrador (`NL`).** Three kinds of owner: the government's Fire Patrol (first four towers begun 1935),
the Newfoundland Forest Protective Association (formed from the railway Fire Patrol in 1944; paper-company and railway
towers) and Anglo-Newfoundland Development Co. The weebly list gives districts only for a few ("Grand Falls District",
"Gander District"); `county` is null and the text is in `source_descriptor`. Terra Nova National Park holds two
(Ochre Hill, built 1959, now a public viewpoint reached by a trail of about 5 km; Bluehill Pond). The provincial government set up forest-fire protection in Labrador for the
first time in 1960 (Canada Year Book); I found no tower there. CGNDB's 132 "Lookout" features in NL are
fishing, whaling and sealing lookouts, not fire towers.

## 4. Excluded, considered and rejected

| Item | Why | Where |
|---|---|---|
| Stonecliffe, Mount Cheminis (on the Quebec weebly page) | Stonecliffe is an Ontario place with no association given; Mount Cheminis lists Ontario MNR as agency. Moved out of the candidates (`excluded_from_records` in the JSON); hand to the Ontario survey | weebly `/quebec.html` |
| Bissett Creek, Deux Rivières | Kept: the source says the tower stood on the Quebec side of the Ottawa River though Ontario MNR ran it. Check against the Ontario list for duplicates | weebly |
| Tours de guet de Sainte-Flavie (two, site patrimonial classé) | Second World War coastal watch towers, not fire detection | RPCQ 165823, 215258 |
| OSM towers "Tour d'observation de St-Fortunat", "...Sainte-Paule", "...St-François", "canards et cervidés", "Grand Héron", "de la mine à ciel ouvert", and three unnamed "Tour d'observation" nodes (Quebec City area, Abitibi, Laurentides) | Tourist or wildlife observation towers; no source ties them to fire detection. Not checked one by one | OSM snapshot |
| OSM "Bradshaw Lookout", "Pejepscot Lookout and Observation Deck" (NB) | Numbered scenic viewpoints on the Fundy Trail Parkway | OSM snapshot |
| Tremblant "tour d'observation 360°", Tour d'observation des Hautes-Appalaches, Mont-Blanc 40 m tower, Tour de l'Innovation, Montagne du Diable's new tower | Modern tourist towers (the last is a homage to the fire tower, which has its own record) | search results, CGNDB |
| CGNDB "Belvédère ..." (about 70 in Quebec), NL "Lookout" features (132) | Scenic viewpoints and fishing lookouts | CGNDB |
| New Yarmouth radar-and-fire-tower combination (RCAF, 1960) | Never built | Wikipedia "New Yarmouth" |

## 5. Open questions for the owner

1. **353 of 364 candidates have no position.** Do you want the name-only sites on the "Lookouts we can't place yet" list for
   Canada (there is no county in the GNIS sense; the unit here is the NB/NS county or the Quebec association), and should the 52
   `approx_hint`s (unique same-name CGNDB hill in the same county) be allowed to become dashed approximate pins, as the GNIS
   rule does in the US? Quebec has only 6 hints because most of its names are lakes and rivers.
2. **Should the pipeline ingest `canada-lookouts.weebly.com`?** It is the only list for these provinces and the owner already
   ingests its US sister sites, but it prints no coordinates, mixes in duplicates and a few Ontario sites, and its Quebec
   spellings lose accents.
3. **A records request is the realistic way to a complete list**: the New Brunswick 1960 tower list (Provincial Archives, P211/10229),
   the Nova Scotia DNR's 2013 closure list with coordinates, and Quebec's MRNF/SOPFEU tower inventory. Shall I write the
   request notes (the owner sends them; I do not)?
4. **Replicas and relocated towers** (Maniwaki, Aiguebelle, Blackville): keep as separate sites with status `replica` /
   `standing`, or hide the replicas?
5. **Nova Scotia statuses**: I set all 27 DNR sites `gone` from the province-wide closure and the CBC statement that towers were
   dismantled; only 3 (Lundy, Nuttby, New Yarmouth) have an individual removal date. Is that acceptable for the "towers standing per year" slider, or
   should they stay `unknown` until each is checked?
