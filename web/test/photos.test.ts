import { describe, expect, it } from 'vitest';
import type { TowerRecord } from '../src/lib/types.ts';
import { photosSection, renderTowerMain, type RenderContext } from '../src/render/tower.ts';

/** photosBase unset: DESIGN.md Step 1 -- "photos are not hosted yet; use the interim link cards". */
const ctxNoHost: RenderContext = {
  base: '/firefinder/',
  siteUrl: 'https://example.org/firefinder/',
  repo: 'holdTheDoorHoid/firefinder',
  sources: new Map(),
};

/** photosBase set, site-relative (the other documented form is an absolute https URL). */
const ctxHosted: RenderContext = { ...ctxNoHost, photosBase: '/firefinder/photos/' };

const base: TowerRecord = {
  id: 'us-or-flag-point',
  name: 'Flag Point Lookout',
  region: 'OR',
  location: { lat: 45.3, lon: -121.4, precision: 'exact', from: 'ffla' },
  kind: 'tower',
  status: 'standing',
  verification: 'unverified',
};

describe('a photo with no mirrored file and a plain-http original (photosBase unset)', () => {
  const r: TowerRecord = {
    ...base,
    photos: [{ url: 'http://nhlr.org/photos/flag-point.jpg', source_url: 'http://nhlr.org/lookouts/us/or/flag-point/', credit: 'Jane Smith via NHLR', year: 1998 }],
  };
  const out = photosSection(r, ctxNoHost)!.value;

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
    expect(renderTowerMain(r, ctxNoHost).value).toContain('View photo at nhlr.org');
  });

  it('behaves the same whether photosBase is absent or explicitly null', () => {
    const out2 = photosSection(r, { ...ctxNoHost, photosBase: null })!.value;
    expect(out2).toBe(out);
  });
});

describe('a photo with no mirrored file but an https original', () => {
  const r: TowerRecord = {
    ...base,
    photos: [{ url: 'https://commons.wikimedia.org/wiki/Special:FilePath/Flag_Point.jpg', source_url: 'https://commons.wikimedia.org/wiki/File:Flag_Point.jpg', credit: 'via Wikimedia Commons' }],
  };

  it('still shows a normal <img>, not a link card, with photosBase unset', () => {
    const out = photosSection(r, ctxNoHost)!.value;
    expect(out).toContain('<img');
    expect(out).toContain('src="https://commons.wikimedia.org/wiki/Special:FilePath/Flag_Point.jpg"');
    expect(out).not.toContain('View photo at');
  });

  it('still hotlinks the https original even when photosBase is set, since there is no mirrored file', () => {
    const out = photosSection(r, ctxHosted)!.value;
    expect(out).toContain('src="https://commons.wikimedia.org/wiki/Special:FilePath/Flag_Point.jpg"');
  });
});

describe('a mirrored photo (file/thumb set by pipeline/merge.py from the manifest)', () => {
  const r: TowerRecord = {
    ...base,
    photos: [{ file: 'ab/deadbeef.webp', thumb: 'ab/deadbeef.t.webp', url: 'http://firetower.org/photos/flag-point.jpg', credit: 'via FFLOS', w: 1024, h: 768 }],
  };

  it('with photosBase set, resolves file/thumb against it and uses the thumb as the shown image', () => {
    const out = photosSection(r, ctxHosted)!.value;
    expect(out).toContain('<img');
    expect(out).toContain('src="/firefinder/photos/ab/deadbeef.t.webp"');
    expect(out).toContain('href="/firefinder/photos/ab/deadbeef.webp"');
    expect(out).not.toContain('View photo at');
  });

  it('carries width/height through to avoid layout shift', () => {
    const out = photosSection(r, ctxHosted)!.value;
    expect(out).toContain('width="1024"');
    expect(out).toContain('height="768"');
  });

  it('resolves against an absolute https photosBase too', () => {
    const out = photosSection(r, { ...ctxNoHost, photosBase: 'https://example.github.io/firefinder-photos/' })!.value;
    expect(out).toContain('src="https://example.github.io/firefinder-photos/ab/deadbeef.t.webp"');
  });

  it('lazy-loads the image', () => {
    expect(photosSection(r, ctxHosted)!.value).toContain('loading="lazy"');
  });

  it('with photosBase unset, falls back to the interim link card even though it has been mirrored', () => {
    const out = photosSection(r, ctxNoHost)!.value;
    expect(out).not.toContain('<img');
    expect(out).toContain('View photo at firetower.org');
  });

  it('keeps the credit line and a link to the source page in both cases', () => {
    const r2: TowerRecord = { ...r, photos: [{ ...r.photos![0]!, source_url: 'http://firetower.org/lookouts/us/or/flag-point/' }] };
    for (const ctx of [ctxHosted, ctxNoHost]) {
      const out = photosSection(r2, ctx)!.value;
      expect(out).toContain('via FFLOS');
      expect(out).toContain('href="http://firetower.org/lookouts/us/or/flag-point/"');
    }
  });
});

describe('a mirrored photo with no thumb recorded', () => {
  const r: TowerRecord = { ...base, photos: [{ file: 'ab/deadbeef.webp', thumb: null, url: 'http://firetower.org/x.jpg', credit: 'via FFLOS' }] };
  it('falls back to the full image as the shown src', () => {
    const out = photosSection(r, ctxHosted)!.value;
    expect(out).toContain('src="/firefinder/photos/ab/deadbeef.webp"');
  });
});

describe('a photo with neither a mirrored file nor a usable url', () => {
  const r: TowerRecord = {
    ...base,
    photos: [{ url: 'javascript:alert(1)', source_url: 'http://nhlr.org/lookouts/us/or/flag-point/', credit: 'unknown' }],
  };

  it('falls back to the source page link rather than showing nothing', () => {
    const out = photosSection(r, ctxNoHost)!.value;
    expect(out).toContain('href="http://nhlr.org/lookouts/us/or/flag-point/"');
    expect(out).not.toContain('javascript:');
  });
});
