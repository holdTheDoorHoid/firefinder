# Firefinder — design

Firefinder brings together the scattered, often outdated fire-lookout websites on one modern
interactive map. Every lookout site in the US gets an entry, standing or gone. Each tower page
has practical information (can I visit, can I stay, what are the rules) and a sourced history.
There is a simulated view from the cab, including for towers that no longer exist.

The project is named for the Osborne Firefinder, the round sighting table in the middle of
every lookout cab.

This file is **authoritative**. Agents read it before touching code. Decisions marked
DECIDED came from the owner's interview on 2026-10-03. Do not change them without asking.

---

## 1. Decisions (DECIDED 2026-10-03)

| Topic | Decision |
|---|---|
| Audience | Balanced, in layers. A clean map for anyone. Each tower page puts practical info first (visit / stay / access) and history below. |
| Geography | US at launch. The data model carries `country` + `region` so Canada and others can be added without rework. |
| Scope | **Structures only**: elevated towers and ground cabs/houses, standing or gone. Tree platforms, tent camps and bare "lookout points" are out of scope (kept in source extracts, `hidden: true` with a reason). |
| 3D | (a) 360° **panorama from the cab** at eye height, with labeled peaks and a Firefinder compass ring; (b) **"what it could see"** viewshed shading on the map, several towers at once, to show network coverage; (c) **smoke-spotting demo**: take a bearing from two towers and cross the lines. No free-roam 3D flyover. Gone towers use their recorded site and height. |
| Extras | Historical USGS topo overlay (the map from when the tower stood); then-and-now timeline per tower plus a national "towers standing per year" slider; tower-designs guide (L-4, Aermotor, CCC cupola…) linking to surviving examples. Not now: live wildfire layer, offline mode. |
| Contributing | GitHub only: a "Suggest an edit" button on each tower opens a pre-filled GitHub issue. |
| Checklist | Visited / stayed / want-to-go, saved in the browser (localStorage) with export/import. No accounts, nothing collected. |
| Publishing | Public from the start. Thin or unchecked entries show a visible **Unverified** badge. |
| Access | Exact location for every site. Private, tribal and closed sites get a prominent access label. Warn, don't hide. |
| History tone | Story first: readable narrative with footnoted sources at the end of every page. |
| Registry data | Use **facts** (location, type, status, years, register numbers, agency) from FFLA / NHLR / FFLOS, with credit and a link on every tower page. Write our own prose; never copy their text. The owner sends a partnership / permission note (draft in `docs/outreach/`). |
| Photos | Mirror photos from all sources now, **with credit and a takedown note**, including hobbyist and registry sites. The owner chose this knowingly; do not relitigate. |
| Research depth | Researched stories for every rentable or standing lookout first (~2,500). Gone sites get a facts card now and stories later, in batches the owner approves. |
| License | Code GPL-3.0; database ODbL 1.0; our prose CC BY-SA 4.0; photos keep their own rights. |

---

## 2. Sources

Crawl politely: at most one request every 2 s per host, an honest User-Agent
(`FirefinderBot/0.1 (+https://github.com/holdTheDoorHoid/firefinder)`), honour robots.txt.
Cache raw responses under `data/raw/` (git-ignored) so nothing is fetched twice.

