/**
 * Drawing the view from the cab on a canvas, in the manner of the panorama drawings and
 * photographs the Forest Service made from its lookouts: ridge behind ridge, each farther one
 * paler (atmospheric perspective), with peak names above and a graduated azimuth ring below,
 * like the Osborne Firefinder's.
 *
 * Pure drawing and geometry; the interactive component is panorama-view.ts.
 */
import type { PanoramaData, Sighted } from './engine.ts';
import { wrap360 } from './describe.ts';

export type Theme = 'light' | 'dark';

export interface Palette {
  skyTop: string;
  skyHorizon: string;
  near: [number, number, number];
  far: [number, number, number];
  lineNear: [number, number, number];
  lineFar: [number, number, number];
  ink: string;
  muted: string;
  ringBg: string;
  ringLine: string;
  ringInk: string;
  accent: string;
  lookout: string;
  labelHalo: string;
  leader: string;
  level: string;
  smoke: [number, number, number];
}

export const PALETTES: Record<Theme, Palette> = {
  light: {
    skyTop: '#c9d8e2',
    skyHorizon: '#eef0ea',
    near: [74, 92, 76],
    far: [184, 197, 204],
    lineNear: [22, 32, 25],
    lineFar: [120, 137, 150],
    ink: '#1c2620',
    muted: '#56625a',
    ringBg: '#fffdf7',
    ringLine: '#bdb299',
    ringInk: '#1c2620',
    accent: '#a9441b',
    lookout: '#9a3a12',
    labelHalo: 'rgba(244,241,232,0.88)',
    leader: 'rgba(28,38,32,0.45)',
    level: 'rgba(28,38,32,0.35)',
    smoke: [248, 248, 244],
  },
  dark: {
    skyTop: '#0c131c',
    skyHorizon: '#26323b',
    near: [10, 15, 12],
    far: [70, 86, 98],
    lineNear: [96, 116, 104],
    lineFar: [120, 140, 156],
    ink: '#e9e5d9',
    muted: '#a2aca4',
    ringBg: '#19211c',
    ringLine: '#4a5a51',
    ringInk: '#e9e5d9',
    accent: '#ffa577',
    lookout: '#f5a37a',
    labelHalo: 'rgba(17,23,19,0.85)',
    leader: 'rgba(233,229,217,0.45)',
    level: 'rgba(233,229,217,0.3)',
    smoke: [214, 214, 210],
  },
};

export const FONT = "'Public Sans Variable', system-ui, sans-serif";

export interface View {
  /** Azimuth at the centre of the view, degrees. */
  az: number;
  /** Horizontal scale, CSS px per degree. */
  pxPerDeg: number;
  /** Vertical stretch (1 = true proportions). */
  exaggeration: number;
}

export interface Layout {
  width: number;
  height: number;
  labelRows: number;
  rowHeight: number;
  /** Top of the terrain area (below the labels). */
  terrainTop: number;
  /** Top of the azimuth ring. */
  ringTop: number;
  /** y of the eye's level (elevation angle 0). */
  horizonY: number;
  /** Vertical px per degree. */
  vScale: number;
}

const RING_H = 40;

/** Place the scene: the highest skyline anywhere in the circle sits just under the labels. */
export function makeLayout(data: PanoramaData, width: number, height: number, view: View, labelRows: number): Layout {
  const rowHeight = 30;
  const terrainTop = labelRows * rowHeight + 18;
  const ringTop = height - RING_H;
  const vScale = view.pxPerDeg * view.exaggeration;
  const last = data.layersM.length - 1;
  let hi = -90;
  for (let c = 0; c < data.columns; c++) hi = Math.max(hi, data.horizon[last * data.columns + c]!);
  if (hi < -60) hi = 0;
  // Keep the eye level in view even where everything is below it.
  const horizonY = Math.min(terrainTop + 10 + hi * vScale, ringTop - 30);
  return { width, height, labelRows, rowHeight, terrainTop, ringTop, horizonY, vScale };
}

/** Horizon angle of a layer at any azimuth, interpolating between columns. */
export function horizonAt(data: PanoramaData, layer: number, az: number): number {
  const f = wrap360(az) / data.azStep;
  const c0 = Math.floor(f) % data.columns;
  const c1 = (c0 + 1) % data.columns;
  const t = f - Math.floor(f);
  const row = layer * data.columns;
  const a = data.horizon[row + c0]!;
  const b = data.horizon[row + c1]!;
  return a * (1 - t) + b * t;
}

