/**
 * Tower page and side-panel markup. Pure functions returning escaped HTML, used by
 * scripts/prerender.ts at build time (one static page per lookout) and by the map's side
 * panel in the browser, so both say the same thing in the same words.
 */
import { feetAndMetres, formatCoords, formatDate, formatDistance, distanceMetres, plainCoords, yesNo } from '../lib/format.ts';
import { html, raw, safeUrl, isSafeStoryHtml, type SafeHtml } from '../lib/html.ts';
import { fillFor, markerSvg, rentBadgeSvg, shapeFor } from '../lib/icons.ts';
import { MARKS, MARK_LABELS } from '../lib/checklist.ts';
import { builtYear, isRentable, type Conflict, type SourceInfo, type TowerProps, type TowerRecord } from '../lib/types.ts';
import {
  ACCESS,
  OWNERSHIP,
  REGISTER_NAMES,
  STAFFING,
  TRIBAL_ACCESS,
  eventLabel,
  kindWording,
  regionName,
  statusWording,
  verificationWording,
} from '../lib/vocab.ts';

export interface RenderContext {
  /** Site base path, e.g. "/firefinder/". */
  base: string;
  /** Absolute site URL for canonical links, e.g. "https://…/firefinder/". */
  siteUrl: string;
  /** GitHub "owner/name" that receives edit suggestions and takedown requests. */
  repo: string;
  sources: Map<string, SourceInfo>;
  takedownEmail?: string | null;
}

const SHORT_SOURCE: Record<string, string> = {
  ffla: 'FFLA',
  nhlr: 'NHLR',
  fflos: 'FFLOS',
  ridb: 'recreation.gov',
  osm: 'OpenStreetMap',
  wikidata: 'Wikidata',
};

export function sourceShortName(id: string | null | undefined, ctx: RenderContext): string {
  if (!id) return 'unknown source';
  return SHORT_SOURCE[id] ?? ctx.sources.get(id)?.title ?? id;
}

/* ---------- URLs ---------- */

export function towerPath(id: string, ctx: Pick<RenderContext, 'base'>): string {
  return `${ctx.base}t/${id}/`;
}

export function towerUrl(id: string, ctx: Pick<RenderContext, 'siteUrl'>): string {
  return `${ctx.siteUrl}t/${id}/`;
}

export function mapLink(r: Pick<TowerRecord, 'id' | 'location'>, ctx: Pick<RenderContext, 'base'>, zoom = 12): string {
  const { lat, lon } = r.location;
  return `${ctx.base}?at=${zoom}/${lat.toFixed(4)}/${lon.toFixed(4)}&t=${r.id}`;
}

export function editIssueUrl(r: Pick<TowerRecord, 'id' | 'name'>, ctx: RenderContext): string {
  const q = new URLSearchParams({
    template: 'edit.yml',
    title: `Edit: ${r.name} (${r.id})`,
    tower_id: r.id,
    tower_name: r.name,
    page_url: towerUrl(r.id, ctx),
  });
  return `https://github.com/${ctx.repo}/issues/new?${q.toString()}`;
}

export function takedownIssueUrl(r: Pick<TowerRecord, 'id' | 'name'> | null, ctx: RenderContext): string {
  const q = new URLSearchParams({ template: 'takedown.yml', title: r ? `Takedown: ${r.name}` : 'Takedown: ' });
  if (r) {
    q.set('tower_id', r.id);
    q.set('page_url', towerUrl(r.id, ctx));
  }
  return `https://github.com/${ctx.repo}/issues/new?${q.toString()}`;
}

/* ---------- Small pieces ---------- */

export function placeLine(r: Pick<TowerRecord, 'county' | 'region'>): string {
  const state = regionName(r.region);
  if (!r.county) return state;
  const c = r.county.trim();
  const hasSuffix = /\b(County|Parish|Borough|Census Area|Municipality|City)$/i.test(c);
  const suffix = hasSuffix ? '' : r.region === 'LA' ? ' Parish' : r.region === 'AK' ? ' Borough' : ' County';
  return `${c}${suffix}, ${state}`;
}

function icon(kind: string, status: string, rentable = false, size = 20): SafeHtml {
  return raw(markerSvg(shapeFor(kind), fillFor(status), { rentable, size, className: 'marker-icon' }));
}

const EXT = raw('<svg class="ext-icon" width="14" height="14" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M9 2h5v5M14 2 7.5 8.5M12 9.5V13a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>');
const WARN = raw('<svg class="notice-icon" width="20" height="20" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M10 2.5 18.5 17h-17Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M10 8v4.2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="10" cy="14.6" r="1.1" fill="currentColor"/></svg>');
const INFO = raw('<svg class="notice-icon" width="20" height="20" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M10 9v5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="10" cy="6.1" r="1.1" fill="currentColor"/></svg>');

export function externalLink(url: string | null | undefined, text: unknown, className = ''): SafeHtml {
  const safe = safeUrl(url);
  if (!safe) return html`${text}`;
  return html`<a href="${safe}" class="${className || null}" rel="noopener">${text}${EXT}<span class="visually-hidden"> (opens another site)</span></a>`;
}

