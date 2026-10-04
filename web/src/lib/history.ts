/**
 * Then and now: which lookouts stood in a given year, and the shape of one lookout's history.
 * Pure functions (no DOM), unit-tested in test/history.test.ts.
 *
 * The owner's rule: a lookout counts as standing in a year if it was built on or before that
 * year and not yet gone. The pipeline gives each map point y0 (first year it is recorded
 * standing) and y1 (year it came down), each only when an event records it. Most lookouts
 * lack one or both, so every count here comes in two parts: those the records place in that
 * year, and those that MAY have stood then but whose dates are incomplete. Nothing is guessed,
 * and nothing is silently dropped.
 */
import type { TowerEvent, TowerProps } from './types.ts';
import { eventLabel } from './vocab.ts';

/** First year on the national slider. */
export const SLIDER_FIRST_YEAR = 1900;

/** Statuses that mean the structure stands today. */
export function standsToday(status: string): boolean {
  return status === 'standing' || status === 'replica';
}

/**
 * Why a lookout is, or may be, on the map in a year:
 *   stood       the records place it there (built by then, and gone later or standing today)
 *   built       built by then, but when it came down is not recorded
 *   nostart     no build year: it stands today, or came down later, but may not have been built yet
 *   nodates     no build year and no end year at all
 *   no          not standing then by the records (not yet built, or already gone)
 */
export type YearState = 'stood' | 'built' | 'nostart' | 'nodates' | 'no';

export function yearState(p: Pick<TowerProps, 's' | 'y0' | 'y1'>, year: number, thisYear: number): YearState {
  const now = standsToday(p.s);
  if (year >= thisYear) {
    // Today the status says it: standing ones stand, gone ones do not, unknown ones may.
    if (now) return 'stood';
    if (p.s !== 'unknown' || p.y1 !== undefined) return 'no';
    return p.y0 === undefined ? 'nodates' : 'built';
  }
  if (p.y0 !== undefined && p.y0 > year) return 'no';
  if (p.y1 !== undefined && p.y1 <= year) return 'no';
  if (p.y0 !== undefined) return now || p.y1 !== undefined ? 'stood' : 'built';
  if (now || p.y1 !== undefined) return 'nostart';
  return 'nodates';
}

/** "May have stood then" states, drawn dimmed when the visitor asks for them. */
export function isMaybe(state: YearState): boolean {
  return state === 'built' || state === 'nostart' || state === 'nodates';
}

export interface YearCounts {
  year: number;
  stood: number;
  built: number;
  nostart: number;
  nodates: number;
  /** stood + every maybe: the most that could have stood. */
  upper: number;
}

export function yearCounts(features: readonly { properties: TowerProps }[], year: number, thisYear: number): YearCounts {
  const c: YearCounts = { year, stood: 0, built: 0, nostart: 0, nodates: 0, upper: 0 };
  for (const f of features) {
    const st = yearState(f.properties, year, thisYear);
    if (st !== 'no') {
      c[st]++;
      c.upper++;
    }
  }
  return c;
}

/**
 * Counts for every year from `from` to `to` (inclusive), in one pass over the features using
 * difference arrays. The year `thisYear` and later uses today's status, as yearState does.
 */
