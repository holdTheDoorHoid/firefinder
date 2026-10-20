export const meta = {
  name: 'firefinder-story-batch-v5',
  description: 'Lookout story research and fact-check (US, Alaska, Hawaii, Canada), 3 lookouts per agent with compact briefs; model from args.model (default sonnet)',
  phases: [
    { title: 'Research', detail: 'one agent per group of 3 lookouts' },
    { title: 'Fact-check', detail: 'one checker per group of 3 stories, starting from check_quotes.py' },
  ],
}

const ROOT = '/home/hoid/Desktop/firefinder'
const today = args.today
const ids = args.ids
const GROUP = args.group || 3
const MODEL = args.model || 'sonnet'
// Haiku takes no effort setting; Sonnet/Opus run at medium.
const OPTS = MODEL === 'haiku' ? { model: MODEL } : { model: MODEL, effort: 'medium' }
const groups = []
for (let i = 0; i < ids.length; i += GROUP) groups.push(ids.slice(i, i + GROUP))
// Ids are <country>-<region>-<slug>: us-or-abbot-butte, us-ak-..., ca-on-shining-tree. Extra rules are sent only to runs that need them.
const hasCA = ids.some((id) => id.startsWith('ca-'))
const hasAKHI = ids.some((id) => /^us-(ak|hi)-/.test(id))
const SEARCH_FLAGS = hasCA ? '--country US (a us- tower) or --country CA (a ca- tower)' : '--country US' // websearch.py's DuckDuckGo region
const labelOf = (id) => id.replace(/^(us|ca)-/, '') // "or-abbot-butte", "on-shining-tree"

const CANADA_RULES = `
- **Canada (ids ca-*)**:
  - Places: use the brief's region_name (a province or territory) and local_unit (District, Regional District, Division No. 18, Borough...) as given. Never write "state" or "county" for a Canadian tower. Land is usually provincial Crown land, not a national forest; name the agency the source names (do not guess it).
  - Sources: provincial and territorial archives (Archives of Ontario, BC Archives, Provincial Archives of Alberta, Saskatchewan Archives, Archives of Manitoba, BAnQ, the Atlantic and territorial archives), Library and Archives Canada, Canadiana.ca, the Canadian Register of Historic Places (historicplaces.ca) and provincial heritage registers, forest-history societies (Forest History Ontario, Forest History Association of BC and of Alberta), ministry annual reports. Registers here are not NHLR/FFLOS/NRHP. For a French-language search add \`--lang fr\` to the websearch.py command.
  - Language: read French sources (BAnQ, Quebec ministry reports), write the story in English. Keep official French names of places and towers as they are ("tour à feu", "Mont-Tremblant"), with an English gloss once where it helps. An evidence quote from a French page stays in French, exact, accents included.
  - Units: metres first with feet in brackets (12 m (39 ft)) for a ca- tower; feet first with metres in brackets (40 ft (12 m)) for a us- tower. height_m in the JSON is always metres.`
const AK_HI_RULES = `
- **Alaska (us-ak-*) and Hawaii (us-hi-*)**: Alaska has boroughs and census areas, not counties (use the brief's local_unit). Sources: BLM Alaska Fire Service history, Alaska State Library, UAF archives, plus the usual US ones. Hawaii has no known fire lookouts: a us-hi- record is probably a WWII coastal-artillery fire-control station, which is NOT a fire lookout. If your sources show the site is not a fire lookout, write no story; put what you found in notes_for_editor, set confidence low and say so in your returned note.`

