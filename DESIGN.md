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

Canonical files are the source of truth. Merge **adds and refreshes, never deletes**:

1. Match each source record to a tower, in order: an existing `sources[].key`; a shared register
   number; then proximity (< 400 m, or < 1.5 km with a strong name match) within the same region.
2. Unmatched records in scope create a new tower.
3. Field precedence for facts: NHLR/FFLOS detail page > FFLA table > RIDB (rentals and
   coordinates of rentals) > Wikidata > OSM > regional. Fields listed in `locked` (set by
   research or a human edit) are never overwritten.
4. Disagreements are recorded in `conflicts` (coordinates > 500 m apart, status mismatch,
   different build years), not silently resolved.
5. `verification` is upgraded to `facts` when ≥2 independent sources agree on location and status.

### 3.6 What the site loads

`pipeline/build_site_data.py` writes `web/public/data/`:

- `towers.geojson`: every visible tower as a point. Minimal properties for map styling and
  filtering: `id, name, region, kind, status, rentable, built (year|null), registered (bool),
  verification, access`.
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
