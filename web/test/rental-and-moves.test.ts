import { describe, expect, it } from 'vitest';
import { isRentable, type TowerRecord } from '../src/lib/types.ts';
import { renderPanel, renderTowerMain, type RenderContext } from '../src/render/tower.ts';

const ctx: RenderContext = {
  base: '/firefinder/',
  siteUrl: 'https://example.org/firefinder/',
  repo: 'holdTheDoorHoid/firefinder',
  sources: new Map(),
};

const base: TowerRecord = {
  id: 'us-or-flag-point',
  name: 'Flag Point Lookout',
  region: 'OR',
  location: { lat: 45.3, lon: -121.4, precision: 'exact', from: 'ffla' },
  kind: 'tower',
  status: 'gone',
  verification: 'unverified',
  access: { level: 'unknown', note: null },
};

describe('a listing on a lookout another source records as burned', () => {
  const warning = 'FFLA reports this lookout burned in 2026, but recreation.gov still lists it. Check with the forest before booking.';
  const r: TowerRecord = {
    ...base,
    rental: { available: false, provider: 'recreation.gov', url: 'https://www.recreation.gov/camping/campgrounds/10289153', warning },
  };
  const main = renderTowerMain(r, ctx).value;
  const panel = renderPanel(r, ctx).value;

  it('is not counted as rentable', () => {
    expect(isRentable(r)).toBe(false);
  });

  it.each([['tower page', main], ['side panel', panel]])('%s shows the warning above the recreation.gov link', (_, out) => {
    const w = out.indexOf('Check with the forest before booking');
    const link = out.indexOf('href="https://www.recreation.gov/camping/campgrounds/10289153"');
    expect(w).toBeGreaterThan(-1);
    expect(link).toBeGreaterThan(w);
    expect(out).toContain('See the listing on recreation.gov');
    expect(out).not.toContain('Book on recreation.gov');
  });

  it('does not say "not rentable" or "nothing to rent" without the explanation', () => {
    expect(main).not.toContain('Not rentable right now');
    expect(main).not.toContain('Gone: site only.');
    expect(panel).not.toContain('Nothing to climb or rent');
  });

  it('keeps the plain "not currently listed" wording when there is no warning', () => {
    const plain = renderTowerMain({ ...base, status: 'standing', rental: { available: false } }, ctx).value;
    expect(plain).toContain('Not rentable right now');
  });
});

describe('a moved lookout and its original site link to each other', () => {
  const moved: TowerRecord = {
    ...base,
    id: 'us-ny-padlock-hill-at-state-fair',
    name: 'Padlock Hill Lookout (now at the State Fair)',
    region: 'NY',
    status: 'standing',
    links: [
      { label: 'Original site: Padlock Hill', url: '../us-ny-padlock-hill/', kind: 'relocated_from', id: 'us-ny-padlock-hill' },
      { label: 'FFLA New York lookout list', url: 'https://firelookout.org/lookouts/us/ny/', kind: 'association' },
    ],
  };
  const origin: TowerRecord = {
    ...base,
    id: 'us-ny-padlock-hill',
    name: 'Padlock Hill',
    region: 'NY',
    status: 'relocated',
    links: [{ label: 'Now at the State Fair', url: '../us-ny-padlock-hill-at-state-fair/', kind: 'relocated_to', id: 'us-ny-padlock-hill-at-state-fair' }],
  };

  it('links to the other tower page inside the site', () => {
    expect(renderTowerMain(moved, ctx).value).toContain('href="/firefinder/t/us-ny-padlock-hill/"');
    const o = renderTowerMain(origin, ctx).value;
    expect(o).toContain('href="/firefinder/t/us-ny-padlock-hill-at-state-fair/"');
    expect(o).toContain('The lookout that stood here was moved.');
    expect(renderPanel(origin, ctx).value).toContain('href="/firefinder/t/us-ny-padlock-hill-at-state-fair/"');
  });

  it('does not list the internal link as an external page', () => {
    const out = renderTowerMain(moved, ctx).value;
    expect(out).not.toContain('href="../us-ny-padlock-hill/"');
    expect(out).toContain('href="https://firelookout.org/lookouts/us/ny/"');
  });

  it('ignores a malformed id', () => {
    const bad = { ...moved, links: [{ label: 'x', url: '../evil/', kind: 'relocated_from', id: '../../evil' }] };
    expect(renderTowerMain(bad, ctx).value).not.toContain('evil');
  });
});
