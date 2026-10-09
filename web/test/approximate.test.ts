/**
 * Approximate locations (no source gives a position; the lookout is shown on the one same-name
 * USGS GNIS high point in its county) and the "Lookouts we can't place yet" pages. DESIGN.md 3.5.
 */
import { describe, expect, it } from 'vitest';
import { activeFilterCount, applyFilters, defaultFilters } from '../src/lib/filters.ts';
import { iconName, markerSvg } from '../src/lib/icons.ts';
import type { TowerProps, TowerRecord, UnplacedFile, UnplacedLookout } from '../src/lib/types.ts';
import { defaultState, parseState, serializeState } from '../src/lib/urlstate.ts';
import { badges, factRows, renderPanel, renderPanelStub, renderTowerMain, type RenderContext } from '../src/render/tower.ts';
import { reasonText, suggestLocationUrl, unplacedHead, unplacedIndexMain, unplacedPageStates, unplacedStateMain, unplacedStates } from '../src/render/unplaced.ts';

const ctx: RenderContext = {
  base: '/firefinder/',
  siteUrl: 'https://example.org/firefinder/',
  repo: 'holdTheDoorHoid/firefinder',
  sources: new Map([['eastern_us_lookouts', { id: 'eastern_us_lookouts', title: 'FOREST LOOKOUTS -- eastern US' }]]),
};

const approx: TowerRecord = {
  id: 'us-al-black-jack-ridge',
  name: 'Black Jack Ridge',
  region: 'AL',
  county: 'Clay',
  location: {
    lat: 33.3, lon: -85.8, precision: 'approximate', from: 'gnis', approximate: true, method: 'gnis_name_match',
    gnis: { id: 100, name: 'Black Jack Ridge', class: 'Ridge', county: 'Clay' },
  },
  kind: 'tower',
  status: 'unknown',
  verification: 'unverified',
  access: { level: 'unknown', note: null },
  sources: [{ source: 'eastern_us_lookouts', key: 'eastern_us_lookouts:al:black-jack-ridge', fields: ['name', 'county'] }],
};

describe('an approximate location on the tower page', () => {
  const main = renderTowerMain(approx, ctx).value;

  it('says where the pin is, why, and how to give the real spot', () => {
    expect(main).toContain('Approximate location');
    expect(main).toContain('the one ridge of that name in Clay County, Alabama');
    expect(main).toContain('A ridge can run for miles');
    expect(main).toContain('title=Location%3A+Black+Jack+Ridge');
    expect(main).toContain('topic=Location+on+the+map');
  });

  it('always carries the Unverified badge, even after research', () => {
    expect(badges(approx).value).toContain('Unverified');
    expect(badges({ ...approx, verification: 'researched' }).value).toContain('Unverified');
    expect(badges(approx).value).toContain('Approximate location');
  });

  it('credits GNIS for the position and says so in the facts', () => {
    expect(main).toContain('id="src-gnis"');
    const coords = factRows(approx).find(([k]) => k === 'Coordinates')![1] as { value: string };
    expect(coords.value).toContain('Approximate: placed on Black Jack Ridge (a ridge), from USGS GNIS');
  });

  it('cautions that the views are from the approximate location', () => {
    expect(main).toContain('From an approximate location');
    const panel = renderPanel(approx, ctx).value;
    expect(panel).toContain('Approximate location.');
    expect(panel).toContain('Both views are worked out from the approximate location');
  });

  it('draws a dashed marker in the mini-map', () => {
    expect(main).toContain('mk-approx-edge');
  });

  it('a lookout a source places says none of it', () => {
    const real = renderTowerMain({ ...approx, location: { lat: 33.3, lon: -85.8, precision: 'exact', from: 'ffla' } }, ctx).value;
    expect(real).not.toContain('Approximate location');
    expect(real).not.toContain('mk-approx-edge');
  });
});

describe('approximate markers and the filter', () => {
  it('has its own dashed icon', () => {
    expect(iconName('tri', 'solid', false, true)).toBe('ff-tri-solid-ap');
    expect(iconName('tri', 'solid', true)).toBe('ff-tri-solid-rent');
    const svg = markerSvg('house', 'hollow', { approximate: true });
    expect(svg).toContain('stroke-dasharray');
    expect(svg).not.toContain('class="mk-edge"');
  });

  const props = (i: string, ap?: 1): { properties: TowerProps } => ({ properties: { i, n: i, r: 'AL', k: 'tower', s: 'standing', v: 'unverified', a: 'unknown', ...(ap ? { ap } : {}) } });
  const feats = [props('us-al-a'), props('us-al-b', 1)];

  it('shows approximate locations by default and can hide them', () => {
    expect(applyFilters(feats, defaultFilters())).toHaveLength(2);
    const off = { ...defaultFilters(), approximate: false };
    expect(applyFilters(feats, off).map((f) => f.properties.i)).toEqual(['us-al-a']);
    expect(activeFilterCount(off)).toBe(1);
  });

  it('keeps the switch in the URL only when it is off', () => {
    expect(serializeState(defaultState())).toBe('');
    const s = defaultState();
    s.filters.approximate = false;
    expect(serializeState(s)).toBe('?ap=0');
    expect(parseState('?ap=0').filters.approximate).toBe(false);
    expect(parseState('?ap=1').filters.approximate).toBe(true);
  });

  it('the panel stub shows the badge from the map feature', () => {
    const stub = renderPanelStub({ ...props('us-al-b', 1).properties }, ctx, 'Loading').value;
    expect(stub).toContain('Approximate location');
  });
});

