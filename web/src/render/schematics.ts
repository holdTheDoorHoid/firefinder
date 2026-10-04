/**
 * Simple schematic drawings for the designs guide: a cab on a tower, a ground cab, a cupola
 * house, a steel tower with its small cab. Drawn here (not traced from any plan), in
 * currentColor so they follow the theme, and always captioned as schematics, not to scale.
 */

type Roof = 'hip' | 'gable' | 'flat';
type Tower = 'none' | 'timber' | 'steel' | 'block' | 'footing';
type Walls = 'frame' | 'log';

interface Spec {
  cabW: number;
  cabH: number;
  roof: Roof;
  tower: Tower;
  towerH: number;
  catwalk: boolean;
  shutters: boolean;
  walls: Walls;
  /** A two-part cupola house instead of a single cab. */
  cupola?: boolean;
  /** A separate ground cabin beside the tower (living quarters). */
  quarters?: boolean;
  cx?: number;
}

const W = 160;
const GROUND = 186;
const f = (n: number) => n.toFixed(1);

function ground(): string {
  const ticks = Array.from({ length: 12 }, (_, i) => `M${f(14 + i * 12)} ${GROUND}l-5 6`).join('');
  return `<path class="sk-ground" d="M8 ${GROUND}H152"/><path class="sk-hatch" d="${ticks}"/>`;
}

function roof(cx: number, top: number, w: number, kind: Roof): string {
  if (kind === 'flat') return `<rect class="sk-fill sk-roof" x="${f(cx - w / 2 - 9)}" y="${f(top - 5)}" width="${f(w + 18)}" height="5"/>`;
  const rise = kind === 'hip' ? w * 0.36 : w * 0.3;
  const eave = kind === 'hip' ? 4 : 6;
  const extra = kind === 'gable' ? `<path class="sk-thin" d="M${f(cx)} ${f(top - rise + 4)}V${f(top)}"/>` : '';
  return `<path class="sk-fill sk-roof" d="M${f(cx - w / 2 - eave)} ${f(top)}L${f(cx)} ${f(top - rise)}L${f(cx + w / 2 + eave)} ${f(top)}Z"/>${extra}`;
}

/** Walls with a band of windows on the upper part (frame) or log courses (log). */
function walls(cx: number, base: number, w: number, h: number, kind: Walls, glazed = 0.58): string {
  const x = cx - w / 2;
  const top = base - h;
  const out = [`<rect class="sk-fill" x="${f(x)}" y="${f(top)}" width="${f(w)}" height="${f(h)}"/>`];
  if (glazed > 0) {
    const gh = h * glazed;
    out.push(`<rect class="sk-glass" x="${f(x + 2)}" y="${f(top + 2)}" width="${f(w - 4)}" height="${f(gh - 2)}"/>`);
    const panes = Math.max(2, Math.round(w / 9));
    const mullions = Array.from({ length: panes - 1 }, (_, i) => `M${f(x + 2 + ((w - 4) * (i + 1)) / panes)} ${f(top + 2)}v${f(gh - 2)}`).join('');
    out.push(`<path class="sk-thin" d="${mullions}"/>`);
  }
  const courses = kind === 'log' ? 5 : 3;
  const below = top + h * glazed;
  const lines = Array.from({ length: courses }, (_, i) => `M${f(x)} ${f(below + ((base - below) * (i + 1)) / (courses + 1))}h${f(w)}`).join('');
  out.push(`<path class="sk-thin" d="${lines}"/>`);
  out.push(`<rect class="sk-edge" x="${f(x)}" y="${f(top)}" width="${f(w)}" height="${f(h)}"/>`);
  return out.join('');
}

function shutters(cx: number, top: number, w: number): string {
  // Wooden shutters propped open above the windows.
  return `<path class="sk-line" d="M${f(cx - w / 2)} ${f(top + 2)}l-9 -7M${f(cx + w / 2)} ${f(top + 2)}l9 -7"/>`;
}

function catwalk(cx: number, base: number, w: number): string {
  const x0 = cx - w / 2 - 8;
  const x1 = cx + w / 2 + 8;
  return `<path class="sk-line" d="M${f(x0)} ${f(base)}H${f(x1)}M${f(x0)} ${f(base - 9)}H${f(x1)}M${f(x0)} ${f(base)}v-9M${f(x1)} ${f(base)}v-9"/>`;
}

