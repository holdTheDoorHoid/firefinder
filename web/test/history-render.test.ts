import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { designsEnd, designsMain } from '../src/render/designs.ts';
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

  it('groups designs by material and region, lists standing lookouts first, and ends with equipment', () => {
    const t = (i: string, s: string, extra: Partial<DesignsFile['designs'][number]['towers'][number]> = {}) => ({ i, n: i, r: 'WA', s, k: 'tower', ...extra });
    const f: DesignsFile = {
      coverage: { total: 4, with_design_text: 1, recognised: 3, by_design: {}, unmatched_text: 0 },
      groups: { materials: [{ id: 'steel', label: 'Steel towers and cabs' }, { id: 'wood', label: 'Wooden cabs, houses and towers' }], regions: [{ id: 'national', label: 'Nationwide' }, { id: 'R6', label: 'Pacific Northwest (Region 6)' }] },
      designs: [
        { id: 'l4', name: 'L-4', family: 'l4', part: 'cab', material: 'wood', region_codes: ['R6'], count: 2, by_status: { standing: 1, gone: 1 }, towers: [t('us-wa-gone', 'gone'), t('us-wa-up', 'standing')],
          variants: [{ name: '1936 revision', years: '1936', description: 'Hip roof.', plans: [{ title: 'L-4 (1936)', url: 'https://firelookout.org/x.pdf' }] }] },
        { id: 'aermotor', name: 'Aermotor', family: 'aermotor', part: 'tower', material: 'steel', region_codes: ['national'], count: 2, by_status: { standing: 2 }, towers: [t('us-wa-aer', 'standing')], members: [{ id: 'aermotor_mc39', name: 'Aermotor MC-39', count: 1 }], count_unspecified: 1 },
        { id: 'aermotor_mc39', name: 'Aermotor MC-39', family: 'aermotor', part: 'tower', material: 'steel', region_codes: ['national'], count: 1, by_status: { standing: 1 }, towers: [t('us-wa-mc', 'standing', { m: ['MC-39'] })] },
      ],
      equipment: [{ id: 'osborne', name: 'Osborne Firefinder', kind: 'firefinder', summary: 'A sighting table.', links: [{ title: 'Diagram', url: 'https://firelookout.org/o.pdf' }] }],
    };
    const out = designsMain(f, { base: '/', repo: 'o/r' }, { toc: [['structure-types', 'Structure types']] }).value;
    const end = designsEnd(f).value;
    // Wood comes after steel here because the file's groups put steel first.
    expect(out.indexOf('id="m-steel"')).toBeLessThan(out.indexOf('id="m-wood"'));
    expect(out).toContain('id="m-wood-r6"');
    expect(out).toContain('Pacific Northwest (Region 6)');
    // Standing first, gone folded away.
    expect(out.indexOf('us-wa-up')).toBeLessThan(out.indexOf('us-wa-gone'));
    expect(out).toContain('gone, moved or unknown');
    // Plan versions link the FFLA scans and credit FFLA.
    expect(out).toContain('href="https://firelookout.org/x.pdf"');
    expect(out).toContain('Forest Fire Lookout Association');
    // A family head names its members and lists only the lookouts with no model on record.
    expect(out).toContain('href="#aermotor_mc39"');
    expect(out).toContain('Part of the <a href="#aermotor">Aermotor</a> family');
    expect(out).toContain('The other 1 are listed under their own design');
    // Structure types (another module) and Equipment and reference (designsEnd, the end of the
    // page) are listed in the contents.
    expect(out).toContain('href="#structure-types"');
    expect(out).toContain('href="#equipment"');
    expect(out).not.toContain('id="equipment"');
    expect(end).toContain('id="equipment"');
    expect(end).toContain('Osborne Firefinder');
  });
});