export function yearSeries(features: readonly { properties: TowerProps }[], from: number, to: number, thisYear: number): YearCounts[] {
  const n = to - from + 1;
  if (n <= 0) return [];
  const diff = { stood: new Int32Array(n + 1), built: new Int32Array(n + 1), nostart: new Int32Array(n + 1), nodates: new Int32Array(n + 1) };
  const today: Omit<YearCounts, 'year' | 'upper'> = { stood: 0, built: 0, nostart: 0, nodates: 0 };
  const add = (key: keyof typeof diff, a: number, b: number) => {
    // Adds 1 to every year in [a, b) clipped to [from, min(to + 1, thisYear)).
    const lo = Math.max(a, from);
    const hi = Math.min(b, to + 1, thisYear);
    if (hi <= lo) return;
    diff[key][lo - from]! += 1;
    diff[key][hi - from]! -= 1;
  };
  const INF = Number.MAX_SAFE_INTEGER;
  for (const { properties: p } of features) {
    const now = standsToday(p.s);
    const end = p.y1 ?? INF;
    if (p.y0 !== undefined) {
      add(now || p.y1 !== undefined ? 'stood' : 'built', p.y0, end);
    } else if (now || p.y1 !== undefined) {
      add('nostart', -INF, end);
    } else {
      add('nodates', -INF, INF);
    }
    const t = yearState(p, thisYear, thisYear);
    if (t !== 'no') today[t]++;
  }
  const out: YearCounts[] = [];
  const run = { stood: 0, built: 0, nostart: 0, nodates: 0 };
  for (let i = 0; i < n; i++) {
    const year = from + i;
    if (year >= thisYear) {
      out.push({ year, ...today, upper: today.stood + today.built + today.nostart + today.nodates });
      continue;
    }
    for (const k of ['stood', 'built', 'nostart', 'nodates'] as const) run[k] += diff[k][i]!;
    out.push({ year, ...run, upper: run.stood + run.built + run.nostart + run.nodates });
  }
  return out;
}

/* ---------- One lookout's timeline ---------- */

/** Event kinds, for the marker shape on the tower-page timeline (never colour alone). */
export type EventShape = 'start' | 'staff' | 'record' | 'care' | 'end' | 'move' | 'other';

const SHAPE_OF: Record<string, EventShape> = {
  built: 'start',
  rebuilt: 'start',
  replaced: 'start',
  staffed_first: 'staff',
  staffed_last: 'staff',
  staffed: 'staff',
  nrhp_listed: 'record',
  nhlr_registered: 'record',
  fflos_registered: 'record',
  restored: 'care',
  rental_opened: 'care',
  modified: 'care',
  destroyed: 'end',
  burned: 'end',
  removed: 'end',
  abandoned: 'end',
  closed: 'end',
  fire: 'end',
  relocated: 'move',
};

export function eventShape(event: string): EventShape {
  return SHAPE_OF[event] ?? 'other';
}

/** Events that show the lookout was there in that year. */
const PRESENT = new Set(['built', 'rebuilt', 'replaced', 'staffed_first', 'staffed_last', 'staffed', 'restored', 'rental_opened', 'nrhp_listed', 'nhlr_registered', 'modified']);
const END = new Set(['destroyed', 'burned', 'removed', 'abandoned']);

/** Gaps at least this long between two dated events are pointed out. */
export const GAP_YEARS = 15;

export type TimelineItem =
  | { type: 'event'; year: number | null; event: TowerEvent; index: number }
  | { type: 'gap'; from: number; to: number }
  | { type: 'today'; year: number; status: string };

export interface Segment {
  from: number;
  to: number;
  /** stood: the records show it standing; unknown: no record either way; gone: after it came down. */
  kind: 'stood' | 'unknown' | 'gone';
}

export interface TimelineModel {
  items: TimelineItem[];
  /** Left and right ends of the drawn line (the right end is this year). */
  first: number;
  last: number;
  segments: Segment[];
  /** Dated events, for markers on the line. */
  marks: { year: number; event: string; label: string; shape: EventShape; index: number }[];
  /** True when nothing records when it was built (the line starts dashed). */
  startUnknown: boolean;
  /** True when it does not stand today and nothing records when it came down. */
  endUnknown: boolean;
}

/**
 * The tower page's then-and-now timeline: dated events in order with honest gaps ("No record
 * between 1934 and 1987") and a "today" entry, plus the segments and markers for the drawn line.
 * Returns null when no event has a year (the page then says so in words).
 */
