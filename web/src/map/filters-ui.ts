/**
 * The filter panel. The checkboxes double as the map key: each status and type option shows
 * the marker it draws, and each count says how many lookouts you would see with it ticked.
 */
import { MARKS, MARK_LABELS, type Mark } from '../lib/checklist.ts';
import { formatCount } from '../lib/format.ts';
import { facetCounts, isSelected, matches, toggleValue, type Facet, type Filters, type ChecklistLookup } from '../lib/filters.ts';
import { html, raw, type SafeHtml } from '../lib/html.ts';
import { markerSvg, rentBadgeSvg, shapeFor, fillFor } from '../lib/icons.ts';
import type { TowerFeature } from '../lib/types.ts';
import { KIND, KIND_ORDER, STATUS_ORDER, VERIFICATION, VERIFICATION_ORDER, regionName } from '../lib/vocab.ts';
import { mapKey } from '../render/site.ts';

export interface FilterPanelDeps {
  root: HTMLElement;
  features: () => readonly TowerFeature[];
  filters: () => Filters;
  checklist: ChecklistLookup & { counts(): Record<Mark, number> };
  onChange: (next: Filters) => void;
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

export function renderFilterPanel(d: FilterPanelDeps): () => void {
  const regions = [...new Set(d.features().map((f) => f.properties.r))].sort((a, b) => regionName(a).localeCompare(regionName(b)));

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
    write('rentable', countWith({ rentable: true }));
    write('registered', countWith({ registered: true }));
    for (const m of MARKS) write(`mine:${m}`, d.checklist.counts()[m]);
  };
}
