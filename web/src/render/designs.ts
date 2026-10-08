/**
 * The tower designs guide (/designs/): the standard plans grouped by what they are built of
 * (wood, log, steel, stone...) and, within that, by Forest Service region. Each design has a
 * schematic, the facts and their sources, links to the original drawings (scans hosted by the
 * Forest Fire Lookout Association), and every lookout on Firefinder recorded as that design,
 * standing ones first. Firefinders, lightning protection and plan books come last, under
 * "Equipment and reference".
 *
 * Built from designs.json (pipeline/build_site_data.py) at build time by scripts/prerender.ts,
 * and in the browser in development.
 *
 * The page has three parts, each filled into its own placeholder in designs/index.html at
 * prerender (and in the browser in development): designsMain (the designs), then the separate
 * "Structure types" section (render/structures.ts), then designsEnd (Equipment and reference, and
 * the general sources). DesignsExtras.toc adds contents-list entries for sections other modules
 * render, such as Structure types.
 */
import { formatCount } from '../lib/format.ts';
import { html, raw, safeUrl, type SafeHtml } from '../lib/html.ts';
import { fillFor, markerSvg, shapeFor } from '../lib/icons.ts';
import type { Design, DesignGroup, DesignPlan, DesignReference, DesignSource, DesignTower, DesignsFile } from '../lib/types.ts';
import { regionName, statusWording } from '../lib/vocab.ts';
import { schematicSvg } from './schematics.ts';

export interface DesignsContext {
  base: string;
  repo: string;
}

export interface DesignsExtras {
  /** Contents-list entries for sections other modules render on the page: [anchor id, label]. */
  toc?: [string, string][];
}

const EXT = raw('<svg class="ext-icon" width="12" height="12" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M9 2h5v5M14 2 7.5 8.5M12 9.5V13a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>');

/** Lists longer than this start folded. */
const OPEN_UP_TO = 12;

/** Used when designs.json has no "groups" (and for any material or region it leaves out). */
const MATERIALS: DesignGroup[] = [
  { id: 'wood', label: 'Wooden cabs, houses and towers' },
  { id: 'log', label: 'Log lookouts' },
  { id: 'steel', label: 'Steel towers and cabs' },
  { id: 'stone', label: 'Stone lookouts' },
  { id: 'concrete', label: 'Concrete lookouts' },
  { id: 'mixed', label: 'Mixed construction' },
];
const REGIONS: DesignGroup[] = [
  { id: 'national', label: 'Nationwide' },
  { id: 'R1', label: 'Northern Rockies (Forest Service Region 1)' },
  { id: 'R2', label: 'Rocky Mountains (Region 2)' },
  { id: 'R3', label: 'Southwest (Region 3)' },
  { id: 'R4', label: 'Intermountain (Region 4)' },
  { id: 'R5', label: 'California (Region 5)' },
  { id: 'R6', label: 'Pacific Northwest (Region 6)' },
  { id: 'R8', label: 'South (Region 8)' },
  { id: 'R9', label: 'East and Lake States (Region 9)' },
];
const PART_LABEL: Record<string, string> = { cab: 'Cab', house: 'Ground house', tower: 'Tower', whole: 'Whole lookout' };
const STATUS_ORDER = ['standing', 'gone', 'ruins', 'relocated', 'replica', 'unknown'];

function idOk(id: string): boolean {
  return /^[a-z0-9_]+$/.test(id);
}

function mergeGroups(given: DesignGroup[] | undefined, fallback: DesignGroup[]): DesignGroup[] {
  const out = (given ?? []).filter((g) => g && typeof g.id === 'string' && idOk(g.id.toLowerCase()));
  for (const g of fallback) if (!out.some((o) => o.id === g.id)) out.push(g);
  return out;
}

