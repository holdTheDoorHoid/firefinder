import { describe, expect, it } from 'vitest';
import { GAP_YEARS, labelRows, timelineModel, yearCounts, yearPosition, yearSeries, yearState } from '../src/lib/history.ts';
import type { TowerEvent, TowerProps } from '../src/lib/types.ts';

const NOW = 2026;

function p(s: string, y0?: number, y1?: number): TowerProps {
  const props: TowerProps = { i: 'us-or-x', n: 'X', r: 'OR', k: 'tower', s, v: 'facts', a: 'public' };
  if (y0 !== undefined) props.y0 = y0;
  if (y1 !== undefined) props.y1 = y1;
  return props;
}

describe('yearState: built on or before the year and not yet gone', () => {
  it('places towers with full dates', () => {
    expect(yearState(p('standing', 1933), 1935, NOW)).toBe('stood');
    expect(yearState(p('standing', 1933), 1933, NOW)).toBe('stood');
    expect(yearState(p('standing', 1933), 1932, NOW)).toBe('no');
    expect(yearState(p('gone', 1934, 1975), 1960, NOW)).toBe('stood');
    expect(yearState(p('gone', 1934, 1975), 1974, NOW)).toBe('stood');
    expect(yearState(p('gone', 1934, 1975), 1975, NOW)).toBe('no');
    expect(yearState(p('gone', 1934, 1975), 1990, NOW)).toBe('no');
  });

  it('never guesses: incomplete dates are "maybe", with the reason', () => {
    // Built, but when it came down is not recorded.
    expect(yearState(p('gone', 1934), 1960, NOW)).toBe('built');
    expect(yearState(p('gone', 1934), 1930, NOW)).toBe('no');
    // Stands today, build year unknown: maybe in 1935.
    expect(yearState(p('standing'), 1935, NOW)).toBe('nostart');
    // Came down in 1966, build year unknown: maybe before, certainly not after.
    expect(yearState(p('gone', undefined, 1966), 1950, NOW)).toBe('nostart');
    expect(yearState(p('gone', undefined, 1966), 1970, NOW)).toBe('no');
    // No dates at all.
    expect(yearState(p('gone'), 1950, NOW)).toBe('nodates');
    expect(yearState(p('unknown'), 1950, NOW)).toBe('nodates');
  });

  it('uses today\'s status for today', () => {
    expect(yearState(p('standing'), NOW, NOW)).toBe('stood');
    expect(yearState(p('replica'), NOW, NOW)).toBe('stood');
    expect(yearState(p('gone'), NOW, NOW)).toBe('no');
    expect(yearState(p('gone', 1934), NOW, NOW)).toBe('no');
    expect(yearState(p('ruins'), NOW, NOW)).toBe('no');
    expect(yearState(p('relocated', 1931), NOW, NOW)).toBe('no');
    expect(yearState(p('unknown'), NOW, NOW)).toBe('nodates');
    expect(yearState(p('unknown', 1950), NOW, NOW)).toBe('built');
    expect(yearState(p('unknown', 1950, 1990), NOW, NOW)).toBe('no');
  });
});

describe('yearSeries', () => {
  const statuses = ['standing', 'gone', 'ruins', 'unknown', 'relocated', 'replica'];
  // A deterministic mix of every combination of start, end and status.
  const feats: { properties: TowerProps }[] = [];
  let seed = 7;
  const rnd = (n: number) => ((seed = (seed * 1103515245 + 12345) % 2147483648), seed % n);
  for (let i = 0; i < 600; i++) {
    const s = statuses[rnd(statuses.length)]!;
    const y0 = rnd(3) ? 1880 + rnd(140) : undefined;
    const y1 = s !== 'standing' && s !== 'replica' && rnd(3) === 0 ? (y0 ?? 1880) + rnd(80) : undefined;
    feats.push({ properties: p(s, y0, y1 !== undefined && y1 > NOW ? undefined : y1) });
  }

  it('agrees with counting year by year', () => {
    const series = yearSeries(feats, 1900, NOW, NOW);
    expect(series).toHaveLength(NOW - 1900 + 1);
    for (const year of [1900, 1901, 1933, 1950, 1975, 1999, 2025, NOW]) {
      expect(series[year - 1900]).toEqual(yearCounts(feats, year, NOW));
    }
  });

  it('counts the example towers', () => {
    const towers = [p('standing', 1933), p('gone', 1934, 1975), p('gone', 1934), p('standing'), p('gone'), p('unknown')].map((properties) => ({ properties }));
    expect(yearCounts(towers, 1935, NOW)).toEqual({ year: 1935, stood: 2, built: 1, nostart: 1, nodates: 2, upper: 6 });
    expect(yearCounts(towers, 1980, NOW)).toEqual({ year: 1980, stood: 1, built: 1, nostart: 1, nodates: 2, upper: 5 });
    expect(yearCounts(towers, NOW, NOW)).toEqual({ year: NOW, stood: 2, built: 0, nostart: 0, nodates: 1, upper: 3 });
  });
});

