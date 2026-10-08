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
| Scope | **Structures first**: elevated towers and ground cabs/houses, standing or gone. Tree platforms, tent camps and bare "lookout points" were out of scope (`hidden: true` with a reason). **Owner changed 2026-10-08: no-structure sites shown, off by default**: camps, lookout trees and bare points are a "no structure" group with their own label on the map and tower pages; the map leaves them off until the visitor switches them on; their tower pages are public; structure counts leave them out, "all sites" counts include them. Non-fire towers, never-built sites and human `HIDE_KEYS` stay hidden. Hiding a kind again is one edit (`"hidden": true`) in `data/structure_kinds.json`. |
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
| **FFLA** firelookout.org/lookouts/us/`<st>`/ | Master table per state: Name, County, Lat, Long, Type, Status, NHLR/FFLOS number. 6,157 rows in 30 states (crawled 2026-10-08, `pipeline/fetch_ffla.py --refresh`). 20 states have no table yet: Georgia, North Carolina and New Jersey show counts on the index and "Under construction" on their pages. Each state page links other sorts of the same list: by county (`<st>-co`), standing only (`<st>-st`), by region (`<st>-rg`; MT, ID, OR, WA) and CA's "Unknown/Undocumented" list (`ca-un`: 174 emergency, planned and never-built sites from one survey, 34 with a position). A row seen in several views is one record (the alphabetical list names its key). `<st>-add/` pages hold "additional information". | HTML tables | No licence stated; facts only |
| **NHLR** nhlr.org (standing) | Per-lookout page: register numbers, date registered, location, coordinates, elevation, year built, administering agency, cooperators, prose, photo, links | Per-state lists → `/lookouts/us/<state>/<slug>/` | "All rights reserved" (American Resources Inc.); facts only, photos mirrored with credit |
| **FFLOS** firetower.org (former sites) | Same schema as NHLR for gone lookouts; often historical photos with credits | Same as NHLR | Same as NHLR |
| **RIDB** (recreation.gov) | Rentable lookouts: description, rules, season, occupancy, pets, fees, reservation URL, coordinates | Daily bulk export `ridb.recreation.gov/downloads/RIDBFullExport_V1_JSON.zip` (~572 MB, no key). Activities "FIRE LOOKOUTS/CABINS OVERNIGHT", "LOOKOUT TOWER". Selected by name, plus the hand-checked `EXTRA_INCLUDE` list in `pipeline/fetch_ridb.py` (a reason per facility) for lookout rentals whose RIDB names carry no "lookout" (the FFLA lists them as lookout rentals: Post Creek, Mt. Baldy, Bishop Mountain, Gird Point, Strawberry, Tamarack, Timber Butte). | Public; credit "Data source: ridb.recreation.gov" |
| **OpenStreetMap** | `emergency=fire_lookout` (~1,035) plus `man_made=tower`+`tower:type=observation` named *Lookout* | Overpass API | ODbL (compatible) |
| **Wikidata** | Q748998 "fire lookout tower" (~319 with coords): Wikipedia links, NRHP ids (P649), Commons images (P18), inception | SPARQL | CC0 |
| **Regional** | firelookout.com state maps (MT: 134 `GV_Draw_Marker` points, plus WA/OR/ID/WY/SD); PA StoryMap (48 towers, `…/items/ed47c97ebe7246868ce8ef3e7139a0b4/data?f=json`); andyarthur.org NY towers (CC BY 3.0); CSKT Flathead Reservation (6); fire-lookouts.org Sierra NF (~18, reuse allowed with credit); idahofirelookouts.com (not yet surveyed) | Mixed | Per source |
| **Gap-state regional** (2026-10-04) | easternuslookouts.weebly.com / centraluslookouts.weebly.com, the same hobby-site template split by region (one page per tower; AL/CT/FL/GA/KY/MA/MI/MS/NJ/NC/PA/SC/TN and AR/LA/MO/OK); Wikipedia *List of fire lookout towers in Louisiana* and *List of New Jersey Forest Fire Service fire towers* (coordinate-bearing wikitables, CC BY-SA, facts only); michiganfiretower.com (a small young single-author site, 8 towers); tnlandforms.us (Tom Dunigan's independently surveyed GA/NC/TN tower lists, 929 towers, every one with coordinates) | Mixed | Per source; no licence stated on the two weebly sites or tnlandforms.us |
| **Links-page sites** (2026-10-08) | The sites FFLA's links page (`firelookout.org/resources/links/`) points to, surveyed in `docs/sources/links_survey.md`. Ron Kemnow's *western* weebly sites (westlookouts, californialookouts, idaholookouts, montanalookouts, oregonlookouts, washingtonlookouts; ~3,700 pages, ~60% with a map-widget position), and the eastern / central sites now read for **every** state they cover (they had been limited to the gap states, and a mislabelled nav header had hidden 178 Michigan, 27 Missouri and 30 Indiana towers); TrailChick's Washington guide (93 visited lookouts with coordinates); *Every Lookout in Oregon* (155 standing lookouts, no coordinates, matched by register number or name); the per-lookout pages of FFLA chapters and Friends groups (`ffla_groups`: links, and the California-South chapter's table of register numbers and conditions); WillhiteWeb.com's Washington lookout pages (names and links); Indiana Fire Towers (Mark Armantrout's guide to ~40 Indiana tower sites, each with coordinates) | HTML | None stated on any; facts and links only |
| **FFLA resources** | `firelookout.org/resources/…`: *Lookout Rentals* (88 rentals by state, each with its booking link and any closure or manager note: the recreation.gov ones and the state-park and private ones; source `ffla_rentals`, `pipeline/regional/ffla_rentals.py`), *Lookout Types and Historic Plans* (for the designs guide), *Historical Reference Documents*, *Staffing / Volunteer Opportunities* | HTML | Facts + links |
| **Association project reports** (2026-10-08) | Year-by-year reports of the work lookout associations do on particular lookouts, one source per association, one shared record shape (3.7). First: the Northwest Montana Lookout Association, nwmt-ffla.org: project posts 2025-26, "Completed Projects" PDFs 2014-24 (print-outs of its old website) and the yearly newsletters, 37 lookouts in Glacier NP, the Flathead and Kootenai NFs and Montana DNRC, about 180 dated restoration, repair and assessment events | WordPress posts, PDFs (pdftotext) | No licence stated; facts only, notes in our words, every event linked to its report |
| **Western association project reports** (2026-10-08) | Fifteen more sources in the same family (3.7) for the West and the Rockies: the FFLA chapter and restoration-grant reports 2003-2025 (212 PDFs from the AZ, CA, CO-UT, ID, NM, OR, WA and WY chapters; `ffla_west_reports`, 248 lookouts, 491 events), the Sand Mountain Society (OR), Mountaineers Everett (WA), Snoqualmie Fire Lookouts, Methow Valley FFLA, Buck Rock Foundation, Angeles NF FLA, Southern California Mountains Foundation, FFLA San Diego-Riverside, Monterey and California South, Hi Mountain Lookout Project, Siskiyou Mountain Club, HistoriCorps and the Green Mountain Lookout story (Washington Trust, WTA). 308 lookouts, 680 dated events in all; survey in `docs/sources/associations_west.md` | WordPress/Squarespace/Wix pages, PDFs (pdftotext) | No licence stated; facts only, notes in our words, every event linked to its page or PDF |
| **Eastern association projects** (2026-10-08) | The same shape for the East, the South and the Midwest: the FFLA New York State Chapter's monthly newsletters 2016-2026 (121 issues, 75 NY towers, 227 events), nine single-tower "Friends of" and similar groups with dated logs or newsletters (St. Regis, Hurricane, Mount Arab, Azure, Bald/Rondaxe, Bramley, Stillwater, the Kent Conservation Foundation for Nimham, Friends of the Smokies for Mount Cammerer), and the FFLA's own yearly chapter and restoration-grant reports 2003-2025 for the eastern chapters (236 PDFs, 122 lookouts, 217 events; the only written record of the chapters that otherwise exist on Facebook). Survey of every group considered, with why the others were not read: `docs/sources/associations_east.md` | WordPress and hand-made pages, PDFs (pdftotext) | No licence stated; facts only, notes in our words, every event linked to its report |
| Later | USGS historical topos (public domain, `ngmdb.usgs.gov/arcgis/rest/services/topoview/ustOverlay(Auto)/MapServer`), NRHP NPS dataset, Library of Congress HABS/HAER (measured drawings, public domain), Forest History Society, state forestry lists, newspapers | — | — |

