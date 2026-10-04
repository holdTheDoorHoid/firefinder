import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { buildIndex, normalize, search } from '../src/lib/search.ts';
import type { TowerFeature } from '../src/lib/types.ts';
import { ACCESS, DESIGN_NAMES, EVENT, KIND, OWNERSHIP, STAFFING, STATUS, VERIFICATION } from '../src/lib/vocab.ts';

const vocab = JSON.parse(readFileSync(resolve(import.meta.dirname, '../../data/vocab.json'), 'utf8')) as Record<string, string[] | Record<string, string>>;
const codes = (k: string) => {
  const v = vocab[k]!;
  return Array.isArray(v) ? v : Object.keys(v);
};

describe('site wording covers data/vocab.json', () => {
  it.each([
    ['kind', KIND],
    ['status', STATUS],
    ['access', ACCESS],
    ['verification', VERIFICATION],
    ['staffing', STAFFING],
    ['ownership', OWNERSHIP],
    ['event', EVENT],
  ] as const)('every %s code has plain-language wording', (key, table) => {
    for (const code of codes(key)) expect(table, `${key}.${code}`).toHaveProperty(code);
  });
});

describe('design names', () => {
  it('match pipeline/designs.py and data/designs.json', () => {
    const py = readFileSync(resolve(import.meta.dirname, '../../pipeline/designs.py'), 'utf8');
    const block = py.slice(py.indexOf('DESIGN_NAMES: dict[str, str] = {'));
    const pyNames = Object.fromEntries([...block.matchAll(/^\s+"([a-z0-9_]+)": "([^"]+)",$/gm)].map((m) => [m[1], m[2]]));
    expect(DESIGN_NAMES).toEqual(pyNames);
    const guide = JSON.parse(readFileSync(resolve(import.meta.dirname, '../../data/designs.json'), 'utf8')) as { designs: { id: string }[] };
    expect(guide.designs.map((d) => d.id).sort()).toEqual(Object.keys(DESIGN_NAMES).sort());
  });
});

function t(i: string, n: string, r = 'OR', o?: string): TowerFeature {
  return { type: 'Feature', geometry: { type: 'Point', coordinates: [0, 0] }, properties: { i, n, r, k: 'tower', s: 'standing', v: 'facts', a: 'public', ...(o ? { o } : {}) } };
}

describe('name search', () => {
  const index = buildIndex([
    t('us-ca-hirz-mountain', 'Hirz Mountain Lookout', 'CA'),
    t('us-ny-hunter-mountain', 'Hunter Mountain Fire Tower', 'NY'),
    t('us-or-dutchmans-peak', 'Dutchman Peak Lookout', 'OR', 'Dutchman Peak Lookout Station'),
    t('us-mt-garnet-mountain', 'Garnet Mountain Lookout', 'MT'),
    t('us-wa-mount-peak', 'Mount Peak Fire Lookout', 'WA'),
  ]);
  const names = (q: string) => search(index, q).map((e) => e.props.i);

  it('normalises case, accents and punctuation', () => {
    expect(normalize("  Dutchman's  PEAK—Lookout ")).toBe('dutchman s peak lookout');
    expect(normalize('Crêpe Mountain')).toBe('crepe mountain');
  });

  it('ranks names that start with the query first', () => {
    expect(names('h')).toEqual(['us-ca-hirz-mountain', 'us-ny-hunter-mountain']);
    expect(names('mount')[0]).toBe('us-wa-mount-peak');
  });

  it('matches word prefixes in any order, including the state', () => {
    expect(names('hunter ny')).toEqual(['us-ny-hunter-mountain']);
    expect(names('mountain lookout')).toEqual(['us-ca-hirz-mountain', 'us-mt-garnet-mountain']);
    expect(names('montana')).toEqual(['us-mt-garnet-mountain']);
  });

  it('finds other names and plain substrings', () => {
    expect(names('station')).toEqual(['us-or-dutchmans-peak']);
    expect(names('arnet')).toEqual(['us-mt-garnet-mountain']);
  });

  it('returns nothing for an empty query', () => {
    expect(search(index, '   ')).toEqual([]);
  });
});