export function xOf(view: View, layout: Layout, az: number): number {
  const d = ((az - view.az + 540) % 360) - 180;
  return layout.width / 2 + d * view.pxPerDeg;
}

export function yOf(layout: Layout, angle: number): number {
  return layout.horizonY - angle * layout.vScale;
}

export function azOf(view: View, layout: Layout, x: number): number {
  return wrap360(view.az + (x - layout.width / 2) / view.pxPerDeg);
}

/** Representative distance of each layer (geometric middle), m. */
export function layerDistances(layersM: Float64Array): number[] {
  return Array.from(layersM, (b, j) => (j === 0 ? b / 2 : Math.sqrt(layersM[j - 1]! * b)));
}

/** Atmospheric perspective: how far toward the haze colour a ridge at this distance goes. */
export function haze(distM: number): number {
  return Math.min(0.9, 1 - Math.exp(-distM / 42_000));
}

function mix(a: [number, number, number], b: [number, number, number], t: number): string {
  const c = (i: number) => Math.round(a[i]! + (b[i]! - a[i]!) * t);
  return `rgb(${c(0)},${c(1)},${c(2)})`;
}

/* ---------- Labels ---------- */

export interface LabelItem {
  key: string;
  kind: 'peak' | 'lookout' | 'smoke';
  name: string;
  sub: string;
  sight: Sighted;
  score: number;
  /** For lookouts: gone (hollow marker) or standing. */
  gone?: boolean;
}

export interface PlacedLabel {
  item: LabelItem;
  ax: number;
  ay: number;
  row: number;
  x: number;
  w: number;
}

/**
 * Greedy placement: best-scoring names first, each in the lowest free row above its anchor,
 * centred on it where possible. Names that do not fit are left for the list below the view.
 */
export function placeLabels(items: LabelItem[], view: View, layout: Layout, measure: (text: string, bold: boolean) => number): PlacedLabel[] {
  const rows: [number, number][][] = Array.from({ length: layout.labelRows }, () => []);
  const placed: PlacedLabel[] = [];
  const sorted = [...items].sort((a, b) => b.score - a.score);
  for (const item of sorted) {
    const ax = xOf(view, layout, item.sight.az);
    if (ax < -40 || ax > layout.width + 40) continue;
    const ay = yOf(layout, item.sight.angle);
    const w = Math.max(measure(item.name, item.kind !== 'peak'), measure(item.sub, false)) + (item.kind === 'lookout' ? 16 : 0) + 8;
    const x = Math.min(Math.max(ax - w / 2, 2), layout.width - w - 2);
    if (ax < x + 3 || ax > x + w - 3) continue; // its leader would miss the label: wait until panned into view
    for (let r = layout.labelRows - 1; r >= 0; r--) {
      const row = rows[r]!;
      if (row.every(([a, b]) => x + w + 6 < a || x > b + 6)) {
        row.push([x, x + w]);
        placed.push({ item, ax, ay, row: r, x, w });
        break;
      }
    }
  }
  return placed;
}

/* ---------- Drawing ---------- */

export interface Smoke {
  az: number;
  baseAngle: number;
  topAngle: number;
  widthDeg: number;
  /** Seed for the plume's shape, so it does not flicker between frames. */
  seed: number;
}

export interface DrawOptions {
  labels: PlacedLabel[];
  palette: Palette;
  smoke?: Smoke | null;
  highlight?: string | null;
  /** Draw the centre sighting hair. */
  reticle?: boolean;
}

