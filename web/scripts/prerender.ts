/**
 * Prerender one static page per lookout, plus the About page's generated parts.
 * Runs after `vite build` (see package.json "build"): node scripts/prerender.ts
 *
 * Input:  dist/tower.html (template with hashed asset links, from Vite)
 *         dist/data/t/<id>.json, dist/data/meta.json (from pipeline/build_site_data.py)
 * Output: dist/t/<id>/index.html, filled dist/about/index.html, dist/sitemap.xml,
 *         dist/unplaced/index.html and dist/unplaced/<st>/index.html ("Lookouts we can't place yet",
 *         from dist/data/unplaced.json)
 *
 * Plain string templates and synchronous file writes: ~9,000 pages take a few seconds.
 */
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { performance } from 'node:perf_hooks';
import config from '../site.config.json' with { type: 'json' };
import { isTowerId } from '../src/lib/checklist.ts';
import { isSafeStoryHtml } from '../src/lib/html.ts';
import type { Meta, SourceInfo, TowerRecord } from '../src/lib/types.ts';
import { renderTowerHead, renderTowerMain, type RenderContext } from '../src/render/tower.ts';
import { fixtureBanner, mapKey, sourcesRows, takedownEmail } from '../src/render/site.ts';
import { designsEnd, designsMain } from '../src/render/designs.ts';
import type { DesignsFile } from '../src/lib/types.ts';
import { structuresSection } from '../src/render/structures.ts';
import type { StructureKindsFile } from '../src/lib/types.ts';
import type { UnplacedFile } from '../src/lib/types.ts';
import { escapeHtml } from '../src/lib/html.ts';
import { unplacedHead, unplacedIndexMain, unplacedPageStates, unplacedStateMain } from '../src/render/unplaced.ts';

const t0 = performance.now();
const root = resolve(import.meta.dirname, '..');
const dist = join(root, 'dist');
const dataDir = join(dist, 'data');

function fail(msg: string): never {
  console.error(`prerender: ${msg}`);
  process.exit(1);
}

if (!existsSync(join(dist, 'tower.html'))) fail('dist/tower.html is missing. Run `vite build` first.');
if (!existsSync(join(dataDir, 'meta.json'))) {
  fail('dist/data/meta.json is missing. Run `python3 pipeline/build_site_data.py` before building the site.');
}

const meta = JSON.parse(readFileSync(join(dataDir, 'meta.json'), 'utf8')) as Meta;
const ctx: RenderContext = {
  base: config.base,
  siteUrl: config.siteUrl,
  repo: config.repo,
  sources: new Map<string, SourceInfo>(meta.sources.map((s) => [s.id, s])),
  takedownEmail: config.takedownEmail,
  photosBase: config.photosBase ?? null,
};
const banner = fixtureBanner(meta).value;

/* ---------- Tower pages ---------- */
const template = readFileSync(join(dist, 'tower.html'), 'utf8');
for (const mark of ['<!--ff:head-->', '<!--ff:main-->', '<!--ff:banner-->']) {
  if (!template.includes(mark)) fail(`tower.html template has no ${mark} placeholder`);
}
// Split once so each page is a cheap concatenation.
const [beforeHead, afterHead] = template.split('<!--ff:head-->') as [string, string];
const [headToBanner, afterBanner] = afterHead.split('<!--ff:banner-->') as [string, string];
const [bannerToMain, afterMain] = afterBanner.split('<!--ff:main-->') as [string, string];

const files = existsSync(join(dataDir, 't')) ? readdirSync(join(dataDir, 't')).filter((f) => f.endsWith('.json')) : [];
const outDir = join(dist, 't');
rmSync(outDir, { recursive: true, force: true });
mkdirSync(outDir);

let pages = 0;
let unsafeStories = 0;
const sitemap: string[] = [];
for (const file of files) {
  const rec = JSON.parse(readFileSync(join(dataDir, 't', file), 'utf8')) as TowerRecord;
  if (!isTowerId(rec.id) || `${rec.id}.json` !== file) {
    console.warn(`prerender: skipped ${file}: id ${JSON.stringify(rec.id)} does not match the file name`);
    continue;
  }
  if (rec.story_html && !isSafeStoryHtml(rec.story_html)) {
    unsafeStories++;
    console.warn(`prerender: ${rec.id}: story HTML contains markup outside the allowed set; the page shows a notice instead`);
  }
  const page = (
    beforeHead + renderTowerHead(rec, ctx).value + headToBanner + banner + bannerToMain + renderTowerMain(rec, ctx).value + afterMain
  ).replace(/\n\s+/g, '\n'); // drop template indentation (about a third of each page); no <pre> here
  mkdirSync(join(outDir, rec.id));
  writeFileSync(join(outDir, rec.id, 'index.html'), page);
  pages++;
  if (!rec.fixture) sitemap.push(`<url><loc>${ctx.siteUrl}t/${rec.id}/</loc>${rec.updated ? `<lastmod>${rec.updated}</lastmod>` : ''}</url>`);
}
rmSync(join(dist, 'tower.html'));
rmSync(join(dataDir, '.firefinder-site-data'), { force: true }); // the pipeline's own bookkeeping file