export interface AccessInfo {
  level: string;
  label: string;
  meaning: string;
  note: string | null;
  tone: 'ok' | 'caution' | 'stop' | 'unknown';
}

/** Plain-language access wording; tribal land gets its own, firmer wording. */
export function accessInfo(r: TowerRecord): AccessInfo {
  const level = r.access?.level ?? 'unknown';
  const note = r.access?.note ?? null;
  const tribal = r.ownership === 'tribal' && level !== 'public' && level !== 'closed' && level !== 'private';
  if (tribal) return { level, note, label: TRIBAL_ACCESS.label, meaning: TRIBAL_ACCESS.meaning, tone: 'stop' };
  const w = ACCESS[level] ?? { label: level, meaning: '', tone: 'unknown' as const };
  return { level, note, label: w.label, meaning: w.meaning, tone: w.tone };
}

const CHECK = raw('<svg class="notice-icon" width="16" height="16" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="m4.5 10.5 3.5 3.5 7.5-8" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>');

/** Status, rentable, access and verification badges. Text always accompanies the icon. */
export function badges(r: TowerRecord): SafeHtml {
  const st = statusWording(r.status);
  const ver = verificationWording(r.verification);
  const rent = isRentable(r);
  const acc = accessInfo(r);
  return html`<ul class="badges" aria-label="Status">
    <li class="badge badge-status status-${r.status}" title="${st.meaning}">${icon(r.kind, r.status)}<span>${st.label}</span></li>
    ${rent ? html`<li class="badge badge-rent">${raw(rentBadgeSvg(14))}<span>Rentable</span></li>` : ''}
    <li class="badge badge-access tone-${acc.tone}" title="${acc.meaning}">${acc.tone === 'ok' ? CHECK : acc.tone === 'unknown' ? INFO : WARN}<span>${acc.label}</span></li>
    ${r.verification === 'unverified'
      ? html`<li class="badge badge-unverified" title="${ver.meaning}">${WARN}<span>Unverified</span></li>`
      : html`<li class="badge badge-ver ver-${r.verification}" title="${ver.meaning}"><span>${ver.label}</span></li>`}
    ${r.fixture ? html`<li class="badge badge-fixture"><span>Sample entry</span></li>` : ''}
  </ul>`;
}

/**
 * The access notice: label, plain meaning and the record's note. On a tower page it appears
 * once: at the top for "stop" access (private, tribal, permission, closed), otherwise in
 * Visit & stay. `compact` (the map panel) skips plainly public access.
 */
export function accessNotice(r: TowerRecord, opts: { compact?: boolean } = {}): SafeHtml {
  const a = accessInfo(r);
  if (a.tone === 'ok') {
    return opts.compact ? html`` : html`<p class="access-line tone-ok"><strong>${a.label}.</strong> ${a.note}</p>`;
  }
  return html`<div class="notice tone-${a.tone}" role="note">
    ${a.tone === 'unknown' ? INFO : WARN}
    <div><p class="notice-title">${a.label}</p><p>${a.meaning}${a.note ? html` ${a.note}` : ''}</p></div>
  </div>`;
}

const TOWER_ID_RE = /^[a-z]{2}-[a-z0-9]{1,3}-[a-z0-9]+(?:-[a-z0-9]+)*$/;

/** Links between a moved structure and its original site (links of kind relocated_*). */
export function movedLinks(r: TowerRecord): { id: string; label: string; kind: string }[] {
  return (r.links ?? [])
    .filter((l) => (l.kind === 'relocated_from' || l.kind === 'relocated_to') && typeof l.id === 'string' && TOWER_ID_RE.test(l.id))
    .map((l) => ({ id: l.id!, label: l.label, kind: l.kind! }));
}

export function movedNotice(r: TowerRecord, ctx: RenderContext): SafeHtml {
  const moved = movedLinks(r);
  if (!moved.length) return html``;
  // Labels come from the pipeline and say what the link is ("Original site: Padlock Hill",
  // "Now at the State Fair", "Parts came from Whites Hill").
  const lead = r.status === 'relocated' && moved.some((m) => m.kind === 'relocated_to') ? 'The lookout that stood here was moved.' : '';
  return html`<div class="notice tone-unknown moved-notice" role="note">${INFO}<div>
    <p>${lead ? html`${lead} ` : ''}${moved.map((m, i) => html`${i ? ' · ' : ''}<a href="${towerPath(m.id, ctx)}">${m.label}</a>`)}</p>
  </div></div>`;
}

export function unverifiedNotice(r: TowerRecord, ctx: RenderContext): SafeHtml {
  if (r.verification !== 'unverified') return html``;
  return html`<div class="notice tone-caution" role="note">${WARN}<div>
    <p class="notice-title">Unverified entry</p>
    <p>This comes from a single source and nobody has checked it yet, so details may be wrong. If you know better, <a href="${editIssueUrl(r, ctx)}">suggest an edit</a>.</p>
  </div></div>`;
}

