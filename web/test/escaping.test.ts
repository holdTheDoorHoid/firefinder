import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { escapeHtml, html, isSafeStoryHtml, raw, safeUrl } from '../src/lib/html.ts';
import type { TowerRecord } from '../src/lib/types.ts';
import { renderPanel, renderTowerHead, renderTowerMain, type RenderContext } from '../src/render/tower.ts';

const ctx: RenderContext = {
  base: '/firefinder/',
  siteUrl: 'https://example.org/firefinder/',
  repo: 'holdTheDoorHoid/firefinder',
  sources: new Map(),
};

/** Run the pipeline's Markdown converter (Python) on `md`. */
function pythonStory(md: string): string {
  const pipeline = resolve(import.meta.dirname, '../../pipeline');
  return execFileSync(
    'python3',
    ['-c', `import sys; sys.path.insert(0, ${JSON.stringify(pipeline)}); from build_site_data import markdown_to_html; sys.stdout.write(markdown_to_html(sys.stdin.read()))`],
    { input: md, encoding: 'utf8' },
  );
}

describe('escapeHtml and the html template', () => {
  it('escapes the five HTML-special characters', () => {
    expect(escapeHtml(`<a href="x">'&'</a>`)).toBe('&lt;a href=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/a&gt;');
  });

  it('escapes interpolations but not nested safe HTML', () => {
    const name = '<img src=x onerror=alert(1)>';
    expect(html`<p title="${name}">${name} ${html`<b>ok</b>`}</p>`.value).toBe(
      '<p title="&lt;img src=x onerror=alert(1)&gt;">&lt;img src=x onerror=alert(1)&gt; <b>ok</b></p>',
    );
  });

  it('renders null, undefined and false as nothing, and joins arrays', () => {
    expect(html`${null}${undefined}${false}${['a', '<', raw('<i>')]}`.value).toBe('a&lt;<i>');
  });
});

describe('safeUrl', () => {
  it.each(['https://www.recreation.gov/camping/campgrounds/234189', 'http://nhlr.org/x', 'mailto:a@b.org', '/firefinder/t/x/', '#fn-1', 'relative/path'])(
    'allows %s',
    (u) => expect(safeUrl(u)).toBe(u),
  );
  it.each(['javascript:alert(1)', 'JavaScript:alert(1)', ' javascript:alert(1)', 'java\tscript:alert(1)', 'java\nscript:x', 'data:text/html,<b>', 'vbscript:x', 'file:///etc/passwd'])(
    'rejects %j',
    (u) => expect(safeUrl(u)).toBeNull(),
  );
  it('rejects non-strings and empty strings', () => {
    expect(safeUrl(null)).toBeNull();
    expect(safeUrl(42)).toBeNull();
    expect(safeUrl('  ')).toBeNull();
  });
});

describe('isSafeStoryHtml', () => {
  it('accepts what the converter produces', () => {
    expect(
      isSafeStoryHtml(
        '<p>Built in <em>1927</em> &amp; <strong>staffed</strong>.<sup id="fnref-1" class="fnref"><a href="#fn-1" aria-label="Note 1">1</a></sup></p>\n<h3 id="s-x">Later</h3><hr><section class="footnotes" aria-label="Notes and sources"><ol><li id="fn-1"><a href="https://nhlr.org/?a=1&amp;b=2">NHLR</a> <a href="#fnref-1" class="fn-back" aria-label="Back to the text">↩</a></li></ol></section>',
      ),
    ).toBe(true);
  });
  it.each([
    '<script>alert(1)</script>',
    '<p onclick="x">hi</p>',
    '<img src="x">',
    '<a href="javascript:alert(1)">x</a>',
    '<a href="&#106;avascript:alert(1)">x</a>',
    '<a href="java&#x09;script:x">x</a>',
    '<p style="color:red">x</p>',
    '<!-- comment -->',
    '<p>a < b</p>',
    '<a href=\'x\'>single quotes</a>',
    '</p class="x">',
    '<svg><script>x</script></svg>',
  ])('rejects %s', (markup) => expect(isSafeStoryHtml(markup)).toBe(false));
});