---

## 3. Data model

### 3.1 Files

```
data/
  sources/<source>.json     normalized extract from one source (list of source records, §3.2); committed
  towers/<region>/<id>.json one canonical record per lookout site (§3.3); the source of truth
  stories/<id>.md           researched narrative with footnotes (stage 2)
  research/<id>.json        that research's facts, events, sources and fact-check (research/STORY_GUIDE.md)
  photos_manifest.json      pipeline/mirror_photos.py's output (§3.5 "Photos"); committed. The
                            files themselves are served from holdTheDoorHoid/firefinder-photos
  raw/                      crawl cache, git-ignored
  vocab.json                controlled vocabularies (§3.4)
  structure_kinds.json      the kinds of structure in plain words: label, group (structure /
                            no_structure), the hide switch, one paragraph each; materials; roles
```

The mirrored image files themselves are not under `data/`: `pipeline/mirror_photos.py` (stage
1b) writes them outside the repo entirely, named by content hash (`<hh>/<sha1>.webp` full
size, `<hh>/<sha1>.t.webp` thumbnail, so one photo reused across sources/towers is stored
once), and records the mapping from each source url to its file in `photos_manifest.json`.
Where the files themselves are published is a separate, still-open decision
(`web/site.config.json`'s `photosBase`, §4).

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
use the vocabularies in §3.4. Keep the original strings in `type_raw` / `status_raw`: the merge
reads them again through `pipeline/structure.py`, whose tables give **every** type and status
value of every source a deliberate mapping (a fetcher's own `kind`/`status` only stands where
the value says nothing, or for OSM tags and Wikidata classes the fetcher reads in full).
`pipeline/test_structure.py` fails when a crawl brings a value nobody has mapped, so it never
quietly becomes `unknown`; `python3 pipeline/structure.py --check` lists such values and the
merge report has them under `unmapped_structure_values`. Sources whose description text is only
in the crawl cache (NHLR, FFLOS, firelookout.com) store short structure facts from it in
`extra.structure_words` (a closed vocabulary: "steel tower", "wood cab", "kind ground",
"role aws"; never prose), refreshed from the cache with `python3 pipeline/structure.py --backfill`.

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
  "material": "steel", "material_from": "nhlr",
  "roles": [],
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

A rental the Forest Fire Lookout Association lists (`ffla_rentals`, §3.5) adds three optional keys:
`manager` (who runs it when it is not the Forest Service: "private owner", "MT DNRC"),
`status_note` (a closure or unavailability the list notes: "Maintenance Closure 2026", "Currently
Unavailable") with `status_note_from` ("ffla"). The lookout stays a rental (`available` is
untouched) and the page shows the note beside the booking link, as a plain notice, not the
"check before booking" warning that a lookout recorded as gone gets. A lookout recreation.gov
does not list gets its rental from the FFLA entry alone: `source: "ffla"`, `provider` the
booking site ("Airbnb", "Washington State Parks"), `url` its booking page, `ridb_facility_id`
the recreation.gov number when the link has one; the page then credits the FFLA list, not RIDB.

### 3.4 Vocabularies (`data/vocab.json`)

- `kind` (plain words, groups and the hide switch in `data/structure_kinds.json`):
  - structures: `tower` (cab or platform on a tower), `enclosed_tower`, `platform` (open tower or
    raised platform, no cab; FFLA "Crowsnest" counts here), `ground` (ground-level cab/house; also
    summit shelters and stone huts), `two_story`, `three_story`, `rooftop` (a cab on another
    building: ranger station, hotel, office, grain elevator, clock tower), `mobile` (trailer,
    bus, portable cab), `unknown` (no source says);
  - no structure (shown, map switch off by default): `camp` (summit tent camp), `tree` (lookout
    tree / tree platform), `point` (bare point: firefinder, map board, alidade, cairn).
  FFLA types mapped deliberately include: Rooftop / Roof Top / Rooftop Cab / Rooftop Tower /
  Hotel / Office Building / Grain Elevator / Clock Tower → `rooftop`; Trailer, Bus/cupola →
  `mobile`; Log Crib, Log base (a cab on a log crib), Log Tower, Stone (Obs) Tower, Wooden Tower,
  Radio / Windmill / Security Tower, Obs Tower, Tower/Ground, Tower? → `tower`; Open Tower,
  Platform Tower, Obs Deck, Crowsnest → `platform`; Shelter, Rock Shelter, Stone Hut, Stone
  Walls, Tram House, Map Board (cabin) → `ground`; Firefinder, Map Board(s), Map Table, Alidade,
  Obs Pt, High Point, Open Site, Rock Cairn → `point`; AWS → no kind (a role); Unknown, Unk,
  Unconfirmed → `unknown`; "Gone" in the Type column is read as the status.
- `material` (what the main structure is built of: the tower for a tower kind, the walls for a
  building; none for a site with no structure): `steel`, `wood`, `log`, `stone`, `concrete`,
  `masonry` (brick or block), `mixed` (a source names two, "stone and wood"). `material_from`
  is the source that said it, or `design`.
- `role` (`roles[]`, a job, not a kind of building): `aws` (Second World War Aircraft Warning
  Service post: FFLA types AWS / AWS Tower, or "Aircraft Warning" in a register description).
- `status`: `standing`, `gone`, `relocated` (moved; `events` record from/to), `ruins` (footings/remains only), `replica`, `unknown`.
  FFLA: Standing; Standing* → standing with the note "The tower still stands, but its cab is gone"
  (FFLA's legend); Gone, Gone** (unexplained), Removed, Abandoned → gone; Ruins, Standing (Ruins),
  Collapsed → ruins; Relocated → relocated; Unknown, Duplicate? → no claim; Undocumented, Temp*
  (temporarily removed, e.g. High Rock, WA, away for restoration) → no claim with a note; Private →
  no claim, ownership private; Proposed / Planned / Never Built → hidden as never built; Non-fire
  / Non-wildfire → the non-fire rule (§3.5). A year inside a status is an event: "Burned 2026" →
  gone + `burned` 2026, "Removed 2026" → gone + `removed`, "New 2026" → standing + `rebuilt`.
  The other sources' wordings (weebly "dismantled"/"razed"/"still stands", tnlandforms "moved",
  NJFFS "Not in service or no longer standing" → no claim, Wikipedia "Torn down?" → no claim with
  "Sources suggest it is gone.", OSM lifecycle tags, Wikidata dissolved dates) are tabled too.
- `ownership`: `federal`, `state`, `tribal`, `local`, `private`, `unknown`.
- `access.level`: `public`, `restricted` (seasonal/gated/permit), `permission` (tribal or landowner permission needed), `private` (no public access), `closed`, `unknown`.
- `staffing.status`: `staffed`, `emergency`, `volunteer`, `unstaffed`, `unknown`.
- `verification`: `unverified` (single source, untouched), `facts` (≥2 sources agree), `researched` (story written), `verified` (researched + independent check).
- `events[].event`: `built`, `rebuilt`, `replaced`, `staffed_first`, `staffed_last`, `staffed`, `abandoned`, `destroyed`, `burned`, `removed`, `relocated`, `restored` (repair, rehabilitation, re-roofing, repainting), `modified` (something added or changed), `assessed` (a volunteer or agency condition assessment, 2026-10-08), `fire` (the lookout was threatened or wrapped, not lost), `closed`, `rental_opened`, `nrhp_listed`, `nhlr_registered`, `fflos_registered`, `other` (needs a note). An event may carry `source_url` (and `source_urls` when several pages report it): the page that supports it, shown as "Source: <host>" on the timeline.

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
the easternuslookouts and centraluslookouts weebly sites, the association project sources (3.7: the Northwest Montana Lookout Association, the western and the eastern associations, in the order of `ASSOCIATION_SOURCES`), Wikidata, OSM, and then (2026-10-08) Ron
Kemnow's western weebly sites, TrailChick (WA), Every Lookout in Oregon, the FFLA chapter and Friends
pages, WillhiteWeb (WA), and Indiana Fire Towers:

1. **Key**: the record's key is already in a tower's `sources[].key`. A record named in
   `RECORD_JOINS` (merge.py; each entry says why) joins its pinned tower right after this, for
   the few a position and name cannot be trusted to find: recreation.gov's "Post Creek Guard
   Station" is NHLR's "Post Creek Fireman-Lookout House", 779 m away under another name, and
   would otherwise start a second, permanent tower.
2. **Register number**. NHLR and FFLOS number their entries separately ("NHLR US 674" is
   Apache Maid, AZ; "FFLOS US 674" is Buzzard Butte, OR), so the register name is part of the
   key. US numbers decide; state numbers ("WI 49") only when no US number matches. A register
   match more than 5 km away is not taken when the record is a relocated or replica entry, or
   when there is a matching tower on the spot (the review file lists both cases).
3. **Place and name**: towers nearby in the same state, best name first, then nearest.
   Accepted when names agree strongly (score ≥ 0.85) within 1.5 km (3 km for idahofirelookouts.com,
   RIDB and Ron Kemnow's western weebly sites, whose pins are rougher: 95% of the western sites' pins
   fall within 1.5 km of the tower they name, 97.5% within 3 km; 15 km for CSKT's dead-reckoned positions); when names agree
   partly (≥ 0.5) or one is generic ("Fire Tower", unnamed) within 400 m; or within 100 m whatever
   the names (different names for one tower are common: Pequawket = Kearsarge North) — **except**
   for idahofirelookouts.com and RIDB: if the name there is clearly different (score < 0.5) from
   every name at the near tower, and strongly (≥ 0.85) and uniquely names another tower in the
   state within about 75 km, it joins that tower instead (the review file's
   `reassigned_same_spot`; more than one strong match elsewhere is `reassign_same_spot_ambiguous`
   and left on the near tower for a human). This is for the two sources' own coordinate errors,
   not the common-alternate-name case above, so it never fires on a tower that is itself a
   relocated/replica/parts-from structure's current site — RIDB's "Lookout Butte Lookout"
   facility sits 45 m from Black Butte, ID (a coordinate slip) but is genuinely Lookout Butte's
   listing, 64 km away. Across a state line only 400 m with a strong name, or 100 m.
4. **Name only**, for records with no coordinates, after every source: a unique same-name
   tower in the state (and county, when both give one). Otherwise the record is listed in the
   review file as unplaced; it does not make a tower, since a tower needs a position.
5. Anything else **starts a new tower**.

**FFLA's other views and border rows.** The alphabetical list fixes a record's key; the by-county,
standing and by-region views only enrich it (county) and are paired with it by key, by the same
name at the same spot, by position alone (FFLA spells "Remer - first" and "Remer #1" in different
views), or by name when a view leaves the position out or mistypes it. Registers and links come
from the alphabetical list only. FFLA's `ca-un` list is another list, not another sort: its rows
are records of their own, and a tower only they describe is hidden ("Not confirmed as a lookout").
A row under "(Border - see Montana)" is a lookout on a state line listed in both states: it joins
the other state's tower by name when it has no position, and two such rows up to 400 m apart are
one tower (the home state's row gives the position). Rows FFLA lists without a position that no
rule above places stay in the review file as unplaced (no position, no tower).

**The rentals list** (`ffla_rentals`: a name, a state and a booking link, no position) is placed
last, once every tower exists, by `Matcher.match_rentals()`: `FFLA_RENTAL_OVERRIDES` (a table in
merge.py, each entry with its reason; the value is a tower id or the key of a record the tower
holds), then the key from an earlier run, then the recreation.gov facility number in the link
(the tower holding `ridb:<number>`), then the name among the state's towers: of those that name it
(score >= 0.95) the ones recreation.gov rents win, then the ones not known to be gone, and only a
single survivor is taken; a near-match (>= 0.85) is taken only when it is the one tower in the
state recreation.gov rents (and is listed for review); anything else is listed as unplaced with
its candidates. A rental the extract gives a position (only the two private MoonPass towers, whose
owner publishes none: the town of Wallace, rounded to two decimals, so "approximate") matches by
position or starts a tower of its own. One lookout can carry several rental entries.

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
| kind | FFLA > NHLR, FFLOS > RIDB > firelookout.com > fire-lookouts.org > tnlandforms.us > NJFFS table > PA StoryMap > andyarthur.org > Wikipedia lists > CSKT > OSM > the weebly sites > Wikidata > idahofirelookouts.com > michiganfiretower.com. Each record's kind is its type value read through `structure.py`, else its description words (NHLR/FFLOS "100-foot steel tower", "ground cabin"; words about an earlier structure or the living quarters are skipped), else the fetcher's reading. A bare `point` counts only when no source records a structure; with no kind at all, a recognised steel-tower design (Aermotor, IDECO) makes it a `tower` |
| material | Explicit words first: FFLA > NHLR, FFLOS > firelookout.com > fire-lookouts.org > RIDB > OSM (`tower:construction`, `building:material`) > andyarthur.org; type values ("Stone Tower", "Log Crib") and description words read for the tower's kind (a tower's material is the tower's, not the cab's). Then the design (`material_from: "design"`): `data/designs.json`'s `material` for each design when present, else a fallback (L-4, L-6, R-6, D-6 wood; D-1 log; Aermotor, IDECO, other steel makers steel; L-5, cupola houses, California plans none, since their sources describe two materials). A steel-tower design gives a tower's material; a cab design only a building's |
| roles | union |
| built (and its events) | NHLR, FFLOS > firelookout.com > fire-lookouts.org > PA StoryMap > RIDB > the weebly sites > Wikidata > CSKT > idahofirelookouts.com > michiganfiretower.com > OSM > andyarthur.org > Wikipedia lists > FFLA; one source's build dates are used, others' go to `conflicts` |
| elevation | NHLR, FFLOS > firelookout.com > fire-lookouts.org > tnlandforms.us > NJFFS table > RIDB > Wikidata > CSKT > OSM |
| design, height | NHLR, FFLOS > firelookout.com > fire-lookouts.org > NJFFS table (height only) > PA StoryMap > CSKT > the weebly sites (> Wikidata > OSM for height) |
| county | NHLR, FFLOS > FFLA > firelookout.com > PA StoryMap > CSKT > andyarthur.org > Wikipedia lists > fire-lookouts.org > tnlandforms.us > NJFFS table > the weebly sites > Wikidata > michiganfiretower.com |
| agency | NHLR, FFLOS > RIDB > firelookout.com > fire-lookouts.org > tnlandforms.us > NJFFS table > PA StoryMap > andyarthur.org > CSKT > the weebly sites > OSM > michiganfiretower.com |
| rental | RIDB (recreation.gov) first; the FFLA rentals list adds `manager` and `status_note` to a RIDB rental and is the rental itself when RIDB has none (`source: "ffla"`). If the tower's status is gone/ruins (Flag Point, OR: FFLA "Burned 2026"), warn, don't hide: the listing is kept with `available: false` (not counted or filtered as rentable) and a `warning` ("FFLA reports this lookout burned in 2026, but recreation.gov still lists it. Check with the forest before booking."; "the FFLA rentals list" where the rental came from it), which the site shows above the listing link |
| registers | union of all sources; on a tower with an NHLR/FFLOS record, that register's own number wins and a different copy goes to `conflicts` |
| events, photos, links | union, de-duplicated (events by event + year, photos by URL, links by URL); an event keeps the `source_url`/`source_urls` its source gave |

The association project sources (3.7) sit at the foot of the name, location, status, kind, county,
elevation, built, design, height, agency, ownership, staffing and events lists above (they fill
gaps and add history; the registers and lists outrank them), and count as part of the registers'
location lineage because their positions are copied from them.

The links-page sources (2026-10-08) rank **last** in every field they supply, behind OSM and
Wikidata: Ron Kemnow's western weebly sites (name, location, status, county, design, height, agency,
ownership: the same fields as the eastern and central sites), TrailChick (location, county,
elevation, built year and its event, design, height, agency, ownership, status), Every Lookout in
Oregon (elevation, built year and event, design, height, agency, status), the FFLA chapter and
Friends pages (agency and status from the California-South table, plus the destroyed event, and the
links) and WillhiteWeb (a link, and a "standing" status for its 57 Cascades standing lookouts). The
California-South chapter's "Destroyed in 2024 Line Fire" for Keller Peak therefore shows as a status
conflict, not an overrule, until the owner or the FFLA refresh agrees.

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
current one); `kind` when sources disagree on whether a structure stood there at all (a camp or
lookout tree vs a tower or building, which decides the map group); `material` when two sources
name different materials in words;
`registers` as above.

