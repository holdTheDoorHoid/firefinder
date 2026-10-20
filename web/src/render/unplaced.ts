/**
 * "Lookouts we can't place yet": the lookouts our sources name but none places, one page per
 * state, province or territory plus an index grouped by country (DESIGN.md 3.5, "Approximate
 * locations"). Pure functions returning escaped
 * HTML, used by scripts/prerender.ts at build time and by the page script in dev.
 *
 * Each lookout shows its name, county, the sources that list it (linked), what the gazetteer had
 * (USGS GNIS in the US, Canada's CGNDB: a town of the name as a hint, the lookout on the map it may be), and a
 * "Suggest a location" button that opens the site's Suggest-an-edit form on GitHub, filled in.
 */
import { formatCount } from '../lib/format.ts';
import { html, raw, type SafeHtml } from '../lib/html.ts';
import type { Meta, UnplacedFile, UnplacedLookout } from '../lib/types.ts';
import { regionName } from '../lib/vocab.ts';
import { countryOf, regionGroups, regionKind, regionWithCountry } from '../lib/regions.ts';
import { externalLink, placeLine, sourceShortName, towerPath, type RenderContext } from './tower.ts';

export type UnplacedContext = Pick<RenderContext, 'base' | 'siteUrl' | 'repo' | 'sources'>;

/** The page path for a state's list ("/firefinder/unplaced/pa/"), or the index. */
export function unplacedPath(region: string | null, ctx: Pick<RenderContext, 'base'>): string {
  return `${ctx.base}unplaced/${region ? `${region.toLowerCase()}/` : ''}`;
}

/** States with lookouts listed, by name. Out-of-scope entries do not count. */
export function unplacedStates(file: UnplacedFile): [string, number][] {
  const n = new Map<string, number>();
  for (const u of file.lookouts) if (u.region && !u.out_of_scope) n.set(u.region, (n.get(u.region) ?? 0) + 1);
  return [...n.entries()].sort((a, b) => regionName(a[0]).localeCompare(regionName(b[0])));
}

/** Every state with a page: any entry at all, in scope or not. */
export function unplacedPageStates(file: UnplacedFile): string[] {
  return [...new Set(file.lookouts.map((u) => u.region).filter((r): r is string => !!r))].sort();
}

function place(u: Pick<UnplacedLookout, 'county' | 'region'>): string {
  if (u.county) return placeLine({ county: u.county, region: u.region ?? '' });
  const unit = countryOf(u.region) === 'US' || !countryOf(u.region) ? 'county' : 'district';
  return `${regionWithCountry(u.region ?? '')}, ${unit} not recorded`;
}

const CLASS_WORDS: Record<string, string> = { Summit: 'summit', Ridge: 'ridge', Gap: 'gap', Pillar: 'rock pillar', Cliff: 'cliff', Bench: 'bench',
  // Canada's CGNDB generic terms
  Mount: 'mountain', Mountain: 'mountain', Hill: 'hill', Peak: 'peak', Lookout: 'lookout point', Lookoff: 'lookout point' };

/** The place a source files the lookout under, when it gives one: a district office or a settlement
 * whose position it gives (firelookout.ca), or the forest, association or fire district a Canadian list
 * names. */
function hintText(u: UnplacedLookout, ctx: UnplacedContext): SafeHtml | string {
  const h = u.hint;
  if (!h?.name) return '';
  const at = typeof h.lat === 'number' && typeof h.lon === 'number' ? html` <a href="${mapAt(h.lat, h.lon, ctx, 10)}">See ${h.name} on the map</a>.` : '';
  if (h.why === 'district_office') return html` The source files it under <strong>${h.name}</strong>, the old district office, and gives the office's position, not the tower's.${at}`;
  if (h.why === 'settlement') return html` The source gives the centre of <strong>${h.name}</strong>, not the tower's position.${at}`;
  return html` Its source files it under <strong>${h.name}</strong>.${at}`;
}

function sourceList(u: UnplacedLookout, ctx: UnplacedContext): string {
  return [...new Set(u.records.map((r) => sourceShortName(r.source, ctx as RenderContext)))].join(', ');
}

