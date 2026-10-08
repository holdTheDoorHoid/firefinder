import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { activeFilterCount, applyFilters, defaultFilters, facetCounts } from '../src/lib/filters.ts';
import { shapeFor } from '../src/lib/icons.ts';
import type { StructureKindsFile, TowerFeature, TowerProps, TowerRecord } from '../src/lib/types.ts';
import { parseState, serializeState, defaultState } from '../src/lib/urlstate.ts';
import { KIND, KIND_ORDER, MATERIAL, MATERIAL_ORDER, NO_STRUCTURE_KINDS, ROLE, isNoStructure } from '../src/lib/vocab.ts';
import { structuresSection } from '../src/render/structures.ts';
import { factRows } from '../src/render/tower.ts';

const data = (name: string) => JSON.parse(readFileSync(resolve(import.meta.dirname, '../../data', name), 'utf8'));
const kindsFile = data('structure_kinds.json') as {
  kinds: { id: string; label: string; group: string; hidden: boolean }[];
  materials: { id: string; label: string }[];
  roles: { id: string; label: string }[];
};
const vocab = data('vocab.json') as Record<string, Record<string, string>>;

describe('structure kinds: the site agrees with data/structure_kinds.json', () => {
  it('has the same kinds, labels and no-structure group', () => {
    expect(Object.keys(KIND).sort()).toEqual(kindsFile.kinds.map((k) => k.id).sort());
    for (const k of kindsFile.kinds) expect(KIND[k.id]!.label, k.id).toBe(k.label);
    expect([...NO_STRUCTURE_KINDS].sort()).toEqual(kindsFile.kinds.filter((k) => k.group === 'no_structure').map((k) => k.id).sort());
    expect(Object.keys(vocab.kind!).sort()).toEqual(Object.keys(KIND).sort());
  });

  it('offers every structure kind in the kind filter and gives the rest their own switch', () => {
    const all = new Set([...KIND_ORDER, ...NO_STRUCTURE_KINDS]);
    expect([...all].sort()).toEqual(Object.keys(KIND).sort());
    expect(KIND_ORDER.some((k) => isNoStructure(k))).toBe(false);
  });

  it('words every material and role', () => {
    expect([...MATERIAL_ORDER].sort()).toEqual(Object.keys(vocab.material!).sort());
    for (const m of kindsFile.materials) expect(MATERIAL[m.id]!.label).toBe(m.label);
    expect(Object.keys(ROLE).sort()).toEqual(Object.keys(vocab.role!).sort());
  });

  it('draws sites with no structure as diamonds, buildings as houses', () => {
    for (const k of NO_STRUCTURE_KINDS) expect(shapeFor(k)).toBe('diamond');
    expect(shapeFor('rooftop')).toBe('house');
    expect(shapeFor('mobile')).toBe('house');
    expect(shapeFor('unknown')).toBe('circle');
  });
});

function f(p: Partial<TowerProps> & { i: string }): TowerFeature {
  return { type: 'Feature', geometry: { type: 'Point', coordinates: [-120, 45] }, properties: { n: p.i, r: 'OR', k: 'tower', s: 'standing', v: 'facts', a: 'public', ...p } };
}

const sites = [
  f({ i: 'us-or-a', k: 'tower', m: 'steel' }),
  f({ i: 'us-or-b', k: 'ground', m: 'wood' }),
  f({ i: 'us-or-c', k: 'camp', s: 'gone' }),
  f({ i: 'us-or-d', k: 'tree', s: 'gone' }),
  f({ i: 'us-or-e', k: 'rooftop' }),
];
const ids = (list: TowerFeature[]) => list.map((x) => x.properties.i);