function sourceItem(s: DesignSource): SafeHtml {
  const url = safeUrl(s.url);
  const plans = (s.supports ?? []).includes('plans');
  return html`<li>${plans ? html`<span class="ds-plans">Original drawings:</span> ` : ''}${url ? html`<a href="${url}" rel="noopener">${s.title}${EXT}</a>` : s.title}${s.publisher ? html`<span class="ds-pub">${s.publisher}</span>` : ''}${s.licence ? html`<span class="ds-lic">${s.licence}</span>` : ''}</li>`;
}

function planLink(p: DesignPlan): SafeHtml {
  const url = safeUrl(p.url);
  if (!url) return html``;
  return html`<li><a href="${url}" rel="noopener">${p.title}${EXT}</a>${p.note ? html` <span class="dp-note">${p.note}</span>` : ''}</li>`;
}

function statusSummary(by: Record<string, number>): string {
  return Object.entries(by)
    .sort((a, b) => STATUS_ORDER.indexOf(a[0]) - STATUS_ORDER.indexOf(b[0]))
    .map(([s, n]) => `${formatCount(n)} ${statusWording(s).label.toLowerCase()}`)
    .join(', ');
}

function towerItem(t: DesignTower, ctx: DesignsContext): SafeHtml {
  if (!/^[a-z]{2}-[a-z0-9]{1,3}-[a-z0-9-]+$/.test(t.i)) return html``;
  const st = statusWording(t.s);
  return html`<li><a href="${ctx.base}t/${t.i}/">${raw(markerSvg(shapeFor(t.k), fillFor(t.s), { size: 16, className: 'marker-icon' }))}<span class="dt-name">${t.n}</span></a> <span class="dt-status">${st.label}</span>${t.m?.length ? html` <span class="dt-model">${t.m.join(', ')}</span>` : ''}${t.w ? html`<span class="dt-words">Recorded as: “${t.w}”</span>` : ''}</li>`;
}

function byState(towers: DesignTower[], ctx: DesignsContext): SafeHtml {
  const groups = new Map<string, DesignTower[]>();
  for (const t of towers) groups.set(t.r, [...(groups.get(t.r) ?? []), t]);
  const states = [...groups.keys()].sort((a, b) => regionName(a).localeCompare(regionName(b)));
  return html`${states.map(
    (st) => html`<h6 class="dt-state">${regionName(st)} <span class="muted">(${formatCount(groups.get(st)!.length)})</span></h6>
      <ul class="dt-list">${groups.get(st)!.map((t) => towerItem(t, ctx))}</ul>`,
  )}`;
}

function memberLinks(d: Design): SafeHtml {
  const ms = (d.members ?? []).filter((m) => idOk(m.id));
  if (!ms.length) return html``;
  return html`<p class="design-members"><span class="dm-label">In this family:</span> ${ms.map(
    (m, i) => html`${i ? ' · ' : ''}<a href="#${m.id}">${m.name}</a> <span class="muted">${formatCount(m.count)}</span>`,
  )}</p>`;
}

function towersBlock(d: Design, ctx: DesignsContext): SafeHtml {
  if (!d.count) {
    return html`<p class="muted">No lookout on Firefinder is recorded as this design yet. Know one? Use “Suggest an edit” on its page.</p>`;
  }
  const mapUrl = `${ctx.base}?design=${d.id}`;
  const head = html`<p class="dt-count">${statusSummary(d.by_status)}. <a class="btn btn-quiet btn-small" href="${mapUrl}">Show ${d.count === 1 ? 'it' : `all ${formatCount(d.count)}`} on the map</a></p>`;
  const isHead = !!d.members?.length;
  const listed = d.towers;
  let note: SafeHtml | string = '';
  if (isHead) {
    const rest = d.count - listed.length;
    note = listed.length
      ? html`<p class="muted dt-note">Listed below: the ${formatCount(listed.length)} whose records do not say which ${d.name} plan or model it is. The other ${formatCount(rest)} are listed under their own design.</p>`
      : html`<p class="muted dt-note">Each one is listed under its own plan or model.</p>`;
  }
  if (!listed.length) return html`${head}${note}`;
  const standing = listed.filter((t) => t.s === 'standing');
  const others = listed.filter((t) => t.s !== 'standing');
  const standingBlock = standing.length
    ? html`<h5 class="h-small dt-h">Standing today <span class="muted">(${formatCount(standing.length)})</span></h5>${
        standing.length <= OPEN_UP_TO ? html`<div class="dt-all">${byState(standing, ctx)}</div>` : html`<details class="dt-all"><summary>List all ${formatCount(standing.length)} standing, by state</summary>${byState(standing, ctx)}</details>`
      }`
    : html`<p class="muted dt-none">None is recorded as standing today.</p>`;
  const othersBlock = others.length
    ? html`<details class="dt-all dt-others"><summary>${standing.length ? 'Also' : 'List'} ${formatCount(others.length)} gone, moved or unknown, by state</summary>${byState(others, ctx)}</details>`
    : '';
  return html`${head}${note}${standingBlock}${othersBlock}`;
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
  return shown.length ? html`<dl class="kv kv-design">${shown.map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}</dl>` : html``;
}

