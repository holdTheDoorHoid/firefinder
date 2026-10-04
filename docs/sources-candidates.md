# Regional source candidates for the 16 FFLA gap states

DESIGN.md Sec 2 lists 16 states with no FFLA table yet: AL, AK, AR, CT, FL, HI, KY, LA,
MA, MI, MS, MO, OK, PA, SC, TN. This is a research pass only -- **nothing below has been
scraped**. Found by skimming `firelookout.com/links.html`, the FFLA US index
(`firelookout.org/lookouts/us/`), and a round of web search per state.

PA is technically on the FFLA gap list but is **not actually a gap for this project**: it's
already covered by `pa_storymap.py` (47 towers, committed). Listed below only for completeness.

NHLR (`nhlr.org`) and FFLOS (`firetower.org`) already have per-state pages for every state
below (standing / gone registers respectively) and are presumably being pulled by a sibling
worktree per DESIGN.md Sec 2 -- they are **not** re-listed here as "candidates" except where
noted, since the point of this doc is sources *beyond* NHLR/FFLOS.

## Tier 1 -- two hobbyist sites that could fill most of the gap at once

The same "FOREST LOOKOUTS" weebly template as a Pacific-NW-style per-tower archive, split by
region. Same genre as firelookout.com (one page per tower, photos + short history), unknown
author, no licence statement found on either homepage -- facts only, as with firelookout.com.

| Site | States covered (of our 16) | Also covers | Format | Approx. count | Licence |
|---|---|---|---|---|---|
| **centraluslookouts.weebly.com** | AR, LA, MO, OK | IL, IA, KS, MN, TX, WI | Per-tower HTML pages, one per state subsection | Not yet counted; LA alone has dozens | None stated -- facts only, like firelookout.com |
| **easternuslookouts.weebly.com** | AL, CT, FL, KY, MA, MI, MS, PA, SC, TN | DE, GA, IN, ME, MD, NH, NJ, NY, NC, OH, RI, VT, VA, WV | Per-tower HTML pages, PA split into 3 sub-lists (A-F, G-P, R-Z) | Not yet counted; PA's 3-way split implies a large list | None stated -- facts only |

Between the two, **12 of our 16 gap states** have at least one candidate list here (all but
AK and HI). Worth a proper survey pass (page count, coordinate presence, detail-page schema)
before committing to a fetcher -- same reconnaissance this file's siblings (firelookout.com,
fire-lookouts.org) got before their fetchers were written.

## Tier 2 -- structured, coordinate-bearing, state-specific

