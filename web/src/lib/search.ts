/** Name search over the map features. Pure functions; fast enough per keystroke at ~9,000. */
import type { TowerFeature, TowerProps } from './types.ts';
import { regionName } from './vocab.ts';

export interface SearchEntry {
  props: TowerProps;
  coords: [number, number];
  /** Normalised primary name. */
  name: string;
  /** Normalised names (primary + other names). */
  names: string[];
  /** Words of the names plus the state code and state name words. */
  words: string[];
}

export function normalize(s: string): string {
  return s
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

export function buildIndex(features: readonly TowerFeature[]): SearchEntry[] {
  return features.map((f) => {
    const p = f.properties;
    const names = [p.n, ...(p.o ? p.o.split('|') : [])].map(normalize).filter(Boolean);
    const words = new Set<string>();
    for (const n of names) for (const w of n.split(' ')) words.add(w);
    words.add(p.r.toLowerCase());
    for (const w of normalize(regionName(p.r)).split(' ')) words.add(w);
    return { props: p, coords: f.geometry.coordinates, name: names[0] ?? '', names, words: [...words] };
  });
}

/**
 * Ranking: a name that starts with the query, then names where every typed word starts a word
 * (so "hirz mtn" does not match but "hirz mou" and "hunter ny" do), then plain substring
 * matches of 3+ characters (fewer would match half the list). Ties: shorter names first,
 * then alphabetical.
 */
export function search(index: readonly SearchEntry[], query: string, limit = 30): SearchEntry[] {
  const q = normalize(query);
  if (!q) return [];
  const tokens = q.split(' ');
  const scored: { e: SearchEntry; score: number }[] = [];
  for (const e of index) {
    let score = -1;
    if (e.names.some((n) => n.startsWith(q))) score = 0;
    else if (tokens.every((t) => e.words.some((w) => w.startsWith(t)))) score = 1;
    else if (q.length >= 3 && e.names.some((n) => n.includes(q))) score = 2;
    if (score >= 0) scored.push({ e, score });
  }
  scored.sort((a, b) => a.score - b.score || a.e.name.length - b.e.name.length || a.e.name.localeCompare(b.e.name));
  return scored.slice(0, limit).map((s) => s.e);
}
