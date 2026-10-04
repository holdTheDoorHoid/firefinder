import { describe, expect, it } from 'vitest';
import {
  activeFilterCount,
  applyFilters,
  defaultFilters,
  facetCounts,
  isSelected,
  matches,
  toggleValue,
  type ChecklistLookup,
} from '../src/lib/filters.ts';
import type { Mark } from '../src/lib/checklist.ts';
import type { TowerFeature, TowerProps } from '../src/lib/types.ts';
import { STATUS_ORDER } from '../src/lib/vocab.ts';

function f(p: Partial<TowerProps> & { i: string }): TowerFeature {
  return {
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [-120, 45] },
    properties: { n: p.i, r: 'OR', k: 'tower', s: 'standing', v: 'facts', a: 'public', ...p },
  };
}

const towers = [
  f({ i: 'us-or-a', s: 'standing', k: 'tower', rt: 1, rg: 1 }),
  f({ i: 'us-or-b', s: 'gone', k: 'ground', v: 'unverified' }),
  f({ i: 'us-wa-c', r: 'WA', s: 'standing', k: 'platform', rg: 1 }),
  f({ i: 'us-wa-d', r: 'WA', s: 'ruins', k: 'unknown', v: 'researched' }),
  f({ i: 'us-ny-e', r: 'NY', s: 'relocated', k: 'tower', rt: 1 }),
];

const ids = (list: TowerFeature[]) => list.map((x) => x.properties.i);

function checklist(marks: Record<string, Mark[]>): ChecklistLookup {
  return { hasAny: (id, want) => [...want].some((m) => marks[id]?.includes(m)) };
}

describe('filters', () => {
  it('shows everything by default', () => {
    expect(applyFilters(towers, defaultFilters())).toHaveLength(5);
    expect(activeFilterCount(defaultFilters())).toBe(0);
  });

  it('filters by status, kind and verification sets', () => {
    expect(ids(applyFilters(towers, { ...defaultFilters(), status: new Set(['gone', 'ruins']) }))).toEqual(['us-or-b', 'us-wa-d']);
    expect(ids(applyFilters(towers, { ...defaultFilters(), kind: new Set(['tower']) }))).toEqual(['us-or-a', 'us-ny-e']);
    expect(ids(applyFilters(towers, { ...defaultFilters(), verification: new Set(['unverified']) }))).toEqual(['us-or-b']);
  });

  it('an empty set shows nothing (every box unticked)', () => {
    expect(applyFilters(towers, { ...defaultFilters(), status: new Set() })).toHaveLength(0);
  });

  it('filters rentable, registered and state, and combines filters with AND', () => {
    expect(ids(applyFilters(towers, { ...defaultFilters(), rentable: true }))).toEqual(['us-or-a', 'us-ny-e']);
    expect(ids(applyFilters(towers, { ...defaultFilters(), registered: true }))).toEqual(['us-or-a', 'us-wa-c']);
    expect(ids(applyFilters(towers, { ...defaultFilters(), region: 'WA' }))).toEqual(['us-wa-c', 'us-wa-d']);
    const both = { ...defaultFilters(), rentable: true, registered: true };
    expect(ids(applyFilters(towers, both))).toEqual(['us-or-a']);
    expect(activeFilterCount(both)).toBe(2);
  });

  it('filters by design: one design, or any recognised design', () => {
    const t = [f({ i: 'us-wa-l4', d: 'l4' }), f({ i: 'us-wa-two', d: 'l4|r6' }), f({ i: 'us-wa-none' })];
    expect(ids(applyFilters(t, { ...defaultFilters(), design: 'r6' }))).toEqual(['us-wa-two']);
    expect(ids(applyFilters(t, { ...defaultFilters(), design: 'l4' }))).toEqual(['us-wa-l4', 'us-wa-two']);
    expect(ids(applyFilters(t, { ...defaultFilters(), design: 'any' }))).toEqual(['us-wa-l4', 'us-wa-two']);
    expect(activeFilterCount({ ...defaultFilters(), design: 'l4' })).toBe(1);
  });

  it('filters by my checklist: any of the ticked marks', () => {
    const list = checklist({ 'us-or-b': ['visited'], 'us-wa-c': ['want'], 'us-ny-e': ['visited', 'stayed'] });
    const mine = (m: Mark[]) => ({ ...defaultFilters(), mine: new Set(m) });
    expect(ids(applyFilters(towers, mine(['visited']), list))).toEqual(['us-or-b', 'us-ny-e']);
    expect(ids(applyFilters(towers, mine(['stayed', 'want']), list))).toEqual(['us-wa-c', 'us-ny-e']);
    // Without a checklist available, a checklist filter matches nothing rather than everything.
    expect(applyFilters(towers, mine(['visited']), null)).toHaveLength(0);
  });

  it('keeps new vocabulary values visible while a filter is "all"', () => {
    const odd = f({ i: 'us-or-z', s: 'some-new-status' });
    expect(matches(odd.properties, defaultFilters())).toBe(true);
  });

  it('toggleValue returns null when everything ends up selected', () => {
    const off = toggleValue(null, 'gone', false, STATUS_ORDER);
    expect(off).not.toBeNull();
    expect(isSelected(off, 'gone')).toBe(false);
    expect(isSelected(off, 'standing')).toBe(true);
    expect(toggleValue(off, 'gone', true, STATUS_ORDER)).toBeNull();
  });

  it('facet counts apply every other filter but not their own', () => {
    const counts = facetCounts(towers, { ...defaultFilters(), status: new Set(['standing']), region: 'WA' }, 'status');
    expect(counts.get('standing')).toBe(1);
    expect(counts.get('ruins')).toBe(1);
    expect(counts.get('gone')).toBeUndefined();
  });
});