/** The Suggest-an-edit form (.github/ISSUE_TEMPLATE/edit.yml), filled in for a lookout with no place. */
export function suggestLocationUrl(u: UnplacedLookout, ctx: UnplacedContext): string {
  const where = place(u);
  const q = new URLSearchParams({
    template: 'edit.yml',
    title: `Location: ${u.name} (${u.county ? `${where}` : regionName(u.region ?? '')})`,
    tower_name: u.name,
    page_url: `${ctx.siteUrl}unplaced/${(u.region ?? '').toLowerCase()}/#${u.anchor}`,
    topic: 'This lookout is missing from Firefinder',
    whats_wrong: `${u.name} (${where}) is listed by ${sourceList(u, ctx)}, but no source says where it stood, so it is not on the Firefinder map.`,
    correct_info: 'Where it stood (coordinates, a map link, or the hill or road it was on): ',
  });
  return `https://github.com/${ctx.repo}/issues/new?${q.toString()}`;
}

function mapAt(lat: number, lon: number, ctx: UnplacedContext, zoom = 12): string {
  return `${ctx.base}?at=${zoom}/${lat.toFixed(4)}/${lon.toFixed(4)}`;
}

/** Why it is not on the map, and what the gazetteer offers, in plain words. */
export function reasonText(u: UnplacedLookout, ctx: UnplacedContext): SafeHtml {
  const state = regionName(u.region ?? '');
  const feature = u.feature?.name ?? 'the high point of its name';
  const canada = countryOf(u.region) === 'CA';
  // Canada's gazetteer (CGNDB): with no district or county, the whole province is searched.
  const unitWords = canada ? (u.county ? 'the district' : `all of ${state}`) : 'the county';
  const gazetteer = canada ? 'The Canadian Geographical Names Database' : 'The USGS gazetteer';
  switch (u.gnis) {
    case 'town': {
      const t = u.town;
      if (!t) return html`No hill or ridge of this name in the county, only several towns of the name.`;
      const see = typeof t.lat === 'number' && typeof t.lon === 'number' ? html` <a href="${mapAt(t.lat, t.lon, ctx)}">See ${t.name} on the map</a>.` : '';
      return html`No hill or ridge of this name in the county, but there is a town: <strong>${t.name}</strong>. Many fire towers were named for the nearest town.${see}`;
    }
    case 'none':
      return canada
        ? html`${gazetteer} has no hill, mountain or ridge of this name in ${unitWords}. Many lookouts were named for a lake, a river or the nearest town.${hintText(u, ctx)}`
        : html`${gazetteer} has no hill, ridge or town of this name in the county.`;
    case 'no_county':
      return html`No source says which county it was in, so we cannot look it up.`;
    case 'county_unknown':
      return canada
        ? html`Its source files it under “${u.county ?? ''}”, a unit the Canadian gazetteer cannot be searched by, so we cannot look it up.${hintText(u, ctx)}`
        : html`We could not find the county “${u.county ?? ''}” in ${state}, so we cannot look it up.`;
    case 'ambiguous': {
      const c = u.candidates ?? [];
      const where = canada ? (u.county ? 'The district' : state) : 'The county';
      return html`${where} has ${c.length} places of this name (${c.map((f, i) => html`${i ? ', ' : ''}${f.name}, a ${CLASS_WORDS[f.class] ?? f.class.toLowerCase()}`)}), so we cannot tell which one it stood on.${canada ? hintText(u, ctx) : ''}`;
    }
    case 'near_mapped_lookout':
      return u.near && u.near_name
        ? html`A lookout already on the map stands ${typeof u.near_m === 'number' ? `${formatCount(u.near_m)} m` : 'close'} from ${feature}: <a href="${towerPath(u.near, ctx)}">${u.near_name}</a>. It may be this one under another name.`
        : html`A lookout already on the map stands at ${feature}; it may be this one under another name.`;
    case 'similar_name_on_map':
      return u.similar && u.similar_name
        ? html`It may be <a href="${towerPath(u.similar, ctx)}">${u.similar_name}</a>, already on the map with a similar name.`
        : html`A lookout with a similar name is already on the map; it may be this one.`;
    case 'same_name_on_map':
      return html`Several lookouts of this name are already on the map in ${state}; this listing may be one of them.`;
    case 'same_source_twice':
      return html`One source lists two lookouts at ${feature}; we cannot tell them apart.`;
    case 'rental_unmatched':
      return html`On the Forest Fire Lookout Association’s rentals list, but we could not match it to a lookout.`;
    case 'no_name':
      return html`Its name says only “lookout” or “tower”, so there is nothing to look up.`;
    case 'not_covered':
      return html`No source gives its position, and Firefinder has no gazetteer to look it up in here yet.${hintText(u, ctx)}`;
    default:
      return html`No source says where it stood.`;
  }
}