describe('timelineModel', () => {
  const e = (year: number | null, event: string, extra: Partial<TowerEvent> = {}): TowerEvent => ({ year, event, ...extra });

  it('returns null when nothing is dated', () => {
    expect(timelineModel([], 'gone', NOW)).toBeNull();
    expect(timelineModel([e(null, 'built')], 'gone', NOW)).toBeNull();
  });

  it('points out long gaps and ends with today', () => {
    const m = timelineModel([e(1934, 'built'), e(1987, 'nhlr_registered'), e(1990, 'restored')], 'standing', NOW)!;
    expect(m.items.map((i) => i.type)).toEqual(['event', 'gap', 'event', 'event', 'today']);
    expect(m.items[1]).toEqual({ type: 'gap', from: 1934, to: 1987 });
    expect(m.items.at(-1)).toEqual({ type: 'today', year: NOW, status: 'standing' });
    expect(m.segments).toEqual([{ from: 1934, to: NOW, kind: 'stood' }]);
    expect(m.startUnknown).toBe(false);
    expect(m.endUnknown).toBe(false);
  });

  it(`does not call gaps shorter than ${GAP_YEARS} years`, () => {
    const m = timelineModel([e(1934, 'built'), e(1948, 'staffed_last')], 'gone', NOW)!;
    expect(m.items.filter((i) => i.type === 'gap')).toHaveLength(0);
  });

  it('draws an unknown stretch after the last record of a lookout that has gone', () => {
    const m = timelineModel([e(1934, 'built'), e(1960, 'staffed_last')], 'gone', NOW)!;
    expect(m.segments).toEqual([
      { from: 1934, to: 1960, kind: 'stood' },
      { from: 1960, to: NOW, kind: 'unknown' },
    ]);
    expect(m.endUnknown).toBe(true);
  });

  it('draws a gone stretch after a recorded end, and ignores an end before a rebuild', () => {
    const m = timelineModel([e(1922, 'built'), e(1940, 'burned'), e(1942, 'rebuilt'), e(1981, 'removed')], 'gone', NOW)!;
    expect(m.segments).toEqual([
      { from: 1922, to: 1981, kind: 'stood' },
      { from: 1981, to: NOW, kind: 'gone' },
    ]);
  });

  it('starts dashed when the build year is not recorded', () => {
    const m = timelineModel([e(1995, 'nhlr_registered')], 'standing', NOW)!;
    expect(m.startUnknown).toBe(true);
    expect(m.first).toBeLessThan(1995);
    expect(m.segments[0]).toEqual({ from: m.first, to: 1995, kind: 'unknown' });
    expect(m.segments[1]).toEqual({ from: 1995, to: NOW, kind: 'stood' });
  });

  it('keeps undated events, after the dated ones', () => {
    const m = timelineModel([e(null, 'restored'), e(1933, 'built')], 'standing', NOW)!;
    const events = m.items.filter((i) => i.type === 'event');
    expect(events.map((i) => (i.type === 'event' ? i.year : 'x'))).toEqual([1933, null]);
    expect(m.marks).toHaveLength(1);
  });
});

describe('drawing helpers', () => {
  it('positions years on the line', () => {
    expect(yearPosition(1900, 1900, 2000)).toBe(0);
    expect(yearPosition(1950, 1900, 2000)).toBe(50);
    expect(yearPosition(2100, 1900, 2000)).toBe(100);
  });
  it('puts close labels on another row', () => {
    expect(labelRows([0, 5, 30, 33, 34], 10)).toEqual([0, 1, 0, 1, 0]);
  });
});
