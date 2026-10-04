# Fixtures

Sample data for building and testing the Firefinder site before real pipeline data exists.

These records use real lookout names and approximate, real-ish locations (right mountain,
right county), with plausible facts drawn from public sources such as the National Historic
Lookout Register, the Forest Fire Lookout Association, Wikipedia/Wikidata, and recreation.gov.
Every record is marked `"fixture": true` and carries today's date.

**Not authoritative. Do not cite anything here as fact.** Details such as elevations, build
years, staffing, and rental terms may be approximate, simplified, or just wrong — they exist
only to exercise the map, tower pages, filters, and checklist against realistic-looking data.

`towers/<state>/<id>.json` are canonical tower records (one hidden tree-platform record is
included to test the out-of-scope filter). `stories/us-or-dutchmans-peak.md` is a sample
researched narrative to test story rendering and footnotes.
