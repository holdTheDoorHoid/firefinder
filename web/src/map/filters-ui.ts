/**
 * The filter panel. The checkboxes double as the map key: each status and type option shows
 * the marker it draws, and each count says how many lookouts you would see with it ticked.
 */
import { MARKS, MARK_LABELS, type Mark } from '../lib/checklist.ts';
import { formatCount } from '../lib/format.ts';
import { designIds, facetCounts, isSelected, matches, toggleValue, type Facet, type Filters, type ChecklistLookup } from '../lib/filters.ts';
import { html, raw, type SafeHtml } from '../lib/html.ts';
import { markerSvg, rentBadgeSvg, shapeFor, fillFor } from '../lib/icons.ts';
import type { TowerFeature } from '../lib/types.ts';
import {
  DESIGN_MATERIAL,
  DESIGN_MATERIAL_LABEL,
  DESIGN_NAMES,
  KIND,
  KIND_ORDER,
  MATERIAL,
  MATERIAL_ORDER,
  NO_STRUCTURE_KINDS,
  NO_STRUCTURE_LABEL,
  NO_STRUCTURE_MEANING,
  STATUS_ORDER,
  VERIFICATION,
  VERIFICATION_ORDER,
  designName,
  isNoStructure,
  regionName,
} from '../lib/vocab.ts';
import { mapKey } from '../render/site.ts';

export interface FilterPanelDeps {
  root: HTMLElement;
  features: () => readonly TowerFeature[];
  filters: () => Filters;
  checklist: ChecklistLookup & { counts(): Record<Mark, number> };
  onChange: (next: Filters) => void;
  /** Lookouts no source places, by state (meta.json counts.unplaced_by_region), for the links to their lists. */
  unplaced?: () => Record<string, number> | null;
}

const STATUS_LABEL: Record<string, string> = {
  standing: 'Standing',
  gone: 'Gone',
  ruins: 'Ruins or footings',
  relocated: 'Moved to a new site',
  replica: 'Replica',
  unknown: 'Status unknown',
};

function option(name: string, value: string, label: string, icon: SafeHtml | string, hint?: string): SafeHtml {
  return html`<label class="opt">
    <input type="checkbox" name="${name}" value="${value}">
    <span class="opt-icon">${typeof icon === 'string' ? raw(icon) : icon}</span>
    <span class="opt-label">${label}${hint ? html`<span class="opt-hint">${hint}</span>` : ''}</span>
    <span class="opt-count" data-count="${name}:${value}"></span>
  </label>`;
}

function multiFieldset(facet: Facet, legend: string, body: SafeHtml, help?: string): SafeHtml {
  return html`<fieldset class="fs" data-facet="${facet}">
    <legend>${legend}</legend>
    ${help ? html`<p class="fs-help">${help}</p>` : ''}
    ${body}
    <button type="button" class="linklike fs-all" data-all="${facet}" hidden>Show all again</button>
  </fieldset>`;
}

/** The design filter's options grouped by what the design is built of (wood, steel...). */
function designGroups(ids: string[]): [string, string[]][] {
  const groups = new Map<string, string[]>();
  for (const id of ids) {
    const m = DESIGN_MATERIAL[id] ?? 'other';
    groups.set(m, [...(groups.get(m) ?? []), id]);
  }
  const order = [...Object.keys(DESIGN_MATERIAL_LABEL), 'other'];
  return [...groups.entries()]
    .sort((a, b) => order.indexOf(a[0]) - order.indexOf(b[0]))
    .map(([m, list]) => [DESIGN_MATERIAL_LABEL[m] ?? 'Other', list]);
}