const RULES = `RULES (condensed from ${ROOT}/research/STORY_GUIDE.md; open that file only if something here is unclear):
- Reading: use \`python3 ${ROOT}/research/fetch_text.py "<url>" --grep "<a|b|c>" --max 3000\`. It reads nhlr.org/firetower.org pages from the local crawl cache, caches everything else and handles PDFs. **Put several fetch_text calls in ONE Bash command** (separated by ; with echo markers) to save steps. Budget per tower: at most 2 WebSearch calls (fallback: \`python3 ${ROOT}/research/websearch.py "<q>" -n 8 ${SEARCH_FLAGS}\`) and at most 6 page reads. Stop once you have enough for an honest story.
- Good sources: the tower's source_pages, the managing agency's pages (US Forest Service and state forestry; Canadian provincial and territorial forestry or parks ministries), heritage-register pages and nominations (NRHP PDFs on npgallery; historicplaces.ca), booking pages (recreation.gov, provincial park reservation sites), newspapers, Wikipedia (for leads; prefer what it cites).
- **Story** \`${ROOT}/data/stories/<id>.md\`:
  - 120–450 words, the length set by the evidence. No heading. Warm, plain English, no "nestled" or "breathtaking". Own words: no copied sentences.
  - Order: built (when, why, design) → staffing, notable fires → fate (abandoned, burned, moved, restored, rented) → today (access, rental).
  - Every factual sentence gets a footnote [^n]. Definitions at the end, one per source, each with a full http(s) URL: \`[^1]: Title, Publisher, https://… (accessed ${today}).\`
  - Never invent names, dates or numbers. Where sources disagree, say so. Don't encourage climbing closed or private towers.
  - **Gone, moved or ruined lookouts** (check the brief's status): the story still runs built → staffing → fate, and "today" means what a source says remains at the site (footings, a foundation, a radio tower, nothing) and whether the site is public. Say plainly when no source describes the site today; never invent remains or a view. For a moved or replica tower, cover both the original site and where the structure stands now.
  - When sources say nothing about a topic (staffing, fires...), leave it out rather than writing a sentence about the missing evidence. The one exception is what remains at the site today, where "no source describes the site now" helps a visitor.
- **Research JSON** \`${ROOT}/data/research/<id>.json\`, with keys:
  - id, researched ("${today}"), summary (one sentence ≤200 chars);
  - facts: only keys a source supports, from design, height_m, status, status_note (only if not plainly standing), staffing {status, as_of}, access {level: public|restricted|permission|private|closed, note}, visit {climbable, drive_up, trail_note}, agency;
  - events [{year, event, note, cite:[n]}] (cite is always a LIST of source numbers, everywhere) where event is one of built, rebuilt, replaced, staffed_first, staffed_last, staffed, abandoned, destroyed, burned, removed, relocated, restored, modified, assessed, fire, closed, rental_opened, nrhp_listed, nhlr_registered, fflos_registered, other (a Canadian register listing is \`other\`, with a note naming the register);
  - **evidence** [{cite, supports, quote}], with an EXACT quote (≤300 chars) from the cited source for every footnoted sentence;
  - corrections [{field, current, proposed, cite, why}], only for errors in the brief's record;
  - resolved_conflicts [{field, explanation, cite}];
  - sources [{n, title, publisher, url, accessed}] numbered as the footnotes;
  - photos [{url, source_url, credit, license, caption, year}], new finds only;
  - confidence (high|medium|low), notes_for_editor.

  Omit unknown keys; no nulls.
- **Quotes are machine-checked.** Copy every evidence quote character for character from what fetch_text printed (never retype, tidy or paraphrase it, and never quote our brief or a search snippet as if it were the page). \`research/check_quotes.py\` compares each quote with the cached page afterwards, and stories whose quotes are not found are thrown out.
- Tools: Bash, Read, Write, Edit, WebSearch, and WebFetch only when fetch_text fails. Do not call spawn_task or any other task, chip or notification tool.${hasCA ? CANADA_RULES : ''}${hasAKHI ? AK_HI_RULES : ''}`

const RESEARCH_SCHEMA = {
  type: 'object',
  properties: { towers: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, words: { type: 'integer' }, sources: { type: 'integer' }, confidence: { type: 'string' }, note: { type: 'string' } }, required: ['id', 'words', 'sources', 'confidence', 'note'] } } },
  required: ['towers'],
}
const VERIFY_SCHEMA = {
  type: 'object',
  properties: { towers: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, verdict: { type: 'string', enum: ['pass', 'fixed', 'fail'] }, claims_checked: { type: 'integer' }, unsupported_removed: { type: 'integer' }, errors_fixed: { type: 'integer' }, quotes_not_found: { type: 'integer' }, copied_prose_found: { type: 'boolean' }, note: { type: 'string' } }, required: ['id', 'verdict', 'claims_checked', 'unsupported_removed', 'errors_fixed', 'quotes_not_found', 'copied_prose_found', 'note'] } } },
  required: ['towers'],
}

