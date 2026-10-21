/**
 * "Satellite": the view from the cab as photos of today's land draped over the terrain, drawn
 * by MapLibre GL, with the drawn view's peak and lookout names and its ring of bearings. You are
 * locked in the cab: drag turns and tilts, a pinch or Ctrl/⌘ + wheel zooms like binoculars (the field
 * of view narrows), the arrow keys and + and − do the same. "Step outside" circles the lookout
 * from the air, an orbit around the tower rather than free flight (DESIGN.md 4.1), and "Back in
 * the cab" flies back to the eye and the bearing you left at.
 *
 * Mounted by panorama-view.ts, which loads this module (and MapLibre with it) only when the
 * satellite view is shown. Camera recipe, the earth's curve and the frame: earth-geo.ts; tiles:
 * earth-tiles.ts.
 */
import 'maplibre-gl/dist/maplibre-gl.css';
import { LngLat, Map as MlMap, Marker, setWorkerUrl, type CalculateTileZoomFunction, type ErrorEvent, type OverscaledTileID, type StyleSpecification } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import { html } from '../lib/html.ts';
import { zoomKeys } from './cab-prefs.ts';
import { angleDiff, wrap360 } from './describe.ts';
import {
  IMAGERY_CREDITS,
  USGS_MAX_ZOOM,
  cabFrame,
  cameraSpace,
  clipNear,
  demZoomFor,
  discBounds,
  firstImagery,
  focalPx,
  horizontalFov,
  lookTarget,
  mercatorBearing,
  metresPerMercatorUnit,
  orbitEye,
  project,
  safeTilt,
  targetDistanceM,
  tileDistanceM,
  tileZoomFor,
  toScreen,
  unproject,
  type CabCamera,
  type GeoPoint,
  type ImagerySource,
} from './earth-geo.ts';
import { earthSources, type EarthSources, type Tally } from './earth-tiles.ts';
import type { PanoramaData } from './engine.ts';
import { mercY } from './tiles.ts';
import { FONT, PALETTES, drawLabels, drawRingWith, placeLabels, type LabelItem, type Layout, type Palette, type Theme } from './panorama-draw.ts';

/** Field of view, degrees: wide as the eye down to binoculars. */
const FOV_MAX = 60;
const FOV_MIN = 4;
const TILT_MIN = -60;
const TILT_MAX = 20;
/** Outside: pitch from straight down, distance from the cab's foot. */
const ORBIT = { pitchMin: 25, pitchMax: 82, pitch: 64, distMin: 150, distMax: 4_000, dist: 700, fov: 45 };
const RING_H = 40;
const FLIGHT_MS = 1_400;
/** The finest terrain, about 12 m, for the summit under the cab (see demZoomFor). */
const DEM_MAX_ZOOM = 13;
/**
 * The coarsest: the drawn view's far tiles. MapLibre also loads, for every terrain tile, its
 * parent and an ancestor at this zoom or 5; starting at 8 keeps those among the drawn view's.
 */
const DEM_MIN_ZOOM = 8;
/** How far the satellite view draws the land, m: the drawn view's 150 km and a margin. */
const REACH_M = 170_000;
/** Terrain tile skirts, m (see the 'style.load' handler). */
const SKIRT_M = 1_500;
/** Photo detail against screen pixels (tileZoomFor): a little under one to one. */
const PHOTO_LOD_BIAS = -0.25;

/**
 * Daylight sky with haze toward the horizon (the "aerial perspective" of the drawn view). It
 * stays daylight in the dark theme: it is a picture of the outdoors, and only the chrome changes.
 */
const SKY = {
  'sky-color': '#6f9fdc',
  'horizon-color': '#dfe8f0',
  'fog-color': '#c8d4e0',
  'sky-horizon-blend': 0.5,
  'horizon-fog-blend': 0.8,
  'fog-ground-blend': 0.35,
  'atmosphere-blend': 0,
} as const;

export interface SatelliteOptions {
  /** The focusable element the map fills. */
  host: HTMLElement;
  /** Where the photo and terrain credits go. */
  credit: HTMLElement;
  data: PanoramaData;
  /** Eye above the ground, m (sets how near the camera's near plane may be). */
  eyeAboveGroundM: number;
  /** The drawn view's labels: peaks and lookouts in sight. */
  items: LabelItem[];
  bearing: number;
  /** Elevation angle of the view's centre to start with, degrees. */
  tilt: number;
  /** Phones: the drawn view's lighter terrain set (see demZoomFor). */
  light: boolean;
  /** The terrain tiles ("z/x/y") the drawn view fetched. */
  sharedTiles: Iterable<string>;
  theme: Theme;
  frame: boolean;
  highlight: string | null;
  /** The lookout's short name, for its marker outside. */
  name: string;
  /** A distance in the lookout's units ("0.4 mi (700 m)"). */
  distance: (m: number) => string;
  /** The visitor turned the view: the new bearing, and whether to say it (keys, end of a drag). */
  onTurn: (az: number, announce: boolean) => void;
  /** Tilt, zoom or inside/outside changed. */
  onChange: () => void;
  /** The first full set of tiles is in. */
  onReady: () => void;
  /** The view could not start (no WebGL, …). */
  onFail: (err: unknown) => void;
  /** A photo source was used for the first time. */
  onSources: () => void;
  /** Everything in view has loaded (after a turn, a zoom…): the notes' download count. */
  onIdle: () => void;
}

