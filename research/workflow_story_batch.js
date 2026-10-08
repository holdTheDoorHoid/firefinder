export const meta = {
  name: 'firefinder-story-batch-v4',
  description: 'Lookout story research and fact-check, 3 lookouts per agent with compact briefs; model from args.model (default sonnet)',
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

const RULES = `RULES (condensed from ${ROOT}/research/STORY_GUIDE.md; open that file only if something here is unclear):
- Reading: use \`python3 ${ROOT}/research/fetch_text.py "<url>" --grep "<a|b|c>" --max 3000\`. It reads nhlr.org/firetower.org pages from the local crawl cache, caches everything else and handles PDFs. **Put several fetch_text calls in ONE Bash command** (separated by ; with echo markers) to save steps. Budget per tower: at most 2 WebSearch calls (fallback: \`python3 ${ROOT}/research/websearch.py "<q>" -n 8\`) and at most 6 page reads. Stop once you have enough for an honest story.
- Good sources: the tower's source_pages, Forest Service and state pages, NRHP nominations (npgallery PDFs), recreation.gov listings, newspapers, Wikipedia (for leads; prefer what it cites).
- **Story** \`${ROOT}/data/stories/<id>.md\`:
  - 120–450 words, the length set by the evidence. No heading. Warm, plain English, no "nestled" or "breathtaking". Own words: no copied sentences.
  - Order: built (when, why, design) → staffing, notable fires → fate (abandoned, burned, moved, restored, rented) → today (access, rental).
  - Every factual sentence gets a footnote [^n]. Definitions at the end, one per source, each with a full http(s) URL: \`[^1]: Title, Publisher, https://… (accessed ${today}).\`
  - Never invent names, dates or numbers. Where sources disagree, say so. Don't encourage climbing closed or private towers.
- **Research JSON** \`${ROOT}/data/research/<id>.json\`, with keys:
  - id, researched ("${today}"), summary (one sentence ≤200 chars);
  - facts: only keys a source supports, from design, height_m, status, status_note (only if not plainly standing), staffing {status, as_of}, access {level: public|restricted|permission|private|closed, note}, visit {climbable, drive_up, trail_note}, agency;
  - events [{year, event, note, cite:[n]}] (cite is always a LIST of source numbers, everywhere) where event is one of built, rebuilt, replaced, staffed_first, staffed_last, staffed, abandoned, destroyed, burned, removed, relocated, restored, modified, fire, closed, rental_opened, nrhp_listed, nhlr_registered, fflos_registered, other;
  - **evidence** [{cite, supports, quote}], with an EXACT quote (≤300 chars) from the cited source for every footnoted sentence;
  - corrections [{field, current, proposed, cite, why}], only for errors in the brief's record;
  - resolved_conflicts [{field, explanation, cite}];
  - sources [{n, title, publisher, url, accessed}] numbered as the footnotes;
  - photos [{url, source_url, credit, license, caption, year}], new finds only;
  - confidence (high|medium|low), notes_for_editor.

  Omit unknown keys; no nulls.
- **Quotes are machine-checked.** Copy every evidence quote character for character from what fetch_text printed (never retype, tidy or paraphrase it, and never quote our brief or a search snippet as if it were the page). \`research/check_quotes.py\` compares each quote with the cached page afterwards, and stories whose quotes are not found are thrown out.
- Tools: Bash, Read, Write, Edit, WebSearch, and WebFetch only when fetch_text fails. Do not call spawn_task or any other task, chip or notification tool.`

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

Edit only those files; no git. Tools: Bash, Read, Write, Edit only. Return one row per id.`

const results = await pipeline(
  groups,
  (g, _o, i) => agent(researchPrompt(g), { label: `research group ${i + 1}: ${g.map((id) => id.replace(/^us-/, '')).join(', ')}`, phase: 'Research', schema: RESEARCH_SCHEMA, ...OPTS }),
  (r, g, i) => agent(verifyPrompt(g), { label: `check group ${i + 1}`, phase: 'Fact-check', schema: VERIFY_SCHEMA, ...OPTS })
    .then((v) => ({ research: r && r.towers, verify: v && v.towers })),
)
const rows = []
for (const x of results.filter(Boolean)) for (const v of x.verify || []) rows.push(v)
const verdicts = {}
for (const v of rows) verdicts[v.verdict] = (verdicts[v.verdict] || 0) + 1
log(`Checked ${rows.length} of ${ids.length} (${MODEL}): ${JSON.stringify(verdicts)}`)
return { verdicts, checked: rows.length, rows: rows.map((v) => ({ id: v.id, verdict: v.verdict, u: v.unsupported_removed, e: v.errors_fixed, nf: v.quotes_not_found, c: v.copied_prose_found })) }