/* ---------- Visit & stay ---------- */

/**
 * The warning for a listing on a lookout another source records as gone or burned (the
 * pipeline sets rental.warning and available: false). Shown above the booking link: warn,
 * don't hide.
 */
export function rentalWarning(r: TowerRecord): SafeHtml {
  const w = r.rental?.warning;
  if (!w) return html``;
  return html`<div class="notice tone-stop rental-warning" role="note">${WARN}<div>
    <p class="notice-title">Check before booking</p>
    <p>${w}</p>
  </div></div>`;
}

function rentalDetails(r: TowerRecord): SafeHtml {
  const rent = r.rental!;
  const warned = !!rent.warning;
  const rows: [string, unknown][] = [
    ['Season', rent.season],
    ['Sleeps', typeof rent.max_occupancy === 'number' ? `Up to ${rent.max_occupancy} ${rent.max_occupancy === 1 ? 'person' : 'people'}` : null],
    ['Pets', rent.pets],
    ['Fee', rent.fee],
    ['Getting there', rent.access_note],
  ];
  const shown = rows.filter(([, v]) => v !== null && v !== undefined && v !== '');
  const book = safeUrl(rent.url);
  const provider = rent.provider ?? 'recreation.gov';
  return html`<div class="rental${warned ? ' rental-warned' : ''}">
    ${warned
      ? html`<p class="lede">${provider} still lists this lookout for overnight stays.</p>`
      : html`<p class="lede">You can rent this lookout for overnight stays${provider ? html` through ${provider}` : ''}.</p>`}
    ${shown.length ? html`<dl class="kv kv-rental">${shown.map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}</dl>` : ''}
    ${rent.rules?.length ? html`<h3 class="h-small">Rules</h3><ul class="rules">${rent.rules.map((x) => html`<li>${x}</li>`)}</ul>` : ''}
    ${rent.description ? html`<p class="rental-desc">${rent.description}</p>` : ''}
    ${warned ? rentalWarning(r) : ''}
    ${book
      ? warned
        ? html`<p class="book-row"><a class="btn btn-book" href="${book}" rel="noopener">See the listing on ${provider}${EXT}<span class="visually-hidden"> (opens ${provider})</span></a></p>`
        : html`<p class="book-row"><a class="btn btn-primary btn-book" href="${book}" rel="noopener">Book on ${provider}${EXT}<span class="visually-hidden"> (opens ${provider})</span></a></p>`
      : ''}
    <p class="fine">Rental details from recreation.gov${rent.checked ? html`, checked ${formatDate(rent.checked)}` : ''}. Rules, fees and seasons change, so confirm on the booking page before you go. <span class="credit-line">Data source: ridb.recreation.gov</span></p>
  </div>`;
}

export function visitSection(r: TowerRecord): SafeHtml {
  let lead: SafeHtml;
  if (isRentable(r) || r.rental?.warning) {
    lead = rentalDetails(r);
  } else if (r.status === 'gone') {
    lead = html`<p class="lede"><strong>Gone: site only.</strong> The lookout no longer stands, so there is nothing to climb or rent. ${r.access?.level === 'public' ? 'You may still be able to visit the site.' : ''}</p>`;
  } else if (r.status === 'ruins') {
    lead = html`<p class="lede"><strong>Ruins: footings or remains only.</strong> There is no structure to climb or rent.</p>`;
  } else if (r.rental && r.rental.available === false) {
    lead = html`<p class="lede"><strong>Not rentable right now.</strong> This lookout has been rented before but is not currently listed.</p>`;
  } else {
    lead = html`<p class="lede"><strong>Not rentable.</strong> As far as we know, this lookout cannot be booked for overnight stays.</p>`;
  }
  const v = r.visit ?? {};
  const standingish = !['gone', 'ruins'].includes(r.status);
  const rows: [string, unknown][] = [];
  if (standingish) rows.push(['Can you climb it?', yesNo(v.climbable, 'Yes', 'No')]);
  rows.push(['Road to the top?', yesNo(v.drive_up, 'Yes, you can drive up', 'No, you have to hike')]);
  if (v.trail_note) rows.push(['Trail', v.trail_note]);
  if (r.staffing && standingish) {
    const s = STAFFING[r.staffing.status] ?? r.staffing.status;
    rows.push(['Staffing', r.staffing.as_of ? `${s} (as of ${r.staffing.as_of})` : s]);
  }
  const acc = accessInfo(r);
  return html`${lead}
    <h3 class="h-small">Access</h3>
    ${acc.tone === 'stop'
      ? html`<p class="access-line"><strong>${acc.label}.</strong> See the warning at the top of this page.</p>`
      : accessNotice(r)}
    <dl class="kv">${rows.map(([k, val]) => html`<div><dt>${k}</dt><dd>${val}</dd></div>`)}</dl>`;
}

/* ---------- Facts ---------- */

