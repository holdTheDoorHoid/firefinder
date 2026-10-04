import { describe, expect, it } from 'vitest';
import type { TowerRecord } from '../src/lib/types.ts';
import { photosSection, renderTowerMain, type RenderContext } from '../src/render/tower.ts';

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
  status: 'standing',
  verification: 'unverified',
};

describe('a photo with no mirrored file and a plain-http original', () => {
  const r: TowerRecord = {
    ...base,
    photos: [{ url: 'http://nhlr.org/photos/flag-point.jpg', source_url: 'http://nhlr.org/lookouts/us/or/flag-point/', credit: 'Jane Smith via NHLR', year: 1998 }],
  };
  const out = photosSection(r, ctx)!.value;

  it('does not emit an <img> for the http original', () => {
    expect(out).not.toContain('<img');
  });

  it('links out to the source host instead, with the external-link marker', () => {
    expect(out).toContain('href="http://nhlr.org/photos/flag-point.jpg"');
    expect(out).toContain('View photo at nhlr.org');
    expect(out).toContain('class="ext-icon"');
  });

  it('keeps the credit line and caption', () => {
    expect(out).toContain('Jane Smith via NHLR');
    expect(out).toContain('(1998)');
  });

  it('is reachable from the full tower page too', () => {
    expect(renderTowerMain(r, ctx).value).toContain('View photo at nhlr.org');
  });
});

describe('a photo with no mirrored file but an https original', () => {
  const r: TowerRecord = {
    ...base,
    photos: [{ url: 'https://commons.wikimedia.org/wiki/Special:FilePath/Flag_Point.jpg', source_url: 'https://commons.wikimedia.org/wiki/File:Flag_Point.jpg', credit: 'via Wikimedia Commons' }],
  };
  const out = photosSection(r, ctx)!.value;

  it('still shows a normal <img>, not a link card', () => {
    expect(out).toContain('<img');
    expect(out).not.toContain('View photo at');
  });
});

describe('a photo with a mirrored file', () => {
  const r: TowerRecord = {
    ...base,
    photos: [{ file: 'ab/deadbeef.webp', thumb: 'ab/deadbeef.t.webp', url: 'http://firetower.org/photos/flag-point.jpg', credit: 'via FFLOS' }],
  };
  const out = photosSection(r, ctx)!.value;

  it('uses the mirrored copy, even though the original is plain http', () => {
    expect(out).toContain('<img');
    expect(out).toContain('src="/firefinder/data/ab/deadbeef.t.webp"');
    expect(out).not.toContain('View photo at');
  });
});

describe('a photo with neither a mirrored file nor a usable url', () => {
  const r: TowerRecord = {
    ...base,
    photos: [{ url: 'javascript:alert(1)', source_url: 'http://nhlr.org/lookouts/us/or/flag-point/', credit: 'unknown' }],
  };
  const out = photosSection(r, ctx)!.value;

  it('falls back to the source page link rather than showing nothing', () => {
    expect(out).toContain('href="http://nhlr.org/lookouts/us/or/flag-point/"');
    expect(out).not.toContain('javascript:');
  });
});