const row = (over: Partial<UnplacedLookout>): UnplacedLookout => ({
  anchor: 'cornwall-lancaster',
  name: 'Cornwall',
  region: 'PA',
  county: 'Lancaster',
  records: [{ source: 'eastern_us_lookouts', key: 'eastern_us_lookouts:pa:cornwall', name: 'Cornwall', url: 'https://easternuslookouts.weebly.com/cornwall.html' }],
  gnis: 'town',
  town: { id: 1, name: 'Cornwall', class: 'Populated Place', lat: 40.27, lon: -76.4 },
  ...over,
});

const file: UnplacedFile = {
  count: 2,
  by_region: { PA: 2 },
  lookouts: [
    row({}),
    row({ anchor: 'mount-x', name: 'Mount <X> & Co', county: null, gnis: 'no_county', town: null }),
    row({ anchor: 'state-fair', name: 'State Fair', gnis: 'none', town: null, out_of_scope: 'Never built (FFLA lists it as "Proposed")' }),
    row({ anchor: 'other', region: 'NJ', name: 'Other', gnis: 'none', town: null }),
  ],
};

describe("lookouts we can't place yet", () => {
  it('gives the town as a hint, with a map link', () => {
    const t = reasonText(row({}), ctx).value;
    expect(t).toContain('there is a town: <strong>Cornwall</strong>');
    expect(t).toContain('href="/firefinder/?at=12/40.2700/-76.4000"');
  });

  it('names the lookout on the map it may be', () => {
    const t = reasonText(row({ gnis: 'near_mapped_lookout', near: 'us-pa-x', near_name: 'X Fire Tower', near_m: 230, feature: { id: 2, name: 'Bald Knob', class: 'Summit' } }), ctx).value;
    expect(t).toContain('230 m from Bald Knob');
    expect(t).toContain('href="/firefinder/t/us-pa-x/"');
    const amb = reasonText(row({ gnis: 'ambiguous', candidates: [{ id: 3, name: 'Bald Knob', class: 'Summit' }, { id: 4, name: 'Bald Knob', class: 'Ridge' }] }), ctx).value;
    expect(amb).toContain('2 places of this name');
  });

  it('opens the Suggest-an-edit form filled in', () => {
    const url = new URL(suggestLocationUrl(row({}), ctx));
    expect(url.pathname).toBe('/holdTheDoorHoid/firefinder/issues/new');
    expect(url.searchParams.get('template')).toBe('edit.yml');
    expect(url.searchParams.get('title')).toBe('Location: Cornwall (Lancaster County, Pennsylvania)');
    expect(url.searchParams.get('tower_name')).toBe('Cornwall');
    expect(url.searchParams.get('page_url')).toBe('https://example.org/firefinder/unplaced/pa/#cornwall-lancaster');
    expect(url.searchParams.get('whats_wrong')).toContain('listed by FOREST LOOKOUTS -- eastern US');
  });

  it('a state page lists its lookouts, escaped, and the out-of-scope ones apart', () => {
    const page = unplacedStateMain(file, 'PA', { counts: { total: 0, approximate_by_region: { PA: 37 } } }, ctx).value;
    expect(page).toContain('2 lookouts in Pennsylvania are named by our sources');
    expect(page).toContain('Mount &lt;X&gt; &amp; Co');
    expect(page).toContain('Pennsylvania, county not recorded');
    expect(page).toContain('37 more in Pennsylvania are on <a href="/firefinder/?state=PA">the map</a>');
    expect(page).toMatch(/<details class="up-out">.*State Fair/s);
    expect(page).not.toContain('>Other<');
    expect(page.match(/class="up-item"/g)).toHaveLength(2);
  });

  it('the index links every state with a count, and each state gets a page', () => {
    expect(unplacedStates(file)).toEqual([['NJ', 1], ['PA', 2]]);
    expect(unplacedPageStates(file)).toEqual(['NJ', 'PA']);
    const index = unplacedIndexMain(file, null, ctx).value;
    expect(index).toContain('href="/firefinder/unplaced/pa/"');
    expect(unplacedHead(file, 'PA').title).toBe("Lookouts we can't place yet in Pennsylvania · Firefinder");
  });
});
