# Story research guide

This is for research agents writing a lookout's history. DESIGN.md §1 holds the owner's
decisions: **story first, sourced**, with footnotes at the end of every page, and our own
prose only. It covers the US (Alaska and Hawaii included) and Canada; the section
"Canada, Alaska and Hawaii" at the end has what differs there.

## Inputs

- The tower record, `data/towers/<folder>/<id>.json`. Ids are `<country>-<region>-<slug>`
  (`us-or-abbot-butte`, `us-ak-…`, `ca-on-shining-tree`); the folder is the bare state code for a US
  tower (`or/`) and `ca-on/` for a Canadian one. Find a record by id with
  `ls data/towers/*/<id>.json`; `research/queue.py --briefs <id>` prints it compactly. Treat it
  as a starting point that may be wrong; `conflicts` lists where sources already disagree.
- **Cached source pages** live under `/home/hoid/Desktop/firefinder/data/raw/`. Read them
  before going to the web. Do not refetch nhlr.org or firetower.org, which only answer plain
  http and are slow.
  - Register pages: `http://nhlr.org/lookouts/us/or/foo/` is cached at
    `data/raw/nhlr/nhlr.org/lookouts/us/or/foo/index.html`. FFLOS pages are the same
    under `data/raw/fflos/firetower.org/…`.
  - Other caches (`firelookout_com/`, `idaho_fl/`, `eastern_us_lookouts/`,
    `central_us_lookouts/`, `tnlandforms/`, `fire_lookouts_org/`, `pa_storymap/`; for Canada
    `firelookout_ca/` and `ontario_lio/`…): find the page with
    `grep -rl "<distinctive name>" data/raw/<source>/`.
- **The web:** read pages with the cheap reader, not WebFetch:
  `python3 /home/hoid/Desktop/firefinder/research/fetch_text.py "<url>" --grep "<words|that|matter>" --max 4000`.
  It caches pages, reads register pages from the local crawl, handles PDFs (NRHP nominations),
  and with `--grep` returns only the matching lines. Use WebFetch only if fetch_text fails
  (e.g. a JavaScript-only page).
  - Good sources:
    - Forest Service and state forestry pages, NRHP nomination forms (NPGallery PDFs), HABS/HAER records (loc.gov).
    - Newspapers (e.g. chroniclingamerica.loc.gov, digital state newspaper archives).
    - Forest histories, Wikipedia (for leads only: cite what it cites where you can) and FFLA's *Lookout Network* articles.
    - Hiking and trail guides (for access only).
    - For Canada, Alaska and Hawaii see the last section.
  - **Budget per tower:** at most 2 WebSearch calls (if WebSearch is unavailable, use
    `python3 /home/hoid/Desktop/firefinder/research/websearch.py "<query>" -n 8 --country US`;
    `--country CA`, with `--lang fr` for French, for a Canadian lookout), and at most
    8 page reads in total. Stop researching once you have enough for an honest story.

## Outputs (write both files; nothing else)

### 1. `data/stories/<id>.md`

- **Length follows the evidence:** about 120 words when sources are thin, at most about 450
  when they are rich. A short honest story beats a padded one. Do not start with a title
  heading (the page already shows the name).
- **Content:** tell what happened, roughly in order. Who built it and when, and why there.
  The design. Notable staffing, smokes and fires. What happened to it: abandoned, burned,
  moved, restored, rented. What it is like today. No headings.
- **Footnotes:** every factual sentence that is not common knowledge carries a footnote
  `[^n]`. Footnote definitions go at the end, in this form:
  `[^1]: Title of page or document, Publisher/site, URL (accessed YYYY-MM-DD).`
  Cite the specific page, not a site's home page.
- **Never invent.** No guessed names, dates, numbers or anecdotes. If two sources disagree,
  say so in the text ("The register gives 1934; the Forest Service history says 1936.[^2][^3]").
  Unknowns stay unknown.
- **Own words.** Do not copy sentences from any source. A short quotation (one sentence at
  most, in quotation marks and attributed) is fine when the wording itself matters, e.g. a
  lookout's log entry.
- **Places and units:** name the region the way the brief gives it (`region_name`, `local_unit`):
  a county, parish, borough or census area in the US; a province or territory and a district,
  regional district, division or the like in Canada. Never "county" or "state" for a Canadian
  tower. US stories give feet first with metres in brackets ("a 40-foot (12 m) tower");
  Canadian stories give metres first with feet in brackets ("a 12 m (39 ft) tower"), matching
  the tower pages. `height_m` in the JSON is always metres.
- **Tone:** warm, concrete, plain English for a curious visitor. No superlatives you can't
  source, no "nestled", no "breathtaking".
- **Safety and access:** do not encourage climbing a closed or private tower. If it's
  private, closed or on tribal land, say so plainly.

### 2. `data/research/<id>.json`

```json
{
  "id": "us-or-hager-mountain",
  "researched": "YYYY-MM-DD",
  "summary": "One sentence (≤ 200 chars) teaser shown on the map panel.",
  "facts": {
    "design": "L-4 ground cab",
    "staffing": {"status": "volunteer", "as_of": "2025"},
    "access": {"level": "public", "note": "Open to hikers; rented overnight in winter."},
    "visit": {"climbable": true, "trail_note": "4.2 mi round trip from the Hager Mountain trailhead"},
    "agency": "Fremont-Winema National Forest"
  },
  "events": [{"year": 1967, "event": "built", "note": "Current R-6 flat-top cab", "cite": [1]}],
  "evidence": [
    {"cite": 1, "supports": "built 1967", "quote": "Built 1967"},
    {"cite": 2, "supports": "rented Dec-May, sleeps 4", "quote": "The lookout is available to rent from December through May and sleeps up to four"}
  ],
  "corrections": [{"field": "location", "current": [42.98, -121.02], "proposed": [42.991, -121.013], "cite": [2], "why": "The record's point is 1.4 km from the summit the sources describe"}],
  "resolved_conflicts": [{"field": "built", "explanation": "1912 is the first lookout on the site; 1967 is the current cab", "cite": [1, 3]}],
  "sources": [{"n": 1, "title": "…", "publisher": "…", "url": "…", "accessed": "YYYY-MM-DD"}],
  "photos": [{"url": "…", "source_url": "…", "credit": "…", "license": "…", "caption": "…", "year": null}],
  "confidence": "high|medium|low",
  "notes_for_editor": "Anything uncertain, disputed or worth a human look."
}
```

