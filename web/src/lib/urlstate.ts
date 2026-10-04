/**
 * Map position, filters and the selected lookout live in the URL query so any view can be
 * shared by copying the address bar. Example:
 *
 *   ?at=7.5/44.1/-121.6&t=us-or-warner-mountain&status=standing&rent=1&state=OR&base=topo
 *
 * "What it could see" adds the lookouts whose views are shaded and the radius in km:
 *
 *   &vs=us-id-pilot-peak,us-id-sheep-mountain&vr=40
 *
 * Defaults are left out, so a plain visit has a clean URL. Unknown or malformed values are
 * dropped rather than causing an error.
 */
import { MARKS, isTowerId, type Mark } from './checklist.ts';
import { defaultFilters, type Filters } from './filters.ts';
import { KIND_ORDER, STATUS_ORDER, VERIFICATION_ORDER } from './vocab.ts';

export interface View {
  zoom: number;
  lat: number;
  lon: number;
}

export type Basemap = 'map' | 'topo';

export interface AppState {
  filters: Filters;
  view: View | null;
  selected: string | null;
  basemap: Basemap;
  /** Lookouts whose viewsheds are shown ("What it could see"). */
  seen: string[];
  /** Viewshed radius, km (null = the default). */
  seenKm: number | null;
}

/** Radii offered for "What it could see", km. */
export const SEEN_RADII_KM = [20, 40, 60] as const;
export const SEEN_MAX = 12;

export function defaultState(): AppState {
  return { filters: defaultFilters(), view: null, selected: null, basemap: 'map', seen: [], seenKm: null };
}

/** "none" encodes a deliberately empty selection (every box unticked). */
const NONE = 'none';

function parseSet(value: string | null, allowed: readonly string[]): Set<string> | null {
  if (value === null) return null;
  if (value === NONE) return new Set();
  const picked = value.split(',').map((v) => v.trim()).filter((v) => allowed.includes(v));
  if (picked.length === 0) return null;
  const set = new Set(picked);
  return allowed.every((v) => set.has(v)) ? null : set;
}

function formatSet(set: Set<string> | null, order: readonly string[]): string | null {
  if (set === null) return null;
  if (set.size === 0) return NONE;
  const known = order.filter((v) => set.has(v));
  const extra = [...set].filter((v) => !order.includes(v)).sort();
  return [...known, ...extra].join(',');
}

function parseView(value: string | null): View | null {
  if (!value) return null;
  const parts = value.split('/').map(Number);
  if (parts.length !== 3 || parts.some((n) => !Number.isFinite(n))) return null;
  const [zoom, lat, lon] = parts as [number, number, number];
  if (zoom < 0 || zoom > 22 || lat < -85 || lat > 85 || lon < -180 || lon > 180) return null;
  return { zoom, lat, lon };
}

function trim(n: number, digits: number): string {
  return String(Number(n.toFixed(digits)));
}

export function formatView(v: View): string {
  return `${trim(v.zoom, 2)}/${trim(v.lat, 4)}/${trim(v.lon, 4)}`;
}

export function parseState(search: string): AppState {
  const q = new URLSearchParams(search);
  const state = defaultState();
  const f = state.filters;
  f.status = parseSet(q.get('status'), STATUS_ORDER);
  f.kind = parseSet(q.get('kind'), KIND_ORDER);
  f.verification = parseSet(q.get('ver'), VERIFICATION_ORDER);
  f.rentable = q.get('rent') === '1';
  f.registered = q.get('reg') === '1';
  const region = (q.get('state') ?? '').toUpperCase();
  f.region = /^[A-Z]{2}$/.test(region) ? region : null;
  const mine = (q.get('mine') ?? '').split(',').filter((m): m is Mark => (MARKS as readonly string[]).includes(m));
  f.mine = mine.length ? new Set(mine) : null;
  state.view = parseView(q.get('at'));
  const t = q.get('t');
  state.selected = isTowerId(t) ? t : null;
  state.basemap = q.get('base') === 'topo' ? 'topo' : 'map';
  state.seen = [...new Set((q.get('vs') ?? '').split(',').filter((id) => isTowerId(id)))].slice(0, SEEN_MAX);
  const km = Number(q.get('vr'));
  state.seenKm = (SEEN_RADII_KM as readonly number[]).includes(km) ? km : null;
  return state;
}

/** Returns "?..." or "" when everything is at its default. */
export function serializeState(state: AppState): string {
  const q = new URLSearchParams();
  const f = state.filters;
  if (state.view) q.set('at', formatView(state.view));
  if (state.selected) q.set('t', state.selected);
  const status = formatSet(f.status, STATUS_ORDER);
  if (status !== null) q.set('status', status);
  const kind = formatSet(f.kind, KIND_ORDER);
  if (kind !== null) q.set('kind', kind);
  const ver = formatSet(f.verification, VERIFICATION_ORDER);
  if (ver !== null) q.set('ver', ver);
  if (f.rentable) q.set('rent', '1');
  if (f.registered) q.set('reg', '1');
  if (f.region) q.set('state', f.region);
  if (f.mine && f.mine.size) q.set('mine', MARKS.filter((m) => f.mine!.has(m)).join(','));
  if (state.basemap === 'topo') q.set('base', 'topo');
  if (state.seen.length) q.set('vs', state.seen.join(','));
  if (state.seen.length && state.seenKm !== null) q.set('vr', String(state.seenKm));
  const s = q.toString().replace(/%2C/g, ',').replace(/%2F/g, '/');
  return s ? `?${s}` : '';
}
