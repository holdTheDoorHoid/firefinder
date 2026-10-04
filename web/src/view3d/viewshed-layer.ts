/**
 * "What it could see" on the map: the ground in line of sight of one or more lookouts, shaded
 * by how many of them see it. The terrain work runs in the worker (Rust/WASM); this module
 * paints the count grid onto a canvas the map stretches over the area, and runs the small
 * control card with the legend.
 */
import '../styles/view3d.css';
import type { CanvasSourceSpecification, Map as MlMap } from 'maplibre-gl';
import { html } from '../lib/html.ts';
import type { TowerFeature } from '../lib/types.ts';
import { requestViewshed, progressText } from './client.ts';
import { areaText, eyeHeight, megabytes } from './describe.ts';
import type { ViewshedData } from './engine.ts';
import { destination, distanceM } from './tiles.ts';

export const SEEN_SRC = 'ff-seen';
export const SEEN_LAYER = 'ff-seen';
const RING_SRC = 'ff-seen-ring';
const RING_LAYER = 'ff-seen-ring';
/** The layer the shading goes under (the lookout markers stay on top). */
const BELOW = 'ff-clusters';

export type Theme = 'light' | 'dark';

export interface SeenDeps {
  map: MlMap;
  /** Where the card goes (the map's box). */
  host: HTMLElement;
  base: string;
  tower: (id: string) => TowerFeature | undefined;
  towers: () => TowerFeature[];
  theme: () => Theme;
  /** The set of lookouts or the radius changed (for the URL). */
  onChange: (ids: string[], km: number) => void;
}

const COLOURS: Record<Theme, { one: [number, number, number, number]; two: [number, number, number, number]; stripe: [number, number, number, number]; ring: string }> = {
  light: { one: [222, 150, 20, 120], two: [184, 62, 18, 150], stripe: [110, 30, 6, 215], ring: '#7a3412' },
  dark: { one: [246, 186, 66, 110], two: [255, 124, 76, 140], stripe: [255, 210, 180, 220], ring: '#ffb38a' },
};

/** RGBA pixels for a count grid. Two or more is also striped, so it does not rely on colour. */
export function paintCounts(counts: Uint8Array, width: number, height: number, theme: Theme, multi: boolean): Uint8ClampedArray {
  const c = COLOURS[theme];
  const out = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const n = counts[y * width + x]!;
      if (!n) continue;
      const px = (n >= 2 && multi ? ((x + y) % 7 < 2 ? c.stripe : c.two) : c.one) as number[];
      out.set(px, (y * width + x) * 4);
    }
  }
  return out;
}

function lonLat(mx: number, my: number): [number, number] {
  return [(mx - 0.5) * 360, (Math.atan(Math.sinh((0.5 - my) * 2 * Math.PI)) * 180) / Math.PI];
}

function circle(lat: number, lon: number, r: number): [number, number][] {
  const pts: [number, number][] = [];
  for (let a = 0; a <= 360; a += 4) {
    const [la, lo] = destination(lat, lon, a, r);
    pts.push([lo, la]);
  }
  return pts;
}

interface TowerMeta {
  heightM: number | null;
}

export class SeenLayer {
  #d: SeenDeps;
  ids: string[] = [];
  km = 40;
  #card: HTMLElement;
  #canvas = document.createElement('canvas');
  #data: ViewshedData | null = null;
  #run = 0;
  #meta = new Map<string, Promise<TowerMeta>>();
  #status = '';