function chips(d: Design, regions: DesignGroup[]): SafeHtml {
  const items: string[] = [];
  if (d.part && PART_LABEL[d.part]) items.push(PART_LABEL[d.part]!);
  if (d.material) items.push(d.material[0]!.toUpperCase() + d.material.slice(1));
  for (const r of d.region_codes ?? []) {
    const g = regions.find((x) => x.id === r);
    if (g) items.push(r === 'national' ? g.label : g.id.replace(/^R(\d)$/, 'Region $1'));
  }
  const y = d.years_in_use;
  if (y?.from) items.push(y.to ? `${y.from}–${y.to}` : `from ${y.from}`);
  return items.length ? html`<ul class="design-chips" aria-label="At a glance">${items.map((x) => html`<li>${x}</li>`)}</ul>` : html``;
}

function plansBlock(d: Design): SafeHtml {
  const variants = (d.variants ?? []).filter((v) => v && v.name);
  const plans = (d.plans ?? []).filter((p) => p && safeUrl(p.url));
  if (!variants.length && !plans.length) return html``;
  const credit = html`<p class="fine dp-credit">Scans of the original drawings, hosted by the <a href="https://firelookout.org/resources/plans/" rel="noopener">Forest Fire Lookout Association${EXT}</a>.</p>`;
  return html`${variants.length
      ? html`<h5 class="h-small">Plan versions</h5><ol class="design-variants">${variants.map(
          (v) => html`<li><p class="dv-name"><strong>${v.name}</strong>${v.years ? html` <span class="muted">${v.years}</span>` : ''}</p>${v.description ? html`<p class="dv-desc">${v.description}</p>` : ''}${v.plans?.length ? html`<ul class="design-plans">${v.plans.map(planLink)}</ul>` : ''}</li>`,
        )}</ol>`
      : ''}${plans.length ? html`<h5 class="h-small">Original drawings</h5><ul class="design-plans">${plans.map(planLink)}</ul>` : ''}${credit}`;
}

function familyLine(d: Design, byId: Map<string, Design>): SafeHtml {
  if (!d.family || d.family === d.id) return html``;
  const head = byId.get(d.family);
  if (!head || !idOk(head.id)) return html``;
  return html`<p class="design-family">Part of the <a href="#${head.id}">${head.name}</a> family</p>`;
}