function registersList(r: TowerRecord): SafeHtml | null {
  const regs = r.registers ?? [];
  if (!regs.length) return null;
  return html`<ul class="plain">${regs.map((g) => {
    const name = REGISTER_NAMES[g.register] ?? g.register;
    const num = [g.number, g.state_number].filter(Boolean).join(' · ');
    const label = html`<abbr title="${name}">${g.register}</abbr> ${num}`;
    const url = safeUrl(g.url);
    return html`<li>${url ? html`<a href="${url}" rel="noopener">${label}</a>` : label}</li>`;
  })}</ul>`;
}

function hasConflict(r: TowerRecord, field: string): boolean {
  return (r.conflicts ?? []).some((c) => c.field === field);
}

export function factRows(r: TowerRecord, opts: { short?: boolean } = {}): [string, unknown][] {
  const st = statusWording(r.status);
  const kind = kindWording(r.kind);
  const built = builtYear(r);
  const disagree = (field: string) => (hasConflict(r, field) ? html` <a class="disagree" href="#conflicts">sources disagree</a>` : '');
  const rows: [string, unknown][] = [
    ['Status', html`<span class="with-icon">${icon(r.kind, r.status, false, 16)}${st.label}</span>${disagree('status')}`],
    ['Type', r.design ? html`${kind.label}<span class="sub">${r.design}</span>` : kind.label],
    ['Built', built !== null ? html`${built}${disagree('built')}` : 'Unknown'],
  ];
  const height = feetAndMetres(r.height_m, 1);
  if (height || !opts.short) rows.push(['Height', height ?? 'Unknown']);
  rows.push(['Elevation', feetAndMetres(r.elevation_m) ?? 'Unknown']);
  rows.push(['Agency', r.agency ?? 'Unknown']);
  if (!opts.short) {
    rows.push(['Land', OWNERSHIP[r.ownership ?? 'unknown'] ?? r.ownership]);
    rows.push(['Location', placeLine(r)]);
    const prec = r.location.precision && r.location.precision !== 'exact' ? ` (${r.location.precision})` : '';
    rows.push([
      'Coordinates',
      html`<span class="coords" data-coords="${plainCoords(r.location.lat, r.location.lon)}">${formatCoords(r.location.lat, r.location.lon)}</span>${prec}${disagree('location')}`,
    ]);
  }
  const regs = registersList(r);
  if (regs || !opts.short) rows.push(['Registers', regs ?? 'Not on a lookout register']);
  return rows;
}

export function factsCard(r: TowerRecord): SafeHtml {
  const ver = verificationWording(r.verification);
  return html`<dl class="kv kv-facts">${factRows(r).map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}
    <div><dt>This entry</dt><dd>${ver.label}<span class="sub">${ver.meaning}${r.updated ? ` Updated ${formatDate(r.updated)}.` : ''}</span></dd></div>
    <div><dt>Firefinder id</dt><dd><code>${r.id}</code></dd></div>
  </dl>`;
}

/* ---------- History ---------- */

export function timeline(r: TowerRecord, ctx: RenderContext): SafeHtml {
  const events = [...(r.events ?? [])].sort((a, b) => (a.year ?? 1e9) - (b.year ?? 1e9));
  if (!events.length) return html`<p class="muted">No dated events recorded yet.</p>`;
  return html`<ol class="timeline">${events.map(
    (e) => html`<li>
      <span class="tl-year">${e.year ?? 'Date unknown'}</span>
      <span class="tl-body"><span class="tl-what">${eventLabel(e.event)}</span>${e.note ? html`<span class="tl-note">${e.note}</span>` : ''}${e.from ? html`<span class="tl-src">Source: ${sourceShortName(e.from, ctx)}</span>` : ''}</span>
    </li>`,
  )}</ol>`;
}

export function storyBlock(r: TowerRecord, ctx: RenderContext): SafeHtml {
  if (r.story_html) {
    if (isSafeStoryHtml(r.story_html)) return html`<div class="prose story">${raw(r.story_html)}</div>`;
    return html`<p class="notice tone-caution">This lookout's story could not be shown because it contains markup we do not allow. It has been flagged for a fix.</p>`;
  }
  return html`<p class="muted">We have not written this lookout's story yet. ${r.status === 'standing' ? 'Stories for standing and rentable lookouts come first.' : ''} Know something about its history? <a href="${editIssueUrl(r, ctx)}">Tell us</a>.</p>`;
}

/* ---------- Photos ---------- */

/** True only for a URL whose scheme is https (safeUrl already rejects dangerous schemes). */
function isHttpsUrl(url: string | null | undefined): boolean {
  const safe = safeUrl(url);
  return !!safe && /^https:\/\//i.test(safe);
}

/** Hostname for the "View photo at <host>" card, without a leading "www.". */
function photoHost(url: string | null | undefined): string | null {
  const safe = safeUrl(url);
  if (!safe) return null;
  try {
    return new URL(safe).hostname.replace(/^www\./, '');
  } catch {
    return null;
  }
}