export function drawPanorama(ctx: CanvasRenderingContext2D, data: PanoramaData, view: View, L: Layout, o: DrawOptions): void {
  const P = o.palette;
  const { width: W, height: H } = L;
  ctx.clearRect(0, 0, W, H);

  // Sky.
  const sky = ctx.createLinearGradient(0, 0, 0, Math.max(L.horizonY, 1));
  sky.addColorStop(0, P.skyTop);
  sky.addColorStop(1, P.skyHorizon);
  ctx.fillStyle = sky;
  ctx.fillRect(0, 0, W, L.ringTop);

  // Eye level.
  ctx.save();
  ctx.strokeStyle = P.level;
  ctx.setLineDash([3, 5]);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, Math.round(L.horizonY) + 0.5);
  ctx.lineTo(W, Math.round(L.horizonY) + 0.5);
  ctx.stroke();
  ctx.restore();

  // Ridges, farthest first.
  const nl = data.layersM.length;
  const dists = layerDistances(data.layersM);
  const half = W / 2 / view.pxPerDeg + 1;
  const c0 = Math.floor((view.az - half) / data.azStep) - 1;
  const c1 = Math.ceil((view.az + half) / data.azStep) + 1;
  const xs: number[] = [];
  for (let c = c0; c <= c1; c++) xs.push(W / 2 + (c * data.azStep - view.az) * view.pxPerDeg);
  const col = (c: number) => ((c % data.columns) + data.columns) % data.columns;
  const bottom = L.ringTop;
  for (let j = nl - 1; j >= 0; j--) {
    const t = haze(dists[j]!);
    const row = j * data.columns;
    const ys: number[] = [];
    const fill = new Path2D();
    for (let i = 0, c = c0; c <= c1; c++, i++) {
      const a = data.horizon[row + col(c)]!;
      const y = a < -89 ? bottom + 2 : Math.min(L.horizonY - a * L.vScale, bottom + 2);
      ys.push(y);
      if (i === 0) fill.moveTo(xs[i]!, y);
      else fill.lineTo(xs[i]!, y);
    }
    fill.lineTo(xs[xs.length - 1]!, bottom + 2);
    fill.lineTo(xs[0]!, bottom + 2);
    fill.closePath();
    ctx.fillStyle = mix(P.near, P.far, t);
    ctx.fill(fill);
    // Ink only the real ridgelines: where this layer's highest point lies inside it, with lower
    // ground behind. Where the ground keeps rising to the layer's edge, its outline is not an
    // edge you would see, and inking it would draw contour-like streaks down every slope.
    const line = new Path2D();
    let pen = false;
    const outer = data.layersM[j]!;
    for (let i = 0, c = c0; c <= c1; c++, i++) {
      const crest = data.crest[row + col(c)]!;
      const ridge = Number.isFinite(crest) && crest < outer * 0.96;
      if (ridge) {
        if (pen) line.lineTo(xs[i]!, ys[i]!);
        else line.moveTo(xs[i]!, ys[i]!);
      }
      pen = ridge;
    }
    ctx.strokeStyle = mix(P.lineNear, P.lineFar, t);
    ctx.lineWidth = j < nl / 3 ? 1.3 : 1;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.stroke(line);
  }

  if (o.smoke) drawSmoke(ctx, view, L, o.smoke, P);

  // Labels.
  ctx.textBaseline = 'alphabetic';
  for (const p of o.labels) {
    const top = 6 + p.row * L.rowHeight;
    const isLookout = p.item.kind === 'lookout';
    const hl = o.highlight === p.item.key;
    ctx.strokeStyle = hl ? P.accent : isLookout ? P.lookout : P.leader;
    ctx.lineWidth = hl ? 1.6 : 1;
    ctx.beginPath();
    ctx.moveTo(Math.round(p.ax) + 0.5, top + L.rowHeight - 4);
    ctx.lineTo(Math.round(p.ax) + 0.5, p.ay - 3);
    ctx.stroke();
    // Anchor tick.
    ctx.fillStyle = ctx.strokeStyle;
    ctx.beginPath();
    ctx.arc(p.ax, p.ay, hl ? 3 : 2, 0, Math.PI * 2);
    ctx.fill();
    // Text with a soft backing so it reads over the sky.
    ctx.fillStyle = P.labelHalo;
    roundRect(ctx, p.x, top, p.w, L.rowHeight - 5, 4);
    ctx.fill();
    if (hl) {
      ctx.strokeStyle = P.accent;
      ctx.lineWidth = 1.5;
      roundRect(ctx, p.x, top, p.w, L.rowHeight - 5, 4);
      ctx.stroke();
    }
    let tx = p.x + 4;
    if (isLookout) {
      drawTriangle(ctx, tx + 5, top + 9, 5, P.lookout, !!p.item.gone, P.labelHalo);
      tx += 14;
    }
    ctx.fillStyle = isLookout ? P.lookout : P.ink;
    ctx.font = `${isLookout ? 700 : 600} 12px ${FONT}`;
    ctx.fillText(p.item.name, tx, top + 12);
    ctx.fillStyle = P.muted;
    ctx.font = `500 10.5px ${FONT}`;
    ctx.fillText(p.item.sub, tx, top + 23);
  }

  drawRing(ctx, view, L, P);

  if (o.reticle !== false) {
    const x = Math.round(W / 2) + 0.5;
    ctx.strokeStyle = P.accent;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(x, L.terrainTop - 8);
    ctx.lineTo(x, L.ringTop);
    ctx.stroke();
    ctx.fillStyle = P.accent;
    ctx.beginPath();
    ctx.moveTo(x - 6, L.terrainTop - 14);
    ctx.lineTo(x + 6, L.terrainTop - 14);
    ctx.lineTo(x, L.terrainTop - 6);
    ctx.closePath();
    ctx.fill();
  }
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number): void {
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
}