**Coverage check.** After a merge, `python3 pipeline/coverage.py` lists every source record, from
every source, that no tower holds, with the reason, and per source how many records sit on a
visible tower, on a hidden one only, or on none. `--strict` exits 1 if a record with a usable
position is held by no tower (the tower files are older than the extracts). Records with no
position (FFLA rows it publishes without coordinates, rentals no name settles) are the expected
remainder: a tower needs a position.

**Verification**: `facts` when two independent sources agree on location (within 500 m of the
shown position) and status; otherwise `unverified`. NHLR, FFLOS, FFLA and firelookout.com count
as one lineage for this (FFLA carries the register numbers, and 3,173 of firelookout.com's 3,266
coordinates are byte-identical to an FFLA row). `researched`/`verified` are never downgraded.

**Out of scope** (kept, `hidden: true` with a `hidden_reason`): a kind whose `hidden` is true in
`data/structure_kinds.json` (none since 2026-10-08: camps, lookout trees and bare points are
shown as sites with no structure); FFLA "Proposed/Planned/Never Built"; FFLA's "Sites determined
NOT to have been used as wildland fire lookouts"; non-fire towers; sites only FFLA's "Unknown/Undocumented" list (ca-un) has, with no
register or structure from another source; single records hidden by a
human decision (`HIDE_KEYS` in merge.py, e.g. OSM's "East Lookout Tower" on Guam: "Not
confirmed as a fire lookout").

**Ids**: `us-<st>-<slug>` from the display name without trailing "Lookout"/"Tower" words (also
before a parenthetical: "Pilot Peak Lookout (Payette NF)" → `pilot-peak-payette-nf`); moved and
replica structures as above; new
towers are numbered `-2`, `-3`… in a fixed order (state, slug, north to south, first key), so a
re-run from scratch gives the same ids and a new record never takes an existing id.

**Photos** are `{file, thumb, url, source_url, credit, license, caption, year, w, h}`; until
mirrored, `file`/`thumb` (and `w`/`h`) are null, `url` is the remote image (Wikimedia via
`Special:FilePath`) and `source_url` the page it came from. Credit is the photographer "via"
the site, or the site. `file`/`thumb` are filled in from `data/photos_manifest.json`
(written by `pipeline/mirror_photos.py`, §4) each time `pipeline/merge.py` runs; a photo the
mirror step could not use (download failed, or too small once decoded to be a real photo) is
dropped rather than kept on the tower record as a dead link.
**Links** carry a credit-ready `label` and a `kind`: `relocated_from` / `relocated_to` (another
tower page, by `id`), `register`, `rental`, `association` (FFLA
state list; an association's own reports on the lookout), `wikipedia`, `site` (hobbyist and regional pages), `agency`, `website`, `commons`,
`wikidata`, `osm`, `reference` (a page research cites). **`sources[]`** lists, per record, the
fields it supplied.

**Research overlay.** After the source merge, every run lays `data/research/<id>.json` over its
tower (`--research` to point elsewhere), so a re-merge never loses research:

- `facts` (`design`, `height_m`, `status`, `status_note`, `kind`, `staffing`, `access`,
  `visit`, `agency`) replace the merged values, except fields in `locked` (human edits win).
  Values outside the vocabulary are skipped and reported; null `visit` keys are left alone.
  If research changes `status` or `kind` against what the sources say, a conflict keeps the
  research value first and the sources' values, with a note.
- `events` join the sources' events tagged `"from": "research"` with `source_url` (the first
  cited page, `source_urls` when several); the same year + event appears once, research's.
  Event names outside `vocab.event` are left out and reported; a few plain synonyms are mapped
  (unstaffed → staffed_last, decommissioned → abandoned, renovated / restoration_completed →
  restored).
- `summary` becomes the tower's `summary` (map panel and page header); `research` records
  `{researched, checked, verdict, confidence}` for the page's "Researched …, fact-checked" line.
- `verification` becomes `verified` when the fact-check verdict is `pass` or `fixed`, otherwise
  `researched`.
- `photos` are appended (credit and licence kept, de-duplicated by URL); `sources` become links
  of kind `reference` (de-duplicated by URL); `sources[]` gains `{"source": "research",
  "key": "research:<id>", "fields": [...]}`.
- `corrections` are **never applied**: all of them, with `notes_for_editor` and any problems,
  go to `data/merge_report.json` (`research_corrections`, `research`) for a human.

`pipeline/validate.py` checks the research files (shape, vocabulary, citations) and that every
`[^n]` in a story has a definition and a research source `n`.

### 3.6 What the site loads

`pipeline/build_site_data.py` writes `web/public/data/`:

- `towers.geojson`: every visible tower as a point, coordinates rounded to 5 dp. Short
  property names (missing key = null/false; the legend is repeated in `meta.json` → `format`):
  `i` id, `n` name, `r` state, `c` county, `k` kind, `s` status, `v` verification, `a` access,
  `b` year built, `rt` 1 if rentable, `rg` 1 if on a register, `o` other names joined by `|`,
  `y0` / `y1` first year it stood / year it came down (only when an event records it; §4.2),
  `d` recognised design ids joined by `|`, `m` material. Sites with no structure (`k` camp,
  tree, point) are in the file; the map leaves them off until switched on.
- `t/<id>.json`: the full canonical record plus the story HTML, when one exists.
- `meta.json`: counts, source list with retrieved dates, and build date; `history` (how many
  towers have a start year, an end year, neither) and `designs` (design coverage). `counts.total`
  is every site shown; `counts.structures` and `counts.no_structure` split it; `history` and the
  design coverage count structures only; `counts.by_material` too.
- `structure_kinds.json`: `data/structure_kinds.json` with each kind's count and the sources'
  own words for it ("Rooftop", "Grain Elevator"), for the Structure types guide.
- `designs.json`: the designs guide, `data/designs.json`'s curated facts with every lookout of
  each design (`pipeline/designs.py` recognises "L-4", "L4", "Aermotor MC-39"… in the tower's
  `design` and its sources' `type_raw` / `extra.design`; it never guesses).
- `peaks/` (from `pipeline/build_peaks.py`, run after `build_site_data.py`): named summits from
  USGS GNIS (`data/sources/peaks_gnis.json`, fetched by `pipeline/fetch_peaks.py`) cut into
  1° cells, `peaks/<floor lat>_<floor lon>.json` = `[[name, lat, lon, gnis_id], …]` (4 dp), plus
  `peaks/index.json` listing the cells. Files in `data/sources/` with `"kind": "reference"` are
  not lookout sources: `merge.py` and `build_site_data.py` skip them.

### 3.7 Association project sources

Lookout associations (FFLA chapters, "Friends of" groups, the Catskill Fire Tower Project, ...)
publish year-by-year reports of the work they did on particular lookouts: restorations, repairs,
condition assessments, rebuilds. Firefinder reads each association's reports into **one source
per association**, all in the same record shape, so they join the tower timelines as dated,
sourced events and add a few low-ranking facts. Nothing in merge changes when one is added.

**Shape.** A normal source record (3.2) with these conventions. The code is
`pipeline/regional/_projects.py` (helpers and validator, with a docstring that is the full shape);
the first user is `pipeline/regional/nwmt_projects.py`.

| Part | Rule |
|---|---|
| file | `data/sources/<source>.json`, header has `"family": "association_projects"`, `"association": {"name", "url"}` and `"credit"` (the credit line for the About page) |
| `key` | `<source>:<state>:<slug>`, one per lookout (not per report) |
| `url` | the association's best page for that lookout (its latest report); merge shows it as a link of kind `association`, "<association>: work on <lookout>" |
| `name`, `region`, `county` | the association's own name for the lookout; the unit it files it under goes in `extra.forest`; other names in `extra.aliases` |
| position | `lat`/`lon` **copied from a register or list we already hold** (`position_key="nhlr:US 38"` in `_projects.lookout_record`, recorded in `extra.position_from`), because associations rarely publish coordinates. A lookout in no list needs a position from elsewhere, said in `extra.position_note`. No position: matched by unique name in the state only |
| facts | `status` (what the reports show), `agency`, `extra.design` (design and dimensions as the association gives them), `extra.height_ft` (tower height), `extra.staffing_hint` (`staffed`/`emergency`/`volunteer`/`unstaffed`, only for what a recent report says), `extra.ownership` |
| `events` | `{year, event, note, from, source_url[, source_urls]}`. `event` is in `data/vocab.json` (3.4); `note` is our own short sentence (at most 220 characters, never the association's prose); `source_url` is the report that gives the fact (a post, or the PDF itself). One record may not repeat an event name and year: join them in one note. Use `assessed` for condition assessments, `restored` for repair and repainting, `modified` for additions |

**Merge.** The source id is listed once in `ASSOCIATION_SOURCES` (`pipeline/merge.py`). That
puts it in the match order after the other regional sources (before Wikidata and OSM), at the
foot of the `name`, `location`, `status`, `kind`, `county`, `elevation`, `built`, `design`,
`height`, `agency`, `ownership`, `staffing` and `events` precedence lists (the registers and
lists outrank it, an association fills gaps and adds history), and in the registers' location
lineage (its positions are copied from them, so it never makes a tower "facts"-verified by
itself). Its events are unioned into the timeline like any source's, de-duplicated by event +
year, each keeping its `source_url`. Because `built` comes from one source only, an
association's `built` year shows only on towers no register dates; a different year from a
register is reported as a `built` conflict. It supplies no registers, photos, access or rental.

**Adding an association.**

1. Read the association's robots.txt and be polite (2 s per host, honest user agent, cache under
   `$FIREFINDER_RAW_ROOT/<source>/`, as in 2). Never get around a login or a block; note it.
2. Write `pipeline/regional/<source>.py`, modelled on `nwmt_projects.py`: a `DocSet` of the
   reports (post and PDF URLs); the lookouts and their events as curated data (the reports are
   prose, so a person or agent reads them and writes each fact once, in our words, citing the
   report by id); `lookout_record(...)` for each lookout; `check_citations` to verify the
   curated facts against the report text; `write_association_source(...)`.
3. Match lookouts to our towers by copying their position from the register entry
   (`position_key`); confirm in a local merge run that every record joined the tower you meant.
   Create a new tower only for a lookout no list has, with a position from a source you name.
4. Add the source id to `ASSOCIATION_SOURCES` in `pipeline/merge.py` (nothing else there), add
   a row to the sources table in 2 and a short note to the matching order in 3.5, and unit-test
   the parsing.
5. Run `python3 pipeline/merge.py && python3 pipeline/validate.py && python3 pipeline/build_site_data.py --strict`
   and `python3 -m unittest discover -s pipeline`; commit the module, its test and
   `data/sources/<source>.json`, not the regenerated towers.

**First source: `nwmt_projects`** (Northwest Montana Lookout Association, `pipeline/regional/nwmt_projects.py`
with the curated facts in `nwmt_projects_data.py`). 37 lookouts, all matched to towers we already had
(Glacier NP 9, Flathead NF 9, Kootenai NF 16, Montana DNRC 2, one relocated lookout in Eureka),
181 events. NMLA's reports are prose, so the facts were read once and written down in our words,
each citing its report; the script checks every citation against the report's text (the lookout is
named, the year appears) and lists new project posts nobody has curated. Conventions: `built` is the
first structure NMLA names or the only one, `replaced` every later one, earlier-structure notes where
a register already dates the present structure are `other`; NMLA's own disagreements (it gives two
build years for Mount Brown, McGuire, Star Peak...) are kept in `extra.discrepancies` and the note
names the other year. Not read: oral histories, event pages, and NMLA's Google My Map of lookouts
(robots.txt disallows `google.com/maps/`).