describe('the no-structure switch and the material filter', () => {
  it('leaves sites with no structure off by default', () => {
    expect(ids(applyFilters(sites, defaultFilters()))).toEqual(['us-or-a', 'us-or-b', 'us-or-e']);
    expect(activeFilterCount(defaultFilters())).toBe(0);
  });

  it('shows them when switched on, whatever the kind filter says about structures', () => {
    const on = { ...defaultFilters(), noStructure: true };
    expect(ids(applyFilters(sites, on))).toHaveLength(5);
    expect(ids(applyFilters(sites, { ...on, kind: new Set(['tower']) }))).toEqual(['us-or-a', 'us-or-c', 'us-or-d']);
    expect(ids(applyFilters(sites, { ...on, kind: new Set() }))).toEqual(['us-or-c', 'us-or-d']);
    expect(activeFilterCount(on)).toBe(1);
  });

  it('does not count them in the kind facet while they are off', () => {
    const counts = facetCounts(sites, defaultFilters(), 'kind');
    expect(counts.get('camp')).toBeUndefined();
    expect(counts.get('rooftop')).toBe(1);
  });

  it('filters by material', () => {
    expect(ids(applyFilters(sites, { ...defaultFilters(), material: 'steel' }))).toEqual(['us-or-a']);
  });

  it('keeps both in the URL', () => {
    const s = defaultState();
    s.filters.noStructure = true;
    s.filters.material = 'stone';
    const q = serializeState(s);
    expect(q).toBe('?mat=stone&ns=1');
    const back = parseState(q);
    expect(back.filters.noStructure).toBe(true);
    expect(back.filters.material).toBe('stone');
    expect(parseState('?mat=chocolate&ns=yes').filters).toMatchObject({ material: null, noStructure: false });
  });
});

describe('structure types guide', () => {
  const file: StructureKindsFile = {
    groups: [
      { id: 'structure', label: 'Lookout structures', shown_by_default: true, about: 'Towers and buildings.', count: 3 },
      { id: 'no_structure', label: 'Sites with no structure', shown_by_default: false, about: 'Camps and trees.', count: 2 },
    ],
    kinds: [
      { id: 'tower', label: 'Cab on a tower', group: 'structure', about: 'The classic.', count: 2, source_words: ['Tower', 'Obs Tower'] },
      { id: 'rooftop', label: 'Cab on a rooftop', group: 'structure', about: 'On a <roof>.', count: 1, source_words: ['Grain Elevator'] },
      { id: 'camp', label: 'Summit camp', group: 'no_structure', about: 'A tent.', count: 2, source_words: [] },
    ],
    materials: [{ id: 'steel', label: 'Steel', about: 'A frame.', count: 1 }],
    roles: [{ id: 'aws', label: 'Aircraft Warning Service post', about: 'Wartime.' }],
    counts: { structures: 3, no_structure: 2, with_material: 1 },
  };
  const out = structuresSection(file, { base: '/ff/' }).value;

  it('has a paragraph, a count and a map link per kind', () => {
    expect(out).toContain('id="structure-types"');
    expect(out).toContain('Cab on a rooftop');
    expect(out).toContain('1 lookout site');
    expect(out).toContain('href="/ff/?kind=rooftop"');
    expect(out).toContain('href="/ff/?ns=1&amp;kind=none"');
    expect(out).toContain('“Grain Elevator”');
    expect(out).toContain('Show sites with no structure');
    expect(out).toContain('1 of the 3 towers and buildings');
    expect(out).toContain('On a &lt;roof&gt;.');
  });
});

describe('tower facts', () => {
  const base: TowerRecord = {
    id: 'us-or-x', name: 'X', region: 'OR', location: { lat: 45, lon: -120 }, kind: 'tower', status: 'standing', verification: 'facts',
  };
  const rows = (r: TowerRecord) => Object.fromEntries(factRows(r).map(([k, v]) => [k, String((v as { value?: string })?.value ?? v)]));

  it('says what it is built of, and when that comes from the design', () => {
    expect(rows({ ...base, material: 'steel', material_from: 'nhlr' })['Built of']).toBe('Steel');
    expect(rows({ ...base, material: 'wood', material_from: 'design' })['Built of']).toContain('Going by its design');
    expect(rows(base)['Built of']).toBe('Not recorded');
  });

  it('labels a site with no structure', () => {
    const r = rows({ ...base, kind: 'tree', status: 'gone' });
    expect(r['Type']).toContain('Lookout tree');
    expect(r['Type']).toContain('Sites with no structure');
    expect(r['Built of']).toBe('Nothing was built');
  });

  it('lists a wartime role', () => {
    expect(rows({ ...base, roles: ['aws'] })['Also served as']).toContain('Aircraft Warning Service post');
  });
});
