import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { designsMain } from '../src/render/designs.ts';
import { hasSchematic, schematicSvg } from '../src/render/schematics.ts';
import { eventSource, oldMapsBlock, timeline, topoViewUrl, type RenderContext } from '../src/render/tower.ts';
import type { DesignsFile, TowerRecord } from '../src/lib/types.ts';

const ctx: RenderContext = {
  base: '/firefinder/',
  siteUrl: 'https://example.test/firefinder/',
  repo: 'owner/repo',
  sources: new Map([['nhlr', { id: 'nhlr', title: 'National Historic Lookout Register' }]]),
  thisYear: 2026,
};

function rec(extra: Partial<TowerRecord>): TowerRecord {
  return {
    id: 'us-wa-test',
    name: 'Test Lookout',
    region: 'WA',
    location: { lat: 48.1, lon: -121.2 },
    kind: 'ground',
    status: 'standing',
    verification: 'facts',
    events: [],
    sources: [{ source: 'nhlr' }],
    registers: [],
    ...extra,
  };
}

describe('tower timeline', () => {
  it('draws the line for sighted readers and says everything in the list', () => {
    const out = timeline(rec({ events: [{ year: 1935, event: 'built', from: 'nhlr' }, { year: 1997, event: 'nhlr_registered', from: 'nhlr' }] }), ctx).value;
    expect(out).toContain('class="tl-figure" aria-hidden="true"');
    expect(out).toContain('<ol class="timeline">');
    expect(out).toContain('No record between 1935 and 1997');
    expect(out).toContain('<span class="tl-year">Today</span>');
    expect(out).toContain('It still stands, as far as our sources know.');
  });

  it('says when an end was never recorded', () => {
    const out = timeline(rec({ status: 'gone', events: [{ year: 1934, event: 'built' }] }), ctx).value;
    expect(out).toContain('When it came down is not recorded.');
    expect(out).toContain('tl-seg-unknown');
  });

  it('says so plainly when nothing is dated', () => {
    expect(timeline(rec({ status: 'gone', events: [] }), ctx).value).toContain('nobody has recorded when this lookout was built or when it came down');
  });

  it('links each event to its source', () => {
    const r = rec({ registers: [{ register: 'NHLR', number: 'US 1', url: 'http://nhlr.org/lookouts/us/wa/test/' }] });
    expect(eventSource({ year: 1935, event: 'built', source_url: 'https://en.wikipedia.org/wiki/X', source_urls: ['https://en.wikipedia.org/wiki/X', 'https://www.fs.usda.gov/y'] }, r, ctx).toString()).toContain('Sources: <a href="https://en.wikipedia.org/wiki/X"');
    expect(eventSource({ year: 1935, event: 'built', from: 'nhlr' }, r, ctx).toString()).toContain('href="http://nhlr.org/lookouts/us/wa/test/"');
    expect(eventSource({ year: 1935, event: 'built', from: 'nhlr' }, rec({}), ctx).toString()).toContain('href="#src-nhlr"');
    expect(eventSource({ year: 1935, event: 'built', source_url: 'javascript:alert(1)' }, rec({}), ctx).toString()).not.toContain('javascript');
  });

  it('escapes event notes', () => {
    const out = timeline(rec({ events: [{ year: 1935, event: 'built', note: '<img src=x onerror=alert(1)>' }] }), ctx).value;
    expect(out).not.toContain('<img');
    expect(out).toContain('&lt;img');
  });
});

describe('old maps links', () => {
  it('points at USGS TopoView and at the map with the old topo base', () => {
    expect(topoViewUrl(41.92381, -74.51791)).toBe('https://ngmdb.usgs.gov/topoview/viewer/#13/41.9238/-74.5179');
    const out = oldMapsBlock(rec({}), ctx).value;
    expect(out).toContain('&amp;base=old');
    expect(out).toContain('USGS TopoView');
  });
});

describe('designs guide', () => {
  const file = JSON.parse(readFileSync(resolve(import.meta.dirname, '../../data/designs.json'), 'utf8')) as { designs: { id: string; schematic?: string }[] };

  it('has a schematic for every design', () => {
    for (const d of file.designs) expect(hasSchematic(d.schematic), d.id).toBe(true);
    expect(schematicSvg('steel', 'Aermotor')).toContain('role="img"');
    expect(schematicSvg('nope', 'x')).toBe('');
  });

  it('lists the lookouts, escaped, with a link to the map filter', () => {
    const f: DesignsFile = {
      coverage: { total: 10, with_design_text: 4, recognised: 3, by_design: { l4: 2 } },
      designs: [
        {
          id: 'l4',
          name: 'L-4',
          schematic: 'l4',
          summary: 'A <b>cab</b>',
          count: 2,
          by_status: { standing: 1, gone: 1 },
          sources: [{ title: 'Plans', url: 'https://example.test/plan.pdf', supports: ['plans'] }],
          towers: [
            { i: 'us-wa-a', n: 'A <script>', r: 'WA', s: 'standing', k: 'tower', w: 'L-4 "on a tower"' },
            { i: '../../etc', n: 'Bad', r: 'WA', s: 'gone', k: 'tower' },
          ],
        },
      ],
    };
    const out = designsMain(f, { base: '/firefinder/', repo: 'o/r' }).value;
    expect(out).toContain('A &lt;b&gt;cab&lt;/b&gt;');
    expect(out).toContain('A &lt;script&gt;');
    expect(out).not.toContain('../../etc');
    expect(out).toContain('href="/firefinder/?design=l4"');
    expect(out).toContain('Original drawings:');
    expect(out).toContain('for <strong>3</strong> of its 10 lookouts (30%)');
    expect(out).toContain('Another 1 have a design described in words');
  });
});