**Western sources** (agent chapters-west, 2026-10-08; the survey with every group, its robots.txt and what it
holds is `docs/sources/associations_west.md`). Fifteen sources, one module each in `pipeline/regional/`, built
on a small shared driver, `_assoc_site.py` (`E(...)` for an event, `doc(...)` for a cited page or PDF, `run(...)`
fetches and caches the documents, builds the records, checks every cited fact against the document's text and
writes the extract). Fourteen are single-site sources whose few pages were read by hand (`sand_mountain`,
`mountaineers_everett`, `snoqualmie_lookouts`, `buck_rock`, `anffla`, `scmf_lookouts`, `ffla_sdrc`,
`ffla_monterey`, `ffla_ca_south`, `hi_mountain`, `mvffla`, `historicorps_west`, `siskiyou_mountain_club`,
`green_mountain_wa`; 60 lookouts, 189 events). The fifteenth, `ffla_west_reports`, is the large one: the FFLA's
yearly chapter reports and restoration-grant reports for the 14 western states, read by agents batch by batch
into records (lookout, forest, year, event, a note in our words, a short verbatim run of the report as
evidence), which a script checked against the PDF text (name, year, evidence), filtered, and matched to towers
by state, name and forest, ambiguous ones by hand; the result is `ffla_west_reports_data.py` (248 lookouts, 491
events, 146 reports cited). What the filter drops, by rule: plans and hopes, funding amounts, site visits,
nominations to the register (the register's own dates are the authority, so no `nhlr_registered` from the
reports), "wrapped as a precaution" notes, continuing-staffing notes, uncertain years on status events (a
wrong date there would move a lookout on the national slider), and the Northwest Montana Lookout Association's
own projects. Grants awarded are kept as `other` ("FFLA restoration grant of $500 ... for ..."); in the New
Mexico compendium (2020) only the earliest `built` per lookout stays `built`, later structures and additions
are `replaced` or `modified`. PDF text from these files loses the letters of the "ti", "tt", "ft" and "fi"
ligatures, so names are compared in a folded form (`_assoc_site.fold`). Image-only scans (California
Sierra-Nevada 2017-2019, Arizona-New Mexico 2004, Oregon 2004) were read from page images and are not
text-checked; the California Sierra-Nevada 2016 scan holds no project facts. HistoriCorps pages are
announcements of planned work, so those events say "scheduled".

