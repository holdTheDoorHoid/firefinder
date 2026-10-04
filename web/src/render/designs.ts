/**
 * The tower designs guide (/designs/): one section per standard design with a schematic,
 * the facts and their sources, and every lookout on Firefinder recorded as that design.
 * Built from designs.json (pipeline/build_site_data.py) at build time by
 * scripts/prerender.ts, and in the browser in development.
 */
import { formatCount } from '../lib/format.ts';
import { html, raw, safeUrl, type SafeHtml } from '../lib/html.ts';
import { fillFor, markerSvg, shapeFor } from '../lib/icons.ts';
import type { Design, DesignSource, DesignTower, DesignsFile } from '../lib/types.ts';
import { regionName, statusWording } from '../lib/vocab.ts';
import { schematicSvg } from './schematics.ts';

export interface DesignsContext {
  base: string;
  repo: string;
}

const EXT = raw('<svg class="ext-icon" width="12" height="12" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M9 2h5v5M14 2 7.5 8.5M12 9.5V13a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>');

/** Lists longer than this start folded. */
const OPEN_UP_TO = 12;

function idOk(id: string): boolean {
  return /^[a-z0-9_]+$/.test(id);
}

function sourceItem(s: DesignSource): SafeHtml {
  const url = safeUrl(s.url);
  const plans = (s.supports ?? []).includes('plans');
  return html`<li>${plans ? html`<span class="ds-plans">Original drawings:</span> ` : ''}${url ? html`<a href="${url}" rel="noopener">${s.title}${EXT}</a>` : s.title}${s.publisher ? html`<span class="ds-pub">${s.publisher}</span>` : ''}${s.licence ? html`<span class="ds-lic">${s.licence}</span>` : ''}</li>`;
}

function statusSummary(by: Record<string, number>): string {
  const order = ['standing', 'gone', 'ruins', 'relocated', 'replica', 'unknown'];
  return Object.entries(by)
    .sort((a, b) => order.indexOf(a[0]) - order.indexOf(b[0]))
    .map(([s, n]) => `${formatCount(n)} ${statusWording(s).label.toLowerCase()}`)
    .join(', ');
}

function towerItem(t: DesignTower, ctx: DesignsContext): SafeHtml {
  if (!/^[a-z]{2}-[a-z0-9]{1,3}-[a-z0-9-]+$/.test(t.i)) return html``;
  const st = statusWording(t.s);
  return html`<li><a href="${ctx.base}t/${t.i}/">${raw(markerSvg(shapeFor(t.k), fillFor(t.s), { size: 16, className: 'marker-icon' }))}<span class="dt-name">${t.n}</span></a> <span class="dt-status">${st.label}</span>${t.m?.length ? html` <span class="dt-model">${t.m.join(', ')}</span>` : ''}${t.w ? html`<span class="dt-words">Recorded as: “${t.w}”</span>` : ''}</li>`;
}

function towersBlock(d: Design, ctx: DesignsContext): SafeHtml {
  if (!d.count) {
    return html`<p class="muted">No lookout on Firefinder is recorded as this design yet. Know one? Use “Suggest an edit” on its page.</p>`;
  }
  const byState = new Map<string, DesignTower[]>();
  for (const t of d.towers) byState.set(t.r, [...(byState.get(t.r) ?? []), t]);
  const states = [...byState.keys()].sort((a, b) => regionName(a).localeCompare(regionName(b)));
  const list = html`${states.map(
    (st) => html`<h4 class="dt-state">${regionName(st)} <span class="muted">(${formatCount(byState.get(st)!.length)})</span></h4>
      <ul class="dt-list">${byState.get(st)!.map((t) => towerItem(t, ctx))}</ul>`,
  )}`;
  const mapUrl = `${ctx.base}?design=${d.id}`;
  return html`<p class="dt-count">${statusSummary(d.by_status)}. <a class="btn btn-quiet btn-small" href="${mapUrl}">Show ${d.count === 1 ? 'it' : `all ${formatCount(d.count)}`} on the map</a></p>
    ${d.count <= OPEN_UP_TO ? html`<div class="dt-all">${list}</div>` : html`<details class="dt-all"><summary>List all ${formatCount(d.count)}, by state</summary>${list}</details>`}`;
}