const PHOTO_PLACEHOLDER = raw(
  '<svg class="photo-link-icon" width="30" height="30" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
    '<rect x="2.5" y="4.5" width="19" height="15" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/>' +
    '<circle cx="8.3" cy="10" r="1.7" fill="currentColor"/>' +
    '<path d="M3.2 16.3 8.3 11l3.3 3.3 3-3 5.2 4.8" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>' +
    '</svg>',
);

/**
 * Interim handling (see pipeline/mirror_photos.py / data/photos_manifest.json for the real
 * fix): until a photo is mirrored, `url` is the remote original. Two of our busiest sources
 * (nhlr.org, firetower.org) reset the TLS handshake, so their photos only load over plain
 * http; an https page cannot embed that without the browser blocking or breaking the image.
 * Rather than emit a broken <img>, those photos get a plain link card that still carries the
 * credit line.
 */
export function photosSection(r: TowerRecord, ctx: RenderContext): SafeHtml | null {
  const photos = (r.photos ?? []).filter((p) => p.file || p.url);
  if (!photos.length) return null;
  const dataUrl = (path: string | null | undefined) => (path && !path.includes('..') ? `${ctx.base}data/${path.replace(/^\/+/, '')}` : null);
  return html`<div class="photos">${photos.map((p) => {
    const mirrored = dataUrl(p.file);
    const source = safeUrl(p.source_url);
    const credit = html`<span class="credit-line">Photo: ${p.credit ?? 'credit unknown'}${p.license ? html` · ${p.license}` : ''}${source ? html` · <a href="${source}" rel="noopener">source</a>` : ''}</span>`;
    const caption = p.caption || p.year
      ? html`<span class="cap">${[p.caption?.replace(/[\s.]+$/, ''), p.year ? `(${p.year})` : null].filter(Boolean).join(' ')}</span>`
      : '';

    if (!mirrored && !isHttpsUrl(p.url)) {
      // No mirrored copy yet, and the remote original is not https: link out instead of
      // embedding it.
      const remote = safeUrl(p.url) ?? source;
      const host = photoHost(p.url) ?? photoHost(p.source_url) ?? 'the source site';
      return html`<figure class="photo photo-link-card">
        ${remote
          ? html`<a class="photo-link" href="${remote}" rel="noopener">${PHOTO_PLACEHOLDER}<span>View photo at ${host}</span>${EXT}<span class="visually-hidden"> (opens another site)</span></a>`
          : html`<span class="photo-link photo-link-unavailable">${PHOTO_PLACEHOLDER}<span>Photo unavailable</span></span>`}
        <figcaption>${caption}${credit}</figcaption>
      </figure>`;
    }

    const full = mirrored ?? safeUrl(p.url);
    const shown = dataUrl(p.thumb) ?? full;
    if (!full || !shown) return '';
    const alt = p.caption ? p.caption : `Photo of ${r.name}${p.year ? `, ${p.year}` : ''}`;
    return html`<figure class="photo">
      <a href="${full}"><img src="${shown}" alt="${alt}" loading="lazy" decoding="async"></a>
      <figcaption>${caption}${credit}</figcaption>
    </figure>`;
  })}</div>
  <p class="fine">Photos keep their own rights and are shown with credit. Is one of these yours? You can <a href="${takedownIssueUrl(r, ctx)}">ask for a different credit or for removal</a>.</p>`;
}

/* ---------- Conflicts ---------- */

function conflictValue(field: string, value: unknown): string {
  if (value && typeof value === 'object' && 'lat' in value && 'lon' in value) {
    const v = value as { lat: number; lon: number };
    if (typeof v.lat === 'number' && typeof v.lon === 'number') return formatCoords(v.lat, v.lon);
  }
  if (field === 'status' && typeof value === 'string') return statusWording(value).label;
  if (field === 'kind' && typeof value === 'string') return kindWording(value).label;
  if (value === null || value === undefined) return 'no value';
  if (typeof value === 'object') return JSON.stringify(value).slice(0, 120);
  return String(value);
}

const FIELD_WORDS: Record<string, string> = {
  location: 'the location',
  status: 'whether it still stands',
  built: 'the year it was built',
  kind: 'what kind of structure it is',
  elevation_m: 'the elevation',
  height_m: 'the height',
  name: 'the name',
};

export function conflictSentence(c: Conflict, r: TowerRecord, ctx: RenderContext): SafeHtml {
  const values = c.values ?? [];
  const what = FIELD_WORDS[c.field] ?? `the ${c.field.replace(/_/g, ' ')}`;
  let headline = html`Sources disagree on ${what}.`;
  if (c.field === 'location') {
    let d = typeof c.distance_m === 'number' ? c.distance_m : null;
    const pts = values.map((v) => v.value as { lat?: number; lon?: number });
    if (d === null && pts.length >= 2 && typeof pts[0]!.lat === 'number' && typeof pts[1]!.lat === 'number') {
      d = distanceMetres(pts[0]!.lat!, pts[0]!.lon!, pts[1]!.lat!, pts[1]!.lon!);
    }
    if (d !== null) headline = html`Sources disagree on the location by ${formatDistance(d)}.`;
  }
  const list = values.map((v) => html`<li><span class="src">${sourceShortName(v.source, ctx)}:</span> ${conflictValue(c.field, v.value)}</li>`);
  const usedFrom = c.field === 'location' && r.location.from ? html`<p class="fine">The map uses the position from ${sourceShortName(r.location.from, ctx)}.</p>` : '';
  return html`<li class="conflict"><p class="conflict-head">${headline}</p>${list.length ? html`<ul class="plain">${list}</ul>` : ''}${c.note ? html`<p>${c.note}</p>` : ''}${usedFrom}</li>`;
}

