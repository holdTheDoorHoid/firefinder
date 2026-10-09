import { describe, expect, it } from 'vitest';
import { resolveRedirect, type RedirectsFile } from '../src/lib/redirects.ts';
import { renderRedirectPage } from '../src/render/redirect.ts';

const ctx = { base: '/firefinder/', siteUrl: 'https://example.org/firefinder/' };

describe('resolveRedirect', () => {
  const file: RedirectsFile = {
    redirects: {
      'us-or-mount-emily': 'us-or-mount-emily-lookout-site-snf',
      'us-xx-a': 'us-xx-b',
      'us-xx-b': 'us-xx-c',
      'us-xx-loop-1': 'us-xx-loop-2',
      'us-xx-loop-2': 'us-xx-loop-1',
      'us-xx-bad': 'not an id',
    },
  };

  it('sends a retired id to the tower that took it', () => {
    expect(resolveRedirect('us-or-mount-emily', file)).toBe('us-or-mount-emily-lookout-site-snf');
  });

  it('leaves every other id alone, with or without a list', () => {
    expect(resolveRedirect('us-or-abbot-butte', file)).toBe('us-or-abbot-butte');
    expect(resolveRedirect('us-or-abbot-butte', null)).toBe('us-or-abbot-butte');
    expect(resolveRedirect('us-or-abbot-butte', { redirects: {} })).toBe('us-or-abbot-butte');
    expect(resolveRedirect('toString', file)).toBe('toString');
  });

  it('follows a chain, stops at a loop, and ignores a target that is not an id', () => {
    expect(resolveRedirect('us-xx-a', file)).toBe('us-xx-c');
    expect(['us-xx-loop-1', 'us-xx-loop-2']).toContain(resolveRedirect('us-xx-loop-1', file));
    expect(resolveRedirect('us-xx-bad', file)).toBe('us-xx-bad');
  });
});

describe('renderRedirectPage', () => {
  it('redirects at once, names the new page and is not indexed', () => {
    const page = renderRedirectPage({ id: 'us-or-mount-emily-lookout-site-snf', name: 'Mount Emily Lookout Site - SNF' }, ctx);
    expect(page.startsWith('<!doctype html>')).toBe(true);
    expect(page).toContain('<meta http-equiv="refresh" content="0; url=/firefinder/t/us-or-mount-emily-lookout-site-snf/">');
    expect(page).toContain('<link rel="canonical" href="https://example.org/firefinder/t/us-or-mount-emily-lookout-site-snf/">');
    expect(page).toContain('<meta name="robots" content="noindex">');
    expect(page).toContain('<a href="/firefinder/t/us-or-mount-emily-lookout-site-snf/">Mount Emily Lookout Site - SNF</a>');
  });

  it('escapes the name', () => {
    const page = renderRedirectPage({ id: 'us-xx-b', name: '<img src=x onerror=alert(1)> "Joe\'s"' }, ctx);
    expect(page).not.toContain('<img');
    expect(page).toContain('&lt;img src=x onerror=alert(1)&gt; &quot;Joe&#39;s&quot;');
  });
});