export function renderFilterPanel(d: FilterPanelDeps): () => void {
  const regions = [...new Set(d.features().map((f) => f.properties.r))].sort((a, b) => regionName(a).localeCompare(regionName(b)));
  const present = new Set(d.features().flatMap((f) => designIds(f.properties)));
  const designs = [...Object.keys(DESIGN_NAMES).filter((x) => present.has(x)), ...[...present].filter((x) => !(x in DESIGN_NAMES)).sort()];

  d.root.innerHTML = html`
    ${multiFieldset(
      'status',
      'Still standing?',
      html`${STATUS_ORDER.map((s) => option('status', s, STATUS_LABEL[s] ?? s, markerSvg('tri', fillFor(s), { size: 20 })))}`,
      'The marker fill shows this.',
    )}
    ${multiFieldset(
      'kind',
      'Type of structure',
      html`${KIND_ORDER.map((k) => option('kind', k, KIND[k]?.label ?? k, markerSvg(shapeFor(k), 'solid', { size: 20 })))}`,
      'The marker shape shows this.',
    )}
    <fieldset class="fs fs-nostructure">
      <legend>${NO_STRUCTURE_LABEL}</legend>
      <p class="fs-help">${NO_STRUCTURE_MEANING} Off unless you switch them on, so the map shows towers and buildings. <a href="${import.meta.env.BASE_URL}designs/#structure-types">About structure types</a></p>
      <label class="opt"><input type="checkbox" name="nostructure" value="1"><span class="opt-icon">${raw(markerSvg('diamond', 'solid', { size: 20 }))}</span><span class="opt-label">Show sites with no structure<span class="opt-hint">${NO_STRUCTURE_KINDS.map((k) => KIND[k]?.label ?? k).join(', ')}</span></span><span class="opt-count" data-count="nostructure"></span></label>
    </fieldset>
    <fieldset class="fs fs-approx">
      <legend>Approximate locations</legend>
      <p class="fs-help">No source says where these stood, so each is shown on the hill or ridge of its name in its county (a dashed marker). <span data-unplaced-link></span></p>
      <label class="opt"><input type="checkbox" name="approximate" value="1"><span class="opt-icon">${raw(markerSvg('tri', 'solid', { size: 20, approximate: true }))}</span><span class="opt-label">Show approximate locations<span class="opt-hint">Placed by name from the USGS gazetteer</span></span><span class="opt-count" data-count="approximate"></span></label>
    </fieldset>
    <fieldset class="fs">
      <legend>Staying and history</legend>
      <label class="opt"><input type="checkbox" name="rentable" value="1"><span class="opt-icon">${raw(rentBadgeSvg(16))}</span><span class="opt-label">Only lookouts you can rent<span class="opt-hint">Bookable on recreation.gov</span></span><span class="opt-count" data-count="rentable"></span></label>
      <label class="opt"><input type="checkbox" name="registered" value="1"><span class="opt-icon" aria-hidden="true">${raw('<svg width="18" height="18" viewBox="0 0 20 20"><path d="M5 2.5h10v15l-5-3.4-5 3.4Z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>')}</span><span class="opt-label">Only lookouts on a historic register<span class="opt-hint">NHLR, FFLOS or the National Register</span></span><span class="opt-count" data-count="registered"></span></label>
    </fieldset>
    <div class="fs fs-select">
      <label for="f-state" class="fs-label">State</label>
      <select id="f-state" name="region">
        <option value="">All states</option>
        ${regions.map((r) => html`<option value="${r}">${regionName(r)}</option>`)}
      </select>
    </div>
    <div class="fs fs-select">
      <label for="f-design" class="fs-label">Design</label>
      <select id="f-design" name="design" aria-describedby="f-design-help">
        <option value="">Any design, or none recorded</option>
        <option value="any">Any recognised standard design</option>
        ${designGroups(designs).map(([label, ids]) => html`<optgroup label="${label}">${ids.map((d) => html`<option value="${d}">${designName(d)}</option>`)}</optgroup>`)}
      </select>
      <p class="fs-help" id="f-design-help"><span data-design-share></span> <a href="${import.meta.env.BASE_URL}designs/">About the designs</a></p>
    </div>
    <div class="fs fs-select">
      <label for="f-material" class="fs-label">Built of</label>
      <select id="f-material" name="material" aria-describedby="f-material-help">
        <option value="">Any material, or none recorded</option>
        ${MATERIAL_ORDER.map((m) => html`<option value="${m}">${MATERIAL[m]?.label ?? m}</option>`)}
      </select>
      <p class="fs-help" id="f-material-help" data-material-share></p>
    </div>
    ${multiFieldset(
      'verification',
      'How well checked',
      html`${VERIFICATION_ORDER.map((v) => option('verification', v, VERIFICATION[v]?.label ?? v, '', VERIFICATION[v]?.meaning))}`,
    )}
    <fieldset class="fs">
      <legend>My checklist</legend>
      <p class="fs-help">Show only lookouts you marked in this browser. Leave all unticked to show everything.</p>
      ${MARKS.map(
        (m) => html`<label class="opt"><input type="checkbox" name="mine" value="${m}"><span class="opt-icon"></span><span class="opt-label">${MARK_LABELS[m]}</span><span class="opt-count" data-count="mine:${m}"></span></label>`,
      )}
      <button type="button" class="linklike" data-open-checklist-dialog>Download or import my checklist</button>
    </fieldset>
    <div class="fs-actions">
      <button type="button" class="btn btn-quiet" data-reset-filters>Reset all filters</button>
    </div>
    <details class="fs-key">
      <summary>What the map symbols mean</summary>
      ${mapKey()}
    </details>
    <p class="fine fs-credit">Lookout data from many sources, see <a href="${import.meta.env.BASE_URL}about/#sources">sources and credits</a>.</p>
  `.value;

  const root = d.root;
  root.addEventListener('change', (e) => {
    const input = e.target as HTMLInputElement | HTMLSelectElement;
    const f: Filters = { ...d.filters() };
    switch (input.name) {
      case 'status':
        f.status = toggleValue(f.status, input.value, (input as HTMLInputElement).checked, STATUS_ORDER);
        break;
      case 'kind':
        f.kind = toggleValue(f.kind, input.value, (input as HTMLInputElement).checked, KIND_ORDER);
        break;
      case 'verification':
        f.verification = toggleValue(f.verification, input.value, (input as HTMLInputElement).checked, VERIFICATION_ORDER);
        break;
      case 'rentable':
        f.rentable = (input as HTMLInputElement).checked;
        break;
      case 'registered':
        f.registered = (input as HTMLInputElement).checked;
        break;
      case 'region':
        f.region = input.value || null;
        break;
      case 'design':
        f.design = input.value || null;
        break;
      case 'material':
        f.material = input.value || null;
        break;
      case 'nostructure':
        f.noStructure = (input as HTMLInputElement).checked;
        break;
      case 'approximate':
        f.approximate = (input as HTMLInputElement).checked;
        break;
      case 'mine': {
        const next = new Set(f.mine ?? []);
        if ((input as HTMLInputElement).checked) next.add(input.value as Mark);
        else next.delete(input.value as Mark);
        f.mine = next.size ? next : null;
        break;
      }
      default:
        return;
    }
    d.onChange(f);
  });
  root.addEventListener('click', (e) => {
    const all = (e.target as Element).closest<HTMLElement>('[data-all]');
    if (!all) return;
    const facet = all.dataset.all as 'status' | 'kind' | 'verification';
    d.onChange({ ...d.filters(), [facet]: null });
    root.querySelector<HTMLInputElement>(`fieldset[data-facet="${facet}"] input`)?.focus();
  });

  /** Sync checkboxes and counts with the current filters. */
  return function sync(): void {
    const f = d.filters();
    const feats = d.features();
    const set = (name: string, value: string, checked: boolean) => {
      const el = root.querySelector<HTMLInputElement>(`input[name="${name}"][value="${value}"]`);
      if (el) el.checked = checked;
    };
    for (const s of STATUS_ORDER) set('status', s, isSelected(f.status, s));
    for (const k of KIND_ORDER) set('kind', k, isSelected(f.kind, k));
    for (const v of VERIFICATION_ORDER) set('verification', v, isSelected(f.verification, v));
    set('rentable', '1', f.rentable);
    set('registered', '1', f.registered);
    set('nostructure', '1', f.noStructure);
    set('approximate', '1', f.approximate);
    for (const m of MARKS) set('mine', m, !!f.mine?.has(m));
    const sel = root.querySelector<HTMLSelectElement>('#f-state');
    if (sel) {
      if (f.region && !sel.querySelector(`option[value="${f.region}"]`)) {
        sel.insertAdjacentHTML('beforeend', html`<option value="${f.region}">${regionName(f.region)} (no lookouts yet)</option>`.value);
      }
      sel.value = f.region ?? '';
    }
    for (const facet of ['status', 'kind', 'verification'] as const) {
      const btn = root.querySelector<HTMLElement>(`[data-all="${facet}"]`);
      if (btn) btn.hidden = f[facet] === null;
    }

    const write = (key: string, n: number) => {
      const el = root.querySelector(`[data-count="${key}"]`);
      if (el) el.textContent = formatCount(n);
    };
    for (const facet of ['status', 'kind', 'verification'] as const) {
      const counts = facetCounts(feats, f, facet, d.checklist);
      const order = facet === 'status' ? STATUS_ORDER : facet === 'kind' ? KIND_ORDER : VERIFICATION_ORDER;
      for (const v of order) write(`${facet}:${v}`, counts.get(v) ?? 0);
    }
    const regionCounts = facetCounts(feats, f, 'region', d.checklist);
    if (sel) {
      for (const opt of sel.options) {
        if (!opt.value) continue;
        const n = regionCounts.get(opt.value) ?? 0;
        opt.textContent = `${regionName(opt.value)} (${formatCount(n)})`;
      }
    }
    const countWith = (patch: Partial<Filters>) => feats.filter((x) => matches(x.properties, { ...f, ...patch }, d.checklist)).length;
    const dsel = root.querySelector<HTMLSelectElement>('#f-design');
    if (dsel) {
      if (f.design && !dsel.querySelector(`option[value="${CSS.escape(f.design)}"]`)) {
        dsel.insertAdjacentHTML('beforeend', html`<option value="${f.design}">${designName(f.design)}</option>`.value);
      }
      dsel.value = f.design ?? '';
      const others = feats.filter((x) => matches(x.properties, { ...f, design: null }, d.checklist));
      const counts = new Map<string, number>();
      let anyDesign = 0;
      for (const x of others) {
        const ids = designIds(x.properties);
        if (ids.length) anyDesign++;
        for (const id of ids) counts.set(id, (counts.get(id) ?? 0) + 1);
      }
      for (const opt of dsel.options) {
        if (!opt.value) continue;
        const n = opt.value === 'any' ? anyDesign : counts.get(opt.value) ?? 0;
        opt.textContent = `${opt.value === 'any' ? 'Any recognised standard design' : designName(opt.value)} (${formatCount(n)})`;
      }
      const share = root.querySelector('[data-design-share]');
      if (share) share.textContent = `Only ${formatCount(anyDesign)} of ${formatCount(others.length)} lookouts have a recognisable design on record.`;
    }
    const msel = root.querySelector<HTMLSelectElement>('#f-material');
    if (msel) {
      msel.value = f.material ?? '';
      const others = feats.filter((x) => matches(x.properties, { ...f, material: null }, d.checklist));
      const counts = new Map<string, number>();
      for (const x of others) if (x.properties.m) counts.set(x.properties.m, (counts.get(x.properties.m) ?? 0) + 1);
      let recorded = 0;
      for (const opt of msel.options) {
        if (!opt.value) continue;
        const n = counts.get(opt.value) ?? 0;
        recorded += n;
        opt.textContent = `${MATERIAL[opt.value]?.label ?? opt.value} (${formatCount(n)})`;
      }
      const share = root.querySelector('[data-material-share]');
      if (share) share.textContent = `Recorded for ${formatCount(recorded)} of ${formatCount(others.length)} lookouts, from the sources' own words or the lookout's design.`;
    }
    write('nostructure', feats.filter((x) => isNoStructure(x.properties.k) && matches(x.properties, { ...f, noStructure: true }, d.checklist)).length);
    write('approximate', feats.filter((x) => x.properties.ap && matches(x.properties, { ...f, approximate: true }, d.checklist)).length);
    const link = root.querySelector('[data-unplaced-link]');
    if (link) {
      const byRegion = d.unplaced?.() ?? null;
      const base = import.meta.env.BASE_URL;
      const n = byRegion ? (f.region ? byRegion[f.region] ?? 0 : Object.values(byRegion).reduce((a, b) => a + b, 0)) : 0;
      link.innerHTML = !byRegion
        ? ''
        : f.region
          ? n
            ? html`<a href="${base}unplaced/${f.region.toLowerCase()}/">${formatCount(n)} more in ${regionName(f.region)} we can't place yet</a>`.value
            : ''
          : html`<a href="${base}unplaced/">${formatCount(n)} more lookouts we can't place yet</a>`.value;
    }
    write('rentable', countWith({ rentable: true }));
    write('registered', countWith({ registered: true }));
    for (const m of MARKS) write(`mine:${m}`, d.checklist.counts()[m]);
  };
}