export function timelineModel(events: readonly TowerEvent[] | null | undefined, status: string, thisYear: number): TimelineModel | null {
  const all = (events ?? []).map((event, index) => ({ event, index }));
  const dated = all
    .filter((e) => typeof e.event.year === 'number' && Number.isFinite(e.event.year) && e.event.year >= 1800 && e.event.year <= thisYear)
    .sort((a, b) => a.event.year! - b.event.year! || a.index - b.index);
  if (!dated.length) return null;
  const undated = all.filter((e) => !dated.includes(e));

  const items: TimelineItem[] = [];
  let prev: number | null = null;
  for (const e of dated) {
    const y = e.event.year!;
    if (prev !== null && y - prev >= GAP_YEARS) items.push({ type: 'gap', from: prev, to: y });
    items.push({ type: 'event', year: y, event: e.event, index: e.index });
    prev = y;
  }
  for (const e of undated) items.push({ type: 'event', year: null, event: e.event, index: e.index });
  items.push({ type: 'today', year: thisYear, status });

  // The drawn line: stood from the first year it is known to be there to the last such year
  // (or today when it stands); unknown before a recorded build and after the last record of
  // a lookout that has since gone; gone after the year it came down.
  const years = dated.map((e) => e.event.year!);
  const startYears = dated.filter((e) => ['built', 'rebuilt', 'replaced', 'staffed_first'].includes(e.event.event)).map((e) => e.event.year!);
  const present = dated.filter((e) => PRESENT.has(e.event.event)).map((e) => e.event.year!);
  const lastStart = startYears.length ? Math.max(...startYears) : null;
  const ends = dated.filter((e) => END.has(e.event.event) && (lastStart === null || e.event.year! >= lastStart)).map((e) => e.event.year!);
  const now = standsToday(status);
  const endYear = now ? null : ends.length ? Math.min(...ends) : null;
  const startUnknown = startYears.length === 0;
  const span = Math.max(thisYear - years[0]!, 10);
  const first = startUnknown ? Math.max(1850, Math.round(years[0]! - Math.max(8, span * 0.12))) : years[0]!;
  const last = thisYear;

  const segments: Segment[] = [];
  const knownFrom = startUnknown ? (present.length ? Math.min(...present) : null) : Math.min(...startYears);
  const push = (from: number, to: number, kind: Segment['kind']) => {
    if (to > from) segments.push({ from, to, kind });
  };
  if (knownFrom === null) {
    // Only an end, a move or a register entry is dated: nothing shows it standing.
    const stop = endYear ?? last;
    push(first, stop, 'unknown');
    push(stop, last, endYear !== null ? 'gone' : 'unknown');
  } else {
    push(first, knownFrom, 'unknown');
    if (now) {
      push(knownFrom, last, 'stood');
    } else if (endYear !== null) {
      push(knownFrom, endYear, 'stood');
      push(endYear, last, 'gone');
    } else {
      const lastSeen = Math.max(knownFrom, ...present);
      push(knownFrom, lastSeen, 'stood');
      push(lastSeen, last, 'unknown');
    }
  }

  const marks = dated.map((e) => ({ year: e.event.year!, event: e.event.event, label: eventLabel(e.event.event), shape: eventShape(e.event.event), index: e.index }));
  return { items, first, last, segments, marks, startUnknown, endUnknown: !now && endYear === null };
}

/** Horizontal position of a year on the drawn line, 0..100 (percent). */
export function yearPosition(year: number, first: number, last: number): number {
  if (last <= first) return 0;
  return Math.min(100, Math.max(0, ((year - first) / (last - first)) * 100));
}

/**
 * Rows for year labels on the drawn line so close years do not overlap: a label goes on the
 * first row whose previous label is at least `minGap` percent to its left.
 */
export function labelRows(positions: readonly number[], minGap: number, rows = 2): number[] {
  const lastOn = new Array<number>(rows).fill(-Infinity);
  return positions.map((x) => {
    let row = lastOn.findIndex((p) => x - p >= minGap);
    if (row === -1) row = lastOn.indexOf(Math.min(...lastOn));
    lastOn[row] = x;
    return row;
  });
}