interface Pose {
  eye: GeoPoint;
  bearing: number;
  tilt: number;
  fov: number;
  /** How far along the line of sight MapLibre's centre goes, m. */
  dist: number;
}

const smooth = (t: number) => t * t * (3 - 2 * t);

export class SatelliteView {
  #o: SatelliteOptions;
  #map: MlMap;
  #sources: EarthSources;
  #mapEl: HTMLElement;
  #overlay: HTMLCanvasElement;
  #note: HTMLElement;
  #wheelHint: HTMLElement;
  #wheelHintTimer = 0;
  #loading: HTMLElement;
  #bearing: number;
  #tilt: number;
  #fov: number;
  #orbit: { bearing: number; pitch: number; dist: number } | null = null;
  #flight = 0;
  #marker: Marker | null = null;
  #anchors = new Map<string, number>();
  #widths = new Map<string, number>();
  #frameQuads = cabFrame();
  #resize: ResizeObserver;
  #ready = false;
  #destroyed = false;
  #unbind: (() => void)[] = [];

  constructor(o: SatelliteOptions) {
    this.#o = o;
    this.#bearing = wrap360(o.bearing);
    this.#tilt = o.tilt;
    this.#fov = o.host.clientWidth < 560 ? 50 : 40;
    setWorkerUrl(workerUrl);
    o.host.innerHTML = html`<div class="pv-sat-map"></div>
      <canvas class="pv-sat-overlay" aria-hidden="true"></canvas>
      <p class="pv-sat-outside" data-sat-outside-note hidden></p>
      <p class="pv-sat-hint" data-sat-wheel-hint aria-hidden="true">${zoomKeys()} + scroll to zoom</p>
      <div class="pv-loading pv-sat-loading" data-sat-loading>
        <p class="pv-loading-text" role="status" aria-live="polite">Loading the photos and terrain…</p>
        <div class="pv-meter is-busy" aria-hidden="true"><span></span></div>
      </div>`.value;
    this.#mapEl = o.host.querySelector('.pv-sat-map')!;
    this.#overlay = o.host.querySelector('.pv-sat-overlay')!;
    this.#note = o.host.querySelector('[data-sat-outside-note]')!;
    this.#wheelHint = o.host.querySelector('[data-sat-wheel-hint]')!;
    this.#loading = o.host.querySelector('[data-sat-loading]')!;
    this.#setAnchors(o.items);

    const ob = o.data.observer;
    this.#sources = earthSources(
      ob.lat,
      ob.lon,
      () => {
        this.#renderCredits();
        o.onSources();
      },
      o.sharedTiles,
    );
    this.#renderCredits();
    // Land beyond the drawn view's reach is neither loaded nor drawn.
    const reach = discBounds(ob.lat, ob.lon, REACH_M);
    const style: StyleSpecification = {
      version: 8,
      sources: {
        dem: { type: 'raster-dem', tiles: [this.#sources.dem], encoding: 'terrarium', tileSize: 256, minzoom: DEM_MIN_ZOOM, maxzoom: DEM_MAX_ZOOM, bounds: reach },
        photo: { type: 'raster', tiles: [this.#sources.sat], tileSize: 256, maxzoom: USGS_MAX_ZOOM, bounds: reach },
      },
      layers: [
        // Under the photos while they load: a neutral land colour, not black.
        { id: 'ground', type: 'background', paint: { 'background-color': '#8f9886' } },
        { id: 'photo', type: 'raster', source: 'photo', paint: { 'raster-fade-duration': 120 } },
      ],
      terrain: { source: 'dem', exaggeration: 1 },
      sky: SKY,
    };
    try {
      this.#map = new MlMap({
        container: this.#mapEl,
        style,
        interactive: false,
        attributionControl: false,
        trackResize: false,
        renderWorldCopies: false,
        // The camera hangs in the air at the eye; MapLibre must not pull the centre down to the ground.
        centerClampedToGround: false,
        maxPitch: 90 + TILT_MAX + 5,
        maxZoom: 24,
        pixelRatio: Math.min(window.devicePixelRatio || 1, 2),
        center: [ob.lon, ob.lat],
        zoom: 15,
      });
    } catch (err) {
      this.#sources.release();
      throw err;
    }
    const map = this.#map;
    map.on('error', (e: ErrorEvent) => {
      // Single tiles that fail are counted in the tally and said in the notes.
      const msg = String(e.error?.message ?? e.error ?? '');
      if (/abort/i.test(msg)) return;
      console.warn('Satellite view:', msg);
    });
    map.on('render', () => this.#drawOverlay());
    map.once('style.load', () => {
      const perUnit = metresPerMercatorUnit(ob.lat);
      const photos: CalculateTileZoomFunction = (zc, d2, dz, dc) => tileZoomFor(zc, d2, dz, dc, perUnit, PHOTO_LOD_BIAS);
      const photo = map.getSource('photo');
      if (photo) photo.calculateTileZoom = photos;
      const dem = map.getSource('dem');
      if (dem) dem.calculateTileZoom = (_zc, d2, dz) => demZoomFor(Math.hypot(d2, dz) * perUnit, o.light);
      // A terrain tile takes its heights from the terrain tile a zoom coarser: no coarser than the
      // drawn view's farthest (zoom 8), or far ridges would come from much blurrier tiles.
      const terrainTiles: CalculateTileZoomFunction = (zc, d2, dz, dc, fov) => Math.max(photos(zc, d2, dz, dc, fov), DEM_MIN_ZOOM + 1);
      useTerrainLod(map, terrainTiles, (z, x, y) => tileDistanceM(z, x, y, ob.lat, ob.lon) <= REACH_M);
      // MapLibre hangs "skirts" below each terrain tile's edges to hide the cracks between tiles of
      // different detail, sized from the map's zoom; with the map's centre a few hundred metres
      // ahead that zoom is 18 or more and the skirts come out 15 m long, so far ridges show
      // hairline gaps of sky. Size them as for an ordinary view of the same country.
      const terrain = (map as unknown as { terrain?: { getSkirtLength?: (z: number) => number } }).terrain;
      if (terrain && typeof terrain.getSkirtLength === 'function') terrain.getSkirtLength = () => SKIRT_M;
      map.triggerRepaint();
    });
    map.once('load', () => this.#applyCamera());
    map.once('idle', () => this.#readyNow());
    map.on('idle', () => this.#ready && o.onIdle());
    // Lots of tiles on a slow line: show what has come so far after a while.
    window.setTimeout(() => this.#readyNow(), 15_000);
    map.getCanvas().addEventListener('webglcontextlost', () => this.#o.onFail(new Error('The WebGL context was lost.')), { once: true });
    this.#applyCamera();
    this.#bind();
    this.#resize = new ResizeObserver(() => {
      // Hidden (the drawn view showing): nothing to fit.
      if (this.#destroyed || !this.#mapEl.clientWidth) return;
      map.resize();
      this.#applyCamera();
    });
    this.#resize.observe(o.host);
  }

  /* ---------- State the panorama view reads ---------- */

  get bearing(): number {
    return this.#bearing;
  }

  get outside(): boolean {
    return this.#orbit !== null;
  }

  /** The bearing the camera faces: in the cab, or circling outside. */
  get viewBearing(): number {
    return this.#orbit?.bearing ?? this.#bearing;
  }

  get tally(): Tally {
    return this.#sources.tally;
  }

  /** Degrees of the circle in view across the screen. */
  get spanDeg(): number {
    return horizontalFov(this.#cam());
  }

  /** In words, for screen readers: tilt and zoom, or where you are outside. */
  describe(): string {
    if (this.#orbit) {
      return `Outside, about ${this.#o.distance(this.#orbit.dist)} from the cab, looking at it from the ${compassWord(this.#orbit.bearing + 180)}.`;
    }
    const t = Math.round(this.#tilt);
    const tilt = t === 0 ? 'level' : `${Math.abs(t)} degree${Math.abs(t) === 1 ? '' : 's'} ${t > 0 ? 'up' : 'down'}`;
    return `Looking ${tilt}, ${Math.round(this.spanDeg)} degrees of the circle in view.`;
  }

  /* ---------- Commands ---------- */

  setBearing(az: number): void {
    const a = wrap360(az);
    if (Math.abs(angleDiff(a, this.#bearing)) < 1e-9) return;
    this.#bearing = a;
    if (!this.#orbit && !this.#flight) this.#applyCamera();
  }

  /** Turn by some degrees: the view in the cab (through the panorama view), or the orbit outside. */
  turnBy(deg: number): void {
    if (this.#orbit) {
      this.#orbit.bearing = wrap360(this.#orbit.bearing + deg);
      this.#applyCamera();
      this.#o.onChange();
    } else this.#o.onTurn(this.#bearing + deg, true);
  }

  tiltBy(deg: number): void {
    if (this.#orbit) {
      this.#orbit.pitch = clamp(this.#orbit.pitch - deg, ORBIT.pitchMin, ORBIT.pitchMax);
    } else this.#tilt = clamp(this.#tilt + deg, TILT_MIN, TILT_MAX);
    this.#applyCamera();
    this.#o.onChange();
  }

  /** Zoom in (1) or out (−1) a step. */
  zoom(dir: number): void {
    if (this.#orbit) this.#orbit.dist = clamp(this.#orbit.dist / 1.5 ** dir, ORBIT.distMin, ORBIT.distMax);
    else this.#fov = clamp(this.#fov / 1.45 ** dir, FOV_MIN, FOV_MAX);
    this.#applyCamera();
    this.#o.onChange();
  }

  setOptions(o: Partial<Pick<SatelliteOptions, 'theme' | 'frame' | 'highlight'>>): void {
    Object.assign(this.#o, o);
    this.#drawOverlay();
  }

  /** New terrain result (the eye height changed). */
  update(data: PanoramaData, eyeAboveGroundM: number, items: LabelItem[]): void {
    this.#o.data = data;
    this.#o.eyeAboveGroundM = eyeAboveGroundM;
    this.#setAnchors(items);
    if (this.#marker) this.#marker.setLngLat([data.observer.lon, data.observer.lat]);
    this.#applyCamera();
  }

  stepOutside(): void {
    if (this.#orbit || this.#flight) return;
    const orbit = { bearing: this.#bearing, pitch: ORBIT.pitch, dist: ORBIT.dist };
    this.#addMarker();
    this.#fly(this.#cabPose(), this.#orbitPose(orbit), () => {
      this.#orbit = orbit;
      this.#showOutsideNote();
    });
    this.#o.onChange();
  }

  /** Fly back to the eye, facing the bearing you left at (`instant`: no flight, e.g. when hidden). */
  backInCab(instant = false): void {
    if (!this.#orbit) return;
    if (this.#flight && !instant) return;
    const from = this.#orbitPose(this.#orbit);
    this.#orbit = null;
    this.#note.hidden = true;
    const done = () => {
      this.#marker?.remove();
      this.#marker = null;
    };
    if (instant) {
      cancelAnimationFrame(this.#flight);
      this.#flight = 0;
      done();
      this.#applyCamera();
    } else this.#fly(from, this.#cabPose(), done);
    this.#o.onChange();
  }

  focus(): void {
    this.#o.host.focus({ preventScroll: true });
  }

  destroy(): void {
    this.#destroyed = true;
    cancelAnimationFrame(this.#flight);
    window.clearTimeout(this.#wheelHintTimer);
    this.#resize.disconnect();
    for (const off of this.#unbind) off();
    this.#marker?.remove();
    this.#map.remove();
    this.#sources.release();
  }

  /* ---------- Camera ---------- */

  #cam(): CabCamera {
    return { bearing: this.#bearing, tilt: safeTilt(this.#tilt), fov: this.#fov, width: this.#mapEl.clientWidth || 600, height: this.#mapEl.clientHeight || 400 };
  }

  #eye(): GeoPoint {
    const o = this.#o.data.observer;
    return { lat: o.lat, lon: o.lon, altM: o.eyeM };
  }

  #cabPose(): Pose {
    return { eye: this.#eye(), bearing: this.#bearing, tilt: this.#tilt, fov: this.#fov, dist: targetDistanceM(this.#o.eyeAboveGroundM, this.#fov) };
  }

  /** Outside: the camera `dist` from the cab's foot, looking at it. */
  #orbitPose(orbit: { bearing: number; pitch: number; dist: number }): Pose {
    const o = this.#o.data.observer;
    const foot = { lat: o.lat, lon: o.lon, altM: o.groundM };
    return { eye: orbitEye(foot, orbit.bearing, orbit.pitch, orbit.dist), bearing: orbit.bearing, tilt: orbit.pitch - 90, fov: ORBIT.fov, dist: orbit.dist };
  }

  #applyPose(p: Pose): void {
    const map = this.#map;
    if (Math.abs(map.getVerticalFieldOfView() - p.fov) > 1e-6) map.setVerticalFieldOfView(p.fov);
    const to = lookTarget(p.eye, p.bearing, safeTilt(p.tilt), p.dist);
    map.jumpTo(map.calculateCameraOptionsFromTo(new LngLat(p.eye.lon, p.eye.lat), p.eye.altM, new LngLat(to.lon, to.lat), to.altM));
  }

  #applyCamera(): void {
    if (this.#destroyed || this.#flight) return;
    this.#applyPose(this.#orbit ? this.#orbitPose(this.#orbit) : this.#cabPose());
  }

  /** Fly between two poses (instantly for visitors who ask for less motion). */
  #fly(from: Pose, to: Pose, done: () => void): void {
    cancelAnimationFrame(this.#flight);
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const start = performance.now();
    const turn = angleDiff(from.bearing, to.bearing);
    const step = () => {
      const k = reduce ? 1 : Math.min((performance.now() - start) / FLIGHT_MS, 1);
      const t = smooth(k);
      const lerp = (a: number, b: number) => a + (b - a) * t;
      this.#flight = k < 1 ? requestAnimationFrame(step) : 0;
      this.#applyPose({
        eye: { lat: lerp(from.eye.lat, to.eye.lat), lon: lerp(from.eye.lon, to.eye.lon), altM: lerp(from.eye.altM, to.eye.altM) },
        bearing: from.bearing + turn * t,
        tilt: lerp(from.tilt, to.tilt),
        fov: lerp(from.fov, to.fov),
        dist: Math.exp(lerp(Math.log(from.dist), Math.log(to.dist))),
      });
      if (k >= 1) {
        done();
        this.#applyCamera();
        this.#o.onChange();
      }
    };
    this.#flight = requestAnimationFrame(step);
  }

  #readyNow(): void {
    if (this.#ready || this.#destroyed) return;
    this.#ready = true;
    this.#loading.hidden = true;
    this.#o.onReady();
  }

  /* ---------- Input ---------- */

  #bind(): void {
    const el = this.#o.host;
    const on = <K extends keyof HTMLElementEventMap>(type: K, fn: (e: HTMLElementEventMap[K]) => void, opts?: AddEventListenerOptions) => {
      el.addEventListener(type, fn as EventListener, opts);
      this.#unbind.push(() => el.removeEventListener(type, fn as EventListener, opts));
    };

    // Drag to turn and tilt (grab the scene), two fingers to zoom.
    const pointers = new Map<number, { x: number; y: number }>();
    let drag: { x: number; y: number; bearing: number; tilt: number; orbitBearing: number; pitch: number } | null = null;
    let pinch: { d: number; fov: number; dist: number } | null = null;
    const spread = () => {
      const [a, b] = [...pointers.values()];
      return a && b ? Math.hypot(a.x - b.x, a.y - b.y) : 0;
    };
    on('pointerdown', (e) => {
      if (this.#flight || (e.pointerType === 'mouse' && e.button !== 0)) return;
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      try {
        el.setPointerCapture(e.pointerId);
      } catch {
        /* the pointer is already gone */
      }
      el.classList.add('is-dragging');
      if (pointers.size === 2) {
        drag = null;
        pinch = { d: spread() || 1, fov: this.#fov, dist: this.#orbit?.dist ?? ORBIT.dist };
      } else if (pointers.size === 1) {
        drag = { x: e.clientX, y: e.clientY, bearing: this.#bearing, tilt: this.#tilt, orbitBearing: this.#orbit?.bearing ?? 0, pitch: this.#orbit?.pitch ?? 0 };
      }
    });
    on('pointermove', (e) => {
      if (!pointers.has(e.pointerId) || this.#flight) return;
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (pinch && pointers.size >= 2) {
        const f = (spread() || 1) / pinch.d;
        if (this.#orbit) this.#orbit.dist = clamp(pinch.dist / f, ORBIT.distMin, ORBIT.distMax);
        else this.#fov = clamp(pinch.fov / f, FOV_MIN, FOV_MAX);
        this.#applyCamera();
        this.#o.onChange();
      } else if (drag) {
        const dx = e.clientX - drag.x;
        const dy = e.clientY - drag.y;
        if (this.#orbit) {
          this.#orbit.bearing = wrap360(drag.orbitBearing - dx * 0.3);
          this.#orbit.pitch = clamp(drag.pitch - dy * 0.25, ORBIT.pitchMin, ORBIT.pitchMax);
          this.#applyCamera();
          this.#o.onChange();
        } else {
          const k = this.#fov / (this.#mapEl.clientHeight || 400);
          const tilt = clamp(drag.tilt + dy * k, TILT_MIN, TILT_MAX);
          if (tilt !== this.#tilt) {
            this.#tilt = tilt;
            this.#applyCamera();
            this.#o.onChange();
          }
          this.#o.onTurn(drag.bearing - dx * k, false);
        }
      }
    });
    const end = (e: PointerEvent) => {
      if (!pointers.delete(e.pointerId)) return;
      if (pointers.size < 2) pinch = null;
      if (pointers.size === 1) {
        const [p] = [...pointers.values()];
        drag = { x: p!.x, y: p!.y, bearing: this.#bearing, tilt: this.#tilt, orbitBearing: this.#orbit?.bearing ?? 0, pitch: this.#orbit?.pitch ?? 0 };
      }
      if (pointers.size === 0) {
        if (drag && !this.#orbit) this.#o.onTurn(this.#bearing, true);
        drag = null;
        el.classList.remove('is-dragging');
      }
    };
    on('pointerup', end);
    on('pointercancel', end);

    // A plain wheel scrolls the page, as over the drawn view, so the view never traps a visitor
    // scrolling down the tower page; a sideways swipe turns. Ctrl or ⌘ with the wheel (and a
    // trackpad pinch, which browsers send as Ctrl + wheel) zooms toward the pointer, like
    // binoculars aimed there.
    on(
      'wheel',
      (e) => {
        if (this.#flight) return;
        if (!e.ctrlKey && !e.metaKey) {
          if (!this.#orbit && Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
            e.preventDefault();
            const k = this.#fov / (this.#mapEl.clientHeight || 400);
            this.#o.onTurn(this.#bearing + e.deltaX * k, false);
          } else if (e.deltaY) this.#showWheelHint();
          return;
        }
        const dy = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaMode === 2 ? e.deltaY * 400 : e.deltaY;
        if (!dy) return;
        const f = Math.exp(Math.max(-1, Math.min(1, dy * 0.0015)));
        if (this.#orbit) {
          const dist = clamp(this.#orbit.dist * f, ORBIT.distMin, ORBIT.distMax);
          if (dist === this.#orbit.dist) return;
          this.#orbit.dist = dist;
        } else {
          const fov = clamp(this.#fov * f, FOV_MIN, FOV_MAX);
          if (fov === this.#fov) return;
          const r = this.#mapEl.getBoundingClientRect();
          const x = e.clientX - r.left;
          const y = e.clientY - r.top;
          const aim = unproject(x, y, this.#cam());
          this.#fov = fov;
          // Turn and tilt so the same direction stays under the pointer.
          const now = unproject(x, y, this.#cam());
          this.#tilt = clamp(this.#tilt + (aim.elev - now.elev), TILT_MIN, TILT_MAX);
          this.#o.onTurn(this.#bearing + angleDiff(now.az, aim.az), false);
        }
        e.preventDefault();
        this.#applyCamera();
        this.#o.onChange();
      },
      { passive: false },
    );

    on('keydown', (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const big = e.shiftKey;
      const keys: Record<string, () => void> = {
        ArrowLeft: () => this.turnBy(this.#orbit ? -5 : big ? -10 : -1),
        ArrowRight: () => this.turnBy(this.#orbit ? 5 : big ? 10 : 1),
        ArrowUp: () => this.tiltBy(big ? 5 : 1),
        ArrowDown: () => this.tiltBy(big ? -5 : -1),
        PageUp: () => this.turnBy(10),
        PageDown: () => this.turnBy(-10),
        Home: () => this.#face(0),
        End: () => this.#face(180),
        '+': () => this.zoom(1),
        '=': () => this.zoom(1),
        '-': () => this.zoom(-1),
        n: () => this.#face(0),
        e: () => this.#face(90),
        s: () => this.#face(180),
        w: () => this.#face(270),
      };
      const fn = keys[e.key] ?? keys[e.key.toLowerCase()];
      if (!fn) return;
      e.preventDefault();
      fn();
    });
  }

  #face(az: number): void {
    if (this.#orbit) {
      // Outside, "north" means looking north at the lookout.
      this.#orbit.bearing = az;
      this.#applyCamera();
      this.#o.onChange();
    } else this.#o.onTurn(az, true);
  }

  /* ---------- Overlay: frame, names, ring ---------- */

  #setAnchors(items: LabelItem[]): void {
    this.#o.items = items;
    const o = this.#o.data.observer;
    this.#anchors.clear();
    // Where the satellite view draws each one: straight across the flat map (earth-geo.ts).
    for (const it of items) this.#anchors.set(it.key, mercatorBearing(o.lat, o.lon, it.sight.lat, it.sight.lon));
  }

  #drawOverlay(): void {
    const c = this.#overlay;
    const W = this.#mapEl.clientWidth;
    const H = this.#mapEl.clientHeight;
    if (!W || !H) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    if (c.width !== Math.round(W * dpr) || c.height !== Math.round(H * dpr)) {
      c.width = Math.round(W * dpr);
      c.height = Math.round(H * dpr);
    }
    const ctx = c.getContext('2d')!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    // Outside, and on the way out or back, the photos speak for themselves.
    if (this.#orbit || this.#flight) return;
    const cam = this.#cam();
    const P: Palette = { ...PALETTES[this.#o.theme], leader: 'rgba(255,253,247,0.9)' };
    const ringTop = H - RING_H;

    if (this.#o.frame) this.#drawFrame(ctx, cam);

    // Names, in the drawn view's rows and style; only where the anchor shows below the rows.
    const rows = W < 560 ? 2 : 3;
    const L: Layout = { width: W, height: H, labelRows: rows, rowHeight: 30, labelTop: 6, terrainTop: 6 + rows * 30, ringTop, horizonY: 0, vScale: 1 };
    const at = (it: LabelItem) => {
      const p = project(this.#anchors.get(it.key) ?? it.sight.az, it.sight.angle, cam);
      return p && p.y > L.terrainTop + 4 && p.y < ringTop - 2 ? p : null;
    };
    // Text widths are kept: the overlay is redrawn on every frame MapLibre draws.
    const measure = (s: string, bold: boolean) => {
      const key = `${bold ? 'b' : 'n'}${s}`;
      let w = this.#widths.get(key);
      if (w === undefined) {
        ctx.font = `${bold ? 700 : 600} 12px ${FONT}`;
        w = ctx.measureText(s).width;
        this.#widths.set(key, w);
      }
      return w;
    };
    const placed = placeLabels(this.#o.items, { az: cam.bearing, pxPerDeg: 1, exaggeration: 1 }, L, measure, at);
    ctx.save();
    ctx.shadowColor = 'rgba(0,0,0,0.45)';
    ctx.shadowBlur = 3;
    drawLabels(ctx, placed, L, P, this.#o.highlight);
    ctx.restore();

    // The ring: true bearings where they cross the eye's level.
    const f = focalPx(cam);
    const ct = Math.cos((cam.tilt * Math.PI) / 180);
    const half = Math.min(horizontalFov(cam) / 2 + 3, 85);
    drawRingWith(ctx, W, ringTop, H, P, cam.bearing, (f * Math.PI) / 180 / ct, half, (a) => W / 2 + (f * Math.tan(((a - cam.bearing) * Math.PI) / 180)) / ct);
    // The sight: where the bearing in the bar is read.
    ctx.fillStyle = P.accent;
    ctx.beginPath();
    ctx.moveTo(W / 2 - 6, ringTop);
    ctx.lineTo(W / 2 + 6, ringTop);
    ctx.lineTo(W / 2, ringTop + 8);
    ctx.closePath();
    ctx.fill();
    ctx.fillRect(Math.round(W / 2) - 0.75, ringTop - 12, 1.5, 12);
  }

  /** The cab's posts and sill, fading out as you zoom in (binoculars look past the frame). */
  #drawFrame(ctx: CanvasRenderingContext2D, cam: CabCamera): void {
    const alpha = clamp((cam.fov - 12) / 10, 0, 1);
    if (alpha <= 0) return;
    const color = { post: '#3d3128', sill: '#6b5440', wall: '#54443a' } as const;
    ctx.save();
    ctx.globalAlpha = alpha;
    for (const q of this.#frameQuads) {
      const poly = clipNear(q.pts.map(([e, n, u]) => cameraSpace(e, n, u, cam)));
      if (poly.length < 3) continue;
      ctx.beginPath();
      poly.forEach((p, i) => {
        const s = toScreen(p, cam);
        if (i === 0) ctx.moveTo(s.x, s.y);
        else ctx.lineTo(s.x, s.y);
      });
      ctx.closePath();
      ctx.fillStyle = color[q.part];
      ctx.fill();
      ctx.strokeStyle = 'rgba(20,14,10,0.6)';
      ctx.lineWidth = 1;
      ctx.stroke();
    }
    ctx.restore();
  }

  /* ---------- Outside ---------- */

  #addMarker(): void {
    if (this.#marker) return;
    const el = document.createElement('div');
    el.className = 'pv-sat-marker';
    el.innerHTML = html`<span class="pv-sat-marker-label">${this.#o.name}</span><svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true" focusable="false"><path d="M11 2 20 19H2Z" fill="#a9441b" stroke="#fffdf7" stroke-width="2" stroke-linejoin="round"/></svg>`.value;
    const o = this.#o.data.observer;
    this.#marker = new Marker({ element: el, anchor: 'bottom' }).setLngLat([o.lon, o.lat]).addTo(this.#map);
  }

  #showOutsideNote(): void {
    this.#note.textContent = `Outside the cab: drag to circle the lookout; pinch or ${zoomKeys()} + scroll to come closer or go farther.`;
    this.#note.hidden = false;
  }

  /** Says how to zoom when a plain wheel over the view scrolled the page instead. */
  #showWheelHint(): void {
    this.#wheelHint.classList.add('is-on');
    window.clearTimeout(this.#wheelHintTimer);
    this.#wheelHintTimer = window.setTimeout(() => this.#wheelHint.classList.remove('is-on'), 1400);
  }

  /* ---------- Credits ---------- */

  #renderCredits(): void {
    const used = new Set<ImagerySource>(this.#sources.tally.sources);
    if (!used.size) {
      // Before the first tile: the source the lookout's own spot will use.
      const o = this.#o.data.observer;
      const n = 2 ** 12;
      used.add(firstImagery(12, Math.floor(((o.lon + 180) / 360) * n), Math.floor(mercY(o.lat) * n)));
    }
    const credit = (s: ImagerySource) => html`<a href="${IMAGERY_CREDITS[s].href}" rel="noopener">${IMAGERY_CREDITS[s].text}</a>`;
    this.#o.credit.innerHTML = html`${used.has('usgs') ? html`<span>${credit('usgs')}</span>` : ''}
      ${used.has('eox') ? html`<span>${credit('eox')}</span>` : ''}
      <span>Terrain: <a href="https://registry.opendata.aws/terrain-tiles/" rel="noopener">AWS Terrain Tiles</a></span>`.value;
  }
}

/** MapLibre 6.12's terrain tile manager, as far as `useTerrainLod` touches it. */
interface TerrainTiles {
  tileManager: { update(transform: unknown, terrain: unknown): void; map: { painter: unknown } };
  _tiles: Record<string, { tileID: OverscaledTileID & { key: string; terrainRttPosMatrix32f?: Float32Array }; releaseRTT(painter: unknown): void }>;
  _renderableTilesKeys: string[];
  _lastTilesetChange: number;
  tileSize: number;
  minzoom: number;
  maxzoom: number;
  update(transform: unknown, terrain: unknown): boolean;
}

/** Terrain tiles finer than this hold no more photo detail (512 px tiles, photos to zoom 16). */
const RTT_MAX_ZOOM = 16;

/** `mat4.ortho(0, EXTENT, EXTENT, 0, 0, 1)` with MapLibre's tile extent of 8192. */
const RTT_ORTHO = new Float32Array([2 / 8192, 0, 0, 0, 0, -2 / 8192, 0, 0, 0, 0, -2, 0, -1, 1, -1, 1]);

/**
 * MapLibre drapes the photos over the terrain by drawing them into the terrain's own tiles, and
 * picks those with its built-in level-of-detail rule, which at eye level drops to zoom 7 a
 * kilometre out (see `tileZoomFor`) whatever the photo source asks for. MapLibre 6.12 has no
 * setting for those tiles (`setSourceTileLodParams` reaches sources only), so on this one map
 * the terrain tile manager's `update` is replaced by the same steps with our rule (and only the
 * tiles `wanted`: within the view's reach). Where MapLibre's internals are not what this expects,
 * it leaves the built-in rule alone: the view still works, only blurrier.
 */
function useTerrainLod(map: MlMap, calc: CalculateTileZoomFunction, wanted: (z: number, x: number, y: number) => boolean): void {
  const ttm = (map as unknown as { terrain?: { tileManager?: TerrainTiles } }).terrain?.tileManager;
  if (!ttm || typeof ttm.update !== 'function' || typeof ttm._tiles !== 'object' || !Array.isArray(ttm._renderableTilesKeys) || !ttm.tileManager) return;
  const builtIn = ttm.update;
  ttm.update = function (this: TerrainTiles, transform: unknown, terrain: unknown): boolean {
    // The terrain tiles are made by MapLibre's own class; borrow it from one it made.
    const TileClass = Object.values(this._tiles)[0]?.constructor as (new (id: OverscaledTileID, size: number) => TerrainTiles['_tiles'][string]) | undefined;
    if (!TileClass) return builtIn.call(this, transform, terrain);
    try {
      this.tileManager.update(transform, terrain);
      this._renderableTilesKeys = [];
      const keep = new Set<string>();
      let changed = false;
      const ids = map.coveringTiles({ tileSize: this.tileSize, minzoom: this.minzoom, maxzoom: Math.min(this.maxzoom, RTT_MAX_ZOOM), reparseOverscaled: false, terrain, calculateTileZoom: calc } as Parameters<MlMap['coveringTiles']>[0]);
      for (const tileID of ids as (OverscaledTileID & { key: string; terrainRttPosMatrix32f?: Float32Array })[]) {
        const c = tileID.canonical;
        if (!wanted(c.z, c.x, c.y)) continue;
        keep.add(tileID.key);
        this._renderableTilesKeys.push(tileID.key);
        if (!this._tiles[tileID.key]) {
          tileID.terrainRttPosMatrix32f = new Float32Array(RTT_ORTHO);
          this._tiles[tileID.key] = new TileClass(tileID, this.tileSize);
          this._lastTilesetChange = performance.now();
          changed = true;
        }
      }
      for (const key in this._tiles) {
        if (!keep.has(key)) {
          this._tiles[key]!.releaseRTT(this.tileManager.map.painter);
          delete this._tiles[key];
          changed = true;
        }
      }
      return changed;
    } catch (err) {
      console.warn('Satellite view: using MapLibre’s own terrain detail.', err);
      ttm.update = builtIn;
      return builtIn.call(this, transform, terrain);
    }
  };
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.min(Math.max(v, lo), hi);
}

const WORDS = ['north', 'northeast', 'east', 'southeast', 'south', 'southwest', 'west', 'northwest'];
function compassWord(az: number): string {
  return WORDS[Math.round(wrap360(az) / 45) % 8]!;
}
