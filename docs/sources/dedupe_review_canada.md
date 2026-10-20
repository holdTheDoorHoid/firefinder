# Possible duplicates in Canada: review of 2026-10-20

The follow-up Canadian round added Ron Kemnow's Canadian site, websiteservice.ca, the BC recreation sites
and base-map symbols, the four expansion surveys and CGNDB approximate pins. This file reviews every pair
of separate Canadian towers that might be one lookout, in the manner of `dedupe_review_2026-10.md`:
the merge report's `near_misses` (the same name within 10 km, or different names within 400 m) and
`approximate.close_pairs`, plus a wider scan made for this review, because Canadian pins are rougher
than US ones: every pair of visible Canadian towers in one province with a close name (score >= 0.85)
within 25 km, or any names within 1 km, and every tower that carries only a fallback name ("Fire tower
(LIO ...)", "Unnamed lookout (BC base map)", OpenStreetMap's bare "Fire Tower") with a named tower or
record near it. Nothing was deleted: where two towers became one, one id was retired (its file kept,
hidden, with `merged_into`, its address redirecting; DESIGN.md 3.5, "Retired towers").

Story agents write stories for Canadian ids from tonight, so the agent joined only the clear pairs; the
orchestrator then decided 11 of the probable ones (2026-10-20), recorded below.

## Result

| | pairs |
|---|---|
| Joined, clear: one tower that firelookout.ca lists twice under two names (an existing id retired) | 2 |
| Joined, clear: a bare OpenStreetMap "Fire Tower" that is a named tower (an existing id retired) | 1 |
| A new record named a fallback-named tower (no id retired; the tower keeps its id and gets a name) | 4 |
| Joined by the orchestrator's decision (2026-10-20) from the probable pairs: 8 existing ids retired, 3 new base-map records joined | 11 |
| Left apart, probably the same lookout | 2 |
| Left apart, two lookouts or not enough to tell | 9 |
| **Reviewed** | **29** |

**Retired Canadian ids** (11, all existing before this round): `ca-on-freswick` (into `ca-on-big-crow-lake`),
`ca-on-brigstocke` (into `ca-on-anima-nipissing`), `ca-on-fire-tower-2` (into `ca-on-elliot-lake`), and by the
orchestrator's decision `ca-on-fire-tower-lio-701163167` (into `ca-on-donovon`), `ca-on-fire-tower-lio-701163176`
(into `ca-on-lyman`), `ca-on-fire-tower-lio-701163178` (into `ca-on-boulter`), `ca-on-fire-tower-lio-151208102`
(into `ca-on-max-lake`), `ca-on-fire-tower-lio-1300479679` (into `ca-on-pickle-lake`), `ca-on-wylie` (into
`ca-on-wylie-2`), `ca-on-kwinkwaga-lake-2` (into `ca-on-kwinkwaga-lake`), `ca-on-skymount-2` (into
`ca-on-skymount`). The orchestrator moves or drops any story or research written for a retired id after merging.

## Joined

The two firelookout.ca double listings are folded in the fetcher (`firelookout_ca.LISTED_TWICE`: a source
listing one tower twice under two names, so its two records are never pinned to each other), and
`RECORD_JOINS` retires the tower the second record had made. The other pins are `RECORD_JOINS` entries
(`pipeline/record_joins.py`), each with its evidence as a comment.

| Towers | Distance | Evidence | Decision |
|---|---|---|---|
| `ca-on-freswick` (Freswick Fire Lookout) and `ca-on-big-crow-lake` | 170 m | firelookout.ca gives both the same latitude (45.82152) and the same state (standing, cab gone). Ontario's Fire Tower Lookouts (forestrangers.github.io) lists "Freswick Tower - Big Crow Lake, Algonquin Park"; Canada's Fire Lookouts lists "BIG CROW LAKE (FRESWICK)". Three sources, one tower | joined into `ca-on-big-crow-lake` (the name Friends of Algonquin Park and the hikes use); Freswick kept as another name |
| `ca-on-brigstocke` and `ca-on-anima-nipissing` | 340 m | Both firelookout.ca records give the address "Anima Nipissing Road, Unorganized West Timiskaming". Ontario's Fire Tower Lookouts: "Brigstocke Tower - Anima Nipissing Lake, Latchford"; Canada's Fire Lookouts: "BRIGSTOCKE", Anima Nipissing Lake, Latchford. Land Information Ontario has one fire tower there, between the two pins (190 m and 230 m) | joined into `ca-on-anima-nipissing` (it holds LIO's surveyed point); Brigstocke kept as another name |
| `ca-on-fire-tower-2` (OpenStreetMap "Fire Tower") and `ca-on-elliot-lake` | 499 m | The node is a 2010 GPS waypoint tagged an observation tower, on the hill above Elliot Lake where firelookout.ca places the Elliot Lake tower (the replica lookout); the Ontario survey names that node as the Elliot Lake tower; no source places a second tower there | joined into `ca-on-elliot-lake` |
| `ca-on-unnamed-fire-tower-at-dividing-lake` (LIO) and Canada's Fire Lookouts' "Chester" | 107 m | The Chester page files the tower under "Dividing Lake - Gogama" and its map pin is 107 m from LIO's unnamed point at Dividing Lake (just over the merge's 100 m any-name radius) | the record joins the LIO tower, which is now "Chester" (id unchanged) |
| `ca-nb-fire-tower` (OpenStreetMap "Fire Tower") and Canada's Fire Lookouts' "Mount Champlain" | 64 m from the summit | The page puts a cupola cabin on the 1,462 ft summit of Mount Champlain; the node is 64 m from the CGNDB's Mount Champlain (Queens County), the only one in New Brunswick | the record joins; the tower is now "Mount Champlain" (id unchanged) |
| `ca-on-kwagama-mountain` and Canada's Fire Lookouts' "Kwagama Hill" (Algoma) | 26 m from the hill | The CGNDB's Kwagama Hill (Algoma) is 26 m from firelookout.ca's Kwagama Mountain tower | the record joins `ca-on-kwagama-mountain` |
| `ca-bc-historic-firetower` (OpenStreetMap "Historic Firetower"), the BC/Yukon survey's "Summit Fire Lookout" and Canada's Fire Lookouts' "Mount Revelstoke" | 350 m from the summit | The node stands 350 m from the CGNDB's Mount Revelstoke summit, where the 1927 Summit Fire Lookout stands; the Canadian Register's coordinate (51.0999, -118.067) is 6 km north-east of the summit, a place point, not the building, so the survey's record now carries no position (`survey_candidates.FLAGGED_POSITIONS`) | both records join; the tower is now "Mount Revelstoke" (id unchanged). Canada's Fire Lookouts' bare BC "Summit" is kept apart from it (`KEEP_APART`): nothing ties it to Mount Revelstoke, and the site has its own Mount Revelstoke page |

## Joined by the orchestrator's decision (2026-10-20)

These were listed as probable; the orchestrator decided them under the owner's rules. A fallback-named
surveyed point joins the named tower beside it: the named id survives and the surveyed point gives the
position (Land Information Ontario and the BC base map rank above firelookout.ca's and Canada's Fire
Lookouts' hand-placed pins; Pickle Lake's LIO point, which LIO itself gives only to 500 m, is chosen by a
`LOCATION_PICKS` entry). For one name and one tower under two pins, the LIO tower survives with its position.
The base-map symbols joined towers new in this round, so their pins name the page's record key, and no
published id changes.

| Towers | Distance | Evidence | Survivor (position from) |
|---|---|---|---|
| `ca-on-donovon` and LIO 701163167 (unnamed) | 453 m | LIO's point is accurate to 10 m; firelookout.ca's pin is hand-placed (marked a guess) | `ca-on-donovon` (LIO) |
| `ca-on-lyman` and LIO 701163176 (unnamed) | 474 m | LIO within 10 m | `ca-on-lyman` (LIO) |
| `ca-on-boulter` and LIO 701163178 (unnamed) | 672 m | LIO within 10 m | `ca-on-boulter` (LIO) |
| `ca-on-max-lake` and LIO 151208102 (unnamed) | 742 m | LIO within 100 m | `ca-on-max-lake` (LIO) |
| `ca-on-pickle-lake` and LIO 1300479679 (unnamed) | 761 m | LIO within 500 m | `ca-on-pickle-lake` (LIO, by `LOCATION_PICKS`) |
| `ca-bc-old-fort` (Canada's Fire Lookouts pin) and BC base-map symbol 12405 | 467 m | The page's pin is the author's (3 decimals); the symbol marks a fire lookout | `ca-bc-old-fort` (base map) |
| `ca-bc-beaver-mountain` and BC base-map symbol 17110 | 502 m | as above; the second symbol on the mountain (29111, 1.4 km away) stays apart | `ca-bc-beaver-mountain` (base map) |
| `ca-bc-bulldog-mountain` and BC base-map symbol 33162 | 886 m | as above | `ca-bc-bulldog-mountain` (base map) |
| `ca-on-wylie` (firelookout.ca) and `ca-on-wylie-2` (LIO "Wylie") | 3.2 km | Same name in the Petawawa Research Forest, which has one Wylie tower (with Malone) | `ca-on-wylie-2` (LIO) |
| `ca-on-kwinkwaga-lake` (LIO) and `ca-on-kwinkwaga-lake-2` (firelookout.ca) | 2.9 km | Same name; firelookout.ca marks its pin a guess | `ca-on-kwinkwaga-lake` (LIO) |
| `ca-on-skymount` and `ca-on-skymount-2` (both firelookout.ca) | 3.8 km | One name, one address (The Archipelago Township), both pins marked a guess; the Ontario survey reads it as one tower listed twice (`firelookout_ca.LISTED_TWICE` folds 41025 into 41030) | `ca-on-skymount`; its position stays approximate (a guess: no surveyed position exists), as its page says |

## Left apart, probably the same lookout

| Towers | Distance | Evidence | Why left |
|---|---|---|---|
| `ca-bc-sugar-mountain` (recreation site) and `ca-bc-sugarloaf-mountain` (Canada's Fire Lookouts pin) | 893 m | The BC/Yukon survey merged the two; but Canada's Fire Lookouts lists "Sugar Mountain" (index) and "Sugarloaf Mountain" (a page) as two entries | the author's two entries may be a double listing or two sites (orchestrator: leave apart) |
| `ca-ab-ironstone` (OpenStreetMap) and `ca-ab-ironstone-2` (Alberta Wildfire and OpenStreetMap) | 1.1 km | Same name; OpenStreetMap maps both | may be the old site and the present tower, as at Baseline (orchestrator: leave apart) |

## Left apart: two lookouts, or not enough to tell

| Towers | Distance | Why |
|---|---|---|
| `ca-ab-baseline` (NHLR) and `ca-ab-baseline-2` | 1.1 km | Two structures: the registered old ground house and the active tower (`KEEP_APART`, owner decision 2026-10-20) |
| `ca-on-joan` and `ca-on-bear-island` | 632 m | Different names and states (Joan destroyed by a tornado in 1969; Bear Island standing); nothing says they shared a site |
| `ca-on-castlebar` and LIO 750714035 | 594 m | Two points of one source (LIO), one named, one "Data Load" |
| LIO 750714031 and LIO 750714032 | 273 m | Two points of one source, both "Data Load" |
| Unnamed BC base-map symbols 16245 and 24688, near Black Knight, Kelowna | 421 m | Two symbols of one source |
| Unnamed BC base-map symbols 29113, 17115, 17116 and 17114 | 0.7 to 3.8 km | Four symbols of one source near Rossland and Trail; Canada's Fire Lookouts places several lookouts there |
| BC base-map symbol 29111 and `ca-bc-beaver-mountain` | 1.25 km | A second symbol on Beaver Mountain; perhaps an older or second structure (orchestrator: leave apart) |
| Unnamed BC base-map symbols 24693/28941, 10948/23590, 29111/17114 | 10 to 24 km | Far apart; the shared name is the fallback, not a name |
| `ca-qc-tour-a-feu-du-mont-morissette` and `ca-qc-tour-de-feu-de-maniwaki-rue-comeau` | 20 km | Two heritage-inventory towers (Blue Sea and Maniwaki); the shared words are "tour de feu" |

## Not duplicates, for the record

- Monument 83: the BC/Yukon survey's Canadian lookout and Washington's `us-wa-monument-83-holdover-peak` are
  the two lookouts on either side of the border monument. The merge no longer joins records across the
  national border (DESIGN.md 3.3), so they are two towers.
- Approximate pins: none of the 81 Canadian pins lies within 3 km of another (`approximate.close_pairs`),
  and none within 1 km of a placed lookout (the merge's guard).