describe('story Markdown converter (pipeline/build_site_data.py)', () => {
  it('escapes raw HTML and script tags', () => {
    const out = pythonStory('Hello <script>alert(1)</script> and <img src=x onerror=alert(2)>\n');
    expect(out).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
    expect(out).not.toMatch(/<script|<img/);
    expect(isSafeStoryHtml(out)).toBe(true);
  });

  it('drops dangerous link targets but keeps the link text', () => {
    const out = pythonStory('[click](javascript:alert(1)) [ok](https://nhlr.org/x?a=1&b=2) [data](data:text/html;base64,xx)\n');
    expect(out).not.toMatch(/javascript:|data:/i);
    expect(out).toContain('<a href="https://nhlr.org/x?a=1&amp;b=2">ok</a>');
    expect(out).toContain('click');
    expect(isSafeStoryHtml(out)).toBe(true);
  });

  it('cannot break out of an attribute with quotes', () => {
    const out = pythonStory('[x](https://a.org/"onmouseover="alert(1))\n');
    // The quotes stay inside the href value as &quot;, so the tag has exactly one attribute.
    expect(out).toMatch(/<a href="[^"]*&quot;onmouseover=&quot;[^"]*">x<\/a>/);
    expect(out).not.toMatch(/<a [^>]*"\s+onmouseover/);
    expect(isSafeStoryHtml(out)).toBe(true);
  });

  it('handles paragraphs, headings, emphasis, quotes and ampersands', () => {
    const out = pythonStory('# Title\n\nFire crews called it "the Dutchman" & still do. *Cupola* and **CCC**.\n\nSecond para.\n');
    expect(out).toContain('<h2 id="s-title">Title</h2>');
    expect(out).toContain('&quot;the Dutchman&quot; &amp; still do. <em>Cupola</em> and <strong>CCC</strong>.');
    expect(out.match(/<p>/g)).toHaveLength(2);
  });

  it('numbers footnotes in order of use and links both ways', () => {
    const out = pythonStory('First.[^b] Second.[^a] Again.[^b]\n\n[^a]: Source A, [site](https://a.org).\n[^b]: Source B.\n[^c]: Never cited.\n');
    expect(out).toContain('<sup id="fnref-b" class="fnref"><a href="#fn-b" aria-label="Note 1">1</a></sup>');
    expect(out).toContain('<sup id="fnref-a" class="fnref"><a href="#fn-a" aria-label="Note 2">2</a></sup>');
    expect(out).toContain('id="fnref-b-2"');
    expect(out.indexOf('id="fn-b"')).toBeLessThan(out.indexOf('id="fn-a"'));
    expect(out).toContain('<li id="fn-c">Never cited.</li>');
    expect(isSafeStoryHtml(out)).toBe(true);
  });

  it('leaves an undefined footnote reference as plain text', () => {
    expect(pythonStory('Text[^missing].\n')).toContain('Text[^missing].');
  });
});

describe('tower page rendering escapes hostile data', () => {
  const evil: TowerRecord = {
    id: 'us-or-evil',
    name: '<img src=x onerror=alert(1)>Evil Lookout',
    other_names: ['"><script>alert(2)</script>'],
    region: 'OR',
    county: '<b>County</b>',
    location: { lat: 44, lon: -121, precision: 'exact', from: 'ffla' },
    kind: 'tower',
    status: 'standing',
    verification: 'unverified',
    access: { level: 'private', note: '<script>alert(3)</script>' },
    registers: [{ register: 'NHLR', number: 'US 1', url: 'javascript:alert(4)' }],
    rental: { available: true, url: 'javascript:alert(5)', season: '<i>summer</i>', rules: ['<script>x</script>'] },
    events: [{ year: 1933, event: 'built', note: '<script>alert(6)</script>' }],
    photos: [{ url: 'javascript:alert(7)', credit: '<b>me</b>' }, { url: 'https://example.org/p.jpg', credit: 'x', source_url: 'javascript:alert(8)' }],
    links: [{ label: 'bad', url: 'javascript:alert(9)' }],
    sources: [{ source: '<script>', fields: ['<x>'] }],
    conflicts: [{ field: '<f>', values: [{ source: 'ffla', value: '<script>alert(10)</script>' }], note: '<script>' }],
    story_html: '<p>ok</p><script>alert(11)</script>',
  };

  const outputs = {
    main: renderTowerMain(evil, ctx).value,
    head: renderTowerHead(evil, ctx).value,
    panel: renderPanel(evil, ctx).value,
  };

  it.each(Object.keys(outputs))('%s has no live script, handler or javascript: URL', (key) => {
    const out = outputs[key as keyof typeof outputs];
    expect(out).not.toMatch(/<script/i);
    expect(out).not.toMatch(/<img src=x/i);
    expect(out).not.toMatch(/<b>|<i>/);
    expect(out).not.toMatch(/(href|src)="\s*javascript:/i);
  });

  it('shows a notice instead of an unsafe story', () => {
    expect(outputs.main).toContain('story could not be shown');
    expect(outputs.main).not.toContain('<p>ok</p>');
  });

  it('pre-fills the Suggest an edit issue with id, name and page URL', () => {
    const m = /href="(https:\/\/github\.com\/holdTheDoorHoid\/firefinder\/issues\/new\?[^"]+)"/.exec(outputs.main);
    expect(m).not.toBeNull();
    const url = new URL(m![1]!.replace(/&amp;/g, '&'));
    expect(url.searchParams.get('template')).toBe('edit.yml');
    expect(url.searchParams.get('tower_id')).toBe('us-or-evil');
    expect(url.searchParams.get('tower_name')).toBe(evil.name);
    expect(url.searchParams.get('page_url')).toBe('https://example.org/firefinder/t/us-or-evil/');
  });
});
