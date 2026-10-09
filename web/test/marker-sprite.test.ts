import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { FILLS, MARKER_PALETTE, SHAPES, markerSprite, markerSymbolId, markerUse, type Fill, type Shape } from '../src/lib/icons.ts';
import { designsMain } from '../src/render/designs.ts';
import type { DesignsFile } from '../src/lib/types.ts';

const baseCss = readFileSync(resolve(import.meta.dirname, '../src/styles/base.css'), 'utf8');

/** The --mk-* tokens in base.css as [light, dark]. */
function tokens(): Map<string, [string, string]> {
  const out = new Map<string, [string, string]>();
  for (const m of baseCss.matchAll(/(--mk-[a-z-]+):\s*light-dark\((#[0-9a-f]{6}),\s*(#[0-9a-f]{6})\)/g)) out.set(m[1]!, [m[2]!, m[3]!]);
  return out;
}

describe('marker palette', () => {
  it('matches the --mk-* tokens in base.css, light and dark', () => {
    const t = tokens();
    const want: Record<string, string> = {
      halo: '--mk-halo',
      standing: '--mk-standing',
      standingEdge: '--mk-standing-edge',
      hollow: '--mk-hollow',
      gone: '--mk-gone',
      other: '--mk-other',
      otherEdge: '--mk-other-edge',
      rent: '--mk-rent',
      rentEdge: '--mk-rent-edge',
      approxEdge: '--mk-approx-edge',
    };
    for (const [key, token] of Object.entries(want)) {
      expect(t.get(token), token).toBeDefined();
      expect(MARKER_PALETTE.light[key as keyof typeof MARKER_PALETTE.light], `${token} light`).toBe(t.get(token)![0]);
      expect(MARKER_PALETTE.dark[key as keyof typeof MARKER_PALETTE.dark], `${token} dark`).toBe(t.get(token)![1]);
    }
  });
});

describe('marker sprite', () => {
  const all = SHAPES.flatMap((s) => FILLS.map((f): readonly [Shape, Fill] => [s, f]));

  it('draws each shape and fill once, painted by the theme tokens', () => {
    const sprite = markerSprite([...all, ...all]);
    for (const [s, f] of all) expect(sprite.split(`id="${markerSymbolId(s, f)}"`).length - 1, `${s} ${f}`).toBe(1);
    const known = tokens();
    const used = new Set([...sprite.matchAll(/var\((--mk-[a-z-]+)\)/g)].map((m) => m[1]!));
    expect(used.size).toBeGreaterThan(0);
    for (const u of used) expect(known.has(u), u).toBe(true);
    // Hidden from assistive technology, and not display:none (which stops some browsers drawing <use>).
    expect(sprite).toContain('aria-hidden="true"');
    expect(sprite).not.toContain('display:none');
  });

  it('is empty when nothing is drawn', () => {
    expect(markerSprite([])).toBe('');
  });

  it('draws a marker as a reference that the sprite answers', () => {
    const use = markerUse('tri', 'solid', 'x');
    expect(use).toBe('<svg class="x" aria-hidden="true"><use href="#mkr-tri-solid"/></svg>');
    expect(markerSprite([['tri', 'solid']])).toContain('id="mkr-tri-solid"');
  });
});

describe('designs page markers', () => {
  const t = (i: string, s: string, k: string) => ({ i, n: `Name ${i}`, r: 'WA', s, k });
  const f: DesignsFile = {
    coverage: { total: 5, with_design_text: 0, recognised: 5, by_design: {}, unmatched_text: 0 },
    designs: [
      {
        id: 'l4',
        name: 'L-4',
        material: 'wood',
        region_codes: ['R6'],
        count: 5,
        by_status: { standing: 2, gone: 2, ruins: 1 },
        sources: [{ title: 'A source', url: 'https://example.test/s' }],
        towers: [t('us-wa-a', 'standing', 'tower'), t('us-wa-b', 'standing', 'ground'), t('us-wa-c', 'gone', 'tower'), t('us-wa-d', 'gone', 'ground'), t('us-wa-e', 'ruins', 'tower')],
      },
    ],
  };
  const out = designsMain(f, { base: '/firefinder/', repo: 'o/r' }).value;

  it('draws the markers once in a sprite instead of on every entry', () => {
    const entries = out.match(/<li><a href="\/firefinder\/t\//g) ?? [];
    expect(entries.length).toBe(5);
    expect(out.split('<symbol ').length - 1).toBeGreaterThanOrEqual(4);
    // No entry carries its own paths: the only <path> elements are the sprite's and the external-link icon's.
    const afterSprite = out.slice(out.indexOf('</svg>', out.indexOf('<symbol ')) + 6);
    expect(afterSprite).not.toContain('<path');
    expect(afterSprite).not.toContain('mk-halo');
  });

  it('points every <use> at a symbol that exists', () => {
    const ids = new Set([...out.matchAll(/<symbol id="([^"]+)"/g)].map((m) => m[1]));
    const refs = [...out.matchAll(/<use href="#([^"]+)"/g)].map((m) => m[1]!);
    expect(refs.length).toBeGreaterThan(5);
    for (const r of refs) expect(ids.has(r), r).toBe(true);
  });

  it('still says each lookout\'s status in words, since the marker is decorative', () => {
    for (const label of ['Standing', 'Gone', 'Ruins']) expect(out).toContain(`<span class="dt-status">${label}</span>`);
    for (const m of out.matchAll(/<svg[^>]*><use /g)) expect(m[0]).toContain('aria-hidden="true"');
  });
});
