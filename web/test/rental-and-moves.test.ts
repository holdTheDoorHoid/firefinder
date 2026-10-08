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

describe('a rental the FFLA list notes as closed for 2026', () => {
  const r: TowerRecord = {
    ...base,
    id: 'us-id-arid-peak',
    name: 'Arid Peak Lookout',
    region: 'ID',
    status: 'standing',
    rental: {
      available: true, provider: 'recreation.gov', url: 'https://www.recreation.gov/camping/campgrounds/234447',
      checked: '2026-10-05', status_note: 'Maintenance Closure 2026', status_note_from: 'ffla',
    },
  };
  const main = renderTowerMain(r, ctx).value;
  const panel = renderPanel(r, ctx).value;

  it('is still a rental, with a plain notice (not the gone-lookout warning) before the booking link', () => {
    expect(isRentable(r)).toBe(true);
    const note = main.indexOf('Noted: Maintenance Closure 2026');
    expect(note).toBeGreaterThan(-1);
    expect(main.indexOf('href="https://www.recreation.gov/camping/campgrounds/234447"')).toBeGreaterThan(note);
    expect(main).toContain('Forest Fire Lookout Association’s rentals list');
    expect(main).toContain('Book on recreation.gov');
    expect(main).not.toContain('Check before booking');
  });

  it('says so in the side panel too', () => {
    expect(panel).toContain('Noted: Maintenance Closure 2026');
    expect(panel).toContain('Book on recreation.gov');
  });

  it('shows no note when there is none', () => {
    const plain = renderTowerMain({ ...r, rental: { ...r.rental!, status_note: null } }, ctx).value;
    expect(plain).not.toContain('Noted:');
  });
});

describe('a rental that only the FFLA list knows (booked outside recreation.gov)', () => {
  const r: TowerRecord = {
    ...base,
    id: 'us-wa-north-mountain',
    name: 'North Mountain Lookout',
    region: 'WA',
    status: 'standing',
    rental: {
      available: true, source: 'ffla', provider: 'Airbnb', url: 'https://www.airbnb.com/rooms/50778329',
      manager: 'Friends of North Mountain', checked: '2026-10-08',
    },
  };
  const main = renderTowerMain(r, ctx).value;

  it('names the booking site and the manager, and credits the FFLA list rather than recreation.gov', () => {
    expect(main).toContain('through Airbnb');
    expect(main).toContain('Book on Airbnb');
    expect(main).toContain('href="https://www.airbnb.com/rooms/50778329"');
    expect(main).toContain('Managed by');
    expect(main).toContain('Friends of North Mountain');
    expect(main).toContain('href="https://firelookout.org/resources/rentals/"');
    expect(main).not.toContain('Data source: ridb.recreation.gov');
    expect(main).not.toContain('Rental details from recreation.gov');
  });

  it('does not repeat the provider as the manager', () => {
    const same = renderTowerMain({ ...r, rental: { ...r.rental!, provider: 'Montana DNRC', manager: 'Montana DNRC' } }, ctx).value;
    expect(same).not.toContain('Managed by');
  });

  it('escapes the note and manager', () => {
    const evil = renderTowerMain({ ...r, rental: { ...r.rental!, manager: '<img src=x>', status_note: '<script>x</script>' } }, ctx).value;
    expect(evil).not.toContain('<img src=x>');
    expect(evil).not.toContain('<script>x</script>');
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

describe('a status note from a source name', () => {
  const r: TowerRecord = { ...base, id: 'us-pa-muzette', name: 'Muzette Lookout Tower', region: 'PA', status: 'unknown', status_note: 'Sources suggest it is gone.' };
  it('is shown on the tower page and in the side panel', () => {
    expect(renderTowerMain(r, ctx).value).toContain('Sources suggest it is gone.');
    expect(renderPanel(r, ctx).value).toContain('Sources suggest it is gone.');
  });
  it('is shown on a standing lookout too', () => {
    const s = renderTowerMain({ ...r, status: 'standing', status_note: 'FFLA marks this entry “unknown”: details are uncertain.' }, ctx).value;
    expect(s).toContain('details are uncertain');
  });
});

describe('a researched lookout', () => {
  const r: TowerRecord = {
    ...base,
    id: 'us-or-hager-mountain',
    name: 'Hager Mountain Lookout',
    status: 'standing',
    summary: 'An R-6 flat-top cab built in 1967, staffed in fire season and rentable in winter.',
    research: { researched: '2026-10-04', checked: '2026-10-05', verdict: 'pass', confidence: 'medium' },
    story_html: '<p>Watched for smoke since 1915.<sup id="fnref-1" class="fnref"><a href="#fn-1" aria-label="Note 1">1</a></sup></p>\n<section class="footnotes" aria-label="Notes and sources"><ol><li id="fn-1">NHLR, <a href="http://nhlr.org/lookouts/us/or/hager-mountain-lookout/" rel="noopener noreferrer">http://nhlr.org/lookouts/us/or/hager-mountain-lookout/</a> <a href="#fnref-1" class="fn-back" aria-label="Back to the text">↩</a></li></ol></section>',
    events: [{ year: 1967, event: 'built', note: 'Current R-6 cab', from: 'research', source_url: 'http://nhlr.org/lookouts/us/or/hager-mountain-lookout/' }],
  };
  const main = renderTowerMain(r, ctx).value;

  it('shows the summary in the header and the map panel', () => {
    expect(main).toContain('class="t-summary"');
    expect(renderPanel(r, ctx).value).toContain(r.summary!);
  });

  it('stamps the story with its research and fact-check', () => {
    expect(main).toContain('Researched 4 Oct 2026, fact-checked.');
    expect(renderTowerMain({ ...r, research: { researched: '2026-10-04', verdict: null } }, ctx).value).toContain('Not yet fact-checked.');
  });

  it('renders the story with footnotes and safe external links', () => {
    expect(main).toContain('<section class="footnotes"');
    expect(main).toContain('rel="noopener noreferrer">http://nhlr.org/');
    expect(main).not.toContain('could not be shown');
  });

  it('links a research event to the page it cites', () => {
    expect(main).toContain('Source: <a href="http://nhlr.org/lookouts/us/or/hager-mountain-lookout/" rel="noopener noreferrer">nhlr.org</a>');
  });
});