- **Omit unknown keys.** Include a `facts` key only when a cited source supports it. Never write `null` placeholders.
- `facts` holds citable facts about the lookout: design, `height_m` (structure height to the
  cab floor), staffing, access, visit, agency, and `status` when it differs from the record.
  `status_note` is one short visitor-facing caveat about the status, used **only** when the
  lookout is not plainly standing (e.g. "Cab removed in 2019; the steel tower remains"). Design
  history belongs in `events`, not `status_note`.
- `events`: `event` must be one of `built, rebuilt, replaced, staffed_first, staffed_last,
  staffed, abandoned, destroyed, burned, removed, relocated, restored, modified, assessed, fire, closed,
  rental_opened, nrhp_listed, nhlr_registered, fflos_registered, other` (`other` needs a note).
  A listing on a Canadian register is `other`, with a note naming the register and its number.
  Every event cites a source number.
- **`evidence` (required, internal, not published):** for **every footnoted sentence**, one or
  more entries giving the cited source number, a short label of what it supports, and an
  **exact quotation** from that source (≤ 300 characters, copied character for character from
  the page text you read). The fact-checker verifies the story against these quotes and
  spot-checks that they really appear in the source; a quote that is not in the source fails
  the whole story.
- `corrections` are only for **errors in the record** (name, location, status, kind, built year,
  identity), never for facts you could put in `facts`. `field` is a tower field name;
  `current`/`proposed` are values (not prose); give `why`. They are reviewed by a human, never applied automatically.
- `resolved_conflicts`: when the record's "Where sources disagree" list holds a disagreement
  that your sources explain (first lookout vs current structure, a typo…), say so here.
- `photos`: new photos you found. Prefer public-domain (USFS, LOC) or Creative Commons; always give credit and licence.
- `sources` numbering matches the story's footnotes.

## Canada, Alaska and Hawaii

The same rules apply; these are the sources and habits that differ. Canadian lookouts mostly stand
on provincial or territorial Crown land or in a park, not national forest, and the agency of the
day is often not today's (Ontario's Department of Lands and Forests, the BC Forest Service, the
Alberta Forest Service, Quebec's ministère des Terres et Forêts). Name the agency as the source
does.

### Canada

- **Provincial and territorial archives** hold forestry-branch annual reports, photographs and
  lookout plans: Archives of Ontario; BC Archives (Royal BC Museum); Provincial Archives of
  Alberta; Saskatchewan Archives; Archives of Manitoba; BAnQ (Bibliothèque et Archives nationales
  du Québec); the provincial archives of the Atlantic provinces (New Brunswick, Nova Scotia, PEI,
  Newfoundland and Labrador); Yukon Archives and the NWT Archives.
- **Canadiana.ca** has digitised Canadian books, periodicals and government reports, among them
  forestry-department annual reports. **Library and Archives Canada** covers federal records,
  national parks and maps. Digitised newspapers: BAnQ numérique, Peel's Prairie Provinces,
  and local collections.
- **Registers:** the **Canadian Register of Historic Places** (historicplaces.ca) and the provincial
  and territorial heritage registers (for Quebec, the Répertoire du patrimoine culturel du Québec).
  They are good for design and dates; write your own words. They are not NHLR, FFLOS or NRHP, and
  a listing is an `other` event with a note naming the register.
- **Forest-history societies:** Forest History Ontario (the Forest History Society of Ontario), the
  Forest History Association of British Columbia and the Forest History Association of Alberta;
  their articles and oral histories often name the observers.
- **Language:** read French sources (BAnQ, Quebec ministry reports) but write the story in English.
  Keep the official French names of places and towers as they are ("tour à feu", "Mont-Tremblant"),
  with an English gloss once where it helps. Search words: *tour à feu, tour d'observation, tour de
  guet, poste de guet*; Quebec's fire-protection agency is the SOPFEU (Société de protection des
  forêts contre le feu). Quote French wording in French, exactly, with your own English rendering
  after it, marked as a translation. An `evidence` quote from a French page stays French, copied
  character for character (`check_quotes.py` ignores accents, « » guillemets, curly quotes and
  non-breaking spaces when it compares). A footnote keeps the document's own title; the access
  date stays `(accessed YYYY-MM-DD)`.
- **Names and units:** provinces and territories are written in English on our pages (Quebec, not
  Québec; the brief's `region_name_fr` is for searching). Metres first, feet in brackets.

### Alaska

A US state, so the US sources apply, plus the **BLM Alaska Fire Service** history, the **Alaska
State Library** historical collections and the **UAF** (University of Alaska Fairbanks) archives.
Alaska has boroughs and census areas, not counties (use the brief's `local_unit`). Say plainly
when a source puts a site on Alaska Native corporation or village land.

### Hawaii

No Hawaiian fire lookouts are known. The World War II **coastal-artillery fire-control stations**
there are **not** fire lookouts. If a Hawaii record turns out to be one, write no story: say so in
`notes_for_editor`, set `confidence` to `low`, and add a `corrections` entry (`field` `hidden`,
`proposed` `true`, with `why` and a cite) for a human to review.