export function conflictsSection(r: TowerRecord, ctx: RenderContext): SafeHtml | null {
  const cs = r.conflicts ?? [];
  if (!cs.length) return null;
  return html`<p>We show disagreements between sources instead of quietly picking one. If you know which is right, please <a href="${editIssueUrl(r, ctx)}">tell us</a>.</p>
    <ul class="conflicts">${cs.map((c) => conflictSentence(c, r, ctx))}</ul>`;
}

/* ---------- Sources ---------- */

const FIELD_NAMES: Record<string, string> = {
  location: 'location',
  kind: 'type',
  status: 'status',
  registers: 'register numbers',
  county: 'county',
  events: 'dates',
  elevation_m: 'elevation',
  height_m: 'height',
  agency: 'agency',
  rental: 'rental details',
  photos: 'photos',
  name: 'name',
  design: 'design',
  links: 'links',
};

export function sourcesSection(r: TowerRecord, ctx: RenderContext): SafeHtml {
  const refs = r.sources ?? [];
  const links = (r.links ?? []).filter((l) => safeUrl(l.url) && !String(l.kind ?? '').startsWith('relocated_'));
  return html`
    ${refs.length
      ? html`<ol class="sources">${refs.map((s) => {
          const info = ctx.sources.get(s.source);
          const title = info?.title ?? s.source;
          const fields = (s.fields ?? []).map((f) => FIELD_NAMES[f] ?? f.replace(/_/g, ' '));
          return html`<li>
            <span class="src-title">${info?.url ? externalLink(info.url, title) : title}</span>
            ${fields.length ? html`<span class="src-fields">Gave us: ${fields.join(', ')}</span>` : ''}
            <span class="credit-line">${info?.credit ?? title}${info?.license ? html` · ${info.license}` : ''}${info?.retrieved ? html` · retrieved ${formatDate(info.retrieved)}` : ''}</span>
          </li>`;
        })}</ol>`
      : html`<p class="muted">No sources recorded.</p>`}
    ${links.length
      ? html`<h3 class="h-small">More about this lookout elsewhere</h3><ul class="links">${links.map((l) => html`<li>${externalLink(l.url, l.label)}</li>`)}</ul>`
      : ''}
    <p class="fine">Firefinder takes facts (places, dates, numbers) from these sources and writes its own words. See <a href="${ctx.base}about/#sources">all sources and licences</a>.</p>`;
}

/* ---------- Mini-map (static USGS topo tiles, no JavaScript) ---------- */

export const USGS_TILE = 'https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}';

