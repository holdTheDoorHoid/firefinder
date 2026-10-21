/**
 * "View from the cab": the interactive 360° panorama. Mounts into any element (a tower page
 * section, a dialog on the map, the smoke-spotting lesson) and loads its terrain only when
 * started. Where `satellite` is set (tower pages, the map's dialog) it has two modes: the
 * satellite view of today's land (satellite-view.ts, loaded with MapLibre only when shown) and
 * the drawn panorama, sharing one terrain result, the bearing, the eye height and the lists.
 */
import '../styles/view3d.css';
import { html, raw, type SafeHtml } from '../lib/html.ts';
import { effectiveTheme, onThemeChange } from '../ui/theme.ts';
import { requestPanorama, progressText, siteBase } from './client.ts';
import {
  unitsFor,
  azimuthText,
  eyeHeight,
  megabytes,
  metresFeet,

  quadrantBearing,
  reconstructionNote,
  wrap360,
  type EyeHeight,
} from './describe.ts';
import type { LookoutSight, PanoramaData, PeakSight, Sighted } from './engine.ts';
import {
  FONT,
  PALETTES,
  drawOverview,
  drawPanorama,
  horizonAt,
  makeLayout,
  pick,
  placeLabels,
  type LabelItem,
  type Layout,
  type Smoke,
  type View,
} from './panorama-draw.ts';
import { estimateBytes, panoramaLevels, planTiles } from './tiles.ts';
import { chooseMode, satelliteDownload, type CabMode } from './earth-geo.ts';
import { saveCabMode, saveFrame, storedCabMode, storedFrame, webgl2Works } from './cab-prefs.ts';
import type { SatelliteView } from './satellite-view.ts';

export interface PanoramaTower {
  id: string;
  name: string;
  lat: number;
  lon: number;
  kind: string;
  status: string;
  height_m?: number | null;
  elevation_m?: number | null;
  /** The lookout's country ("US", "CA"): units read feet and miles first in the US, metres and km elsewhere. */
  country?: string | null;
}

export interface PanoramaOptions {
  tower: PanoramaTower;
  maxDistM?: number;
  initialAz?: number;
  /** Peak names and other lookouts (default true). */
  labels?: boolean;
  /** The lists of peaks and lookouts under the view (default true). */
  lists?: boolean;
  /** The eye-height sentence and control (default true). */
  eyeControl?: boolean;
  /** The "this lookout is gone, the view is reconstructed" note (default true; off where the page already says it). */
  recon?: boolean;
  /** Keyboard turning step, degrees (default 1). */
  stepDeg?: number;
  /** A smoke to draw (the lesson). */
  smoke?: { lat: number; lon: number; heightM: number } | null;
  /** Called whenever the view turns. */
  onTurn?: (az: number) => void;
  /** Called once the view is ready. */
  onReady?: (data: PanoramaData) => void;
  /** Offer the satellite view beside the drawn one (default false: the smoke lesson stays drawn). */
  satellite?: boolean;
}

const ZOOMS = [2, 3, 4.5, 6.5, 9, 12, 16, 22, 30, 42];
const MAX_DIST_M = 150_000;

let uid = 0;

/** Whether this screen gets the lighter terrain set (phones). */
export function lightDetail(width = window.innerWidth): boolean {
  return width < 600;
}

/** "about 3.8 MB" for a tower's view, before anything is loaded. */
export function panoramaDownload(t: { lat: number; lon: number }, light = lightDetail()): { tiles: number; bytes: number } {
  const keys = planTiles([t], panoramaLevels(MAX_DIST_M, light ? 'light' : 'full'));
  return { tiles: keys.length, bytes: estimateBytes(keys) };
}

/** Kinds with a cab to look out of (the window frame is offered only for these). */
const CAB_KINDS = new Set(['tower', 'enclosed_tower', 'ground', 'two_story', 'three_story', 'rooftop', 'mobile', 'unknown']);

/** The satellite view of a lookout that is gone (or was moved) shows today's land, not its land. */
function todaysLandNote(status: string): string | null {
  if (status === 'gone' || status === 'ruins' || status === 'relocated') {
    return "The photos show the land today, not as it was when the lookout stood here: reservoirs, clear-cuts, roads and towns may be newer than the tower.";
  }
  return null;
}

function shortName(name: string): string {
  return name.replace(/\s+(Lookout( Site| Tower)?|Fire Tower|L\.O\.)$/i, '').trim() || name;
}

/** Where the peak names come from: GNIS ids are numbers, CGNDB ids strings (pipeline/build_peaks.py). */
function peakCredit(peaks: readonly PeakSight[]): string {
  const us = peaks.some((p) => typeof p.gnisId === 'number');
  const ca = peaks.some((p) => typeof p.gnisId === 'string');
  const cgndb = 'the Canadian Geographical Names Database (contains information licensed under the Open Government Licence – Canada)';
  if (ca && us) return `Names from the USGS Geographic Names Information System and ${cgndb}.`;
  if (ca) return `Names from ${cgndb}.`;
  return 'Names from the USGS Geographic Names Information System.';
}

export class PanoramaView {
  readonly el: HTMLElement;
  #o: PanoramaOptions;
  #id = `pv${++uid}`;
  #data: PanoramaData | null = null;
  #view: View = { az: 0, pxPerDeg: 12, exaggeration: 1 };
  #layout: Layout | null = null;
  #eye: EyeHeight;
  #customEye: number | null = null;
  #items: LabelItem[] = [];
  #highlight: string | null = null;
  #smoke: Smoke | null = null;
  #canvas!: HTMLCanvasElement;
  #overview!: HTMLCanvasElement;
  #viewport!: HTMLElement;
  #frameReq = 0;
  #liveTimer = 0;
  #resize: ResizeObserver | null = null;
  #theme = effectiveTheme();
  #run = 0;
  #offTheme: () => void = () => {};
  /** Which view shows: the satellite view or the drawn panorama. */
  #mode: CabMode = 'drawn';
  /** Why the satellite view is not available here, when it was offered but cannot be shown. */
  #satBlocked: string | null = null;
  #sat: SatelliteView | null = null;
  #satLoad: Promise<typeof import('./satellite-view.ts')> | null = null;
  /** Phones: the visitor tapped to load the satellite view's photos. */
  #satConfirmed = false;
  #frame = storedFrame();
  #stage!: HTMLElement;
  #satEl!: HTMLElement;
  #satView!: HTMLElement;

  get #metric(): boolean {
    return unitsFor(this.#o.tower.country).metric;
  }

  #distance(m: number): string {
    return unitsFor(this.#o.tower.country).distance(m);
  }