**Eastern sources** (agent chapters-east, 2026-10-08; the survey with every group, its robots.txt and what it
holds is `docs/sources/associations_east.md`). Eleven sources, one module each in `pipeline/regional/`, on the same
shared driver `_assoc_site.py` (`_assoc_east.doc()` only works out PDF or page from the URL): 206 lookout records on 163
towers, 514 dated events, every record joined to the tower it names. `nysffla_projects` is the New York State
Chapter's monthly newsletters (2016 to July 2026, 121 issues) read by agents into records (tower, year, event, a
note in our words, a verbatim run of the issue as evidence), then curated by hand and re-checked against the
issue's text by the driver (75 towers, 227 events; undated work, plans, trail and hunting closures and towers outside
New York left out; a tower's observer's cabin is filed as `other`, never as the tower's own build, removal or loss).
Nine more are single-tower groups with a log or yearly newsletters, read by hand: `st_regis_friends`,
`hurricane_friends`, `mt_arab_friends` (robots.txt `Crawl-delay: 10`, which the module honours), `azure_mountain_friends`,
`bald_mountain_friends`, `bramley_friends`, `stillwater_friends`, `kent_conservation_foundation` and `smokies_friends`
(Mount Cammerer; its 2023 repairs are cited to Smoky Mountain News because the group's own page names no tower).
`ffla_east_reports` is the FFLA's yearly chapter and restoration-grant reports for the eastern, southern and
midwestern chapters (236 PDFs, 2003 to 2025, six reading batches; 122 lookouts, 217 events), filtered by the same rules
as `ffla_west_reports`: no register dates (no `nhlr_registered`), no plans, bare visits, closures without a start
year or status events with an approximate year; grants awarded are `other` ("FFLA restoration grant awarded
for ..."). Not read: image-only PDFs (Pennsylvania 2004, 2005, 2008 and 2009, Mount Arab 2010, Azure 2005), garbled ones (New
Hampshire 2024, Mount Arab 2013 and 2016), and JavaScript-only group sites (Poke-O-Moonshine, Hadley, Stissing).
Friends of Sterling Forest's domain has been hijacked for spam; New Hampshire's state fire-tower page answers 403.

---

## 4. Site

- Static site on GitHub Pages: Vite + TypeScript + **MapLibre GL JS**. No server, no keys.
- Basemaps: OpenFreeMap (vector, keyless) by default, a USGS Topo raster toggle, and later the
  historical USGS topo overlay. Terrain from Mapterhorn or AWS terrarium tiles (keyless).
- **Map page**: clustered points styled by status (standing vs gone) and kind (triangle: tower;
  house: a building, including rooftop cabs and trailers; circle: unknown; diamond: no
  structure); filters (status, kind of structure, a "Show sites with no structure" switch that
  is off by default (`&ns=1`), rentable, state, design, "Built of" material (`&mat=steel`),
  register, verification); search by name (all sites); a side panel with the facts card and a
  link to the full page; deep-linkable URL state. The count says what it counts: "All 7,523
  towers and buildings shown", or with the switch on "All 8,093 lookout sites shown, including
  570 with no structure".
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
  terrarium tiles), drawn by the TypeScript UI. Details in §4.1.