function timberTower(cx: number, topY: number, wTop: number): string {
  const wBot = wTop * 1.7;
  const lt = cx - wTop / 2;
  const rt = cx + wTop / 2;
  const lb = cx - wBot / 2;
  const rb = cx + wBot / 2;
  const h = GROUND - topY;
  const n = Math.max(2, Math.round(h / 30));
  const at = (t: number) => [lt + (lb - lt) * t, rt + (rb - rt) * t, topY + h * t] as const;
  const parts = [`M${f(lt)} ${f(topY)}L${f(lb)} ${GROUND}M${f(rt)} ${f(topY)}L${f(rb)} ${GROUND}`];
  for (let i = 0; i < n; i++) {
    const [a0, b0, y0] = at(i / n);
    const [a1, b1, y1] = at((i + 1) / n);
    parts.push(`M${f(a0)} ${f(y0)}H${f(b0)}M${f(a0)} ${f(y0)}L${f(b1)} ${f(y1)}M${f(b0)} ${f(y0)}L${f(a1)} ${f(y1)}`);
  }
  return `<path class="sk-timber" d="${parts.join('')}"/>`;
}

function steelTower(cx: number, topY: number, wTop: number): string {
  const wBot = wTop * 2.6;
  const h = GROUND - topY;
  const n = Math.max(3, Math.round(h / 22));
  const at = (t: number) => [cx - (wTop + (wBot - wTop) * t) / 2, cx + (wTop + (wBot - wTop) * t) / 2, topY + h * t] as const;
  const legs = `M${f(cx - wTop / 2)} ${f(topY)}L${f(cx - wBot / 2)} ${GROUND}M${f(cx + wTop / 2)} ${f(topY)}L${f(cx + wBot / 2)} ${GROUND}`;
  const braces: string[] = [];
  const stairs: string[] = [];
  for (let i = 0; i < n; i++) {
    const [a0, b0, y0] = at(i / n);
    const [a1, b1, y1] = at((i + 1) / n);
    braces.push(`M${f(a0)} ${f(y0)}H${f(b0)}M${f(a0)} ${f(y0)}L${f(b1)} ${f(y1)}M${f(b0)} ${f(y0)}L${f(a1)} ${f(y1)}`);
    // Zigzag stair flights inside the tower.
    const inset = (b1 - a1) * 0.22;
    stairs.push(i % 2 ? `M${f(a1 + inset)} ${f(y1)}L${f(b0 - inset)} ${f(y0)}` : `M${f(b1 - inset)} ${f(y1)}L${f(a0 + inset)} ${f(y0)}`);
  }
  return `<path class="sk-steel" d="${legs}${braces.join('')}"/><path class="sk-stair" d="${stairs.join('')}"/>`;
}

function blockBase(cx: number, topY: number, w: number): string {
  const h = GROUND - topY;
  const rows = Math.max(2, Math.round(h / 6));
  const courses = Array.from({ length: rows - 1 }, (_, i) => `M${f(cx - w / 2)} ${f(topY + (h * (i + 1)) / rows)}h${f(w)}`).join('');
  const joints: string[] = [];
  for (let r = 0; r < rows; r++) {
    const y0 = topY + (h * r) / rows;
    for (let k = 1; k < 5; k++) joints.push(`M${f(cx - w / 2 + (w * (k - (r % 2) * 0.5)) / 5)} ${f(y0)}v${f(h / rows)}`);
  }
  return `<rect class="sk-fill" x="${f(cx - w / 2)}" y="${f(topY)}" width="${f(w)}" height="${f(h)}"/><path class="sk-thin" d="${courses}${joints.join('')}"/><rect class="sk-edge" x="${f(cx - w / 2)}" y="${f(topY)}" width="${f(w)}" height="${f(h)}"/>`;
}