function factsList(d: Design): SafeHtml {
  const rows: [string, unknown][] = [
    ['Years in use', d.years_in_use?.text],
    ['Cab', d.cab_size],
    ['On what', d.tower_heights],
    ['Built of', d.materials],
    ['Made by', d.makers?.length ? d.makers.join('; ') : null],
    ['Models and plans', d.models?.length ? d.models.join('; ') : null],
    ['Where', d.regions],
  ];
  const shown = rows.filter(([, v]) => typeof v === 'string' && v.trim());
  return html`<dl class="kv kv-design">${shown.map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}</dl>`;
}

export function designSection(d: Design, ctx: DesignsContext): SafeHtml {
  if (!idOk(d.id)) return html``;
  const svg = schematicSvg(d.schematic, d.name);
  return html`<section class="design" id="${d.id}" aria-labelledby="${d.id}-h">
    <div class="design-top">
      ${svg ? html`<figure class="design-fig">${raw(svg)}<figcaption>Schematic, not to scale</figcaption></figure>` : ''}
      <div class="design-intro">
        <h2 id="${d.id}-h">${d.name}</h2>
        ${d.aka?.length ? html`<p class="design-aka">Also called ${d.aka.join(', ')}</p>` : ''}
        ${d.summary ? html`<p class="design-summary">${d.summary}</p>` : ''}
        <p class="design-count"><strong>${formatCount(d.count)}</strong> ${d.count === 1 ? 'lookout' : 'lookouts'} on Firefinder</p>
      </div>
    </div>
    ${factsList(d)}
    ${d.features?.length ? html`<h3 class="h-small">How to recognise it</h3><ul class="design-features">${d.features.map((x) => html`<li>${x}</li>`)}</ul>` : ''}
    ${d.uncertain ? html`<details class="design-uncertain"><summary>Where sources disagree</summary><p>${d.uncertain}</p></details>` : ''}
    <h3 class="h-small">On Firefinder</h3>
    ${towersBlock(d, ctx)}
    ${d.sources?.length ? html`<h3 class="h-small">Sources</h3><ul class="design-sources">${d.sources.map(sourceItem)}</ul>` : ''}
  </section>`;
}

export function designsToc(file: DesignsFile): SafeHtml {
  return html`<nav class="toc design-toc" aria-label="Designs on this page"><ul>${file.designs
    .filter((d) => idOk(d.id))
    .map((d) => html`<li><a href="#${d.id}">${d.name}</a> <span class="muted">${formatCount(d.count)}</span></li>`)}</ul></nav>`;
}

export function designsCoverage(file: DesignsFile): SafeHtml {
  const c = file.coverage;
  const unmatched = c.with_design_text - c.recognised;
  return html`<div class="notice tone-unknown design-coverage" role="note"><div>
    <p class="notice-title">How many we can tell</p>
    <p>Firefinder can name a standard design for <strong>${formatCount(c.recognised)}</strong> of its ${formatCount(c.total)} lookouts (${((c.recognised / Math.max(1, c.total)) * 100).toFixed(0)}%). For most of the rest, no source we use records the plan.${unmatched > 0 ? ` Another ${formatCount(unmatched)} have a design described in words we could not match to one of the plans below.` : ''} A lookout whose records describe more than one structure (an earlier cab and today's) is listed under each design they name, with the record's own words.</p>
  </div></div>`;
}

export function designsMain(file: DesignsFile, ctx: DesignsContext): SafeHtml {
  return html`${designsCoverage(file)}${designsToc(file)}${file.designs.map((d) => designSection(d, ctx))}
    ${file.sources?.length ? html`<section class="design-general" aria-labelledby="dg-h"><h2 id="dg-h">More about lookout designs</h2><ul class="design-sources">${file.sources.map(sourceItem)}</ul>${file.note ? html`<p class="fine">${file.note}</p>` : ''}</section>` : ''}`;
}