### 4.1 3D views (stage 3, built 2026-10-04)

- **Engine**: `crates/firefinder-view` (Rust, `cargo test`), built by `npm run wasm`
  (wasm-pack, `--target web`) into `web/src/view3d/wasm/` (git-ignored; CI builds it). It runs in
  a Web Worker (`web/src/view3d/worker.ts`) that fetches the tiles; Rust decodes the PNGs and
  keeps a small tile cache. Spherical earth (R = 6,371,008.8 m) with refraction folded into an
  effective radius R' = R / (1 − k), **k = 0.13**; bearings are true.
- **Terrain**: AWS Terrain Tiles (Mapzen/Tilezen Joerd, Terrarium PNG, keyless, CORS open),
  credited on the About page. Zoom by distance: panorama 12 to 4 km, 10 to 40 km, 9 to 100 km,
  8 to 150 km (phones skip 9); viewshed 12 to 4 km, 10 beyond. Heights below sea level read as 0.
- **Eye height** = ground + structure + 1.6 m. Structure = `height_m` (taken as the cab floor)
  when recorded, otherwise by kind: ground cab and trailer eye 2.5 m, two-story and rooftop cab
  6 m, three-story 9 m, lookout tree floor 15 m (about 50 ft), camp and bare point 1.6 m (on the
  ground); towers (and unknown kinds) 9.1 m (30 ft) west of 100°W, 20 m (66 ft) east of it. The page
  says which applies and lets the visitor change it. The eye stands on the highest terrain
  within 75 m of the recorded position (said in "How this view is made").