/* ---------- About page ---------- */
const aboutPath = join(dist, 'about', 'index.html');
if (existsSync(aboutPath)) {
  const about = readFileSync(aboutPath, 'utf8')
    .replace('<!--ff:sources-->', sourcesRows(meta).value)
    .replace('<!--ff:key-->', mapKey().value)
    .replace('<!--ff:banner-->', banner)
    .replace('<!--ff:takedown-email-->', takedownEmail(config.takedownEmail).value);
  writeFileSync(aboutPath, about);
}

/* ---------- Designs guide ---------- */
const designsPath = join(dist, 'designs', 'index.html');
if (existsSync(designsPath)) {
  const file = existsSync(join(dataDir, 'designs.json')) ? (JSON.parse(readFileSync(join(dataDir, 'designs.json'), 'utf8')) as DesignsFile) : null;
  // "Structure types" (render/structures.ts), its own section on the same page, between the
  // designs and Equipment and reference (designsEnd).
  const kinds = existsSync(join(dataDir, 'structure_kinds.json')) ? (JSON.parse(readFileSync(join(dataDir, 'structure_kinds.json'), 'utf8')) as StructureKindsFile) : null;
  const toc: [string, string][] = kinds ? [['structure-types', 'Structure types']] : [];
  const body = file ? designsMain(file, { base: config.base, repo: config.repo }, { toc }).value : '<p class="notice tone-caution">The designs guide could not be built: designs.json is missing.</p>';
  if (!file) console.warn('prerender: dist/data/designs.json is missing; the designs page says so');
  writeFileSync(designsPath, readFileSync(designsPath, 'utf8').replace('<!--ff:designs-->', body).replace('<!--ff:banner-->', banner).replace(/\n\s+/g, '\n'));
  if (!kinds) console.warn('prerender: dist/data/structure_kinds.json is missing; the designs page leaves out structure types');
  writeFileSync(
    designsPath,
    readFileSync(designsPath, 'utf8')
      .replace('<!--ff:structures-->', kinds ? structuresSection(kinds, { base: config.base }).value.replace(/\n\s+/g, '\n') : '')
      .replace('<!--ff:design-end-->', file ? designsEnd(file).value.replace(/\n\s+/g, '\n') : ''),
  );
}

/* ---------- Lookouts we can't place yet: an index and one page per state ---------- */
const unplacedTemplatePath = join(dist, 'unplaced', 'index.html');
const unplacedPages: string[] = [];
if (existsSync(unplacedTemplatePath)) {
  const tpl = readFileSync(unplacedTemplatePath, 'utf8');
  if (!tpl.includes('<!--ff:unplaced-->')) fail('unplaced/index.html template has no <!--ff:unplaced--> placeholder');
  const file: UnplacedFile = existsSync(join(dataDir, 'unplaced.json'))
    ? (JSON.parse(readFileSync(join(dataDir, 'unplaced.json'), 'utf8')) as UnplacedFile)
    : { count: 0, by_region: {}, lookouts: [] };
  if (!existsSync(join(dataDir, 'unplaced.json'))) console.warn('prerender: dist/data/unplaced.json is missing; the list pages are empty');
  const page = (region: string | null) => {
    const head = unplacedHead(file, region);
    const body = region ? unplacedStateMain(file, region, meta, ctx).value : unplacedIndexMain(file, meta, ctx).value;
    const canonical = `${ctx.siteUrl}unplaced/${region ? `${region.toLowerCase()}/` : ''}`;
    // Function replacements: a "$" in a lookout's name must not be read as a replacement pattern.
    return tpl
      .replace(/<title>[^<]*<\/title>/, () => `<title>${escapeHtml(head.title)}</title>\n  <link rel="canonical" href="${escapeHtml(canonical)}">${meta.fixtures ? '\n  <meta name="robots" content="noindex">' : ''}`)
      .replace(/<meta name="description" content="[^"]*">/, () => `<meta name="description" content="${escapeHtml(head.description)}">`)
      .replace('<!--ff:banner-->', () => banner)
      .replace('<!--ff:unplaced-->', () => body)
      .replace(/\n\s+/g, '\n');
  };
  writeFileSync(unplacedTemplatePath, page(null));
  unplacedPages.push('unplaced/');
  for (const region of unplacedPageStates(file)) {
    const dir = join(dist, 'unplaced', region.toLowerCase());
    mkdirSync(dir, { recursive: true });
    writeFileSync(join(dir, 'index.html'), page(region));
    unplacedPages.push(`unplaced/${region.toLowerCase()}/`);
  }
}

/* ---------- Sitemap ---------- */
writeFileSync(
  join(dist, 'sitemap.xml'),
  `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
    `<url><loc>${ctx.siteUrl}</loc></url>\n<url><loc>${ctx.siteUrl}about/</loc></url>\n<url><loc>${ctx.siteUrl}learn/smoke/</loc></url>\n<url><loc>${ctx.siteUrl}designs/</loc></url>\n` +
    (meta.fixtures ? '' : unplacedPages.map((p) => `<url><loc>${ctx.siteUrl}${p}</loc></url>\n`).join('')) +
    sitemap.join('\n') +
    '\n</urlset>\n',
);

const ms = performance.now() - t0;
console.log(
  `prerender: ${pages} tower pages and ${unplacedPages.length} "can't place yet" pages in ${(ms / 1000).toFixed(2)} s` +
    (meta.fixtures ? ' (FIXTURE DATA: pages are marked noindex and left out of the sitemap)' : '') +
    (unsafeStories ? `; ${unsafeStories} unsafe stories replaced by a notice` : ''),
);
