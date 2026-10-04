/**
 * Prerender one static page per lookout, plus the About page's generated parts.
 * Runs after `vite build` (see package.json "build"): node scripts/prerender.ts
 *
 * Input:  dist/tower.html (template with hashed asset links, from Vite)
 *         dist/data/t/<id>.json, dist/data/meta.json (from pipeline/build_site_data.py)
 * Output: dist/t/<id>/index.html, filled dist/about/index.html, dist/sitemap.xml
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
  const page =
    beforeHead + renderTowerHead(rec, ctx).value + headToBanner + banner + bannerToMain + renderTowerMain(rec, ctx).value + afterMain;
  mkdirSync(join(outDir, rec.id));
  writeFileSync(join(outDir, rec.id, 'index.html'), page);
  pages++;
  if (!rec.fixture) sitemap.push(`<url><loc>${ctx.siteUrl}t/${rec.id}/</loc>${rec.updated ? `<lastmod>${rec.updated}</lastmod>` : ''}</url>`);
}
rmSync(join(dist, 'tower.html'));

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

/* ---------- Sitemap ---------- */
writeFileSync(
  join(dist, 'sitemap.xml'),
  `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
    `<url><loc>${ctx.siteUrl}</loc></url>\n<url><loc>${ctx.siteUrl}about/</loc></url>\n` +
    sitemap.join('\n') +
    '\n</urlset>\n',
);

const ms = performance.now() - t0;
console.log(
  `prerender: ${pages} tower pages in ${(ms / 1000).toFixed(2)} s` +
    (meta.fixtures ? ' (FIXTURE DATA: pages are marked noindex and left out of the sitemap)' : '') +
    (unsafeStories ? `; ${unsafeStories} unsafe stories replaced by a notice` : ''),
);