export function designSection(d: Design, ctx: DesignsContext, byId: Map<string, Design> = new Map(), groups: { materials: DesignGroup[]; regions: DesignGroup[] } = { materials: MATERIALS, regions: REGIONS }): SafeHtml {
  if (!idOk(d.id)) return html``;
  const svg = schematicSvg(d.schematic, d.name);
  const standing = d.by_status?.standing ?? 0;
  return html`<section class="design" id="${d.id}" aria-labelledby="${d.id}-h">
    <div class="design-top">
      ${svg ? html`<figure class="design-fig">${raw(svg)}<figcaption>Schematic, not to scale</figcaption></figure>` : ''}
      <div class="design-intro">
        <h4 class="design-name" id="${d.id}-h">${d.name}</h4>
        ${d.aka?.length ? html`<p class="design-aka">Also called ${d.aka.join(', ')}</p>` : ''}
        ${familyLine(d, byId)}
        ${chips(d, groups.regions)}
        ${d.summary ? html`<p class="design-summary">${d.summary}</p>` : ''}
        <p class="design-count"><strong>${formatCount(d.count)}</strong> ${d.count === 1 ? 'lookout' : 'lookouts'} on Firefinder${d.count ? html`, <strong>${formatCount(standing)}</strong> standing` : ''}</p>
      </div>
    </div>
    ${memberLinks(d)}
    ${factsList(d)}
    ${d.features?.length ? html`<h5 class="h-small">How to recognise it</h5><ul class="design-features">${d.features.map((x) => html`<li>${x}</li>`)}</ul>` : ''}
    ${plansBlock(d)}
    ${d.uncertain ? html`<details class="design-uncertain"><summary>Where sources disagree</summary><p>${d.uncertain}</p></details>` : ''}
    <h5 class="h-small">On Firefinder</h5>
    ${towersBlock(d, ctx)}
    ${d.sources?.length ? html`<h5 class="h-small">Sources</h5><ul class="design-sources">${d.sources.map(sourceItem)}</ul>` : ''}
  </section>`;
}

interface Grouped {
  material: DesignGroup;
  regions: { region: DesignGroup; designs: Design[] }[];
}

/** Designs by material, then by region (a design's first region code), in designs.json order. */
export function groupDesigns(file: DesignsFile): Grouped[] {
  const materials = mergeGroups(file.groups?.materials, MATERIALS);
  const regions = mergeGroups(file.groups?.regions, REGIONS);
  const out: Grouped[] = [];
  const other: DesignGroup = { id: 'other', label: 'Other designs' };
  for (const m of [...materials, other]) {
    const ds = file.designs.filter((d) => idOk(d.id) && (m === other ? !materials.some((x) => x.id === d.material) : d.material === m.id));
    if (!ds.length) continue;
    const byRegion: Grouped['regions'] = [];
    for (const r of [...regions, { id: '', label: 'Other places' }]) {
      const rs = ds.filter((d) => (r.id ? (d.region_codes?.[0] ?? '') === r.id : !regions.some((x) => x.id === d.region_codes?.[0])));
      if (rs.length) byRegion.push({ region: r, designs: rs });
    }
    out.push({ material: m, regions: byRegion });
  }
  return out;
}

function groupAnchor(m: DesignGroup, r?: DesignGroup): string {
  const a = `m-${m.id.toLowerCase()}`;
  return r ? `${a}-${(r.id || 'other').toLowerCase()}` : a;
}

export function designsToc(file: DesignsFile, extras: DesignsExtras = {}): SafeHtml {
  const grouped = groupDesigns(file);
  const extraToc = (extras.toc ?? []).filter(([id]) => /^[a-z0-9-]+$/.test(id));
  return html`<nav class="toc design-toc" aria-label="Designs on this page">${grouped.map(
    (g) => html`<div class="dtoc-group"><p class="dtoc-h"><a href="#${groupAnchor(g.material)}">${g.material.label}</a></p><ul>${g.regions.flatMap((r) =>
      r.designs.map((d) => html`<li><a href="#${d.id}">${d.name}</a> <span class="muted">${formatCount(d.count)}</span></li>`),
    )}</ul></div>`,
  )}${extraToc.length || file.equipment?.length
      ? html`<div class="dtoc-group"><p class="dtoc-h">More</p><ul>${extraToc.map(([id, label]) => html`<li><a href="#${id}">${label}</a></li>`)}${file.equipment?.length ? html`<li><a href="#equipment">Equipment and reference</a></li>` : ''}</ul></div>`
      : ''}</nav>`;
}