- **Panorama**: 36 distance layers drawn far to near, paler with distance; only true ridgelines
  are inked; peak labels for GNIS summits whose top clears the nearer terrain (the last 2 % of
  the distance, 150 m–1.5 km, is ignored so a mountain is not hidden by its own slope); other
  lookouts at typical heights, gone ones at their old sites. Where the whole skyline varies by
  less than 1.5°, heights start drawn ×2, labelled on the view and on the pressed button.
- **Viewshed** ("What it could see"): ground in line of sight within 20, 40 or 60 km, on a
  Web Mercator grid, counted over up to 12 lookouts; map URL `&vs=<ids>&vr=<km>`.
- **Lesson** `/learn/smoke/`: two standing lookouts 12–32 km apart in a cluster of at least
  three; the smoke is placed on ground both see, 4–28 km from each, where the lines cut at
  35–145°. Readings round to the nearest half degree. Screen readers hear how far the smoke is
  from the sight; a hint turns the view to within a few degrees of it (and the result says so).

### 4.2 History extras (stage 4, built 2026-10-04)

- **Old topo maps**: a third base map, "Old topo", draws the USGS Historical Topographic Map
  Collection (public domain, 1880s–2006) under the lookouts. Sheet list: USGS TopoView's
  overlay service (`energy.usgs.gov/arcgis/rest/services/topoview/ustOverlay/MapServer/0`,
  CORS open, one query per 1° cell). Scans: each sheet's cloud-optimised GeoTIFF on The
  National Map's storage (`prd-tnm.s3.amazonaws.com/StagedProducts/Maps/HistoricalTopo/GeoTIFF/`),
  read with range requests in a worker, reprojected (sheet polyconic / transverse Mercator /
  UTM; NAD27 → WGS84 by Molodensky) and clipped to each sheet's neatline. No keys. Esri's
  historical topo image service was rejected: its terms require an ArcGIS account. Eras:
  Oldest, 1930s–50s (default), Newest; the sheets closest in date go on top, broad scales
  zoomed out, detailed ones from zoom 12. Colours are softened a little (said on the card).
