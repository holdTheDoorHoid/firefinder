/**
 * "Structure types" on the designs page (/designs/#structure-types): one plain-language
 * paragraph per kind of lookout, with how many Firefinder has of each, the words the sources
 * use for it, and what they are built of. Rendered from structure_kinds.json
 * (pipeline/build_site_data.py, from data/structure_kinds.json) by scripts/prerender.ts at
 * build time, and in the browser in development. Kept apart from render/designs.ts so the two
 * sections can change independently.
 */
import { formatCount } from '../lib/format.ts';
import { html, raw, type SafeHtml } from '../lib/html.ts';
import { markerSvg, shapeFor } from '../lib/icons.ts';
import type { StructureKind, StructureKindsFile } from '../lib/types.ts';

export interface StructuresContext {
  base: string;
}

const ID_RE = /^[a-z0-9_]+$/;

function plural(n: number, one: string, many: string): string {
  return `${formatCount(n)} ${n === 1 ? one : many}`;
}

/** The map, showing just this kind ("?kind=rooftop"; sites with no structure: switched on, structures off). */
function mapUrl(k: StructureKind, ctx: StructuresContext): string {
  return k.group === 'no_structure' ? `${ctx.base}?ns=1&kind=none` : `${ctx.base}?kind=${k.id}`;
}

function kindItem(k: StructureKind, ctx: StructuresContext): SafeHtml {
  if (!ID_RE.test(k.id)) return html``;
  const words = (k.source_words ?? []).filter((w) => w.toLowerCase() !== k.label.toLowerCase()).slice(0, 8);
  return html`<li class="st-kind" id="kind-${k.id}">
    <h4 class="st-name">${raw(markerSvg(shapeFor(k.id), 'solid', { size: 22, className: 'marker-icon' }))}<span>${k.label}</span></h4>
    ${k.about ? html`<p>${k.about}</p>` : ''}
    ${words.length ? html`<p class="st-words">Sources write: ${words.map((w, i) => html`${i ? ', ' : ''}“${w}”`)}</p>` : ''}
    <p class="st-count">${plural(k.count, 'lookout site', 'lookout sites')}${k.count ? html` · <a href="${mapUrl(k, ctx)}">Show on the map</a>` : ''}</p>
  </li>`;
}

export function structuresSection(file: StructureKindsFile, ctx: StructuresContext): SafeHtml {
  const groups = file.groups ?? [];
  const mats = (file.materials ?? []).filter((m) => ID_RE.test(m.id));
  const recorded = mats.reduce((n, m) => n + m.count, 0);
  const structures = file.counts?.structures ?? groups.find((g) => g.id === 'structure')?.count ?? 0;
  return html`<section class="structure-types" id="structure-types" aria-labelledby="st-h">
    <h2 id="st-h">Structure types</h2>
    <p class="st-lede">Before the plan comes the shape. Firefinder sorts every lookout site into one of these kinds from what its sources say, and the marker shape on the map shows which.</p>
    ${groups.map((g) => {
      const kinds = file.kinds.filter((k) => k.group === g.id);
      if (!kinds.length) return html``;
      return html`<div class="st-group st-group-${ID_RE.test(g.id) ? g.id : 'other'}">
        <h3 class="st-group-h">${g.label} <span class="muted">${formatCount(g.count)}</span></h3>
        ${g.about ? html`<p>${g.about}</p>` : ''}
        ${g.shown_by_default === false ? html`<p class="fine">To see them, open Filters on the map and tick “Show sites with no structure”. Until you do, they are left out of the map's counts, including “Lookouts standing” in a year.</p>` : ''}
        <ul class="st-list">${kinds.map((k) => kindItem(k, ctx))}</ul>
      </div>`;
    })}
    ${mats.length
      ? html`<div class="st-group st-materials">
        <h3 class="st-group-h">What they are built of</h3>
        <p>For a tower, the tower itself; for a building, its walls. It comes from the sources' own words (“Stone Tower”, “a 100-foot steel tower”, OpenStreetMap's material tags) or, failing those, from a recognised design: an Aermotor is a steel tower and an L-4 ground cab is wood. So far that gives a material for ${formatCount(recorded)} of the ${formatCount(structures)} towers and buildings.</p>
        <ul class="st-mats">${mats.map((m) => html`<li><strong>${m.label}</strong> <span class="muted">${formatCount(m.count)}</span>${m.about ? html`<span class="st-mat-about">${m.about}</span>` : ''}</li>`)}</ul>
      </div>`
      : ''}
    ${(file.roles ?? []).length
      ? html`<div class="st-group st-roles">
        <h3 class="st-group-h">Not a kind of building</h3>
        ${(file.roles ?? []).map((r) => html`<p><strong>${r.label}.</strong> ${r.about ?? ''}</p>`)}
      </div>`
      : ''}
  </section>`;
}