const EXT = raw('<svg class="ext-icon" width="14" height="14" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M9 2h5v5M14 2 7.5 8.5M12 9.5V13a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>');

function entry(u: UnplacedLookout, ctx: UnplacedContext): SafeHtml {
  return html`<li class="up-item" id="${u.anchor}">
    <h3 class="up-name">${u.name}</h3>
    <p class="up-place">${place(u)}</p>
    <p class="up-sources"><span class="up-label">Listed by</span> ${u.records.map((r, i) => html`${i ? ', ' : ''}${r.url ? externalLink(r.url, sourceShortName(r.source, ctx as RenderContext)) : sourceShortName(r.source, ctx as RenderContext)}`)}</p>
    <p class="up-hint">${reasonText(u, ctx)}</p>
    <p class="up-action"><a class="btn" href="${suggestLocationUrl(u, ctx)}" rel="noopener">Suggest a location${EXT}<span class="visually-hidden"> for ${u.name} (opens GitHub)</span></a></p>
  </li>`;
}

export interface UnplacedHead {
  title: string;
  description: string;
}

export function unplacedHead(file: UnplacedFile, region: string | null): UnplacedHead {
  if (!region) {
    return {
      title: "Lookouts we can't place yet · Firefinder",
      description: `${formatCount(file.count)} fire lookouts our sources name but none places on a map, by state, province and territory. Know where one stood? Suggest a location.`,
    };
  }
  const n = file.lookouts.filter((u) => u.region === region && !u.out_of_scope).length;
  return {
    title: `Lookouts we can't place yet in ${regionName(region)} · Firefinder`,
    description: `${formatCount(n)} fire lookouts in ${regionName(region)} that our sources name but none places on a map. Know where one stood? Suggest a location.`,
  };
}

function approxLine(meta: Pick<Meta, 'counts'> | null, region: string | null, ctx: UnplacedContext): SafeHtml | string {
  const n = region ? meta?.counts.approximate_by_region?.[region] ?? 0 : meta?.counts.approximate ?? 0;
  if (!n) return '';
  const where = region ? ` in ${regionName(region)}` : '';
  const link = region ? `${ctx.base}?state=${region}` : ctx.base;
  const gz = region && countryOf(region) === 'CA' ? "Canada's gazetteer has exactly one hill, mountain or ridge of the same name in their district (or, when no source names the district, in the whole province or territory)"
    : region ? 'the USGS gazetteer has exactly one summit, ridge or similar high point of the same name in their county'
      : 'the gazetteer (USGS GNIS in the United States, the CGNDB in Canada) has exactly one summit, ridge or similar high point of the same name in their county or district';
  return html`<p>${formatCount(n)} more${where} are on <a href="${link}">the map</a> at <strong>approximate locations</strong>: no source gives their position either, but ${gz}, so they are shown there with a dashed marker and an Unverified badge.</p>`;
}