const researchPrompt = (g) => `Research and write the histories of ${g.length} fire lookouts for Firefinder (repo ${ROOT}), one after another. Today is ${today}. This is a cost-capped run, so work efficiently and batch your shell commands.

${RULES}

The lookouts: ${g.join(', ')}. Get compact briefs of our current records first (the records may be wrong):
\`python3 ${ROOT}/research/queue.py --briefs ${g.join(' ')}\`

For each one, write its story and research JSON, then move on. **Finish all ${g.length} before you return**; do not stop after the first. Write only those files; no git. Return one row per lookout: words, number of sources, confidence, and a short note.`

const verifyPrompt = (g) => `You are the independent fact-checker for ${g.length} Firefinder lookout stories (repo ${ROOT}). Today is ${today}. This is a cost-capped check, so batch your shell commands.

First run the automatic quote check, which compares every evidence quote with the page it cites:
\`python3 ${ROOT}/research/check_quotes.py ${g.join(' ')} --verbose\`

For each id in [${g.join(', ')}]:
1. Read \`${ROOT}/data/stories/<id>.md\` and \`${ROOT}/data/research/<id>.json\`. If either file is missing, report verdict "fail" for that id and move on.
2. For every quote the script lists as missing: look for the real wording at that source with \`python3 ${ROOT}/research/fetch_text.py "<url>" --grep "<distinctive words>" --max 1500\`. If the page supports the claim, replace the quote with the page's exact words; if it does not, remove the claim from the story and its evidence entry. "close" means the quote is nearly verbatim; leave it.
3. Check every footnoted sentence against the \`evidence\` quotes for that footnote: same numbers, names, dates and meaning. Fix or remove anything unsupported, and rewrite sentences that copy a quote's wording. Make sure every footnote definition has a full http(s) URL matching its source in the JSON, and that a story that lost claims still reads well (120 words is fine).
4. Edit both files in place, keeping the JSON's facts, events and sources consistent with the story. Run the quote check again; every quote should now be found or close. Add \`"verification": {"checked": "${today}", "claims_checked": n, "unsupported_removed": n, "errors_fixed": n, "quotes_spot_checked": n, "quotes_not_found": n, "verdict": "pass|fixed|fail"}\` (quotes_spot_checked = quotes the script checked; quotes_not_found = missing on the FIRST run).

Edit only those files; no git. Tools: Bash, Read, Write, Edit only. Return one row per id.${hasCA ? `

Canadian stories (ids ca-*) are written in English, but a quote taken from a French page stays French, exactly as the page prints it (accents, « » and all): never "correct" or translate a quote to make the check pass. Official French place and tower names stay as written. Units: metres first with feet in brackets for ca- towers, feet first with metres in brackets for us- towers; fix the order if it is wrong. Never "state" or "county" for a Canadian tower.` : ''}`

const results = await pipeline(
  groups,
  (g, _o, i) => agent(researchPrompt(g), { label: `research group ${i + 1}: ${g.map(labelOf).join(', ')}`, phase: 'Research', schema: RESEARCH_SCHEMA, ...OPTS }),
  (r, g, i) => agent(verifyPrompt(g), { label: `check group ${i + 1}`, phase: 'Fact-check', schema: VERIFY_SCHEMA, ...OPTS })
    .then((v) => ({ research: r && r.towers, verify: v && v.towers })),
)
const rows = []
for (const x of results.filter(Boolean)) for (const v of x.verify || []) rows.push(v)
const verdicts = {}
for (const v of rows) verdicts[v.verdict] = (verdicts[v.verdict] || 0) + 1
log(`Checked ${rows.length} of ${ids.length} (${MODEL}): ${JSON.stringify(verdicts)}`)
// Keep the completion report small: totals, plus only the rows that need a look.
const problems = rows.filter((v) => v.verdict === 'fail' || v.quotes_not_found > 0).map((v) => ({ id: v.id, verdict: v.verdict, nf: v.quotes_not_found, note: (v.note || '').slice(0, 300) }))
const missing = ids.filter((id) => !rows.some((v) => v.id === id))
return { verdicts, checked: rows.length, of: ids.length, problems, missing }
