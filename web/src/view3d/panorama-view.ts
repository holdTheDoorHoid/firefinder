/**
 * "View from the cab": the interactive 360° panorama. Mounts into any element (a tower page
 * section, a dialog on the map, the smoke-spotting lesson) and loads its terrain only when
 * started.
 */
import '../styles/view3d.css';
import { html, raw } from '../lib/html.ts';
import { effectiveTheme, onThemeChange } from '../ui/theme.ts';
import { requestPanorama, progressText, siteBase } from './client.ts';
import {
  aboutFeet,
  azimuthText,
  eyeHeight,
  megabytes,
  metresFeet,
  milesKm,
  milesShort,
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

export interface PanoramaTower {
  id: string;
  name: string;
  lat: number;
  lon: number;
  kind: string;
  status: string;
  height_m?: number | null;
  elevation_m?: number | null;
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

function shortName(name: string): string {
  return name.replace(/\s+(Lookout( Site| Tower)?|Fire Tower|L\.O\.)$/i, '').trim() || name;
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
  #frame = 0;
  #liveTimer = 0;
  #resize: ResizeObserver | null = null;
  #theme = effectiveTheme();
  #run = 0;

  constructor(host: HTMLElement, opts: PanoramaOptions) {
    this.#o = opts;
    this.#view.az = opts.initialAz ?? 0;
    this.#eye = eyeHeight({ kind: opts.tower.kind, height_m: opts.tower.height_m, lon: opts.tower.lon });
    this.el = document.createElement('div');
    this.el.className = 'pv';
    this.el.dataset.state = 'idle';
    host.replaceChildren(this.el);
    this.#build();
    onThemeChange((t) => {
      this.#theme = t;
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

  /** Turn to an azimuth (degrees). */
  turnTo(az: number, announce = false): void {
    this.#view.az = wrap360(az);
    this.#updateHeading(announce);
    this.#draw();
    this.#o.onTurn?.(this.#view.az);
  }

  #build(): void {
    const t = this.#o.tower;
    const recon = reconstructionNote(t.status, this.#eye.source);
    this.el.innerHTML = html`
      ${this.#o.eyeControl !== false
        ? html`<div class="pv-eye">
            <p class="pv-eye-line"><span data-pv-eye-text>${this.#eye.sentence}</span> <button type="button" class="linklike" data-pv-eye-open aria-expanded="false" aria-controls="${this.#id}-eye">Change</button></p>
            <form class="pv-eye-form" id="${this.#id}-eye" hidden>
              <label for="${this.#id}-eye-ft">Eye height above the ground</label>
              <span class="pv-eye-input"><input id="${this.#id}-eye-ft" type="number" inputmode="decimal" min="3" max="1000" step="1" required> <span>ft</span></span>
              <span class="pv-eye-presets" role="group" aria-label="Typical heights">
                <button type="button" class="chip-btn" data-eye-ft="8">Ground cab</button>
                <button type="button" class="chip-btn" data-eye-ft="35">30-ft tower</button>
                <button type="button" class="chip-btn" data-eye-ft="71">66-ft steel tower</button>
                <button type="button" class="chip-btn" data-eye-ft="105">100-ft tower</button>
              </span>
              <span class="pv-eye-actions"><button type="submit" class="btn">Update the view</button>
              <button type="button" class="linklike" data-pv-eye-reset>Use the ${this.#eye.source === 'recorded' ? 'recorded' : 'typical'} height</button></span>
            </form>
            ${recon && this.#o.recon !== false ? html`<p class="pv-recon">${recon}</p>` : ''}
          </div>`
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
    this.#bind();
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
      if (b.dataset.turn) this.turnTo(this.#view.az + Number(b.dataset.turn), true);
      else if (b.dataset.zoom) this.#zoom(Number(b.dataset.zoom));
      else if (b.hasAttribute('data-stretch')) {
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
        this.turnTo(Number(b.dataset.face), true);
        vp.focus({ preventScroll: true });
        vp.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      } else if (b.hasAttribute('data-pv-retry')) void this.start();
      else if (b.hasAttribute('data-pv-more')) {
        b.closest('section')?.querySelectorAll<HTMLElement>('[data-extra]').forEach((li) => (li.hidden = false));
        b.remove();
      }
    });
    this.#q<HTMLFormElement>('.pv-eye-form')?.addEventListener('submit', (e) => {
      e.preventDefault();
      const ft = Number(this.#q<HTMLInputElement>('.pv-eye-form input')?.value);
      if (!Number.isFinite(ft) || ft <= 0) return;
      this.#customEye = ft * 0.3048;
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
      input.value = String(Math.round(this.#eye.eyeM / 0.3048));
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
    return this.#viewport.clientWidth || 600;
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
      this.#relayout();
      this.#updateHeading(false);
      this.#renderLists(data);
      this.#renderNotes(data);
      this.#o.onReady?.(data);
    } catch (err) {
      if (run !== this.#run) return;
      console.error(err);
      this.el.dataset.state = 'error';
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
        sub: milesShort(p.distM),
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
        sub: `${gone ? 'site, gone' : 'lookout'} · ${milesShort(l.distM)}`,
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
    cancelAnimationFrame(this.#frame);
    this.#frame = requestAnimationFrame(() => {
      const d = this.#data!;
      const L = this.#layout!;
      const P = PALETTES[this.#theme];
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
      const ov = this.#overview;
      const octx = ov.getContext('2d')!;
      const odpr = ov.width / (ov.clientWidth || L.width);
      octx.setTransform(odpr, 0, 0, odpr, 0, 0);
      drawOverview(octx, d, this.#view, ov.clientWidth || L.width, 46, P, L.width / this.#view.pxPerDeg);
    });
  }

  #updateHeading(announce: boolean): void {
    const az = this.#view.az;
    const bearing = quadrantBearing(az);
    const azText = azimuthText(az);
    const b = this.#q('[data-pv-bearing]');
    if (b) b.textContent = bearing;
    const a = this.#q('[data-pv-az]');
    if (a) a.textContent = azText;
    const ahead = this.#ahead();
    const smoke = this.#smokeWords();
    const azWords = this.#o.stepDeg && this.#o.stepDeg < 1 ? azimuthText(Math.round(az * 2) / 2, 1).replace('°', ' degrees') : `${Math.round(az) % 360} degrees`;
    this.#viewport.setAttribute('aria-valuenow', String(Math.round(az) % 360));
    this.#viewport.setAttribute('aria-valuetext', `Looking ${bearing}, azimuth ${azWords}.${ahead ? ` Ahead: ${ahead}.` : ''}${smoke ? ` ${smoke}` : ''}`);
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
    return `${best.kind === 'lookout' ? (best.gone ? 'the site of ' : '') : ''}${best.name}${best.kind === 'lookout' ? ' lookout' : ''}, ${milesKm(best.sight.distM)}`;
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
    this.#tip(p.distM === null ? `Sky · ${bearing}` : `Ground about ${milesKm(p.distM)} away · ${bearing}`, x, y);
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
    const where = (s: Sighted) => html`<span class="pv-where">${milesKm(s.distM)} · ${azimuthText(s.az)} (${quadrantBearing(s.az)})</span>`;
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
          : html`<p class="fine">No other lookout's cab is in line of sight within ${milesShort(this.#o.maxDistM ?? MAX_DIST_M)}.</p>`}
        <p class="fine">${hiddenLookouts ? `${hiddenLookouts} more lookout ${hiddenLookouts === 1 ? 'site is' : 'sites are'} within range but hidden by terrain. ` : ''}Gone lookouts are shown at their old sites, so you can see which ones once watched each other. Their cabs are taken at typical heights.</p>
      </section>
      <section aria-labelledby="${this.#id}-pk">
        <h3 class="h-small" id="${this.#id}-pk">Named peaks in sight <span class="pv-count">${named.length}</span></h3>
        ${named.length
          ? html`<ul class="pv-list">${byBearing.map(
              (p: PeakSight) => html`<li ${top.has(p.gnisId) ? '' : raw('data-extra hidden')}>${faceBtn(p, `p${p.gnisId}`, p.name)} ${where(p)} <span class="pv-elev">${aboutFeet(p.groundM)}</span></li>`,
            )}</ul>
            ${named.length > top.size ? html`<p><button type="button" class="linklike" data-pv-more>Show all ${named.length}</button></p>` : ''}`
          : html`<p class="fine">No named summits in line of sight${d.peaksChecked ? '' : ' (the list of peak names did not load)'}.</p>`}
        <p class="fine">Names from the USGS Geographic Names Information System. Heights are read from the terrain data and are approximate. Sorted by bearing, clockwise from north.</p>
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
      <li><strong>Geometry:</strong> earth curvature and the slight bending of light in the air (refraction coefficient 0.13) are included. Bearings are true (from true north), like a Firefinder's ring, not magnetic. The view reaches ${milesShort(this.#o.maxDistM ?? MAX_DIST_M)}.</li>
      <li><strong>Names:</strong> a peak is named when its summit is in line of sight, even if it is a speck in the distance. Other lookouts are named when their cabs would be in sight at a typical height.</li>
      <li><strong>Computed</strong> in your browser in ${(d.ms.compute / 1000).toFixed(1)} s from ${d.tiles.needed} terrain tiles${d.tiles.bytes ? ` (${megabytes(d.tiles.bytes)} downloaded)` : ' (already downloaded)'}.
        ${d.tiles.failed ? html` <strong class="warn-text">${d.tiles.failed} tiles did not load, so parts of the view may be missing.</strong>` : ''}</li>
    </ul>`.value;
    box.hidden = false;
  }

  destroy(): void {
    this.#resize?.disconnect();
    cancelAnimationFrame(this.#frame);
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

const ARROW_L = '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M10 3 5 8l5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const ARROW_R = '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="m6 3 5 5-5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const ARROW2_L = '<svg width="18" height="16" viewBox="0 0 18 16" aria-hidden="true" focusable="false"><path d="M9 3 4 8l5 5M15 3l-5 5 5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const ARROW2_R = '<svg width="18" height="16" viewBox="0 0 18 16" aria-hidden="true" focusable="false"><path d="m9 3 5 5-5 5M3 3l5 5-5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