function drawTriangle(ctx: CanvasRenderingContext2D, cx: number, cy: number, r: number, color: string, hollow: boolean, bg: string): void {
  ctx.beginPath();
  ctx.moveTo(cx, cy - r);
  ctx.lineTo(cx + r, cy + r * 0.85);
  ctx.lineTo(cx - r, cy + r * 0.85);
  ctx.closePath();
  ctx.fillStyle = hollow ? bg : color;
  ctx.fill();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.4;
  ctx.stroke();
}

const POINT_NAMES: Record<number, string> = { 0: 'N', 45: 'NE', 90: 'E', 135: 'SE', 180: 'S', 225: 'SW', 270: 'W', 315: 'NW' };

/** The azimuth ring: degrees clockwise from true north, numbered every 10°. */
export function drawRing(ctx: CanvasRenderingContext2D, view: View, L: Layout, P: Palette): void {
  const { width: W } = L;
  const top = L.ringTop;
  ctx.fillStyle = P.ringBg;
  ctx.fillRect(0, top, W, L.height - top);
  ctx.strokeStyle = P.ringLine;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, top + 0.5);
  ctx.lineTo(W, top + 0.5);
  ctx.stroke();
  const half = W / 2 / view.pxPerDeg;
  const minor = view.pxPerDeg >= 5 ? 1 : view.pxPerDeg >= 1.5 ? 5 : 10;
  const numberEvery = view.pxPerDeg >= 3 ? 10 : view.pxPerDeg >= 1.2 ? 30 : 45;
  const start = Math.floor((view.az - half) / minor) * minor;
  ctx.textAlign = 'center';
  ctx.strokeStyle = P.ringInk;
  for (let a = start; a <= view.az + half + minor; a += minor) {
    const x = Math.round(W / 2 + (a - view.az) * view.pxPerDeg) + 0.5;
    const az = wrap360(a);
    const len = az % 10 === 0 ? 11 : az % 5 === 0 ? 7 : 4;
    ctx.lineWidth = az % 10 === 0 ? 1.2 : 1;
    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x, top + len);
    ctx.stroke();
    const point = POINT_NAMES[az];
    if (point && (az % 90 === 0 || view.pxPerDeg >= 1.2)) {
      ctx.fillStyle = az % 90 === 0 ? P.accent : P.ringInk;
      ctx.font = `800 ${az % 90 === 0 ? 14 : 12}px ${FONT}`;
      ctx.fillText(point, x, top + 30);
    } else if (az % numberEvery === 0) {
      ctx.fillStyle = P.ringInk;
      ctx.font = `600 11px ${FONT}`;
      ctx.fillText(String(az), x, top + 27);
    }
  }
  ctx.textAlign = 'start';
}

function rand(seed: number): () => number {
  let s = seed >>> 0 || 1;
  return () => {
    s ^= s << 13;
    s ^= s >>> 17;
    s ^= s << 5;
    return ((s >>> 0) % 10_000) / 10_000;
  };
}

