/**
 * The "Old topo maps" card: shown under the base-map switch while the historical USGS topo
 * sheets are on. Era choice, opacity, and, plainly, which sheets (and so which years) are in
 * view, with a link to USGS TopoView for the spot at the centre of the map.
 */
import type { IControl, Map as MlMap } from 'maplibre-gl';
import { sheetsInView, onOldTopoFailures, type InView } from '../history/oldtopo/client.ts';
import { ERA_LABEL, ERAS, MIN_ZOOM, scaleLabel, type Era } from '../history/oldtopo/sheets.ts';
import { html, raw } from '../lib/html.ts';
import { topoViewUrl } from '../render/tower.ts';

export interface OldTopoDeps {
  era: () => Era;
  opacity: () => number;
  onEra: (era: Era) => void;
  onOpacity: (opacity: number) => void;
}

const EXT = '<svg class="ext-icon" width="12" height="12" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M9 2h5v5M14 2 7.5 8.5M12 9.5V13a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';

export class OldTopoControl implements IControl {
  #d: OldTopoDeps;
  #el: HTMLDetailsElement | null = null;
  #map: MlMap | null = null;
  #timer = 0;
  #ask = 0;
  #failures = { index: 0, sheets: 0 };
  #offFailures: (() => void) | null = null;
  #onMove = () => this.#schedule();

  constructor(d: OldTopoDeps) {
    this.#d = d;
  }

  onAdd(map: MlMap): HTMLElement {
    this.#map = map;
    const el = document.createElement('details');
    el.className = 'maplibregl-ctrl ff-oldtopo';
    el.open = !matchMedia('(max-width: 899px)').matches;
    el.hidden = true;
    el.innerHTML = html`<summary><span class="ot-title">Old topo maps</span> <span class="ot-sum" data-sum></span></summary>
      <div class="ot-body">
        <fieldset class="ot-era"><legend>Which maps on top</legend>
          ${ERAS.map((e) => html`<label><input type="radio" name="ot-era" value="${e}"><span>${ERA_LABEL[e]}</span></label>`)}
        </fieldset>
        <label class="ot-opacity"><span>Strength</span><input type="range" min="10" max="100" step="5" data-opacity aria-label="How strongly the old maps show"><output data-opacity-out></output></label>
        <p class="ot-sheets" data-sheets></p>
        <p class="ot-fine">Scans of the USGS Historical Topographic Map Collection (public domain), 1880s to 2006, their colours softened a little so the markers stay readable. Lookouts often appear as a small symbol labelled “Lookout”. <a data-topoview rel="noopener">Find every old sheet of this spot on USGS TopoView${raw(EXT)}<span class="visually-hidden"> (opens the USGS site)</span></a></p>
      </div>`.value;
    el.addEventListener('change', (e) => {
      const t = e.target as HTMLInputElement;
      if (t.name === 'ot-era') this.#d.onEra(t.value as Era);
    });
    el.querySelector<HTMLInputElement>('[data-opacity]')!.addEventListener('input', (e) => {
      const v = Number((e.target as HTMLInputElement).value) / 100;
      this.#d.onOpacity(v);
      this.#syncOpacity();
    });
    this.#el = el;
    map.on('moveend', this.#onMove);
    this.#offFailures = onOldTopoFailures((f) => {
      if (f.index !== this.#failures.index || f.sheets !== this.#failures.sheets) {
        this.#failures = f;
        this.#schedule();
      }
    });
    return el;
  }

  onRemove(): void {
    this.#map?.off('moveend', this.#onMove);
    this.#offFailures?.();
    this.#el?.remove();
  }

  /** Show or hide the card (only while the old maps are the base map) and refresh it. */
  sync(visible: boolean): void {
    const el = this.#el;
    if (!el) return;
    el.hidden = !visible;
    if (!visible) return;
    for (const r of el.querySelectorAll<HTMLInputElement>('input[name="ot-era"]')) r.checked = r.value === this.#d.era();
    this.#syncOpacity();
    this.#schedule(0);
  }

  #syncOpacity(): void {
    const el = this.#el!;
    const pct = Math.round(this.#d.opacity() * 100);
    el.querySelector<HTMLInputElement>('[data-opacity]')!.value = String(pct);
    el.querySelector('[data-opacity-out]')!.textContent = `${pct}%`;
    el.querySelector('[data-sum]')!.textContent = `${ERA_LABEL[this.#d.era()]} · ${pct}%`;
  }

  #schedule(delay = 400): void {
    clearTimeout(this.#timer);
    if (!this.#el || this.#el.hidden) return;
    this.#timer = window.setTimeout(() => void this.#refresh(), delay);
  }

  async #refresh(): Promise<void> {
    const map = this.#map;
    const el = this.#el;
    if (!map || !el || el.hidden) return;
    const c = map.getCenter();
    el.querySelector<HTMLAnchorElement>('[data-topoview]')!.href = topoViewUrl(c.lat, c.lng, Math.max(9, Math.min(15, Math.round(map.getZoom()))));
    const out = el.querySelector('[data-sheets]')!;
    if (map.getZoom() < MIN_ZOOM) {
      out.textContent = 'Zoom in to see the old maps: they start at about the size of a county.';
      return;
    }
    const b = map.getBounds();
    const ask = ++this.#ask;
    out.textContent = 'Looking up the sheets in view…';
    let r: InView;
    try {
      r = await sheetsInView([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()], map.getZoom(), this.#d.era());
    } catch {
      r = { sheets: [], tooFar: false, failed: true };
    }
    if (ask !== this.#ask) return;
    const problems = this.#failures.index || this.#failures.sheets ? ' Some old maps could not be loaded; try again later.' : '';
    if (r.failed) {
      out.textContent = 'The list of old map sheets could not be loaded. Check your connection and try again.';
      return;
    }
    if (!r.sheets.length) {
      out.textContent = `No scanned USGS sheet covers this view at this zoom.${problems}`;
      return;
    }
    const years = r.sheets.map((s) => s.year);
    const span = Math.min(...years) === Math.max(...years) ? `${years[0]}` : `${Math.min(...years)} to ${Math.max(...years)}`;
    const shown = r.sheets.slice(0, 4);
    out.innerHTML = html`<strong>Maps from ${span}</strong> in view: ${shown.map((s, i) => html`${i ? '; ' : ''}${s.name} ${s.year} <span class="ot-scale">(${scaleLabel(s.scale)})</span>`)}${r.sheets.length > shown.length ? ` and ${r.sheets.length - shown.length} more` : ''}.${problems}`.value;
  }
}