- **Year view** ("Then & now", `&yr=`): a lookout stands in a year if built on or before it
  and not yet gone. Start = earliest built / rebuilt / replaced / first-staffed year; end =
  first destroyed / burned / removed / abandoned year after the last (re)build, none for a
  lookout standing today. Today uses current status. Lookouts with incomplete dates are counted
  as "may have stood" with the reason, and shown faded on request (`&yrm=1`), never dropped.
- **Tower timeline**: a drawn line (decorative, `aria-hidden`) above the ordered list; gaps of
  15+ years are named ("No record between …"); a Today entry ends the list.
- **Designs guide** `/designs/`: facts in `data/designs.json` (our words, every fact sourced),
  schematics drawn by us and labelled as such, every lookout of each design, a Design filter
  on the map (`&design=l4`). Its own section **Structure types** (`#structure-types`,
  `web/src/render/structures.ts`, rendered from `structure_kinds.json`): one paragraph per kind
  with its count, the sources' words for it and a map link, the no-structure group explained,
  what lookouts are built of, and the Aircraft Warning Service role.
- The **year view** counts towers and buildings only unless the visitor switches on sites with
  no structure, and says which; the smoke-spotting lesson always uses towers and buildings.

---

## 5. Stages

1. **Facts map** (now): FFLA + NHLR + FFLOS + RIDB + OSM + Wikidata + regional extracts →
   merge → map + prerendered tower pages + checklist + credits; Pages deploy; weekly
   rental-refresh Action (re-reads the RIDB export and FFLA's rentals page, so closure notes
   stay current; the FFLA step fails soft, keeping the committed extract, and refuses a page that
   yields under 70% of the rentals already held).
1b. **Photos** (done): mirrored with credit by `pipeline/mirror_photos.py`, resized (≤1024 px
   full size -- dropped from the original ≤1200 px target to stay under the ~800 MB budget --
   plus a ≤360 px thumbnail), `data/photos_manifest.json`, takedown note. Until
   `web/site.config.json`'s `photosBase` is set, the site shows an interim "View photo at
   <source site>" link card (or hotlinks an https original) instead of the mirrored copy;
   hosting the mirrored files is still an open decision for the owner.
   `pipeline/commons_credits.py` (author/licence for the ~217 Wikidata-sourced Commons photos,
   scraped 2 s apart from ordinary `/wiki/File:` pages since Commons' robots.txt blocks the API
   and `Special:FilePath`) is a **manual step**, run by hand after a Wikidata re-fetch, not part
   of the weekly rental-refresh Action: nothing in that Action re-fetches `data/sources/
   wikidata.json`, so the same ~217 pages would otherwise be re-scraped from Commons every week
   for no new information -- impolite for zero benefit, and unrelated to what that Action
   actually refreshes. Re-run it by hand whenever `pipeline/fetch_wikidata.py` adds photos.
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
  Node 24 for the site. **One exception**: `pipeline/mirror_photos.py` uses Pillow (the
  system `python3`'s copy, 10.2 with WebP) for image decoding, EXIF/orientation handling and
  WebP encoding. It is a dev-time tool an agent runs locally to mirror photos and write
  `data/photos_manifest.json`; it never runs in CI, so the no-installs constraint does not
  apply to it.
