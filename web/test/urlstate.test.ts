import { describe, expect, it } from 'vitest';
import { defaultState, formatView, parseState, serializeState, type AppState } from '../src/lib/urlstate.ts';

function roundTrip(s: AppState): AppState {
  return parseState(serializeState(s));
}

describe('URL state', () => {
  it('the default state is an empty query', () => {
    expect(serializeState(defaultState())).toBe('');
    expect(parseState('')).toEqual(defaultState());
  });

  it('round-trips every filter, the view, the selection and the base map', () => {
    const s = defaultState();
    s.filters.status = new Set(['standing', 'relocated']);
    s.filters.kind = new Set(['ground', 'tower']);
    s.filters.verification = new Set(['researched', 'verified']);
    s.filters.rentable = true;
    s.filters.registered = true;
    s.filters.region = 'OR';
    s.filters.mine = new Set(['visited', 'want']);
    s.view = { zoom: 7.25, lat: 44.1234, lon: -121.6543 };
    s.selected = 'us-or-warner-mountain';
    s.basemap = 'topo';
    s.filters.design = 'l4';
    expect(roundTrip(s)).toEqual(s);
  });

  it('round-trips the history views', () => {
    const s = defaultState();
    s.basemap = 'old';
    s.era = 'oldest';
    s.oldOpacity = 0.6;
    s.year = 1935;
    s.yearMaybe = true;
    expect(serializeState(s)).toBe('?base=old&era=oldest&op=60&yr=1935&yrm=1');
    expect(roundTrip(s)).toEqual(s);
  });

  it('leaves history defaults out and drops nonsense', () => {
    const s = defaultState();
    s.basemap = 'old';
    expect(serializeState(s)).toBe('?base=old');
    const bad = parseState('?base=old&era=jurassic&op=500&yr=12000&yrm=1&design=L-4%3Cscript');
    expect(bad.era).toBe('lookouts');
    expect(bad.oldOpacity).toBe(0.85);
    expect(bad.year).toBeNull();
    expect(bad.yearMaybe).toBe(false);
    expect(bad.filters.design).toBeNull();
    // "Show dimmed" only means something in the year view.
    expect(parseState('?yrm=1').yearMaybe).toBe(false);
  });

  it('writes a readable, stable query', () => {
    const s = defaultState();
    s.filters.status = new Set(['gone', 'standing']);
    s.filters.rentable = true;
    s.view = { zoom: 6, lat: 44.5, lon: -120.25 };
    expect(serializeState(s)).toBe('?at=6/44.5/-120.25&status=standing,gone&rent=1');
  });

  it('rounds the view to sensible precision', () => {
    expect(formatView({ zoom: 7.123456, lat: 44.123456789, lon: -121.987654321 })).toBe('7.12/44.1235/-121.9877');
  });

  it('keeps a deliberately empty selection as "none"', () => {
    const s = defaultState();
    s.filters.status = new Set();
    expect(serializeState(s)).toBe('?status=none');
    expect(roundTrip(s).filters.status).toEqual(new Set());
  });

  it('treats "every value" as no filter', () => {
    const s = parseState('?status=standing,gone,ruins,relocated,replica,unknown');
    expect(s.filters.status).toBeNull();
  });

  it('drops unknown or malformed values instead of failing', () => {
    const s = parseState('?status=standing,bogus&kind=castle&state=Oregon&at=99/1/2&t=../../etc&mine=nope&base=satellite&rent=yes');
    expect(s.filters.status).toEqual(new Set(['standing']));
    expect(s.filters.kind).toBeNull();
    expect(s.filters.region).toBeNull();
    expect(s.view).toBeNull();
    expect(s.selected).toBeNull();
    expect(s.filters.mine).toBeNull();
    expect(s.basemap).toBe('map');
    expect(s.filters.rentable).toBe(false);
  });

  it('accepts a lower-case state code', () => {
    expect(parseState('?state=wa').filters.region).toBe('WA');
  });
});
