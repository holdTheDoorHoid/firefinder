/**
 * Safe HTML building. Everything interpolated into `html` templates is escaped unless it is
 * already a SafeHtml value (produced by `html` itself or by `raw` on trusted, checked input).
 * Used both at build time (prerendered tower pages) and in the browser (map side panel).
 */

export class SafeHtml {
  readonly value: string;
  constructor(value: string) {
    this.value = value;
  }
  toString(): string {
    return this.value;
  }
}

const ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

export function escapeHtml(value: unknown): string {
  return String(value).replace(/[&<>"']/g, (c) => ESCAPES[c]!);
}

function render(value: unknown): string {
  if (value === null || value === undefined || value === false) return '';
  if (value instanceof SafeHtml) return value.value;
  if (Array.isArray(value)) return value.map(render).join('');
  return escapeHtml(value);
}

/** Tagged template: `html\`<p>${text}</p>\`` escapes `text`. */
export function html(strings: TemplateStringsArray, ...values: unknown[]): SafeHtml {
  let out = strings[0]!;
  for (let i = 0; i < values.length; i++) out += render(values[i]) + strings[i + 1]!;
  return new SafeHtml(out);
}

/** Mark a string as trusted HTML. Only for markup this codebase produced or checked. */
export function raw(value: string): SafeHtml {
  return new SafeHtml(value);
}

export function join(items: unknown[], separator: unknown = ''): SafeHtml {
  return new SafeHtml(items.map(render).join(render(separator)));
}

/**
 * Returns the URL if it is safe to put in an href/src (http, https, mailto, or a relative /
 * fragment URL), otherwise null. Rejects javascript:, data:, vbscript: and anything with an
 * unknown scheme, including ones disguised with whitespace or control characters.
 */
export function safeUrl(url: unknown): string | null {
  if (typeof url !== 'string') return null;
  const trimmed = url.trim();
  if (!trimmed) return null;
  // Browsers ignore tabs/newlines/control chars inside schemes ("java\tscript:").
  const probe = trimmed.replace(/[\u0000-\u001F\u007F\s]+/g, '').toLowerCase();
  const scheme = /^([a-z][a-z0-9+.-]*):/.exec(probe);
  if (scheme) {
    return ['http', 'https', 'mailto'].includes(scheme[1]!) ? trimmed : null;
  }
  if (probe.startsWith('//')) return trimmed; // protocol-relative: same scheme as the page
  return trimmed; // relative path or #fragment
}

/* ---------- Story HTML check (defence in depth) ----------
 * Story HTML is produced by pipeline/build_site_data.py, which escapes all text. Before we
 * insert it raw into a page we still check that it only contains the small set of tags and
 * attributes that converter emits. Anything else means the converter (or the data) is wrong,
 * and the page shows a notice instead of the story. */

const STORY_TAGS: Record<string, readonly string[]> = {
  p: [],
  h2: ['id'],
  h3: ['id'],
  h4: ['id'],
  em: [],
  strong: [],
  code: [],
  blockquote: [],
  ul: [],
  ol: [],
  li: ['id'],
  hr: [],
  br: [],
  a: ['href', 'id', 'class', 'aria-label'],
  sup: ['id', 'class'],
  section: ['class', 'aria-label'],
};

const TAG_RE = /<(\/?)([a-zA-Z][a-zA-Z0-9]*)((?:\s+[a-zA-Z][a-zA-Z-]*="[^"<>]*")*)\s*(\/?)>/y;
const ATTR_RE = /\s+([a-zA-Z][a-zA-Z-]*)="([^"<>]*)"/g;

export function isSafeStoryHtml(markup: string): boolean {
  let pos = 0;
  for (;;) {
    const lt = markup.indexOf('<', pos);
    if (lt === -1) return true;
    TAG_RE.lastIndex = lt;
    const m = TAG_RE.exec(markup);
    if (!m) return false; // a "<" that is not a well-formed tag
    const tag = m[2]!.toLowerCase();
    const allowed = STORY_TAGS[tag];
    if (!allowed) return false;
    const attrs = m[3] ?? '';
    if (m[1] && attrs) return false; // attributes on a closing tag
    for (const a of attrs.matchAll(ATTR_RE)) {
      const name = a[1]!.toLowerCase();
      if (!allowed.includes(name)) return false;
      if (name === 'href') {
        // The converter only writes these few entities (Python's html.escape). Any other
        // entity could hide a scheme ("&#106;avascript:"), so it is rejected outright.
        if (/&(?!(?:amp|quot|lt|gt|#x27|#39);)/.test(a[2]!)) return false;
        if (safeUrl(a[2]!.replace(/&amp;/g, '&')) === null) return false;
      }
    }
    pos = TAG_RE.lastIndex;
  }
}
