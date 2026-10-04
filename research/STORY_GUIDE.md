# Story research guide

This is for research agents writing a lookout's history. DESIGN.md §1 holds the owner's
decisions: **story first, sourced**, with footnotes at the end of every page, and our own
prose only.

## Inputs

- The tower record, `data/towers/<region>/<id>.json`. Treat it as a starting point that may
  be wrong; `conflicts` lists where sources already disagree.
- **Cached source pages** live under `/home/hoid/Desktop/firefinder/data/raw/`. Read them
  before going to the web. Do not refetch nhlr.org or firetower.org, which only answer plain
  http and are slow.
  - Register pages: `http://nhlr.org/lookouts/us/or/foo/` is cached at
    `data/raw/nhlr/nhlr.org/lookouts/us/or/foo/index.html`. FFLOS pages are the same
    under `data/raw/fflos/firetower.org/…`.
  - Other caches (`firelookout_com/`, `idaho_fl/`, `eastern_us_lookouts/`,
    `central_us_lookouts/`, `tnlandforms/`, `fire_lookouts_org/`, `pa_storymap/`…): find the
    page with `grep -rl "<distinctive name>" data/raw/<source>/`.
- **The web:**
  - Good sources:
    - Forest Service and state forestry pages, NRHP nomination forms (NPGallery PDFs), HABS/HAER records (loc.gov).
    - Newspapers (e.g. chroniclingamerica.loc.gov, digital state newspaper archives).
    - Forest histories, Wikipedia (for leads only: cite what it cites where you can) and FFLA's *Lookout Network* articles.
    - Hiking and trail guides (for access only).
  - Search limits: use at most 3 WebSearch calls per tower. If WebSearch is unavailable or
    capped, run `python3 /home/hoid/Desktop/firefinder/research/websearch.py "<query>" -n 8`.
    Prefer WebFetch on known URLs.

## Outputs (write both files; nothing else)

### 1. `data/stories/<id>.md`

- **Length follows the evidence:** about 150 words when sources are thin, up to about 700
  when they are rich. A short honest story beats a padded one.
- **Content:** tell what happened, roughly in order. Who built it and when, and why there.
  The design. Notable staffing, smokes and fires. What happened to it: abandoned, burned,
  moved, restored, rented. What it is like today. Use a heading (`## …`) only for stories
  over ~400 words.
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
    "height_m": null,
    "status": "standing",
    "status_note": null,
    "staffing": {"status": "staffed|volunteer|emergency|unstaffed|unknown", "as_of": "2025"},
    "access": {"level": "public|restricted|permission|private|closed|unknown", "note": "…"},
    "visit": {"climbable": true, "drive_up": false, "trail_note": "4.2 mi round trip from …"},
    "agency": "Fremont-Winema National Forest"
  },
  "events": [{"year": 1956, "event": "built", "note": "Replaced a 1923 cupola cab", "cite": [1]}],
  "corrections": [{"field": "location", "current": "…", "proposed": "…", "evidence": "…", "cite": [2]}],
  "sources": [{"n": 1, "title": "…", "publisher": "…", "url": "…", "accessed": "YYYY-MM-DD"}],
  "photos": [{"url": "…", "source_url": "…", "credit": "…", "license": "…", "caption": "…", "year": null}],
  "confidence": "high|medium|low",
  "notes_for_editor": "Anything uncertain, disputed or worth a human look."
}
```

- `facts`: include a key **only** when a cited source supports it. Omit the rest; don't write null placeholders except as shown.
- `events`: use the vocabulary in `data/vocab.json` (`event`), and every event cites a source number.
- `corrections`: proposals only, never applied automatically. Use them when the record looks wrong (name, location, status, kind, built year).
- `photos`: new photos you found. Prefer public-domain (USFS, LOC) or Creative Commons; always give credit and licence.
- `sources` numbering matches the story's footnotes.
