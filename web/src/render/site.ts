/** Site-wide fragments filled in at build time (and in dev, in the browser). */
import { html, raw, safeUrl, type SafeHtml } from '../lib/html.ts';
import { formatCount, formatDate } from '../lib/format.ts';
import { markerSvg, type Fill, type Shape } from '../lib/icons.ts';
import type { Meta } from '../lib/types.ts';

export function sourcesRows(meta: Pick<Meta, 'sources'>): SafeHtml {
  return html`${meta.sources.map((s) => {
    const url = safeUrl(s.url);
    return html`<tr id="source-${s.id}">
      <th scope="row">${url ? html`<a href="${url}" rel="noopener">${s.title}</a>` : s.title}${s.retrieved ? html`<span class="sub">Retrieved ${formatDate(s.retrieved)}</span>` : ''}</th>
      <td>${s.license ?? 'Not stated'}</td>
      <td class="credit-line">${s.credit ?? s.title}</td>
      <td class="num">${typeof s.towers === 'number' ? formatCount(s.towers) : '–'}</td>
    </tr>`;
  })}`;
}

const SHAPE_ROWS: [Shape, string][] = [
  ['tri', 'Triangle: a cab or open platform on a tower'],
  ['house', 'House: a lookout building: a ground-level cab, two or three stories, a cab on a rooftop, or a trailer'],
  ['circle', 'Circle: type not known'],
  ['diamond', 'Diamond: no structure (a summit camp, lookout tree or bare lookout point). Off until you switch them on in Filters'],
];
const FILL_ROWS: [Fill, string][] = [
  ['solid', 'Solid: still standing'],
  ['hollow', 'Hollow: gone, only the site is left'],
  ['ruin', 'Hollow with a dot: ruins, footings or remains only'],
  ['half', 'Half filled: moved to a new site, a replica, or status unknown'],
];

export function mapKey(): SafeHtml {
  return html`<div class="map-key">
    <ul class="key-list" aria-label="Marker shapes">${SHAPE_ROWS.map(([s, label]) => html`<li>${raw(markerSvg(s, 'solid', { size: 22 }))}<span>${label}</span></li>`)}</ul>
    <ul class="key-list" aria-label="Marker fills">${FILL_ROWS.map(([f, label]) => html`<li>${raw(markerSvg('tri', f, { size: 22 }))}<span>${label}</span></li>`)}
      <li>${raw(markerSvg('tri', 'solid', { size: 22, rentable: true }))}<span>Amber dot at the top right: you can rent it (bookable on recreation.gov)</span></li>
      <li>${raw(markerSvg('tri', 'hollow', { size: 22, approximate: true }))}<span>Dashed outline: approximate location. No source says where it stood, so it is shown on the hill or ridge of its name in its county</span></li>
    </ul>
    <p class="fine">Numbered circles are groups of nearby lookouts. Zoom in or select one to spread them out.</p>
  </div>`;
}

export function fixtureBanner(meta: Pick<Meta, 'fixtures'>): SafeHtml {
  if (!meta.fixtures) return html``;
  return html`<p class="fixture-banner" role="note"><strong>Sample data.</strong> This site is showing a few test entries while the real lookout database is being built. Do not plan a trip from them.</p>`;
}

export function takedownEmail(email: string | null | undefined): SafeHtml {
  if (!email || !/^[^@\s"<>]+@[^@\s"<>]+$/.test(email)) return html``;
  return html`<p>Prefer not to use GitHub? Email <a href="mailto:${email}">${email}</a> with the same details.</p>`;
}