  constructor(host: HTMLElement, opts: PanoramaOptions) {
    this.#o = opts;
    this.#view.az = opts.initialAz ?? 0;
    this.#eye = eyeHeight({ kind: opts.tower.kind, height_m: opts.tower.height_m, lon: opts.tower.lon });
    if (opts.satellite) {
      const choice = chooseMode({ offered: true, capable: webgl2Works(), stored: storedCabMode() });
      this.#mode = choice.mode;
      if (choice.unavailable) this.#satBlocked = "This browser can't draw the satellite view (it needs WebGL 2), so the view is drawn.";
    }
    this.el = document.createElement('div');
    this.el.className = 'pv';
    this.el.dataset.state = 'idle';
    host.replaceChildren(this.el);
    this.#build();
    this.#offTheme = onThemeChange((t) => {
      this.#theme = t;
      this.#sat?.setOptions({ theme: t });
      this.#draw();
    });
  }

  get az(): number {
    return this.#view.az;
  }

  get data(): PanoramaData | null {
    return this.#data;
  }

  /** Bearing of the smoke drawn in the view (the lesson), once ready. */
  get smokeAz(): number | null {
    return this.#smoke?.az ?? null;
  }

  /** Where the smoke is relative to the sighting hair, in words (for screen readers). */
  #smokeWords(): string | null {
    if (!this.#smoke) return null;
    const d = ((this.#smoke.az - this.#view.az + 540) % 360) - 180;
    if (Math.abs(d) < 0.25) return 'The smoke is right on the sight.';
    if (Math.abs(d) > 20) return null;
    return `Smoke ${Math.abs(d).toFixed(1)} degrees to the ${d > 0 ? 'right' : 'left'} of the sight.`;
  }

  /** Which view is showing. */
  get mode(): CabMode {
    return this.#mode;
  }

  /** Turn to an azimuth (degrees). */
  turnTo(az: number, announce = false): void {
    this.#view.az = wrap360(az);
    this.#sat?.setBearing(this.#view.az);
    this.#updateHeading(announce);
    this.#draw();
    this.#o.onTurn?.(this.#view.az);
  }

  /** Put the keyboard focus on the view that is showing. */
  focus(): void {
    (this.#satShowing() ? this.#satView : this.#viewport).focus({ preventScroll: true });
  }

  #satShowing(): boolean {
    return this.#mode === 'satellite' && !!this.#data && !this.#satEl.hidden;
  }

  /** Turn by some degrees from the buttons: outside the cab this circles the lookout instead. */
  #turnBy(deg: number): void {
    if (this.#satShowing() && this.#sat?.outside) this.#sat.turnBy(deg);
    else this.turnTo(this.#view.az + deg, true);
  }

  #build(): void {
    const t = this.#o.tower;
    const recon = reconstructionNote(t.status, this.#eye.source);
    const sat = !!this.#o.satellite;
    this.el.innerHTML = html`
      ${this.#o.eyeControl !== false
        ? html`<div class="pv-eye">
            <p class="pv-eye-line"><span data-pv-eye-text>${this.#eye.sentence}</span> <button type="button" class="linklike" data-pv-eye-open aria-expanded="false" aria-controls="${this.#id}-eye">Change</button></p>
            <form class="pv-eye-form" id="${this.#id}-eye" hidden>
              <label for="${this.#id}-eye-ft">Eye height above the ground</label>
              ${this.#metric
                ? html`<span class="pv-eye-input"><input id="${this.#id}-eye-ft" type="number" inputmode="decimal" min="1" max="300" step="0.5" required> <span>m</span></span>
              <span class="pv-eye-presets" role="group" aria-label="Typical heights">
                <button type="button" class="chip-btn" data-eye-ft="2.5">Ground cab</button>
                <button type="button" class="chip-btn" data-eye-ft="11">9 m tower</button>
                <button type="button" class="chip-btn" data-eye-ft="26">24 m steel tower</button>
                <button type="button" class="chip-btn" data-eye-ft="32">30 m tower</button>
              </span>`
                : html`<span class="pv-eye-input"><input id="${this.#id}-eye-ft" type="number" inputmode="decimal" min="3" max="1000" step="1" required> <span>ft</span></span>
              <span class="pv-eye-presets" role="group" aria-label="Typical heights">
                <button type="button" class="chip-btn" data-eye-ft="8">Ground cab</button>
                <button type="button" class="chip-btn" data-eye-ft="35">30-ft tower</button>
                <button type="button" class="chip-btn" data-eye-ft="71">66-ft steel tower</button>
                <button type="button" class="chip-btn" data-eye-ft="105">100-ft tower</button>
              </span>`}
              <span class="pv-eye-actions"><button type="submit" class="btn">Update the view</button>
              <button type="button" class="linklike" data-pv-eye-reset>Use the ${this.#eye.source === 'recorded' ? 'recorded' : 'typical'} height</button></span>
            </form>
            ${recon && this.#o.recon !== false ? html`<p class="pv-recon">${recon}</p>` : ''}
          </div>`
        : ''}
      ${sat
        ? html`<div class="pv-modes">
            <div class="pv-mode-switch" role="group" aria-label="Kind of view">
              <button type="button" class="pv-mode" data-mode="satellite" aria-pressed="false" ${this.#satBlocked ? raw('disabled') : ''}>${raw(SAT_ICON)}Satellite</button>
              <button type="button" class="pv-mode" data-mode="drawn" aria-pressed="false">${raw(DRAWN_ICON)}Drawn</button>
            </div>
            <p class="pv-mode-hint" data-pv-mode-hint></p>
          </div>
          ${todaysLandNote(t.status) ? html`<p class="pv-sat-note" data-pv-sat-note hidden>${todaysLandNote(t.status)}</p>` : ''}`
        : ''}
      <div class="pv-stage">
        <div class="pv-viewport" tabindex="0" role="slider" aria-valuemin="0" aria-valuemax="359" aria-valuenow="0"
          aria-label="View from ${t.name}. Left and right arrow keys turn, Shift turns faster, plus and minus zoom."
          aria-describedby="${this.#id}-keys">
          <canvas class="pv-canvas" aria-hidden="true"></canvas>
          <div class="pv-loading" data-pv-loading>
            <p class="pv-loading-text" role="status" aria-live="polite" data-pv-status>Starting…</p>
            <div class="pv-meter" aria-hidden="true"><span data-pv-meter></span></div>
          </div>
          <div class="pv-tip" data-pv-tip hidden></div>
        </div>
        ${sat
          ? html`<div class="pv-sat" data-pv-sat hidden>
              <div class="pv-sat-view" tabindex="0" role="slider" aria-valuemin="0" aria-valuemax="359" aria-valuenow="0"
                aria-label="Satellite view from ${t.name}. Left and right arrow keys turn, up and down tilt, plus and minus zoom."
                aria-describedby="${this.#id}-keys ${this.#id}-sat-alt"></div>
              <div class="pv-sat-gate" data-pv-sat-gate hidden>
                <p class="pv-sat-gate-title">Satellite view</p>
                <p>Photos of today's land, laid over the terrain. It downloads about ${megabytes(satelliteDownload(true).start)} to start, and up to about ${megabytes(satelliteDownload(true).around)} if you look all the way round.</p>
                <p class="pv-sat-gate-actions"><button type="button" class="btn btn-primary" data-pv-sat-load>Load the satellite view</button>
                  <button type="button" class="linklike" data-mode="drawn">Use the drawn view</button></p>
              </div>
              <p class="pv-sat-credit" data-pv-sat-credit></p>
              <p class="visually-hidden" id="${this.#id}-sat-alt">The satellite view is a picture of the land around the lookout with the names of the peaks and lookouts in sight. They are listed below the view, and the drawn view gives their exact bearings.</p>
            </div>`
          : ''}
        <p class="visually-hidden" id="${this.#id}-keys">N, E, S and W keys face north, east, south and west.</p>
        <div class="pv-bar">
          <div class="pv-turn" role="group" aria-label="Turn">
            <button type="button" class="pv-btn" data-turn="-10" aria-label="Turn left 10 degrees" title="Turn left 10°">${raw(ARROW2_L)}</button>
            <button type="button" class="pv-btn" data-turn="-1" aria-label="Turn left 1 degree" title="Turn left 1°">${raw(ARROW_L)}</button>
            <p class="pv-heading" aria-hidden="true"><span class="pv-heading-label">Looking</span> <strong data-pv-bearing>due north</strong> <span class="pv-heading-az" data-pv-az>000°</span></p>
            <button type="button" class="pv-btn" data-turn="1" aria-label="Turn right 1 degree" title="Turn right 1°">${raw(ARROW_R)}</button>
            <button type="button" class="pv-btn" data-turn="10" aria-label="Turn right 10 degrees" title="Turn right 10°">${raw(ARROW2_R)}</button>
          </div>
          <div class="pv-tools">
            <span class="pv-zoom" role="group" aria-label="Zoom">
              <button type="button" class="pv-btn" data-zoom="-1" aria-label="Zoom out: see more of the circle" title="Zoom out">−</button>
              <button type="button" class="pv-btn" data-zoom="1" aria-label="Zoom in" title="Zoom in">+</button>
            </span>
            <button type="button" class="pv-btn pv-stretch" data-stretch aria-pressed="false" title="Draw heights twice as tall, to read low ridges">Heights ×2</button>
            ${sat
              ? html`<button type="button" class="pv-btn pv-text-btn" data-pv-frame aria-pressed="${String(this.#frame)}" title="Draw the cab's window posts and sill" ${CAB_KINDS.has(t.kind) ? '' : raw('data-no-cab')} hidden>Window frame</button>
                <button type="button" class="pv-btn pv-text-btn" data-pv-outside hidden>Step outside</button>`
              : ''}
          </div>
        </div>
        <div class="pv-overview-wrap">
          <canvas class="pv-overview" aria-hidden="true" title="The whole circle. Click to face that way."></canvas>
        </div>
        <p class="visually-hidden" aria-live="polite" data-pv-live></p>
      </div>
      ${this.#o.lists !== false ? html`<div class="pv-lists" data-pv-lists hidden></div>` : ''}
      <details class="pv-notes" data-pv-notes hidden><summary>How this view is made</summary><div data-pv-notes-body></div></details>`.value;

    this.#canvas = this.el.querySelector('.pv-canvas')!;
    this.#overview = this.el.querySelector('.pv-overview')!;
    this.#viewport = this.el.querySelector('.pv-viewport')!;
    this.#stage = this.el.querySelector('.pv-stage')!;
    this.#satEl = this.el.querySelector('[data-pv-sat]') ?? document.createElement('div');
    this.#satView = this.el.querySelector('.pv-sat-view') ?? this.#viewport;
    this.#bind();
    this.#syncMode();
  }

  #q<T extends HTMLElement>(sel: string): T | null {
    return this.el.querySelector<T>(sel);
  }

  #bind(): void {
    const vp = this.#viewport;
    // Buttons.
    this.el.addEventListener('click', (e) => {
      const b = (e.target as Element).closest<HTMLElement>('button');
      if (!b || !this.el.contains(b)) return;
      if (b.dataset.turn) this.#turnBy(Number(b.dataset.turn));
      else if (b.dataset.zoom) {
        if (this.#satShowing() && this.#sat) this.#sat.zoom(Number(b.dataset.zoom));
        else this.#zoom(Number(b.dataset.zoom));
      } else if (b.dataset.mode) this.#setMode(b.dataset.mode as CabMode, true);
      else if (b.hasAttribute('data-pv-sat-load')) {
        this.#satConfirmed = true;
        void this.#showSatellite(true);
      } else if (b.hasAttribute('data-pv-outside')) {
        if (this.#sat?.outside) this.#sat.backInCab();
        else this.#sat?.stepOutside();
        this.#syncSatTools();
      } else if (b.hasAttribute('data-pv-frame')) {
        this.#frame = !this.#frame;
        saveFrame(this.#frame);
        b.setAttribute('aria-pressed', String(this.#frame));
        this.#sat?.setOptions({ frame: this.#frame });
      } else if (b.hasAttribute('data-stretch')) {
        this.#view.exaggeration = this.#view.exaggeration === 1 ? 2 : 1;
        b.setAttribute('aria-pressed', String(this.#view.exaggeration === 2));
        this.#relayout();
      } else if (b.hasAttribute('data-pv-eye-open')) this.#toggleEyeForm();
      else if (b.dataset.eyeFt) {
        const input = this.#q<HTMLInputElement>('.pv-eye-form input');
        if (input) input.value = b.dataset.eyeFt;
      } else if (b.hasAttribute('data-pv-eye-reset')) {
        this.#customEye = null;
        this.#eye = eyeHeight({ kind: this.#o.tower.kind, height_m: this.#o.tower.height_m, lon: this.#o.tower.lon });
        this.#toggleEyeForm(false);
        void this.start();
      } else if (b.dataset.face) {
        this.#highlight = b.dataset.key ?? null;
        this.#sat?.setOptions({ highlight: this.#highlight });
        this.turnTo(Number(b.dataset.face), true);
        if (this.#sat?.outside) {
          this.#sat.backInCab();
          this.#syncSatTools();
        }
        this.focus();
        (this.#satShowing() ? this.#satEl : vp).scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      } else if (b.hasAttribute('data-pv-retry')) void this.start();
      else if (b.hasAttribute('data-pv-more')) {
        b.closest('section')?.querySelectorAll<HTMLElement>('[data-extra]').forEach((li) => (li.hidden = false));
        b.remove();
      }
    });
    this.#q<HTMLFormElement>('.pv-eye-form')?.addEventListener('submit', (e) => {
      e.preventDefault();
      // feet in the US, metres elsewhere (the input's own unit)
      const v = Number(this.#q<HTMLInputElement>('.pv-eye-form input')?.value);
      if (!Number.isFinite(v) || v <= 0) return;
      this.#customEye = this.#metric ? v : v * 0.3048;
      this.#eye = eyeHeight({ kind: this.#o.tower.kind, height_m: this.#o.tower.height_m, lon: this.#o.tower.lon }, this.#customEye);
      this.#toggleEyeForm(false);
      void this.start();
    });

    // Keyboard on the view.
    vp.addEventListener('keydown', (e) => {
      const step = this.#o.stepDeg ?? 1;
      const keys: Record<string, () => void> = {
        ArrowLeft: () => this.turnTo(this.#view.az - (e.shiftKey ? step * 10 : step), true),
        ArrowRight: () => this.turnTo(this.#view.az + (e.shiftKey ? step * 10 : step), true),
        ArrowDown: () => this.turnTo(this.#view.az - step, true),
        ArrowUp: () => this.turnTo(this.#view.az + step, true),
        PageUp: () => this.turnTo(this.#view.az + 10, true),
        PageDown: () => this.turnTo(this.#view.az - 10, true),
        Home: () => this.turnTo(0, true),
        End: () => this.turnTo(180, true),
        '+': () => this.#zoom(1),
        '=': () => this.#zoom(1),
        '-': () => this.#zoom(-1),
        n: () => this.turnTo(0, true),
        e: () => this.turnTo(90, true),
        s: () => this.turnTo(180, true),
        w: () => this.turnTo(270, true),
      };
      const fn = keys[e.key] ?? keys[e.key.toLowerCase()];
      if (fn && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault();
        fn();
      }
    });

    // Drag to turn.
    let drag: { x: number; az: number; id: number; moved: boolean } | null = null;
    vp.addEventListener('pointerdown', (e) => {
      if (!this.#data || e.button !== 0) return;
      drag = { x: e.clientX, az: this.#view.az, id: e.pointerId, moved: false };
      vp.setPointerCapture(e.pointerId);
      vp.classList.add('is-dragging');
    });
    vp.addEventListener('pointermove', (e) => {
      if (drag && e.pointerId === drag.id) {
        const dx = e.clientX - drag.x;
        if (Math.abs(dx) > 2) drag.moved = true;
        this.turnTo(drag.az - dx / this.#view.pxPerDeg);
        this.#tip(null);
      } else if (e.pointerType === 'mouse') this.#tipAt(e);
    });
    const end = (e: PointerEvent) => {
      if (!drag || e.pointerId !== drag.id) return;
      vp.classList.remove('is-dragging');
      drag = null;
      this.#updateHeading(true);
    };
    vp.addEventListener('pointerup', end);
    vp.addEventListener('pointercancel', end);
    vp.addEventListener('pointerleave', () => this.#tip(null));
    vp.addEventListener(
      'wheel',
      (e) => {
        if (!this.#data || Math.abs(e.deltaX) <= Math.abs(e.deltaY)) return; // vertical wheel scrolls the page
        e.preventDefault();
        this.turnTo(this.#view.az + e.deltaX / this.#view.pxPerDeg);
      },
      { passive: false },
    );

    // The whole-circle strip.
    const ov = this.#overview;
    const fromStrip = (e: PointerEvent) => {
      const r = ov.getBoundingClientRect();
      this.turnTo(((e.clientX - r.left) / r.width) * 360);
    };
    ov.addEventListener('pointerdown', (e) => {
      if (!this.#data) return;
      ov.setPointerCapture(e.pointerId);
      fromStrip(e);
    });
    ov.addEventListener('pointermove', (e) => {
      if (ov.hasPointerCapture(e.pointerId)) fromStrip(e);
    });
    ov.addEventListener('pointerup', () => this.#updateHeading(true));

    this.#resize = new ResizeObserver(() => this.#relayout());
    this.#resize.observe(this.el);
  }

  #toggleEyeForm(open?: boolean): void {
    const form = this.#q<HTMLFormElement>('.pv-eye-form');
    const btn = this.#q<HTMLButtonElement>('[data-pv-eye-open]');
    if (!form || !btn) return;
    const show = open ?? form.hidden;
    form.hidden = !show;
    btn.setAttribute('aria-expanded', String(show));
    if (show) {
      const input = form.querySelector('input')!;
      input.value = this.#metric ? String(Math.round(this.#eye.eyeM * 2) / 2) : String(Math.round(this.#eye.eyeM / 0.3048));
      input.focus();
    }
  }

  #zoom(dir: number): void {
    const i = ZOOMS.findIndex((z) => z >= this.#view.pxPerDeg - 0.01);
    const next = ZOOMS[Math.min(Math.max((i < 0 ? ZOOMS.length - 1 : i) + dir, 0), ZOOMS.length - 1)]!;
    if (next === this.#view.pxPerDeg) return;
    this.#view.pxPerDeg = next;
    this.#relayout();
    this.#announce(`Zoom: ${Math.round(this.#canvasWidth() / next)} degrees of the circle in view.`);
  }

  #canvasWidth(): number {
    return this.#stage?.clientWidth || this.#viewport.clientWidth || 600;
  }

  /* ---------- Satellite and drawn ---------- */

  #setMode(mode: CabMode, byVisitor: boolean): void {
    if (mode === this.#mode || (mode === 'satellite' && this.#satBlocked)) return;
    if (mode === 'drawn') this.#sat?.backInCab(true);
    this.#mode = mode;
    if (byVisitor) saveCabMode(mode);
    this.#syncMode();
    this.#relayout();
    this.#updateHeading(false);
    if (mode === 'satellite') void this.#showSatellite(false);
    this.#announce(mode === 'satellite' ? 'Satellite view.' : 'Drawn view.');
  }

  /** Show what the mode and the loading state call for. */
  #syncMode(): void {
    if (!this.#o.satellite) return;
    const sat = this.#mode === 'satellite';
    const ready = this.el.dataset.state === 'ready';
    const gate = sat && ready && !this.#sat && lightDetail(this.#canvasWidth()) && !this.#satConfirmed;
    for (const b of this.el.querySelectorAll<HTMLButtonElement>('.pv-mode[data-mode]')) {
      b.setAttribute('aria-pressed', String(b.dataset.mode === this.#mode));
      if (b.dataset.mode === 'satellite') b.disabled = !!this.#satBlocked;
    }
    const hint = this.#q('[data-pv-mode-hint]');
    if (hint) {
      hint.textContent =
        this.#satBlocked ??
        (sat ? "Photos of today's land on the terrain. Drag to look around and tilt; the wheel or a pinch zooms." : 'Ridgelines worked out from terrain data, with exact bearings.');
      hint.classList.toggle('is-warn', !!this.#satBlocked);
    }
    const note = this.#q('[data-pv-sat-note]');
    if (note) note.hidden = !sat;
    // While the terrain loads (or reloads) the drawn view's box carries the progress.
    const active = document.activeElement;
    const hadFocus = active === this.#viewport || active === this.#satView;
    this.#viewport.hidden = sat && ready;
    this.#satEl.hidden = !(sat && ready);
    this.#q('[data-pv-sat-gate]')!.hidden = !gate;
    this.#satView.hidden = gate;
    this.#q('[data-pv-sat-credit]')!.hidden = gate;
    this.#q('[data-stretch]')!.hidden = sat;
    this.#syncSatTools();
    // Keep the keyboard on the view when one box gives way to the other.
    if (hadFocus && document.activeElement !== active) {
      const load = gate ? this.#q<HTMLElement>('[data-pv-sat-load]') : null;
      if (load) load.focus({ preventScroll: true });
      else this.focus();
    }
  }

  #syncSatTools(): void {
    const on = this.#satShowing() && !!this.#sat;
    const outside = this.#q<HTMLButtonElement>('[data-pv-outside]');
    if (outside) {
      outside.hidden = !on;
      outside.textContent = this.#sat?.outside ? 'Back in the cab' : 'Step outside';
    }
    const frame = this.#q<HTMLButtonElement>('[data-pv-frame]');
    if (frame) {
      frame.hidden = !on || frame.hasAttribute('data-no-cab');
      frame.disabled = !!this.#sat?.outside;
    }
  }

  /** Where the view's centre starts: a little below level, more where mountains rise all round. */
  #initialTilt(d: PanoramaData): number {
    const last = (d.layersM.length - 1) * d.columns;
    let hi = -90;
    for (let c = 0; c < d.columns; c++) hi = Math.max(hi, d.horizon[last + c]!);
    return Math.min(Math.max(hi * 0.5 - 3, -6), 4);
  }

  /** Start (or show again) the satellite view, once the terrain result is in. */
  async #showSatellite(focus: boolean): Promise<void> {
    if (this.#mode !== 'satellite' || !this.#data || this.el.dataset.state !== 'ready') return;
    this.#syncMode();
    if (this.#sat) {
      this.#sat.setBearing(this.#view.az);
      if (focus) this.#sat.focus();
      return;
    }
    if (!this.#q('[data-pv-sat-gate]')!.hidden) return; // phones: wait for the tap
    const run = this.#run;
    try {
      const { SatelliteView } = await (this.#satLoad ??= import('./satellite-view.ts'));
      if (this.#mode !== 'satellite' || this.#sat || run !== this.#run || !this.#data) return;
      const t = this.#o.tower;
      this.#sat = new SatelliteView({
        host: this.#satView,
        credit: this.#q('[data-pv-sat-credit]')!,
        data: this.#data,
        eyeAboveGroundM: this.#eye.eyeM,
        items: this.#items,
        bearing: this.#view.az,
        tilt: this.#initialTilt(this.#data),
        light: lightDetail(this.#canvasWidth()),
        sharedTiles: planTiles([t], panoramaLevels(this.#o.maxDistM ?? MAX_DIST_M, lightDetail(this.#canvasWidth()) ? 'light' : 'full')),
        theme: this.#theme,
        frame: this.#frame,
        highlight: this.#highlight,
        name: shortName(t.name),
        onTurn: (az, announce) => this.turnTo(az, announce),
        onChange: () => {
          this.#updateHeading(false);
          this.#syncSatTools();
          this.#draw();
        },
        onReady: () => this.#data && this.#renderNotes(this.#data),
        onSources: () => this.#data && this.#renderNotes(this.#data),
        onIdle: () => {
          const li = this.#q('[data-pv-sat-tally]');
          if (li) li.innerHTML = this.#satTally().value;
        },
        onFail: (err) => this.#satFailed(err),
      });
      this.#syncMode();
      this.#updateHeading(false);
      this.#draw();
      if (focus) this.#sat.focus();
    } catch (err) {
      this.#satFailed(err);
    }
  }

  /** The satellite view could not start: fall back to the drawn view and say so. */
  #satFailed(err: unknown): void {
    console.error(err);
    this.#sat?.destroy();
    this.#sat = null;
    this.#satBlocked = "The satellite view couldn't start in this browser, so the view is drawn.";
    this.#mode = 'drawn';
    this.#syncMode();
    this.#relayout();
    this.#updateHeading(false);
  }

  /** Load terrain and names (again, after an eye-height change) and draw. */
  async start(): Promise<void> {
    const run = ++this.#run;
    const t = this.#o.tower;
    this.el.dataset.state = 'loading';
    this.#q('[data-pv-loading]')!.hidden = false;
    const text = this.#q('[data-pv-eye-text]');
    if (text) text.textContent = this.#eye.sentence;
    const status = this.#q('[data-pv-status]')!;
    const meter = this.#q<HTMLElement>('[data-pv-meter]')!;
    const light = lightDetail(this.#canvasWidth());
    const smoke = this.#o.smoke;
    this.#syncMode();
    // The satellite view's code (and MapLibre) loads while the terrain does; phones wait for a tap.
    if (this.#mode === 'satellite' && !light) this.#satLoad ??= import('./satellite-view.ts');
    try {
      if (document.fonts?.load) await Promise.race([document.fonts.load(`600 12px ${FONT}`), new Promise((r) => setTimeout(r, 1500))]);
      const data = await requestPanorama(
        {
          base: siteBase(),
          lat: t.lat,
          lon: t.lon,
          eyeAboveGroundM: this.#eye.eyeM,
          maxDistM: this.#o.maxDistM ?? MAX_DIST_M,
          azStepDeg: light ? 0.2 : 0.1,
          detail: light ? 'light' : 'full',
          selfId: t.id,
          labels: this.#o.labels !== false,
          extra: smoke ? [{ lat: smoke.lat, lon: smoke.lon, aboveGroundM: 0 }, { lat: smoke.lat, lon: smoke.lon, aboveGroundM: smoke.heightM }] : [],
        },
        (p) => {
          if (run !== this.#run) return;
          status.textContent = progressText(p);
          meter.style.width = p.phase === 'terrain' && p.total ? `${Math.round((p.done / p.total) * 100)}%` : p.phase === 'terrain' ? '0%' : '100%';
        },
      );
      if (run !== this.#run) return;
      const first = !this.#data;
      this.#data = data;
      if (smoke && data.extra.length === 2) {
        const [base, top] = data.extra as [Sighted, Sighted];
        this.#smoke = {
          az: base.az,
          baseAngle: base.angle,
          topAngle: top.angle,
          widthDeg: Math.max((120 / base.distM) * (180 / Math.PI), 0.12),
          seed: Math.round(smoke.lat * 1e5) ^ Math.round(smoke.lon * 1e5),
        };
      }
      this.#items = this.#labelItems(data);
      this.el.dataset.state = 'ready';
      this.#q('[data-pv-loading]')!.hidden = true;
      if (first) {
        this.#view.pxPerDeg = this.#canvasWidth() < 560 ? 9 : 12;
        // Where the whole skyline stays within a degree or so of level (plateaus, rolling
        // eastern hills) true proportions show a flat line; start with heights doubled, which
        // the button and the view both say.
        if (skylineRelief(data) < 1.5) {
          this.#view.exaggeration = 2;
          this.#q('[data-stretch]')?.setAttribute('aria-pressed', 'true');
        }
      }
      this.#sat?.update(data, this.#eye.eyeM, this.#items);
      this.#syncMode();
      this.#relayout();
      this.#updateHeading(false);
      this.#renderLists(data);
      this.#renderNotes(data);
      this.#o.onReady?.(data);
      void this.#showSatellite(false);
    } catch (err) {
      if (run !== this.#run) return;
      console.error(err);
      this.el.dataset.state = 'error';
      this.#syncMode();
      status.innerHTML = html`<strong>The view could not be made.</strong> ${navigator.onLine === false ? 'You seem to be offline. ' : 'The terrain or the engine did not load. '}<button type="button" class="linklike" data-pv-retry>Try again</button>`.value;
      meter.style.width = '0%';
    }
  }

  #labelItems(d: PanoramaData): LabelItem[] {
    const lastLayer = d.layersM.length - 1;
    const items: LabelItem[] = [];
    const seenLookouts = d.lookouts.filter((l) => l.visible);
    for (const p of d.peaks) {
      // The summit the lookout stands on, and summits a lookout already names.
      if (p.distM < 300) continue;
      if (seenLookouts.some((l) => Math.abs(l.distM - p.distM) < 500 && Math.abs(((l.az - p.az + 540) % 360) - 180) * (Math.PI / 180) * p.distM < 500)) continue;
      const sky = horizonAt(d, lastLayer, p.az);
      const onSkyline = p.angle >= sky - 0.05;
      items.push({
        key: `p${p.gnisId}`,
        kind: 'peak',
        name: p.name,
        sub: unitsFor(this.#o.tower.country).short(p.distM),
        sight: p,
        score: Math.min(p.clearance, 2) + (onSkyline ? 0.8 : 0) + Math.max(0, p.angle + 2) * 0.25 + p.groundM / 4000,
      });
    }
    for (const l of d.lookouts) {
      if (!l.visible) continue;
      const gone = l.status === 'gone' || l.status === 'ruins';
      items.push({
        key: `l${l.id}`,
        kind: 'lookout',
        name: shortName(l.name),
        sub: `${gone ? 'site, gone' : 'lookout'} · ${unitsFor(this.#o.tower.country).short(l.distM)}`,
        sight: l,
        gone,
        score: 3 + (gone ? 0 : 1.5) - l.distM / 100_000,
      });
    }
    return items;
  }

  #relayout(): void {
    if (!this.#data) return;
    const w = this.#canvasWidth();
    const compact = w < 560;
    const h = compact ? 250 : 330;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    for (const [c, cw, ch] of [
      [this.#canvas, w, h],
      [this.#overview, this.#overview.clientWidth || w, 46],
    ] as const) {
      c.width = Math.round(cw * dpr);
      c.height = Math.round(ch * dpr);
      c.style.height = `${ch}px`;
    }
    this.#layout = makeLayout(this.#data, w, h, this.#view, compact ? 2 : 3);
    this.#draw();
  }

  #draw(): void {
    if (!this.#data || !this.#layout) return;
    cancelAnimationFrame(this.#frameReq);
    this.#frameReq = requestAnimationFrame(() => {
      const d = this.#data!;
      const L = this.#layout!;
      const P = PALETTES[this.#theme];
      const sat = this.#satShowing() ? this.#sat : null;
      if (sat) {
        this.#drawOverview(d, L, P, sat.viewBearing, sat.spanDeg);
        return;
      }
      const dpr = this.#canvas.width / L.width;
      const ctx = this.#canvas.getContext('2d')!;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const measure = (s: string, bold: boolean) => {
        ctx.font = `${bold ? 700 : 600} 12px ${FONT}`;
        return ctx.measureText(s).width;
      };
      const labels = placeLabels(this.#items, this.#view, L, measure);
      drawPanorama(ctx, d, this.#view, L, { labels, palette: P, smoke: this.#smoke, highlight: this.#highlight });
      if (this.#view.exaggeration !== 1) {
        const text = `Heights drawn ×${this.#view.exaggeration}`;
        ctx.font = `700 11px ${FONT}`;
        const w = ctx.measureText(text).width + 12;
        ctx.fillStyle = P.labelHalo;
        ctx.beginPath();
        ctx.roundRect(6, L.ringTop - 24, w, 18, 9);
        ctx.fill();
        ctx.fillStyle = P.accent;
        ctx.fillText(text, 12, L.ringTop - 11);
      }
      this.#drawOverview(d, L, P, this.#view.az, L.width / this.#view.pxPerDeg);
    });
  }

  /** The whole-circle strip, its window on the part in view. */
  #drawOverview(d: PanoramaData, L: Layout, P: (typeof PALETTES)[keyof typeof PALETTES], az: number, spanDeg: number): void {
    const ov = this.#overview;
    const octx = ov.getContext('2d')!;
    const odpr = ov.width / (ov.clientWidth || L.width);
    octx.setTransform(odpr, 0, 0, odpr, 0, 0);
    drawOverview(octx, d, { ...this.#view, az }, ov.clientWidth || L.width, 46, P, spanDeg);
  }

  #updateHeading(announce: boolean): void {
    const sat = this.#satShowing() ? this.#sat : null;
    const outside = !!sat?.outside;
    const az = outside ? sat!.viewBearing : this.#view.az;
    const bearing = quadrantBearing(az);
    const azText = azimuthText(az);
    const b = this.#q('[data-pv-bearing]');
    if (b) b.textContent = bearing;
    const a = this.#q('[data-pv-az]');
    if (a) a.textContent = azText;
    const label = this.#q('.pv-heading-label');
    if (label) label.textContent = outside ? 'Outside, facing' : 'Looking';
    const ahead = outside ? null : this.#ahead();
    const smoke = this.#smokeWords();
    const azWords = this.#o.stepDeg && this.#o.stepDeg < 1 ? azimuthText(Math.round(az * 2) / 2, 1).replace('°', ' degrees') : `${Math.round(az) % 360} degrees`;
    const valuetext = `Looking ${bearing}, azimuth ${azWords}.${ahead ? ` Ahead: ${ahead}.` : ''}${smoke ? ` ${smoke}` : ''}`;
    this.#viewport.setAttribute('aria-valuenow', String(Math.round(az) % 360));
    this.#viewport.setAttribute('aria-valuetext', valuetext);
    if (this.#satView !== this.#viewport) {
      this.#satView.setAttribute('aria-valuenow', String(Math.round(az) % 360));
      this.#satView.setAttribute('aria-valuetext', outside ? sat!.describe() : `${valuetext}${sat ? ` ${sat.describe()}` : ''}`);
    }
    if (announce) {
      clearTimeout(this.#liveTimer);
      this.#liveTimer = window.setTimeout(() => this.#announce(`${bearing}.${ahead ? ` Ahead: ${ahead}.` : ''}${smoke ? ` ${smoke}` : ''}`), 350);
    }
  }

  #announce(text: string): void {
    const live = this.#q('[data-pv-live]');
    if (live) live.textContent = text;
  }

  /** The named thing nearest the sighting hair, within 1.5°. */
  #ahead(): string | null {
    let best: LabelItem | null = null;
    let bestD = 1.5;
    for (const it of this.#items) {
      const dd = Math.abs(((it.sight.az - this.#view.az + 540) % 360) - 180);
      if (dd < bestD) {
        bestD = dd;
        best = it;
      }
    }
    if (!best) return null;
    return `${best.kind === 'lookout' ? (best.gone ? 'the site of ' : '') : ''}${best.name}${best.kind === 'lookout' ? ' lookout' : ''}, ${this.#distance(best.sight.distM)}`;
  }

  #tip(text: string | null, x = 0, y = 0): void {
    const tip = this.#q<HTMLElement>('[data-pv-tip]');
    if (!tip) return;
    if (!text) {
      tip.hidden = true;
      return;
    }
    tip.hidden = false;
    tip.textContent = text;
    const w = this.#canvasWidth();
    tip.style.left = `${Math.min(Math.max(x + 12, 4), w - 200)}px`;
    tip.style.top = `${Math.max(y - 34, 4)}px`;
  }

  #tipAt(e: PointerEvent): void {
    const d = this.#data;
    const L = this.#layout;
    if (!d || !L) return;
    const r = this.#canvas.getBoundingClientRect();
    const x = e.clientX - r.left;
    const y = e.clientY - r.top;
    if (y < L.terrainTop || y > L.ringTop) return this.#tip(null);
    const p = pick(d, this.#view, L, x, y);
    const bearing = `bearing ${azimuthText(p.az)}`;
    this.#tip(p.distM === null ? `Sky · ${bearing}` : `Ground about ${this.#distance(p.distM)} away · ${bearing}`, x, y);
  }

  #renderLists(d: PanoramaData): void {
    const host = this.#q('[data-pv-lists]');
    if (!host) return;
    const named = d.peaks.filter((p) => p.distM >= 300);
    const peaks = [...named].sort((a, b) => scorePeak(b) - scorePeak(a));
    const top = new Set(peaks.slice(0, 12).map((p) => p.gnisId));
    const byBearing = [...named].sort((a, b) => a.az - b.az);
    const visibleLookouts = d.lookouts.filter((l) => l.visible).sort((a, b) => a.distM - b.distM);
    const hiddenLookouts = d.lookouts.length - visibleLookouts.length;
    const base = import.meta.env.BASE_URL;
    const faceBtn = (s: Sighted, key: string, label: string) =>
      html`<button type="button" class="linklike" data-face="${s.az.toFixed(2)}" data-key="${key}" aria-label="Face ${label}">${label}</button>`;
    const where = (s: Sighted) => html`<span class="pv-where">${this.#distance(s.distM)} · ${azimuthText(s.az)} (${quadrantBearing(s.az)})</span>`;
    host.innerHTML = html`
      <section aria-labelledby="${this.#id}-lk">
        <h3 class="h-small" id="${this.#id}-lk">Other lookouts in sight <span class="pv-count">${visibleLookouts.length}</span></h3>
        ${visibleLookouts.length
          ? html`<ul class="pv-list">${visibleLookouts.map(
              (l: LookoutSight, i: number) => html`<li ${i < 8 ? '' : raw('data-extra hidden')}><span class="pv-mark ${l.status === 'gone' || l.status === 'ruins' ? 'is-gone' : ''}" aria-hidden="true"></span>
                ${faceBtn(l, `l${l.id}`, l.name)} ${l.status === 'gone' || l.status === 'ruins' ? html`<span class="pv-tag">gone</span>` : ''}
                ${where(l)} <a class="pv-page" href="${base}t/${l.id}/">page<span class="visually-hidden"> for ${l.name}</span></a></li>`,
            )}</ul>
            ${visibleLookouts.length > 8 ? html`<p><button type="button" class="linklike" data-pv-more>Show all ${visibleLookouts.length}</button></p>` : ''}`
          : html`<p class="fine">No other lookout's cab is in line of sight within ${unitsFor(this.#o.tower.country).short(this.#o.maxDistM ?? MAX_DIST_M)}.</p>`}
        <p class="fine">${hiddenLookouts ? `${hiddenLookouts} more lookout ${hiddenLookouts === 1 ? 'site is' : 'sites are'} within range but hidden by terrain. ` : ''}Gone lookouts are shown at their old sites, so you can see which ones once watched each other. Their cabs are taken at typical heights.</p>
      </section>
      <section aria-labelledby="${this.#id}-pk">
        <h3 class="h-small" id="${this.#id}-pk">Named peaks in sight <span class="pv-count">${named.length}</span></h3>
        ${named.length
          ? html`<ul class="pv-list">${byBearing.map(
              (p: PeakSight) => html`<li ${top.has(p.gnisId) ? '' : raw('data-extra hidden')}>${faceBtn(p, `p${p.gnisId}`, p.name)} ${where(p)} <span class="pv-elev">${unitsFor(this.#o.tower.country).aboutHeight(p.groundM)}</span></li>`,
            )}</ul>
            ${named.length > top.size ? html`<p><button type="button" class="linklike" data-pv-more>Show all ${named.length}</button></p>` : ''}`
          : html`<p class="fine">No named summits in line of sight${d.peaksChecked ? '' : ' (the list of peak names did not load)'}.</p>`}
        <p class="fine">${peakCredit(peaks)} Heights are read from the terrain data and are approximate. Sorted by bearing, clockwise from north.</p>
      </section>`.value;
    host.hidden = false;
  }

  #renderNotes(d: PanoramaData): void {
    const host = this.#q('[data-pv-notes-body]');
    const box = this.#q<HTMLElement>('[data-pv-notes]');
    if (!host || !box) return;
    const o = d.observer;
    const t = this.#o.tower;
    const rec = typeof t.elevation_m === 'number' ? t.elevation_m : null;
    const moved = o.movedM >= 1;
    host.innerHTML = html`<ul class="pv-notes-list">
      <li><strong>Eye:</strong> ${this.#eye.sentence} That puts your eyes at ${metresFeet(o.eyeM, 0)} above sea level.</li>
      <li><strong>Ground:</strong> ${metresFeet(o.groundM, 0)} from the terrain data${rec !== null ? html`; the lookout's records give ${metresFeet(rec, 0)}` : ''}.
        ${moved ? html`The eye stands on the highest ground within ${75} m of the recorded position (${Math.round(o.movedM)} m away), because recorded positions and coarse terrain can put a summit lookout on its own slope.` : ''}</li>
      <li><strong>Terrain:</strong> bare ground from <a href="https://registry.opendata.aws/terrain-tiles/" rel="noopener">AWS Terrain Tiles</a> (USGS 3DEP, SRTM and GMTED2010 elevations), about 30 m apart near the lookout, 110 m out to 25 miles and 220–300 m beyond. Trees, buildings, haze and weather are not shown, and sharp distant summits come out somewhat lower than they are.</li>
      <li><strong>Geometry:</strong> earth curvature and the slight bending of light in the air (refraction coefficient 0.13) are included. Bearings are true (from true north), like a Firefinder's ring, not magnetic. The view reaches ${unitsFor(this.#o.tower.country).short(this.#o.maxDistM ?? MAX_DIST_M)}.</li>
      <li><strong>Names:</strong> a peak is named when its summit is in line of sight, even if it is a speck in the distance. Other lookouts are named when their cabs would be in sight at a typical height.</li>
      <li><strong>Computed</strong> in your browser in ${(d.ms.compute / 1000).toFixed(1)} s from ${d.tiles.needed} terrain tiles${d.tiles.bytes ? ` (${megabytes(d.tiles.bytes)} downloaded)` : ' (already downloaded)'}.
        ${d.tiles.failed ? html` <strong class="warn-text">${d.tiles.failed} tiles did not load, so parts of the view may be missing.</strong>` : ''}</li>
    </ul>
    ${this.#o.satellite ? this.#satNotes(d) : ''}`.value;
    box.hidden = false;
  }

  /** "How this view is made", the satellite view's part. */
  #satNotes(d: PanoramaData): SafeHtml {
    const o = d.observer;
    const t = this.#o.tower;
    const tally = this.#sat?.tally;
    return html`<h4 class="pv-notes-sub">The satellite view</h4>
      <ul class="pv-notes-list">
        <li><strong>Photos:</strong> in the United States, aerial photos from the U.S. Geological Survey's
          <a href="https://www.usgs.gov/programs/national-geospatial-program/national-map" rel="noopener">The National Map</a>: mostly the USDA's
          National Agriculture Imagery Program (NAIP), about 1 m detail, flown in summer in recent years (the service was last refreshed in June 2024), with
          Landsat and Blue Marble images far off. In Canada and Alaska, and wherever the USGS has none, <a href="https://cloudless.eox.at" rel="noopener">Sentinel-2 cloudless 2024</a>
          by EOX: cloud-free summer 2024 satellite images, about 10 m detail. A view across the border uses both, each where it has photos.</li>
        <li><strong>Terrain and the earth's curve:</strong> the same AWS Terrain Tiles as the drawn view, in finer tiles near the cab. The map under the photos is flat, so Firefinder lowers every height by the
          earth's curve less the bending of light (the drawn view's numbers): about 4 m at 8 km, 250 m at 60 km and 1.5 km at 150 km. Far ridges sink behind nearer ones as they do from the cab.</li>
        <li><strong>Eye:</strong> the camera stands where the drawn view's eye does, ${metresFeet(o.eyeM, 0)} above sea level. Names follow the drawn view's rule: a peak or lookout is named only when it is in line of sight.</li>
        <li><strong>Bearings:</strong> the ring reads true bearings. Because the photos lie on a flat (Web Mercator) map, a far peak can sit up to about half a degree from its true bearing (a degree in the far north); read exact bearings in the drawn view.</li>
        <li><strong>Not shown as they are:</strong> the sky and haze are drawn, not photographed, and trees and buildings lie flat on the photos instead of standing up.${CAB_KINDS.has(t.kind) ? " The window frame, if you switch it on, is a typical cab's (the Forest Service's L-4, 14 ft square, walls facing north, east, south and west), not this lookout's own." : ''}</li>
        ${tally ? html`<li data-pv-sat-tally>${this.#satTally()}</li>` : ''}
      </ul>`;
  }

  /** What the satellite view has downloaded so far, for the notes. */
  #satTally(): SafeHtml {
    const t = this.#sat?.tally;
    if (!t) return html``;
    return html`<strong>Downloaded</strong> so far: ${megabytes(t.photoBytes)} of photos (${t.photoTiles} tiles) and ${megabytes(t.demBytes - t.demSharedBytes)} of terrain, besides ${megabytes(t.demSharedBytes)} of terrain the drawn view had already downloaded. Some may have come from your browser's cache; looking around loads more.${t.failed ? html` <strong class="warn-text">${t.failed} tiles did not load, so parts of the view may be blank.</strong>` : ''}`;
  }

  destroy(): void {
    this.#offTheme();
    this.#resize?.disconnect();
    cancelAnimationFrame(this.#frameReq);
    this.#sat?.destroy();
    this.#sat = null;
    this.#run++;
  }
}

/** How much the far skyline rises and falls around the circle, degrees. */
function skylineRelief(d: PanoramaData): number {
  const row = (d.layersM.length - 1) * d.columns;
  let lo = 90;
  let hi = -90;
  for (let c = 0; c < d.columns; c++) {
    const a = d.horizon[row + c]!;
    if (a < -89) continue;
    lo = Math.min(lo, a);
    hi = Math.max(hi, a);
  }
  return hi - lo;
}

function scorePeak(p: PeakSight): number {
  return Math.min(p.clearance, 2) + Math.max(0, p.angle + 2) * 0.25 + p.groundM / 4000;
}

const SAT_ICON = '<svg class="pv-mode-icon" width="18" height="18" viewBox="0 0 18 18" aria-hidden="true" focusable="false"><path d="M1.5 14.5 6 8l3 3.5L12.5 6l4 8.5Z" fill="currentColor" opacity=".35"/><path d="M1.5 14.5 6 8l3 3.5L12.5 6l4 8.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><circle cx="13.5" cy="3.5" r="1.6" fill="currentColor"/></svg>';
const DRAWN_ICON = '<svg class="pv-mode-icon" width="18" height="18" viewBox="0 0 18 18" aria-hidden="true" focusable="false"><path d="M1 12.5 5 8l3 3 3.5-4.5 5.5 6M1 15.5h16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const ARROW_L = '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M10 3 5 8l5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const ARROW_R = '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="m6 3 5 5-5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const ARROW2_L = '<svg width="18" height="16" viewBox="0 0 18 16" aria-hidden="true" focusable="false"><path d="M9 3 4 8l5 5M15 3l-5 5 5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const ARROW2_R = '<svg width="18" height="16" viewBox="0 0 18 16" aria-hidden="true" focusable="false"><path d="m9 3 5 5-5 5M3 3l5 5-5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