function draw(s: Spec): string {
  const cx = s.cx ?? W / 2;
  const parts: string[] = [];
  const base = GROUND - (s.tower === 'none' ? 0 : s.tower === 'footing' ? 4 : s.towerH);
  if (s.quarters) {
    // Living quarters on the ground beside the tower.
    parts.push(walls(30, GROUND, 30, 20, 'frame', 0.35), roof(30, GROUND - 20, 30, 'gable'));
  }
  if (s.tower === 'timber') parts.push(timberTower(cx, base, s.cabW * 0.82));
  if (s.tower === 'steel') parts.push(steelTower(cx, base, s.cabW * 0.9));
  if (s.tower === 'block') parts.push(blockBase(cx, base, s.cabW + 4));
  if (s.tower === 'footing') parts.push(`<rect class="sk-fill sk-edge" x="${f(cx - s.cabW / 2 - 3)}" y="${f(base)}" width="${f(s.cabW + 6)}" height="4"/>`);
  if (s.cupola) {
    const lowH = s.cabH;
    parts.push(walls(cx, base, s.cabW, lowH, s.walls, 0.22));
    parts.push(roof(cx, base - lowH, s.cabW, 'hip'));
    const cw = s.cabW * 0.46;
    const ch = s.cabH * 0.62;
    const cbase = base - lowH - s.cabW * 0.12;
    parts.push(walls(cx, cbase, cw, ch, 'frame', 0.85));
    parts.push(roof(cx, cbase - ch, cw, 'hip'));
  } else {
    parts.push(walls(cx, base, s.cabW, s.cabH, s.walls));
    parts.push(roof(cx, base - s.cabH, s.cabW, s.roof));
    if (s.shutters) parts.push(shutters(cx, base - s.cabH, s.cabW));
    if (s.catwalk) parts.push(catwalk(cx, base, s.cabW));
  }
  parts.push(ground());
  return parts.join('');
}

const SPECS: Record<string, { spec: Spec; alt: string }> = {
  l4: {
    spec: { cabW: 48, cabH: 34, roof: 'hip', tower: 'timber', towerH: 66, catwalk: true, shutters: true, walls: 'frame' },
    alt: 'a square cab with windows all round, a pyramid roof and propped-open shutters, on a timber tower with a catwalk (many stand on the ground instead)',
  },
  l5: {
    spec: { cabW: 36, cabH: 30, roof: 'gable', tower: 'footing', towerH: 0, catwalk: false, shutters: false, walls: 'frame' },
    alt: 'a small gable-roofed cab with windows all round, on the ground',
  },
  l6: {
    spec: { cabW: 28, cabH: 26, roof: 'hip', tower: 'timber', towerH: 112, catwalk: true, shutters: false, walls: 'frame', quarters: true, cx: 104 },
    alt: 'a very small cab with a pyramid roof high on a tall timber tower, with separate living quarters on the ground beside it',
  },
  r6: {
    spec: { cabW: 50, cabH: 32, roof: 'flat', tower: 'block', towerH: 24, catwalk: true, shutters: false, walls: 'frame' },
    alt: 'a square cab with windows all round under a flat roof that overhangs on every side, on a short concrete-block base',
  },
  d6: {
    spec: { cabW: 58, cabH: 34, roof: 'hip', tower: 'footing', towerH: 0, catwalk: false, shutters: false, walls: 'frame', cupola: true },
    alt: 'a small house with a hipped roof and a small glassed observation room (the cupola) on top',
  },
  d1: {
    spec: { cabW: 58, cabH: 34, roof: 'hip', tower: 'footing', towerH: 0, catwalk: false, shutters: false, walls: 'log', cupola: true },
    alt: 'a log cabin with a small glassed cupola on its roof',
  },
  cupola: {
    spec: { cabW: 54, cabH: 32, roof: 'hip', tower: 'footing', towerH: 0, catwalk: false, shutters: false, walls: 'log', cupola: true },
    alt: 'a cabin with a small glassed observation room on its roof',
  },
  r5: {
    spec: { cabW: 46, cabH: 32, roof: 'hip', tower: 'steel', towerH: 66, catwalk: true, shutters: false, walls: 'frame' },
    alt: 'a square live-in cab with a pyramid roof and catwalk on a braced steel tower',
  },
  steel: {
    spec: { cabW: 24, cabH: 24, roof: 'hip', tower: 'steel', towerH: 118, catwalk: false, shutters: false, walls: 'frame' },
    alt: 'a small square steel cab on top of a tall, tapering steel lattice tower with stairs zigzagging up inside',
  },
};

export function hasSchematic(kind: string | null | undefined): boolean {
  return !!kind && kind in SPECS;
}

/** The schematic as an SVG string (role="img" with a description), or '' for an unknown kind. */
export function schematicSvg(kind: string | null | undefined, name: string): string {
  const s = kind ? SPECS[kind] : undefined;
  if (!s) return '';
  const label = `Schematic drawing of ${name}: ${s.alt}. Not to scale.`.replace(/[<>&"]/g, '');
  return `<svg class="schematic" viewBox="0 0 ${W} 196" width="160" height="196" role="img" aria-label="${label}" focusable="false">${draw(s.spec)}</svg>`;
}
