/**
 * Map filters. Pure logic, no DOM, so it is unit-tested directly.
 *
 * A multi-value filter is `null` when "everything" is allowed. That way new vocabulary values
 * added to the data later are shown by default instead of silently disappearing.
 */
import type { Mark } from './checklist.ts';
import type { TowerProps } from './types.ts';

export interface Filters {
  status: Set<string> | null;
  kind: Set<string> | null;
  verification: Set<string> | null;
  rentable: boolean;
  registered: boolean;
  region: string | null;
  /** Show only towers with any of these checklist marks; null = no checklist filter. */
  mine: Set<Mark> | null;
}

export function defaultFilters(): Filters {
  return { status: null, kind: null, verification: null, rentable: false, registered: false, region: null, mine: null };
}

/** Minimal view of the checklist the filter needs (lets tests pass a stub). */
export interface ChecklistLookup {
  hasAny(id: string, marks: Iterable<Mark>): boolean;
}

export function matches(p: TowerProps, f: Filters, checklist?: ChecklistLookup | null): boolean {
  if (f.status && !f.status.has(p.s)) return false;
  if (f.kind && !f.kind.has(p.k)) return false;
  if (f.verification && !f.verification.has(p.v)) return false;
  if (f.rentable && !p.rt) return false;
  if (f.registered && !p.rg) return false;
  if (f.region && p.r !== f.region) return false;
  if (f.mine && f.mine.size > 0) {
    if (!checklist || !checklist.hasAny(p.i, f.mine)) return false;
  }
  return true;
}

export function applyFilters<T extends { properties: TowerProps }>(
  features: readonly T[],
  f: Filters,
  checklist?: ChecklistLookup | null,
): T[] {
  return features.filter((x) => matches(x.properties, f, checklist));
}

/** How many filters differ from the defaults (shown on the phone "Filters (3)" button). */
export function activeFilterCount(f: Filters): number {
  let n = 0;
  if (f.status) n++;
  if (f.kind) n++;
  if (f.verification) n++;
  if (f.rentable) n++;
  if (f.registered) n++;
  if (f.region) n++;
  if (f.mine && f.mine.size) n++;
  return n;
}

export type Facet = 'status' | 'kind' | 'verification' | 'region';
const FACET_PROP: Record<Facet, keyof TowerProps> = { status: 's', kind: 'k', verification: 'v', region: 'r' };

/**
 * Counts per value of one facet, applying every OTHER filter. This is what "Standing (812)"
 * next to a checkbox should mean: how many you would see if you ticked it.
 */
export function facetCounts(
  features: readonly { properties: TowerProps }[],
  f: Filters,
  facet: Facet,
  checklist?: ChecklistLookup | null,
): Map<string, number> {
  const others: Filters = { ...f, [facet]: null };
  const prop = FACET_PROP[facet];
  const counts = new Map<string, number>();
  for (const x of features) {
    if (!matches(x.properties, others, checklist)) continue;
    const key = String(x.properties[prop]);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return counts;
}

/**
 * Toggle one value of a multi-value filter. `all` is every value the UI offers. Returns null
 * (meaning "everything") when every offered value ends up selected.
 */
export function toggleValue(current: Set<string> | null, value: string, on: boolean, all: readonly string[]): Set<string> | null {
  const next = new Set(current ?? all);
  if (on) next.add(value);
  else next.delete(value);
  if (all.every((v) => next.has(v)) && next.size === all.length) return null;
  return next;
}

export function isSelected(current: Set<string> | null, value: string): boolean {
  return current === null || current.has(value);
}
