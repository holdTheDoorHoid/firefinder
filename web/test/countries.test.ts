/**
 * Countries and regions on the site (owner decision 2026-10-20: Alaska, Hawaii and Canada join
 * the lower 48): names, local units, units of length, the place filter and its URL, and the
 * "Lookouts we can't place yet" wording outside the US.
 */
import { describe, expect, it } from 'vitest';
import { lengthFor } from '../src/lib/format.ts';
import { defaultFilters, facetCounts, matches } from '../src/lib/filters.ts';
import { countryOf, localUnitLabel, regionGroups, regionWithCountry, towerCountry } from '../src/lib/regions.ts';
import type { TowerFeature, TowerProps, UnplacedFile, UnplacedLookout } from '../src/lib/types.ts';
import { defaultState, parseState, serializeState } from '../src/lib/urlstate.ts';
import { placeLine } from '../src/render/tower.ts';
import { reasonText, unplacedIndexMain } from '../src/render/unplaced.ts';
import { unitsFor } from '../src/view3d/describe.ts';

function f(p: Partial<TowerProps> & { i: string }): TowerFeature {
  return {
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [-80, 47] },
    properties: { n: p.i, r: 'OR', k: 'tower', s: 'standing', v: 'facts', a: 'public', ...p },
  };
}

describe('regions', () => {
  it('knows each region code its country', () => {
    expect(countryOf('ON')).toBe('CA');
    expect(countryOf('OR')).toBe('US');
    expect(countryOf('AK')).toBe('US');
    expect(countryOf('CA')).toBe('US'); // California: Canada is a country, never a region code
    expect(towerCountry({ region: 'BC' })).toBe('CA');
    expect(towerCountry({ region: 'OR' })).toBe('US');
  });

  it('names a Canadian region with its country, a US state without', () => {
    expect(regionWithCountry('ON')).toBe('Ontario, Canada');
    expect(regionWithCountry('OR')).toBe('Oregon');
  });

  it('adds the US unit word but keeps a Canadian unit as given', () => {
    expect(localUnitLabel('US', 'OR', 'Jefferson')).toBe('Jefferson County');
    expect(localUnitLabel('US', 'LA', 'Caddo')).toBe('Caddo Parish');
    expect(localUnitLabel('US', 'AK', 'Bethel')).toBe('Bethel Census Area');
    expect(localUnitLabel('US', 'AK', 'Matanuska-Susitna')).toBe('Matanuska-Susitna Borough');
    expect(localUnitLabel('US', 'AK', 'Kenai Peninsula Borough')).toBe('Kenai Peninsula Borough');
    expect(localUnitLabel('CA', 'ON', 'Sudbury District')).toBe('Sudbury District');
    expect(localUnitLabel('CA', 'BC', 'Regional District of Central Kootenay')).toBe('Regional District of Central Kootenay');
    expect(placeLine({ county: 'Sudbury District', region: 'ON' })).toBe('Sudbury District, Ontario, Canada');
    expect(placeLine({ county: 'Jefferson', region: 'OR' })).toBe('Jefferson County, Oregon');
    expect(placeLine({ county: null, region: 'SK' })).toBe('Saskatchewan, Canada');
  });

  it('groups regions by country, the US first', () => {
    const g = regionGroups(['ON', 'OR', 'BC', 'AK']);
    expect(g.map((x) => x.country)).toEqual(['US', 'CA']);
    expect(g[0]!.regions.map((r) => r.code)).toEqual(['AK', 'OR']);
    expect(g[1]!.regions.map((r) => r.code)).toEqual(['BC', 'ON']);
  });
});

describe('units', () => {
  it('reads feet first in the US and metres first in Canada', () => {
    expect(lengthFor('US', 459)).toBe('1,506 ft (459 m)');
    expect(lengthFor('CA', 459)).toBe('459 m (1,506 ft)');
    expect(unitsFor('CA').distance(34_000)).toBe('34 km (21 mi)');
    expect(unitsFor('US').distance(34_000)).toBe('21 mi (34 km)');
    expect(unitsFor('CA').aboutHeight(2124)).toBe('about 2,120 m');
  });
});

describe('the place filter', () => {
  const towers = [f({ i: 'us-or-a' }), f({ i: 'ca-on-b', r: 'ON', cc: 'CA' }), f({ i: 'ca-bc-c', r: 'BC', cc: 'CA' })];

  it('keeps one country', () => {
    const fl = { ...defaultFilters(), country: 'CA' };
    expect(towers.filter((t) => matches(t.properties, fl)).map((t) => t.properties.i)).toEqual(['ca-on-b', 'ca-bc-c']);
    const us = { ...defaultFilters(), country: 'US' };
    expect(towers.filter((t) => matches(t.properties, us)).map((t) => t.properties.i)).toEqual(['us-or-a']);
  });

  it('counts every region whatever country is chosen', () => {
    const counts = facetCounts(towers, { ...defaultFilters(), country: 'CA' }, 'region');
    expect(counts.get('OR')).toBe(1);
    expect(counts.get('ON')).toBe(1);
  });

  it('round-trips through the URL', () => {
    const s = defaultState();
    s.filters.country = 'CA';
    expect(serializeState(s)).toBe('?country=CA');
    expect(parseState('?country=CA').filters.country).toBe('CA');
    // a state wins over a country; nonsense is dropped
    expect(parseState('?country=CA&state=ON').filters.country).toBeNull();
    expect(parseState('?country=XX').filters.country).toBeNull();
  });
});

describe("lookouts we can't place yet, outside the US", () => {
  const ctx = { base: '/ff/', siteUrl: 'https://x/ff/', repo: 'o/r', sources: new Map() };
  const u: UnplacedLookout = {
    anchor: 'gull-lake',
    name: 'Gull Lake Fire Tower',
    region: 'ON',
    county: null,
    records: [{ source: 'firelookout_ca', key: 'firelookout_ca:38791', name: 'Gull Lake Fire Tower', url: 'https://firelookout.ca/lookouts/?slug=gull-lake-fire-tower' }],
    gnis: 'not_covered',
    hint: { name: 'Lindsay', lat: 44.355, lon: -78.737, why: 'district_office' },
  };

  it('says why and gives the district-office hint', () => {
    const text = reasonText(u, ctx).value;
    expect(text).toContain('no gazetteer');
    expect(text).toContain('Lindsay');
    expect(text).toContain('district office');
  });

  it("names Canada's gazetteer and searches the whole province when no district is given", () => {
    const none = reasonText({ ...u, gnis: 'none', hint: { name: 'Pembrooke District - Algonquin Park', why: 'filed_under' } }, ctx).value;
    expect(none).toContain('Canadian Geographical Names Database');
    expect(none).toContain('all of Ontario');
    expect(none).toContain('Pembrooke District - Algonquin Park');
    const withUnit = reasonText({ ...u, gnis: 'none', county: 'Renfrew County', hint: null }, ctx).value;
    expect(withUnit).toContain('in the district');
    // the district-office hint still reads as before
    expect(reasonText({ ...u, gnis: 'ambiguous', candidates: [] }, ctx).value).toContain('district office');
  });

  it('lists the provinces under Canada, after the states', () => {
    const file: UnplacedFile = { count: 2, by_region: { ON: 1, OR: 1 }, lookouts: [u, { ...u, anchor: 'x', name: 'X', region: 'OR', gnis: 'none', hint: null }] };
    const html = unplacedIndexMain(file, null, ctx).value;
    expect(html.indexOf('By state')).toBeLessThan(html.indexOf('Canada: by province and territory'));
    expect(html).toContain('/ff/unplaced/on/');
  });
});