export function designsCoverage(file: DesignsFile): SafeHtml {
  const c = file.coverage;
  const unmatched = c.unmatched_text ?? c.with_design_text - c.recognised;
  return html`<div class="notice tone-unknown design-coverage" role="note"><div>
    <p class="notice-title">How many we can tell</p>
    <p>Firefinder can name a standard design for <strong>${formatCount(c.recognised)}</strong> of its ${formatCount(c.total)} lookouts (${((c.recognised / Math.max(1, c.total)) * 100).toFixed(0)}%), from the plan names its sources use. For most of the rest, no source we use records the plan.${unmatched > 0 ? ` Another ${formatCount(unmatched)} have a design described in words we could not match to one of the plans below.` : ''} A lookout whose records describe more than one structure (an earlier cab and today's) is listed under each design they name, with the record's own words.</p>
  </div></div>`;
}

function referenceItem(e: DesignReference): SafeHtml {
  if (!idOk(e.id)) return html``;
  const links = (e.links ?? []).filter((l) => safeUrl(l.url));
  return html`<li class="eq-item" id="eq-${e.id}"><p class="eq-name"><strong>${e.name}</strong></p>${e.summary ? html`<p class="eq-summary">${e.summary}</p>` : ''}${links.length ? html`<ul class="design-plans">${links.map(planLink)}</ul>` : ''}</li>`;
}

const EQUIPMENT_KINDS: [string, string][] = [
  ['firefinder', 'Firefinders'],
  ['lightning', 'Lightning protection'],
  ['reference', 'Plan books and reference documents'],
];

export function equipmentSection(file: DesignsFile): SafeHtml {
  const items = (file.equipment ?? []).filter((e) => e && idOk(e.id));
  if (!items.length) return html``;
  const kinds = [...EQUIPMENT_KINDS, ...[...new Set(items.map((e) => e.kind ?? 'other'))].filter((k) => !EQUIPMENT_KINDS.some(([x]) => x === k)).map((k): [string, string] => [k, 'Other'])];
  return html`<section class="design-equipment" id="equipment" aria-labelledby="equipment-h">
    <h2 id="equipment-h">Equipment and reference</h2>
    <p>Not lookout designs, but on the same Forest Fire Lookout Association page: the instruments a lookout worked with, how lookouts were protected from lightning, and the plan books the drawings above come from.</p>
    ${kinds.map(([k, label]) => {
      const ks = items.filter((e) => (e.kind ?? 'other') === k);
      return ks.length ? html`<h3 class="h-small">${label}</h3><ul class="eq-list">${ks.map(referenceItem)}</ul>` : '';
    })}
  </section>`;
}

/** The end of the page, after Structure types: Equipment and reference, then the general sources. */
export function designsEnd(file: DesignsFile): SafeHtml {
  return html`${equipmentSection(file)}
    ${file.sources?.length ? html`<section class="design-general" aria-labelledby="dg-h"><h2 id="dg-h">More about lookout designs</h2><ul class="design-sources">${file.sources.map(sourceItem)}</ul>${file.note ? html`<p class="fine">${file.note}</p>` : ''}</section>` : ''}`;
}

export function designsMain(file: DesignsFile, ctx: DesignsContext, extras: DesignsExtras = {}): SafeHtml {
  const byId = new Map(file.designs.map((d) => [d.id, d]));
  const groups = { materials: mergeGroups(file.groups?.materials, MATERIALS), regions: mergeGroups(file.groups?.regions, REGIONS) };
  const sections = groupDesigns(file).map(
    (g) => html`<section class="design-group" id="${groupAnchor(g.material)}" aria-labelledby="${groupAnchor(g.material)}-h">
      <h2 class="design-group-h" id="${groupAnchor(g.material)}-h">${g.material.label}</h2>
      ${g.material.intro ? html`<p class="design-group-intro">${g.material.intro}</p>` : ''}
      ${g.regions.map(
        (r) => html`<h3 class="design-region" id="${groupAnchor(g.material, r.region)}">${r.region.label}</h3>${r.designs.map((d) => designSection(d, ctx, byId, groups))}`,
      )}
    </section>`,
  );
  return html`${designsCoverage(file)}${designsToc(file, extras)}${sections}`;
}