| Source | What it gives | Form | Rights |
|---|---|---|---|
| **FFLA** firelookout.org/lookouts/us/`<st>`/ | Master table per state: Name, County, Lat, Long, Type, Status, NHLR/FFLOS number. ~6,100 sites in 33 states. 16 states have no table yet. `<st>-add/` pages hold "additional information". | HTML tables | No licence stated; facts only |
| **NHLR** nhlr.org (standing) | Per-lookout page: register numbers, date registered, location, coordinates, elevation, year built, administering agency, cooperators, prose, photo, links | Per-state lists → `/lookouts/us/<state>/<slug>/` | "All rights reserved" (American Resources Inc.); facts only, photos mirrored with credit |
| **FFLOS** firetower.org (former sites) | Same schema as NHLR for gone lookouts; often historical photos with credits | Same as NHLR | Same as NHLR |
| **RIDB** (recreation.gov) | Rentable lookouts: description, rules, season, occupancy, pets, fees, reservation URL, coordinates | Daily bulk export `ridb.recreation.gov/downloads/RIDBFullExport_V1_JSON.zip` (~572 MB, no key). Activities "FIRE LOOKOUTS/CABINS OVERNIGHT", "LOOKOUT TOWER". | Public; credit "Data source: ridb.recreation.gov" |
| **OpenStreetMap** | `emergency=fire_lookout` (~1,035) plus `man_made=tower`+`tower:type=observation` named *Lookout* | Overpass API | ODbL (compatible) |
| **Wikidata** | Q748998 "fire lookout tower" (~319 with coords): Wikipedia links, NRHP ids (P649), Commons images (P18), inception | SPARQL | CC0 |
| **Regional** | firelookout.com state maps (MT: 134 `GV_Draw_Marker` points, plus WA/OR/ID/WY/SD); PA StoryMap (48 towers, `…/items/ed47c97ebe7246868ce8ef3e7139a0b4/data?f=json`); andyarthur.org NY towers (CC BY 3.0); CSKT Flathead Reservation (6); fire-lookouts.org Sierra NF (~18, reuse allowed with credit); idahofirelookouts.com (not yet surveyed) | Mixed | Per source |
| **Gap-state regional** (2026-10-04) | easternuslookouts.weebly.com / centraluslookouts.weebly.com, the same hobby-site template split by region (one page per tower; AL/CT/FL/GA/KY/MA/MI/MS/NJ/NC/PA/SC/TN and AR/LA/MO/OK); Wikipedia *List of fire lookout towers in Louisiana* and *List of New Jersey Forest Fire Service fire towers* (coordinate-bearing wikitables, CC BY-SA, facts only); michiganfiretower.com (a small young single-author site, 8 towers); tnlandforms.us (Tom Dunigan's independently surveyed GA/NC/TN tower lists, 929 towers, every one with coordinates) | Mixed | Per source; no licence stated on the two weebly sites or tnlandforms.us |
| **FFLA resources** | `firelookout.org/resources/…`: *Lookout Rentals* (rentals outside recreation.gov: state parks and private), *Lookout Types and Historic Plans* (for the designs guide), *Historical Reference Documents*, *Staffing / Volunteer Opportunities* | HTML | Facts + links |
| Later | USGS historical topos (public domain, `ngmdb.usgs.gov/arcgis/rest/services/topoview/ustOverlay(Auto)/MapServer`), NRHP NPS dataset, Library of Congress HABS/HAER (measured drawings, public domain), Forest History Society, state forestry lists, newspapers | — | — |

---

## 3. Data model

### 3.1 Files

```
data/
  sources/<source>.json     normalized extract from one source (list of source records, §3.2); committed
  towers/<region>/<id>.json one canonical record per lookout site (§3.3); the source of truth
  stories/<id>.md           researched narrative with footnotes (stage 2)
  photos/<id>/<n>.jpg       mirrored photos, ≤1600 px long side (stage 1b)
  raw/                      crawl cache, git-ignored
  vocab.json                controlled vocabularies (§3.4)
```

### 3.2 Source record (`data/sources/<source>.json`)

Every fetcher writes `{"source": "<id>", "title": "...", "url": "...", "retrieved": "YYYY-MM-DD",
"license": "...", "records": [ ... ]}` where each record is:

```json
{
  "key": "ffla:or:abbot-butte:44.5577:-121.7088",
  "url": "https://firelookout.org/lookouts/us/or/",
  "name": "Abbot Butte",
  "country": "US", "region": "OR", "county": "Jefferson",
  "lat": 44.55774, "lon": -121.70876,
  "elevation_m": null,
  "type_raw": "Tower", "kind": "tower",
  "status_raw": "Gone", "status": "gone",
  "registers": [{"register": "FFLOS", "number": "US 560", "state_number": "OR 1"}],
  "built": null, "agency": null,
  "events": [],
  "photos": [{"url": "...", "credit": "...", "caption": "...", "year": null}],
  "links": [{"label": "...", "url": "..."}],
  "rental": null,
  "extra": {}
}
```

Rules: `key` is unique and stable within the source. Unknown values are `null`, never `""` or a
guess. Coordinates are WGS84 decimal degrees, west longitudes negative. Elevation is in metres
(convert from feet ×0.3048 and keep the original in `extra.elevation_ft`). `kind` and `status`
use the vocabularies in §3.4. Keep the original strings in `type_raw` / `status_raw`.

### 3.3 Canonical tower (`data/towers/<region>/<id>.json`)

`id` = `us-<st>-<slug>`, with `-2`, `-3`… for same-name sites in one state (there are dozens of
"Bald Mountain"s). **Ids never change once published** (they are URLs and checklist keys).

```json
{
  "id": "us-or-abbot-butte",
  "name": "Abbot Butte Lookout",
  "other_names": [],
  "country": "US", "region": "OR", "county": "Jefferson",
  "location": {"lat": 44.55774, "lon": -121.70876, "precision": "exact", "from": "ffla"},
  "elevation_m": null,
  "kind": "tower",
  "design": null,
  "height_m": null,
  "status": "gone",
  "registers": [{"register": "FFLOS", "number": "US 560", "state_number": "OR 1", "url": "..."}],
  "agency": null,
  "ownership": "unknown",
  "access": {"level": "unknown", "note": null},
  "staffing": {"status": "unknown", "as_of": null},
  "visit": {"climbable": null, "drive_up": null, "trail_note": null},
  "rental": null,
  "events": [{"year": 1933, "event": "built", "note": null, "from": "nhlr"}],
  "photos": [],
  "links": [{"label": "FFLOS register entry", "url": "...", "kind": "register"}],
  "sources": [{"source": "ffla", "key": "ffla:or:...", "fields": ["location", "kind", "status", "registers", "county"]}],
  "conflicts": [],
  "verification": "unverified",
  "locked": [],
  "hidden": false, "hidden_reason": null,
  "updated": "2026-10-03"
}
```

`rental` (when rentable):

```json
{"available": true, "provider": "recreation.gov", "url": "https://www.recreation.gov/camping/campgrounds/234189",
 "ridb_facility_id": "234189", "season": "...", "max_occupancy": 4, "pets": "...",
 "fee": "...", "rules": ["..."], "access_note": "...", "description": "...", "checked": "2026-10-03"}
```

### 3.4 Vocabularies (`data/vocab.json`)

- `kind`: `tower` (cab or platform on a tower), `ground` (ground-level cab/house), `two_story` (2-story cab building), `three_story` (3-story cab building), `enclosed_tower`, `platform` (open tower, no cab), `tree`*, `camp`*, `unknown`. *Out of scope → `hidden`.
- `status`: `standing`, `gone`, `relocated` (moved; `events` record from/to), `ruins` (footings/remains only), `replica`, `unknown`. FFLA "Standing*" is mapped once its legend is confirmed.
- `ownership`: `federal`, `state`, `tribal`, `local`, `private`, `unknown`.
- `access.level`: `public`, `restricted` (seasonal/gated/permit), `permission` (tribal or landowner permission needed), `private` (no public access), `closed`, `unknown`.
- `staffing.status`: `staffed`, `emergency`, `volunteer`, `unstaffed`, `unknown`.
- `verification`: `unverified` (single source, untouched), `facts` (≥2 sources agree), `researched` (story written), `verified` (researched + independent check).
- `events[].event`: `built`, `rebuilt`, `replaced`, `staffed_first`, `staffed_last`, `abandoned`, `destroyed`, `burned`, `removed`, `relocated`, `restored`, `rental_opened`, `nrhp_listed`, `nhlr_registered`, `fflos_registered`.

### 3.5 Merge (`pipeline/merge.py`)

Canonical files are the source of truth. Merge **adds and refreshes, never deletes**: a tower
file keeps its id forever, a tower whose source records all disappear is kept as it is, and
fields listed in `locked` (set by research or a human edit) are never overwritten. Run
`python3 pipeline/merge.py`, then `python3 pipeline/validate.py`; the merge also writes a review
file, `data/merge_report.json` (counts, conflicts, near misses, records it could not place).
Re-running with unchanged inputs writes nothing. A new source extract in `data/sources/` is
picked up with no code change (unknown sources rank last in every field).

**Matching**, per source in the order NHLR, FFLOS, FFLA, RIDB, fire-lookouts.org, tnlandforms.us,
the NJ Forest Fire Service Wikipedia table, firelookout.com, idahofirelookouts.com,
michiganfiretower.com, PA StoryMap, andyarthur.org, the Wikipedia per-state lookout lists, CSKT,
the easternuslookouts and centraluslookouts weebly sites, Wikidata, OSM:

1. **Key**: the record's key is already in a tower's `sources[].key`.
2. **Register number**. NHLR and FFLOS number their entries separately ("NHLR US 674" is
   Apache Maid, AZ; "FFLOS US 674" is Buzzard Butte, OR), so the register name is part of the
   key. US numbers decide; state numbers ("WI 49") only when no US number matches. A register
   match more than 5 km away is not taken when the record is a relocated or replica entry, or
   when there is a matching tower on the spot (the review file lists both cases).
3. **Place and name**: towers nearby in the same state, best name first, then nearest.
   Accepted when names agree strongly (score ≥ 0.85) within 1.5 km (3 km for idahofirelookouts.com
   and RIDB, whose pins are rougher; 15 km for CSKT's dead-reckoned positions); when names agree
   partly (≥ 0.5) or one is generic ("Fire Tower", unnamed) within 400 m; or within 100 m whatever
   the names (different names for one tower are common: Pequawket = Kearsarge North). Across a
   state line only 400 m with a strong name, or 100 m.
4. **Name only**, for records with no coordinates, after every source: a unique same-name
   tower in the state (and county, when both give one). Otherwise the record is listed in the
   review file as unplaced; it does not make a tower, since a tower needs a position.
5. Anything else **starts a new tower**.

Name comparison drops case, punctuation, accents and the words that only say "lookout"
(Lookout, L.O., Fire, Tower, Station, Cabin…), expands Mtn/Mt/Pk, and compares the remaining
core with Peak / Mountain / Butte removed: "Bald Mtn. L.O." = "Bald Mountain Lookout" (1.0),
"Abbot Butte" ≈ "Abbot" (0.95), "Bald Mountain" vs "Bald Knob" only 0.6. North/South,
Upper/Lower, Big/Little and different numbers mark different places (0.2). A one-letter slip
in a long name still counts as strong. A parenthetical is an alternate name ("Putnam
(Liberty)"), except a structure-history note (below); "(North)", "(#2)" stay part of the name.

**Moved, copied and rebuilt structures.** FFLA writes them as "<where it is now> (<note>)":
"State Fair (Relocated Padlock Hill)", "Crystal Ridge (Relocated Stranger Mtn, WA)",
"Kellogg Peak (Replica)", "Missoula Aerial Fire Depot (Hornet Peak Replica)", "Wilson Hill WMA #1
(Parts from Whites Hill)" (NHLR does the same in a few names). The note is never a name to match
on: the site the structure came from is a different place. The record is named the way a
visitor looks for it, the lookout's own name first and where it is now second, "Padlock Hill
Lookout (now at the State Fair)", id `us-ny-padlock-hill-at-state-fair`; a replica is "Hornet
Peak Lookout replica (at the Missoula Aerial Fire Depot)", `us-mt-hornet-peak-replica`. It gets a
`relocated` event with `moved_from` / `moved_to`. If the original site has its own record (a
strong name match in the origin's state; several: the one sources call gone, then the nearest,
the rest listed in the report), the two link to each other with links of kind `relocated_from`
/ `relocated_to` (`id` plus a relative `url`), and the original site's status becomes
`relocated` when its sources say the lookout is gone. "Parts from" links both ways but leaves
the original's status alone. The report's `relocations` lists every case.

**State notes in names** are taken out the same way, and the original text kept in
`other_names` for search: "(Demolished)", "(Removed)", "(Burned)", "(Gone)", "(site only)" →
status `gone`; "(Collapsed)", "(Ruins)" → `ruins`; "(likely gone)" → no status claim plus
`status_note` "Sources suggest it is gone."; "(unknown)", "(same as X?)" → a `status_note`;
"(Private)", "(Closed)" → that access level; "(Non-fire Tower)", like FFLA's status "Non-fire" and
type "Non-fire Tower" → hidden, "Not a fire lookout (FFLA lists it as a non-fire tower)".
`status_note` (text or null) is shown beside the status on the tower page and in the map panel.
Alternate names and qualifiers ("(Loc 2)", "(Liberty)", "(Name Unknown)") stay.

**Same source, one tower**: never, except for sources that list one lookout twice, and only
when the two records agree on name and place: FFLA repeated table rows (50 m), firelookout.com
border lookouts on two state maps (100 m), idahofirelookouts.com repeat posts (100 m), OSM
node + way (100 m; 50 m if unnamed), Wikidata (100 m), RIDB facility + campground (300 m).

**Field precedence** (first source with a value wins; `unknown` is not a value):

| Field | Precedence |
|---|---|
| name | NHLR, FFLOS > RIDB (cleaned) > FFLA > firelookout.com > fire-lookouts.org > tnlandforms.us > NJFFS table > andyarthur.org > Wikipedia lists > PA StoryMap > CSKT > the weebly sites > Wikidata > idahofirelookouts.com > michiganfiretower.com > OSM. A bare name borrows "Lookout"/"Fire Tower" only if another source spells it that way; every other name goes to `other_names` |
| location | NHLR, FFLOS > FFLA > fire-lookouts.org > tnlandforms.us > NJFFS table > firelookout.com > OSM > the weebly sites > Wikidata > RIDB > andyarthur.org > Wikipedia lists > PA StoryMap > idahofirelookouts.com > michiganfiretower.com > CSKT, with *corroborated precedence*: if the winner is confirmed by no other lineage and lies > 500 m from a position that is, the best confirmed position wins (NHLR's Taylor Mountain, ID sits 253 km outside its own county). Rows outside their own state are used last |
| status | FFLA > NHLR, FFLOS > RIDB > fire-lookouts.org > tnlandforms.us > NJFFS table > andyarthur.org > Wikipedia lists > PA StoryMap > CSKT > firelookout.com > idahofirelookouts.com > michiganfiretower.com > OSM > the weebly sites > Wikidata. OSM features imported from GNIS make no status claim (FFLA calls a third of them gone); a "standing" row named "(Replica)" is `replica` |
| kind | FFLA > NHLR, FFLOS > RIDB > firelookout.com > fire-lookouts.org > tnlandforms.us > NJFFS table > PA StoryMap > andyarthur.org > Wikipedia lists > CSKT > OSM > the weebly sites > Wikidata > idahofirelookouts.com > michiganfiretower.com |
| built (and its events) | NHLR, FFLOS > firelookout.com > fire-lookouts.org > PA StoryMap > RIDB > the weebly sites > Wikidata > CSKT > idahofirelookouts.com > michiganfiretower.com > OSM > andyarthur.org > Wikipedia lists > FFLA; one source's build dates are used, others' go to `conflicts` |
| elevation | NHLR, FFLOS > firelookout.com > fire-lookouts.org > tnlandforms.us > NJFFS table > RIDB > Wikidata > CSKT > OSM |
| design, height | NHLR, FFLOS > firelookout.com > fire-lookouts.org > NJFFS table (height only) > PA StoryMap > CSKT > the weebly sites (> Wikidata > OSM for height) |
| county | NHLR, FFLOS > FFLA > firelookout.com > PA StoryMap > CSKT > andyarthur.org > Wikipedia lists > fire-lookouts.org > tnlandforms.us > NJFFS table > the weebly sites > Wikidata > michiganfiretower.com |
| agency | NHLR, FFLOS > RIDB > firelookout.com > fire-lookouts.org > tnlandforms.us > NJFFS table > PA StoryMap > andyarthur.org > CSKT > the weebly sites > OSM > michiganfiretower.com |
| rental | RIDB only. If the tower's status is gone/ruins (Flag Point, OR: FFLA "Burned 2026"), warn, don't hide: the listing is kept with `available: false` (not counted or filtered as rentable) and a `warning` ("FFLA reports this lookout burned in 2026, but recreation.gov still lists it. Check with the forest before booking."), which the site shows above the listing link |
| registers | union of all sources; on a tower with an NHLR/FFLOS record, that register's own number wins and a different copy goes to `conflicts` |
| events, photos, links | union, de-duplicated (events by event + year, photos by URL, links by URL) |

**Ownership and access** only where a source says so: CSKT → tribal, access `permission`;
RIDB (USFS/BLM) → federal; NY DEC and PA state forests → state (via those extracts); an agency
naming a National Forest/Park, BLM or Fish & Wildlife on a register page → federal; tribal
ownership from any source → access `permission`; FFLA's status "Private" → private. Otherwise
`unknown`. OSM's `access=*` tag describes the structure, not the land, so it is kept only as
`access.note`.

**Conflicts** (`{field, values:[{source, value}], distance_m, note}`, chosen value first):
`location` when a source is > 500 m from the shown position (CSKT excluded: approximate);
`status` when sources differ (gone, ruins and relocated count as the same); `built` when build
years differ by 2 or more (one year is usually built vs completed; often it is first structure vs
current one); `kind` when tree/camp vs structure decides visibility;
`registers` as above.

**Verification**: `facts` when two independent sources agree on location (within 500 m of the
shown position) and status; otherwise `unverified`. NHLR, FFLOS, FFLA and firelookout.com count
as one lineage for this (FFLA carries the register numbers, and 3,173 of firelookout.com's 3,266
coordinates are byte-identical to an FFLA row). `researched`/`verified` are never downgraded.

**Out of scope** (kept, `hidden: true` with a `hidden_reason`): kind `tree` or `camp`; FFLA bare
lookout points (types Firefinder, Map Board, Alidade, Obs Pt…) with no structure from another
source; FFLA "Proposed/Planned/Never Built"; FFLA's "Sites determined NOT to have been used as
wildland fire lookouts"; single records hidden by a human decision (`HIDE_KEYS` in merge.py,
e.g. OSM's "East Lookout Tower" on Guam: "Not confirmed as a fire lookout").

**Ids**: `us-<st>-<slug>` from the display name without trailing "Lookout"/"Tower" words (also
before a parenthetical: "Pilot Peak Lookout (Payette NF)" → `pilot-peak-payette-nf`); moved and
replica structures as above; new
towers are numbered `-2`, `-3`… in a fixed order (state, slug, north to south, first key), so a
re-run from scratch gives the same ids and a new record never takes an existing id.

**Photos** are `{file, thumb, url, source_url, credit, license, caption, year}`; until mirrored,
`file`/`thumb` are null, `url` is the remote image (Wikimedia via `Special:FilePath`) and
`source_url` the page it came from. Credit is the photographer "via" the site, or the site.
**Links** carry a credit-ready `label` and a `kind`: `relocated_from` / `relocated_to` (another
tower page, by `id`), `register`, `rental`, `association` (FFLA
state list), `wikipedia`, `site` (hobbyist and regional pages), `agency`, `website`, `commons`,
`wikidata`, `osm`. **`sources[]`** lists, per record, the fields it supplied.

### 3.6 What the site loads

`pipeline/build_site_data.py` writes `web/public/data/`:

- `towers.geojson`: every visible tower as a point, coordinates rounded to 5 dp. Short
  property names (missing key = null/false; the legend is repeated in `meta.json` → `format`):
  `i` id, `n` name, `r` state, `c` county, `k` kind, `s` status, `v` verification, `a` access,
  `b` year built, `rt` 1 if rentable, `rg` 1 if on a register, `o` other names joined by `|`.
- `t/<id>.json`: the full canonical record plus the story HTML, when one exists.
- `meta.json`: counts, source list with retrieved dates, and build date.

---

## 4. Site

- Static site on GitHub Pages: Vite + TypeScript + **MapLibre GL JS**. No server, no keys.
- Basemaps: OpenFreeMap (vector, keyless) by default, a USGS Topo raster toggle, and later the
  historical USGS topo overlay. Terrain from Mapterhorn or AWS terrarium tiles (keyless).
- **Map page**: clustered points styled by status (standing vs gone) and kind; filters (status,
  kind, rentable, state, register, verification); search by name; a side panel with the
  facts card and a link to the full page; deep-linkable URL state.
- **Tower pages**: prerendered static HTML at `/t/<id>/` (shareable, findable by search
  engines). Layout from the top: name, status, access badges; *Visit & stay* (rental rules
  and the recreation.gov button, access, staffing); facts card; timeline; story with
  footnotes; photos with credits; sources; "Suggest an edit" (pre-filled GitHub issue);
  checklist buttons.
- **Checklist**: localStorage `firefinder.checklist.v1`, with export/import as JSON; works on
  the map (filter "my visited") and on tower pages. Every storage access is wrapped in
  try/catch.
- **About / credits / takedown** page: every source with its licence and credit line; how to
  ask for a photo or text to be removed (open an issue or email).
- Accessibility: status is never shown by colour alone (shape and label too); keyboard-usable
  filters; readable at phone width.
- Stage 3 (3D): panorama and viewshed computed in **Rust → WASM** (DEM ray-marching over
  terrarium tiles), drawn by the TypeScript UI.

---

## 5. Stages

1. **Facts map** (now): FFLA + NHLR + FFLOS + RIDB + OSM + Wikidata + regional extracts →
   merge → map + prerendered tower pages + checklist + credits; Pages deploy; weekly
   rental-refresh Action.
1b. **Photos**: mirror register and other photos with credit, resized (≤1600 px plus a 400 px
   thumbnail); takedown note.
2. **Stories**: research batches (Sonnet) for rentable and standing towers first. Each writes
   `data/stories/<id>.md` and locks the fields it confirmed.
3. **3D**: Rust/WASM panorama + viewshed + smoke-spotting demo.
4. **History extras**: historical topo overlay, per-tower timeline, national
   standing-per-year slider, tower-designs guide.
5. Later: Canada, more states' gone sites, photo contributions.

---

## 6. Process

- The orchestrator plans, merges and reviews. Engineering agents run on Opus; research and
  routine agents on Sonnet.
- Each agent works in its own git worktree, `~/Desktop/firefinder-wt/<name>`, on branch
  `agent/<name>`. It commits there and never pushes; the orchestrator merges to `main`.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Python 3.12 using the **standard library only** for the pipeline (CI needs no installs);
  Node 24 for the site.