  constructor(d: SeenDeps) {
    this.#d = d;
    this.#card = document.createElement('section');
    this.#card.className = 'seen-card';
    this.#card.setAttribute('aria-labelledby', 'seen-h');
    this.#card.hidden = true;
    d.host.append(this.#card);
    this.#card.addEventListener('click', (e) => this.#onClick(e));
    this.#card.addEventListener('change', (e) => {
      const sel = (e.target as Element).closest('select');
      if (sel) void this.set(this.ids, Number(sel.value));
    });
  }

  has(id: string): boolean {
    return this.ids.includes(id);
  }

  /** Show the views of these lookouts (an empty list clears everything). */
  async set(ids: string[], km = this.km): Promise<void> {
    this.ids = [...new Set(ids)].filter((id) => this.#d.tower(id)).slice(0, 12);
    this.km = km;
    this.#d.onChange(this.ids, this.km);
    if (!this.ids.length) {
      this.clear();
      return;
    }
    await this.#compute();
  }

  toggle(id: string): Promise<void> {
    return this.set(this.has(id) ? this.ids.filter((x) => x !== id) : [...this.ids, id]);
  }

  /** Add up to `n` of the nearest other lookouts within the radius of the first one. */
  addNearby(n = 4): Promise<void> {
    const first = this.#d.tower(this.ids[0]!);
    if (!first) return Promise.resolve();
    const [lon, lat] = first.geometry.coordinates;
    const near = this.#d
      .towers()
      .filter((f) => !this.ids.includes(f.properties.i))
      .map((f) => ({ f, d: distanceM(lat, lon, f.geometry.coordinates[1], f.geometry.coordinates[0]) }))
      .filter((x) => x.d > 200 && x.d <= this.km * 1000)
      .sort((a, b) => a.d - b.d)
      .slice(0, n)
      .map((x) => x.f.properties.i);
    return this.set([...this.ids, ...near]);
  }

  clear(): void {
    this.#run++;
    this.ids = [];
    this.#data = null;
    this.#remove();
    this.#card.hidden = true;
    this.#d.onChange([], this.km);
  }

  /** Put the layers back after the base style changed (theme switch). */
  reinstall(): void {
    if (this.#data) this.#install();
  }

  #meta1(id: string): Promise<TowerMeta> {
    let p = this.#meta.get(id);
    if (!p) {
      p = fetch(`${this.#d.base}data/t/${id}.json`)
        .then((r) => (r.ok ? r.json() : null))
        .then((rec: { height_m?: number | null } | null) => ({ heightM: rec?.height_m ?? null }))
        .catch(() => ({ heightM: null }));
      this.#meta.set(id, p);
    }
    return p;
  }

  async #compute(): Promise<void> {
    const run = ++this.#run;
    this.#card.hidden = false;
    this.#status = 'Starting…';
    this.#renderCard(true);
    const towers = this.ids.map((id) => this.#d.tower(id)!);
    const metas = await Promise.all(this.ids.map((id) => this.#meta1(id)));
    const observers = towers.map((f, i) => {
      const [lon, lat] = f.geometry.coordinates;
      return { id: f.properties.i, lat, lon, eyeAboveGroundM: eyeHeight({ kind: f.properties.k, height_m: metas[i]!.heightM, lon }).eyeM };
    });
    try {
      const data = await requestViewshed(
        { observers, radiusM: this.km * 1000, targetM: 0, cellM: this.km <= 20 ? 45 : this.km <= 40 ? 75 : 100, maxCells: 3_000_000 },
        (p) => {
          if (run !== this.#run) return;
          this.#status = progressText(p);
          this.#renderCard(true);
        },
      );
      if (run !== this.#run) return;
      this.#data = data;
      this.#paint();
      this.#install();
      const t = data.tiles;
      this.#status = `Worked out in ${(data.ms.compute / 1000).toFixed(1)} s from ${t.needed} terrain tiles${t.bytes ? ` (${megabytes(t.bytes)} downloaded)` : ''}.${t.failed ? ` ${t.failed} tiles did not load, so some ground may be missing.` : ''}`;
      this.#renderCard(false);
    } catch (err) {
      if (run !== this.#run) return;
      console.error(err);
      this.#status = 'The view could not be worked out: the terrain or the engine did not load.';
      this.#renderCard(false, true);
    }
  }

  #paint(): void {
    const d = this.#data!;
    const c = this.#canvas;
    c.width = d.width;
    c.height = d.height;
    const ctx = c.getContext('2d')!;
    const img = new ImageData(paintCounts(d.counts, d.width, d.height, this.#d.theme(), this.ids.length > 1) as Uint8ClampedArray<ArrayBuffer>, d.width, d.height);
    ctx.putImageData(img, 0, 0);
  }

  #install(): void {
    const { map } = this.#d;
    const d = this.#data!;
    if (!map.getStyle()) return;
    const mx1 = d.mx0 + d.width * d.cell;
    const my1 = d.my0 + d.height * d.cell;
    const coordinates: CanvasSourceSpecification['coordinates'] = [lonLat(d.mx0, d.my0), lonLat(mx1, d.my0), lonLat(mx1, my1), lonLat(d.mx0, my1)];
    this.#remove();
    this.#paint();
    map.addSource(SEEN_SRC, { type: 'canvas', canvas: this.#canvas, coordinates, animate: false });
    const before = map.getLayer(BELOW) ? BELOW : undefined;
    map.addLayer({ id: SEEN_LAYER, type: 'raster', source: SEEN_SRC, paint: { 'raster-opacity': 1, 'raster-resampling': 'nearest', 'raster-fade-duration': 0 } }, before);
    const rings = {
      type: 'FeatureCollection',
      features: d.observers.map((o) => ({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: circle(o.lat, o.lon, d.radiusM) } })),
    };
    map.addSource(RING_SRC, { type: 'geojson', data: rings as never });
    map.addLayer(
      { id: RING_LAYER, type: 'line', source: RING_SRC, paint: { 'line-color': COLOURS[this.#d.theme()].ring, 'line-width': 1.4, 'line-dasharray': [3, 3], 'line-opacity': 0.8 } },
      before,
    );
  }

  #remove(): void {
    const { map } = this.#d;
    if (!map.getStyle()) return;
    for (const l of [RING_LAYER, SEEN_LAYER]) if (map.getLayer(l)) map.removeLayer(l);
    for (const s of [RING_SRC, SEEN_SRC]) if (map.getSource(s)) map.removeSource(s);
  }

  /** Zoom the map to show everything computed, clear of the card and anything at `right`. */
  fit(right = 0): void {
    const d = this.#data;
    if (!d) return;
    const [w, n] = lonLat(d.mx0, d.my0);
    const [e, s] = lonLat(d.mx0 + d.width * d.cell, d.my0 + d.height * d.cell);
    const box = this.#d.map.getContainer();
    const card = this.#card.getBoundingClientRect();
    const phone = box.clientWidth < 700;
    // Keep clear of the card: beside it where the visible map is wide, above it where narrow.
    const roomy = box.clientWidth - right - card.width > 600;
    const pad = {
      top: phone ? card.height + 90 : 70,
      bottom: !phone && !roomy ? card.height + 50 : 30,
      left: !phone && roomy ? card.width + 30 : 20,
      right: right + 20,
    };
    // The map keeps padding from when a lookout was selected (for a panel that may since have
    // closed), and fitBounds adds to it: start from none, since `pad` covers everything.
    this.#d.map.setPadding({ top: 0, bottom: 0, left: 0, right: 0 });
    // Never pad more than the map has room for.
    const k = Math.min(1, (box.clientWidth - 80) / (pad.left + pad.right), (box.clientHeight - 80) / (pad.top + pad.bottom));
    for (const key of ['top', 'bottom', 'left', 'right'] as const) pad[key] = Math.max(10, Math.floor(pad[key] * k));
    this.#d.map.fitBounds([w, s, e, n], { padding: pad, duration: 600 });
  }

  #renderCard(busy: boolean, failed = false): void {
    const multi = this.ids.length > 1;
    const c = COLOURS[this.#d.theme()];
    const rgba = (v: number[]) => `rgba(${v.slice(0, 3).join(',')},${(v[3]! / 255).toFixed(2)})`;
    const sw = (v: number[], striped = false) =>
      `background:${striped ? `repeating-linear-gradient(135deg, ${rgba(c.stripe)} 0 2px, ${rgba(v)} 2px 7px)` : rgba(v)}`;
    const names = this.ids.map((id) => ({ id, name: (this.#d.tower(id)?.properties.n ?? id).replace(/\s+(Lookout|Fire Tower)$/i, '') }));
    const one = this.#data && this.#data.observers.length === 1 ? this.#data.observers[0] : null;
    const done = !busy && !failed && this.#data;
    this.#card.innerHTML = html`
      <h2 id="seen-h">What ${multi ? 'they' : 'it'} could see</h2>
      <button type="button" class="icon-btn" data-seen-close aria-label="Hide what the lookouts could see">
        <svg width="18" height="18" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="m5 5 10 10M15 5 5 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
      </button>
      <ul class="seen-towers" aria-label="Lookouts shown">${names.map(
        (t) => html`<li>${t.name}<button type="button" data-seen-remove="${t.id}" aria-label="Remove ${t.name}">×</button></li>`,
      )}</ul>
      <div class="seen-row">
        <label for="seen-r">Out to</label>
        <select id="seen-r">${[20, 40, 60].map((k) => html`<option value="${k}" ${k === this.km ? 'selected' : ''}>${Math.round(k / 1.609)} mi (${k} km)</option>`)}</select>
        <button type="button" class="btn" data-seen-nearby ${busy || this.ids.length >= 12 ? 'disabled' : ''}>Add nearby lookouts</button>
      </div>
      <ul class="seen-legend">
        <li><span class="seen-swatch" style="${sw(c.one)}"></span>${multi ? 'Seen by 1 lookout' : 'Ground in its line of sight'}</li>
        ${multi ? html`<li><span class="seen-swatch" style="${sw(c.two, true)}"></span>Seen by 2 or more (striped)</li>` : ''}
      </ul>
      <p class="seen-status" role="status" aria-live="polite">${done
        ? one
          ? html`It sees about ${areaText(one.areaM2)} of ground.`
          : html`Together they see about ${areaText(this.#countArea())} of ground.`
        : this.#status}</p>
      ${failed ? html`<p><button type="button" class="btn" data-seen-retry>Try again</button></p>` : ''}
      <details class="seen-about"><summary>About this map</summary>
        <p>Shaded: bare ground in direct line of sight from each cab, out to the dashed circle. Worked out from terrain data, with the earth's curvature and the bending of light included, and typical cab heights where the real one isn't recorded.</p>
        <p>Trees are not modelled, and a column of smoke rising above a ridge can be seen from farther than the ground shown here, so real lookouts covered more.</p>
        ${done ? html`<p>${this.#status}</p>` : ''}
      </details>`.value;
  }

  #countArea(): number {
    const d = this.#data;
    if (!d) return 0;
    let cells = 0;
    for (const n of d.counts) if (n) cells++;
    const lat = d.observers[0]?.lat ?? 45;
    const cellM = d.cell * 2 * Math.PI * 6_371_008.8 * Math.cos((lat * Math.PI) / 180);
    return cells * cellM * cellM;
  }

  /** Width of the details panel over the map's right edge, if open. */
  #rightCover(): number {
    const panel = document.getElementById('panel');
    return panel && !panel.hidden && window.innerWidth >= 900 ? panel.getBoundingClientRect().width + 16 : 0;
  }

  #onClick(e: Event): void {
    const b = (e.target as Element).closest<HTMLButtonElement>('button');
    if (!b) return;
    if (b.hasAttribute('data-seen-close')) this.clear();
    else if (b.dataset.seenRemove) void this.toggle(b.dataset.seenRemove);
    else if (b.hasAttribute('data-seen-nearby')) void this.addNearby().then(() => this.fit(this.#rightCover()));
    else if (b.hasAttribute('data-seen-retry')) void this.#compute();
  }
}