/** The index: what this is, how we tried, and the states. */
export function unplacedIndexMain(file: UnplacedFile, meta: Pick<Meta, 'counts'> | null, ctx: UnplacedContext): SafeHtml {
  const states = unplacedStates(file);
  return html`<p class="eyebrow">Help wanted</p>
  <h1>Lookouts we can't place yet</h1>
  <p class="lede">${formatCount(file.count)} fire lookouts are named by at least one of our sources, but no source says where they stood, so they are not on the map. If you know where one stood, each has a <strong>Suggest a location</strong> button.</p>
  ${approxLine(meta, null, ctx)}
  <h2>How we looked</h2>
  <p>For each one in the United States we searched the USGS Geographic Names Information System, the federal list of place names, for a hill, ridge, gap or cliff of the same name in the same county. Where it has exactly one, the lookout goes on the map there, marked approximate. A town of that name is not enough: many towers were named for the nearest town but stood miles away, so the town is shown here as a hint instead. In Canada we search the Canadian Geographical Names Database the same way, for a hill, mountain or ridge of the same name in the lookout's district or county; most Canadian lists name a forest or an association instead of a district, and then the hill must be the only one of its name in the whole province or territory.</p>
  ${regionGroups(states.map(([r]) => r)).map((g) => {
    const n = new Map(states);
    return html`<h2>${g.country === 'US' ? 'By state' : `${g.name}: by province and territory`}</h2>
  <ul class="up-states">${g.regions.map((r) => html`<li><a href="${unplacedPath(r.code, ctx)}">${r.name}</a> <span class="up-count">${formatCount(n.get(r.code) ?? 0)}</span></li>`)}</ul>`;
  })}`;
}

/** One state's list: every lookout we cannot place, alphabetical, then the ones out of scope. */
export function unplacedStateMain(file: UnplacedFile, region: string, meta: Pick<Meta, 'counts'> | null, ctx: UnplacedContext): SafeHtml {
  const all = file.lookouts.filter((u) => u.region === region);
  const shown = all.filter((u) => !u.out_of_scope);
  const out = all.filter((u) => u.out_of_scope);
  const state = regionName(region);
  return html`<nav class="crumbs" aria-label="Breadcrumb"><ol>
    <li><a href="${ctx.base}">Map</a></li>
    <li><a href="${unplacedPath(null, ctx)}">Lookouts we can't place yet</a></li>
    <li><span aria-current="page">${state}</span></li>
  </ol></nav>
  <p class="eyebrow">Help wanted</p>
  <h1>Lookouts we can't place yet in ${state}</h1>
  <p class="lede">${shown.length
    ? html`${formatCount(shown.length)} ${shown.length === 1 ? 'lookout' : 'lookouts'} in ${state} ${shown.length === 1 ? 'is' : 'are'} named by our sources, but none says where ${shown.length === 1 ? 'it' : 'they'} stood, so ${shown.length === 1 ? 'it is' : 'they are'} not on the map. Know where one stood? Use its <strong>Suggest a location</strong> button: it opens a short form on GitHub with the lookout filled in.`
    : html`Every lookout our sources name in ${state} is on the map.`}</p>
  ${countryOf(region) !== 'US' && shown.length ? html`<p>This ${regionKind(region)} is in Canada. A lookout here goes on the map at an approximate location only when the Canadian Geographical Names Database has exactly one hill, mountain or ridge of its name in its district or county, or, when no source names the district, in the whole ${regionKind(region)}. Most Canadian lookouts were named for a lake or a town, so many stay on this list.</p>` : ''}
  ${approxLine(meta, region, ctx)}
  ${shown.length ? html`<h2 class="visually-hidden">The list</h2><ol class="up-list">${shown.map((u) => entry(u, ctx))}</ol>` : ''}
  ${out.length
    ? html`<details class="up-out"><summary>Also listed, but not counted as fire lookouts (${formatCount(out.length)})</summary>
        <p class="fine">Sources list these too, but say they were never built, were not fire lookouts, or are not confirmed as lookouts, so they would stay off the map even with a position.</p>
        <ul class="plain up-out-list">${out.map((u) => html`<li id="${u.anchor}"><strong>${u.name}</strong>, ${place(u)}. <span class="fine">${u.out_of_scope}. Listed by ${u.records.map((r, i) => html`${i ? ', ' : ''}${r.url ? externalLink(r.url, sourceShortName(r.source, ctx as RenderContext)) : sourceShortName(r.source, ctx as RenderContext)}`)}.</span></li>`)}</ul>
      </details>`
    : ''}
  <p class="up-back"><a href="${unplacedPath(null, ctx)}">All ${countryOf(region) === 'CA' ? 'provinces, territories and states' : 'states, provinces and territories'}</a> · <a href="${ctx.base}?state=${region}">${state} on the map</a></p>`;
}