/** A smoke column: soft puffs rising from its base and drifting with the wind. */
export function drawSmoke(ctx: CanvasRenderingContext2D, view: View, L: Layout, s: Smoke, P: Palette): void {
  const x0 = xOf(view, L, s.az);
  if (x0 < -80 || x0 > L.width + 80) return;
  const yb = yOf(L, s.baseAngle);
  const yt = yOf(L, s.topAngle);
  const r = rand(s.seed);
  const w = Math.max(s.widthDeg * view.pxPerDeg, 2.5);
  const n = 22;
  for (let i = 0; i < n; i++) {
    const f = i / (n - 1);
    const y = yb + (yt - yb) * f;
    const drift = f * f * w * 3.2 + (r() - 0.5) * w * 0.6;
    const rad = w * (0.6 + f * 1.8) * (0.8 + r() * 0.4);
    const alpha = 0.55 * (1 - f * 0.75);
    const g = ctx.createRadialGradient(x0 + drift, y, 0, x0 + drift, y, rad);
    const [cr, cg, cb] = P.smoke;
    g.addColorStop(0, `rgba(${cr},${cg},${cb},${alpha})`);
    g.addColorStop(1, `rgba(${cr},${cg},${cb},0)`);
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(x0 + drift, y, rad, 0, Math.PI * 2);
    ctx.fill();
  }
}

/** The whole circle as a small strip, with the current view outlined. */
export function drawOverview(ctx: CanvasRenderingContext2D, data: PanoramaData, view: View, W: number, H: number, P: Palette, windowDeg: number): void {
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = P.skyHorizon;
  ctx.fillRect(0, 0, W, H);
  const nl = data.layersM.length;
  const last = (nl - 1) * data.columns;
  let hi = -90;
  let lo = 90;
  for (let c = 0; c < data.columns; c++) {
    const a = data.horizon[last + c]!;
    if (a > -89) {
      hi = Math.max(hi, a);
      lo = Math.min(lo, a);
    }
  }
  const span = Math.max(hi - lo, 0.5);
  const yOfA = (a: number) => 4 + ((hi - a) / span) * (H - 18);
  const dists = layerDistances(data.layersM);
  const step = Math.max(1, Math.floor(data.columns / W / 1));
  // Three bands are enough at this size: far, middle, near.
  for (const j of [nl - 1, Math.floor(nl * 0.66), Math.floor(nl * 0.4)]) {
    ctx.beginPath();
    for (let c = 0; c <= data.columns; c += step) {
      const a = data.horizon[j * data.columns + (c % data.columns)]!;
      const x = (c / data.columns) * W;
      const y = a < -89 ? H : Math.min(yOfA(a), H);
      if (c === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.lineTo(W, H);
    ctx.lineTo(0, H);
    ctx.closePath();
    ctx.fillStyle = mix(P.near, P.far, haze(dists[j]!) * 0.85);
    ctx.fill();
  }
  // Cardinal letters.
  ctx.font = `700 10px ${FONT}`;
  ctx.textAlign = 'center';
  for (const [a, n] of [[0, 'N'], [90, 'E'], [180, 'S'], [270, 'W']] as const) {
    const x = (a / 360) * W;
    ctx.fillStyle = P.ink;
    ctx.fillText(n, Math.min(Math.max(x, 6), W - 6), H - 3);
  }
  ctx.textAlign = 'start';
  // The window.
  const x0 = ((view.az - windowDeg / 2) / 360) * W;
  const ww = (windowDeg / 360) * W;
  ctx.strokeStyle = P.accent;
  ctx.lineWidth = 2;
  for (const off of [-W, 0, W]) {
    ctx.strokeRect(x0 + off + 1, 1, ww - 2, H - 2);
  }
}

/** What is under a point of the view: sky, or terrain at roughly what distance. */
export function pick(data: PanoramaData, view: View, L: Layout, x: number, y: number): { az: number; angle: number; distM: number | null } {
  const az = azOf(view, L, x);
  const angle = (L.horizonY - y) / L.vScale;
  const nl = data.layersM.length;
  for (let j = 0; j < nl; j++) {
    if (horizonAt(data, j, az) >= angle) {
      const c = Math.round(wrap360(az) / data.azStep) % data.columns;
      const crest = data.crest[j * data.columns + c]!;
      const d = Number.isFinite(crest) ? crest : layerDistances(data.layersM)[j]!;
      return { az, angle, distM: d };
    }
  }
  return { az, angle, distM: null };
}