export function miniMapTiles(lat: number, lon: number, zoom: number, width: number, height: number) {
  const world = 256 * 2 ** zoom;
  const px = ((lon + 180) / 360) * world;
  const rad = (lat * Math.PI) / 180;
  const py = ((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) * world;
  const left = px - width / 2;
  const top = py - height / 2;
  const tiles: { x: number; y: number; left: number; top: number }[] = [];
  const max = 2 ** zoom - 1;
  for (let ty = Math.floor(top / 256); ty <= Math.floor((top + height - 1) / 256); ty++) {
    for (let tx = Math.floor(left / 256); tx <= Math.floor((left + width - 1) / 256); tx++) {
      if (ty < 0 || ty > max) continue;
      const wrapped = ((tx % (max + 1)) + max + 1) % (max + 1);
      tiles.push({ x: wrapped, y: ty, left: Math.round(tx * 256 - left), top: Math.round(ty * 256 - top) });
    }
  }
  return tiles;
}

export function miniMap(r: TowerRecord, ctx: RenderContext): SafeHtml {
  const { lat, lon } = r.location;
  const W = 360;
  const H = 210;
  const Z = 13;
  const us = (r.country ?? 'US') === 'US';
  const tiles = us ? miniMapTiles(lat, lon, Z, W, H) : [];
  return html`<figure class="minimap">
    <a class="minimap-frame" href="${mapLink(r, ctx)}" aria-label="Open ${r.name} on the Firefinder map">
      <span class="minimap-inner" style="width:${W}px;height:${H}px;margin-left:-${W / 2}px">
        ${tiles.map(
          (t) => html`<img src="${USGS_TILE.replace('{z}', String(Z)).replace('{y}', String(t.y)).replace('{x}', String(t.x))}" alt="" width="256" height="256" loading="lazy" decoding="async" style="left:${t.left}px;top:${t.top}px">`,
        )}
        <span class="minimap-pin" style="left:${W / 2}px;top:${H / 2}px">${icon(r.kind, r.status, isRentable(r), 26)}</span>
      </span>
    </a>
    <figcaption><span>${formatCoords(lat, lon)}</span><span class="credit-line">Map: <a href="https://www.usgs.gov/programs/national-geospatial-program/national-map" rel="noopener">USGS The National Map</a></span></figcaption>
  </figure>`;
}

/* ---------- Checklist + edit ---------- */

export function checklistButtons(id: string): SafeHtml {
  return html`<div class="checklist-buttons" data-checklist="${id}" role="group" aria-label="My checklist">
    ${MARKS.map(
      (m) => html`<button type="button" class="chip-toggle" data-mark="${m}" aria-pressed="false" disabled><span class="tick" aria-hidden="true"></span>${MARK_LABELS[m]}</button>`,
    )}
  </div>`;
}

/* ---------- Whole page ---------- */

function section(id: string, title: string, body: SafeHtml | null): SafeHtml {
  if (!body) return html``;
  return html`<section class="t-section" id="${id}" aria-labelledby="${id}-h"><h2 id="${id}-h">${title}</h2>${body}</section>`;
}

export function renderTowerMain(r: TowerRecord, ctx: RenderContext): SafeHtml {
  const other = (r.other_names ?? []).filter(Boolean);
  const photos = photosSection(r, ctx);
  const conflicts = conflictsSection(r, ctx);
  const jump: [string, string][] = [
    ['visit', 'Visit & stay'],
    ['facts', 'Facts'],
    ['history', 'History'],
    ...(photos ? ([['photos', 'Photos']] as [string, string][]) : []),
    ...(conflicts ? ([['conflicts', 'Disagreements']] as [string, string][]) : []),
    ['sources', 'Sources'],
    ['mine', 'My checklist'],
  ];
  return html`
  <nav class="crumbs" aria-label="Breadcrumb"><ol>
    <li><a href="${ctx.base}">Map</a></li>
    <li><a href="${ctx.base}?state=${r.region}">${regionName(r.region)}</a></li>
    <li><span aria-current="page">${r.name}</span></li>
  </ol></nav>
  <header class="t-head">
    <p class="eyebrow">Fire lookout · ${placeLine(r)}</p>
    <h1>${r.name}</h1>
    ${other.length ? html`<p class="aka">Also known as ${other.join(', ')}</p>` : ''}
    ${badges(r)}
    <div class="notices">
      ${accessInfo(r).tone === 'stop' ? accessNotice(r) : ''}
      ${movedNotice(r, ctx)}
      ${unverifiedNotice(r, ctx)}
      ${r.status !== 'standing' || r.status_note
        ? html`<p class="status-meaning">${icon(r.kind, r.status, false, 16)} <strong>${statusWording(r.status).label}:</strong> ${r.status !== 'standing' ? statusWording(r.status).meaning : ''}${r.status_note ? html` ${r.status_note}` : ''}</p>`
        : ''}
    </div>
    <nav class="jump" aria-label="On this page"><ul>${jump.map(([id, label]) => html`<li><a href="#${id}">${label}</a></li>`)}</ul></nav>
  </header>
  <div class="t-grid">
    <div class="t-main">
      ${section('visit', 'Visit & stay', visitSection(r))}
      ${section('facts', 'Facts', factsCard(r))}
      ${section('history', 'History', html`<h3 class="h-small">Timeline</h3>${timeline(r, ctx)}<h3 class="h-small">Story</h3>${storyBlock(r, ctx)}`)}
      ${section('photos', 'Photos', photos)}
      ${section('conflicts', 'Where sources disagree', conflicts)}
      ${section('sources', 'Sources', sourcesSection(r, ctx))}
    </div>
    <aside class="t-rail" aria-label="Map and your checklist">
      ${miniMap(r, ctx)}
      <p class="rail-links"><a class="btn" href="${mapLink(r, ctx)}">Show on the Firefinder map</a></p>
      <section class="card" id="mine" aria-labelledby="mine-h">
        <h2 id="mine-h" class="h-card">My checklist</h2>
        ${checklistButtons(r.id)}
        <p class="fine" data-checklist-note>Saved only in this browser. Nothing is sent anywhere. Marking “Stayed overnight” also marks “Visited”.</p>
        <p class="fine warn-text" data-checklist-problem hidden></p>
        <p><button type="button" class="btn btn-quiet" data-open-checklist-dialog>Download or import my checklist</button></p>
        <noscript><p class="fine">Turn on JavaScript to use the checklist.</p></noscript>
      </section>
      <section class="card" aria-labelledby="edit-h">
        <h2 id="edit-h" class="h-card">Something wrong or missing?</h2>
        <p class="fine">Corrections and additions are welcome. This opens a short form on GitHub (a free account is needed) with this lookout already filled in.</p>
        <p><a class="btn" href="${editIssueUrl(r, ctx)}" rel="noopener">Suggest an edit${EXT}<span class="visually-hidden"> (opens GitHub)</span></a></p>
      </section>
    </aside>
  </div>`;
}

export function describeTower(r: TowerRecord): string {
  const st = statusWording(r.status).label.toLowerCase();
  const built = builtYear(r);
  let d = `${st === 'status unknown' ? 'Fire' : st[0]!.toUpperCase() + st.slice(1) + ' fire'} lookout in ${placeLine(r)}`;
  if (built) d += `, built ${built}`;
  d += '.';
  if (isRentable(r)) d += ' Rentable on recreation.gov.';
  d += ' Visit and stay information, history and sources.';
  return d;
}

export function renderTowerHead(r: TowerRecord, ctx: RenderContext): SafeHtml {
  const title = `${r.name}: fire lookout in ${regionName(r.region)} · Firefinder`;
  const desc = describeTower(r);
  const url = towerUrl(r.id, ctx);
  return html`<title>${title}</title>
    <meta name="description" content="${desc}">
    <link rel="canonical" href="${url}">
    ${r.fixture ? html`<meta name="robots" content="noindex">` : ''}
    <meta property="og:type" content="article">
    <meta property="og:site_name" content="Firefinder">
    <meta property="og:title" content="${r.name}">
    <meta property="og:description" content="${desc}">
    <meta property="og:url" content="${url}">`;
}

/* ---------- Map side panel ---------- */

export function renderPanel(r: TowerRecord, ctx: RenderContext, opts: { hiddenByFilters?: boolean } = {}): SafeHtml {
  const rent = isRentable(r);
  const warned = !!r.rental?.warning;
  const book = rent || warned ? safeUrl(r.rental?.url) : null;
  const occupancy = r.rental?.max_occupancy;
  const provider = r.rental?.provider ?? 'recreation.gov';
  let stay: SafeHtml;
  if (warned) {
    stay = html`<div class="panel-stay">${rentalWarning(r)}
      ${book ? html`<a class="btn" href="${book}" rel="noopener">See the listing on ${provider}${EXT}<span class="visually-hidden"> (opens another site)</span></a>` : ''}</div>`;
  } else if (rent) {
    stay = html`<div class="panel-stay"><p><strong>Rentable.</strong> ${typeof occupancy === 'number' ? `Sleeps up to ${occupancy}. ` : ''}${r.rental?.season ?? ''}</p>
      ${book ? html`<a class="btn btn-primary" href="${book}" rel="noopener">Book on ${provider}${EXT}<span class="visually-hidden"> (opens another site)</span></a>` : ''}</div>`;
  } else if (r.status === 'gone' || r.status === 'ruins') {
    stay = html`<p class="panel-stay"><strong>${r.status === 'gone' ? 'Gone: site only.' : 'Ruins only.'}</strong> Nothing to climb or rent.</p>`;
  } else {
    stay = html`<p class="panel-stay"><strong>Not rentable.</strong></p>`;
  }
  return html`
    <p class="eyebrow">Fire lookout · ${placeLine(r)}</p>
    <h2 id="panel-title" tabindex="-1">${r.name}</h2>
    ${badges(r)}
    ${opts.hiddenByFilters ? html`<p class="notice tone-unknown" role="note">${INFO}<span>Your filters hide this lookout on the map. <button type="button" class="linklike" data-action="reset-filters">Reset filters</button></span></p>` : ''}
    ${accessNotice(r, { compact: true })}
    ${movedNotice(r, ctx)}
    ${r.status_note ? html`<p class="fine status-note">${r.status_note}</p>` : ''}
    ${r.verification === 'unverified' ? html`<p class="fine warn-text">Unverified: from a single source, not yet checked.</p>` : ''}
    ${stay}
    <dl class="kv kv-panel">${factRows(r, { short: true }).map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}</dl>
    ${checklistButtons(r.id)}
    <p class="panel-actions"><a class="btn" href="${towerPath(r.id, ctx)}">Open full page<span class="visually-hidden">: ${r.name}</span></a></p>
    <p class="fine">History, photos, sources and “Suggest an edit” are on the full page.</p>`;
}

/** Shown instantly from the map feature while the full record loads. */
export function renderPanelStub(p: TowerProps, ctx: RenderContext, message: string): SafeHtml {
  const st = statusWording(p.s);
  return html`
    <p class="eyebrow">Fire lookout · ${placeLine({ county: p.c ?? null, region: p.r })}</p>
    <h2 id="panel-title" tabindex="-1">${p.n}</h2>
    <ul class="badges"><li class="badge badge-status status-${p.s}">${icon(p.k, p.s, false)}<span>${st.label}</span></li>
    ${p.rt ? html`<li class="badge badge-rent">${raw(rentBadgeSvg(14))}<span>Rentable</span></li>` : ''}</ul>
    <p class="muted" role="status">${message}</p>
    <p class="panel-actions"><a class="btn" href="${towerPath(p.i, ctx)}">Open full page</a></p>`;
}