| State | Candidate | Format | Approx. count | Licence |
|---|---|---|---|---|
| LA | [Wikipedia: *List of fire lookout towers in Louisiana*](https://en.wikipedia.org/wiki/List_of_fire_lookout_towers_in_Louisiana) | Wikitable: name, parish, nearest town, **coordinates**, status, notes. Has a built-in "map all coordinates" tool and KML/GPX export. | ~40, page self-flagged "incomplete" as of March 2023 | CC BY-SA 4.0 (Wikipedia) -- facts reusable with attribution |
| MI | [michiganfiretower.com](https://michiganfiretower.com/) | Per-tower pages, photos + history, dedicated single-state site (like firelookout.com but MI-only) | "less than 25 remaining" currently documented, state once had 250+ | None stated; site's own credit line is "FFLA.org \| Michigan DNR \| USDA" |
| AR | [Wikipedia: *Category:Fire lookout towers in Arkansas*](https://en.wikipedia.org/wiki/Category:Fire_lookout_towers_in_Arkansas); [Lookouts of the Mena & Oden Ranger Districts](http://www.argenweb.net/montgomery/lookouts.htm) | Category = one Wikipedia article per notable (usually NRHP) tower, each with an infobox lat/lon. Ranger-district page = regional genealogy-society list, unknown coordinate presence | Category: ~8-10 individual articles. Ranger-district page: unsurveyed count | Wikipedia CC BY-SA; ranger-district page licence unknown |
| KY | [Wikimedia Commons: *Category:Fire lookout towers in Kentucky*](https://commons.wikimedia.org/wiki/Category:Fire_lookout_towers_in_Kentucky) | Commons category -- photos + some geocoded via Commons' own coordinate template | Small (NHLR already lists 16 standing) | CC BY-SA (Commons) |
| MA | [Wikipedia: *Category:Fire lookout towers in Massachusetts*](https://en.wikipedia.org/wiki/Category:Fire_lookout_towers_in_Massachusetts) | Same pattern as AR/KY | Small; NHLR already lists 51 standing + 56 former for MA, so this state is close to saturated already | CC BY-SA |
| MO | [Missouri Dept. of Conservation "Discover Nature" towersite pages](https://mdc.mo.gov/discover-nature/places/) (e.g. `knob-lick-towersite`, `lenox-towersite`) | One state-agency facts page per named towersite (history, access) | MDC manages ~50 fire towers; unknown how many have a Discover Nature page | Missouri state government page -- check MDC's own terms before reuse |
| TN | *Tennessee Division of Forestry Fire Lookout Towers, 1933-1975* (referenced in several [Tennessee Historical Commission NR nomination PDFs](https://www.tn.gov/historicalcommission)); Wikidata entries per tower (e.g. [Kettlefoot Fire Lookout Tower](https://www.wikidata.org/wiki/Q86928848)) | Consultant historical report (likely PDF, not yet located at a stable URL) with what looks like a full roster; Wikidata gives individual coordinates for NRHP-listed towers | Report: TN had 208 towers at peak, 142 still standing per a 2014 UT survey -- if the report has a full list, this is the single best TN candidate. Wikidata: handful of entries | Report licence unknown (government-commissioned); Wikidata is CC0 |

## Tier 3 -- lower confidence / unverified, worth a second look

| State | Candidate | Note |
|---|---|---|
| AL | [jacksonsramblings.com/forest-fire-lookouts/](https://jacksonsramblings.com/forest-fire-lookouts/); [anffla.org/towers/](https://www.anffla.org/towers/) | Blog and an FFLA-chapter-looking site respectively; neither verified for structure/coordinates yet. `anffla.org` ("AN" = Alabama/NW Florida?) is worth a direct look -- chapter sites have had real per-tower data elsewhere (cf. the NW Montana FFLA chapter linked from firelookout.com/links.html). |
| SC | [easternuslookouts.weebly.com/south-carolina.html](https://easternuslookouts.weebly.com/south-carolina.html) | Already covered under Tier 1; listed again because it was the one SC-specific page this search surfaced directly. |

## No candidate found

- **HI** -- no evidence of any traditional USFS-style fire lookout tower found. Hawaii's fire
  detection/suppression context (small forested land area, different agency structure) may
  simply not have this kind of structure. Recommend treating as **out of scope** rather than
  a gap, unless a future pass turns up something.
- **AK** -- same result: nothing Alaska-specific surfaced despite several query variants;
  search results kept returning lower-48 towers by keyword collision. Recommend a second,
  more targeted pass (e.g. against Alaska DNR Division of Forestry directly) before concluding
  there's truly nothing, since Alaska's fire detection history is less documented online than
  the Lower 48's, not necessarily nonexistent.

## Ranked priority if picking only a few to build next

1. **easternuslookouts.weebly.com** -- single highest-leverage target; plausibly closes AL,
   CT, FL, KY, MA, MI, MS, SC, TN in one fetcher (PA already done).
2. **centraluslookouts.weebly.com** -- same move for AR, LA, MO, OK.
3. **Wikipedia *List of fire lookout towers in Louisiana*** -- small but clean, coordinates
   included, reuse-permitted licence; a good low-risk first Wikipedia-table fetcher to model
   future per-state Wikipedia lists on, if more turn up.
4. **michiganfiretower.com** -- MI-specific backstop/cross-check if the weebly site's MI
   coverage turns out thin.
5. Everything in Tier 3, plus a second attempt at AK.

## Re-run

This file is hand-researched, not script-generated -- there is nothing to re-run. If revisited,
repeat the same two searches (`firelookout.com/links.html`, `firelookout.org/lookouts/us/`) plus
one web search per remaining gap state, and update the tables above.
