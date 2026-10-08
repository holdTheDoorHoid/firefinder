/**
 * Simple schematic drawings for the designs guide: a cab on a tower, a ground cab, a cupola
 * house, a steel tower with its small cab. Drawn here (not traced from any plan), in
 * currentColor so they follow the theme, and always captioned as schematics, not to scale.
 */

type Roof = 'hip' | 'gable' | 'flat';
type Tower = 'none' | 'timber' | 'steel' | 'block' | 'footing' | 'enclosed' | 'stone' | 'mast';
type Walls = 'frame' | 'log' | 'stone';

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
  /** A lower story under the cab (a two-story lookout): its height and walls. */
  lower?: { h: number; walls: Walls };
  /** How much of the cab wall is window (default 0.58). */
  glazed?: number;
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
  const courses = kind === 'log' ? 5 : kind === 'stone' ? 4 : 3;
  const below = top + h * glazed;
  const rowY = (i: number) => below + ((base - below) * (i + 1)) / (courses + 1);
  const lines = Array.from({ length: courses }, (_, i) => `M${f(x)} ${f(rowY(i))}h${f(w)}`).join('');
  out.push(`<path class="sk-thin" d="${lines}"/>`);
  if (kind === 'stone') {
    // Staggered joints between the courses, so the wall reads as masonry.
    const joints: string[] = [];
    for (let r = 0; r <= courses; r++) {
      const y0 = r ? rowY(r - 1) : below;
      const y1 = r < courses ? rowY(r) : base;
      for (let k = 1; k < 4; k++) joints.push(`M${f(x + (w * (k - (r % 2) * 0.5)) / 3.5)} ${f(y0)}V${f(y1)}`);
    }
    out.push(`<path class="sk-thin" d="${joints.join('')}"/>`);
  }
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

/** A closed-in tower or base: a tapering box with siding (timber) or masonry (stone), and a door. */
function enclosedTower(cx: number, topY: number, w: number, kind: 'enclosed' | 'stone'): string {
  const wBot = w * (kind === 'stone' ? 1.25 : 1.12);
  const h = GROUND - topY;
  const pts = `${f(cx - w / 2)},${f(topY)} ${f(cx + w / 2)},${f(topY)} ${f(cx + wBot / 2)},${GROUND} ${f(cx - wBot / 2)},${GROUND}`;
  const rows = Math.max(2, Math.round(h / (kind === 'stone' ? 9 : 6)));
  const at = (t: number) => [cx - (w + (wBot - w) * t) / 2, cx + (w + (wBot - w) * t) / 2] as const;
  const lines: string[] = [];
  for (let i = 1; i < rows; i++) {
    const [a, b] = at(i / rows);
    lines.push(`M${f(a)} ${f(topY + (h * i) / rows)}H${f(b)}`);
    if (kind === 'stone') {
      const y0 = topY + (h * (i - 1)) / rows;
      for (let k = 1; k < 4; k++) lines.push(`M${f(a + ((b - a) * (k - (i % 2) * 0.5)) / 3.5)} ${f(y0)}v${f(h / rows)}`);
    }
  }
  const door = `M${f(cx - 5)} ${GROUND}v-14h10v14`;
  return `<polygon class="sk-fill" points="${pts}"/><path class="sk-thin" d="${lines.join('')}"/><path class="sk-line" d="${door}"/><polygon class="sk-edge" points="${pts}"/>`;
}

function draw(s: Spec): string {
  const cx = s.cx ?? W / 2;
  const parts: string[] = [];
  const raised = s.tower === 'none' ? 0 : s.tower === 'footing' ? 4 : s.towerH;
  if (s.lower) {
    // The lower story of a two-story lookout, with a couple of small windows.
    const top = GROUND - raised - s.lower.h;
    parts.push(walls(cx, GROUND - raised, s.cabW + 8, s.lower.h, s.lower.walls, 0));
    parts.push(`<rect class="sk-glass" x="${f(cx - s.cabW / 2 + 2)}" y="${f(top + s.lower.h * 0.25)}" width="9" height="9"/><rect class="sk-glass" x="${f(cx + s.cabW / 2 - 11)}" y="${f(top + s.lower.h * 0.25)}" width="9" height="9"/>`);
  }
  const base = GROUND - raised - (s.lower?.h ?? 0);
  if (s.quarters) {
    // Living quarters on the ground beside the tower.
    parts.push(walls(30, GROUND, 30, 20, 'frame', 0.35), roof(30, GROUND - 20, 30, 'gable'));
  }
  if (s.tower === 'timber') parts.push(timberTower(cx, base, s.cabW * 0.82));
  if (s.tower === 'steel') parts.push(steelTower(cx, base, s.cabW * 0.9));
  if (s.tower === 'block') parts.push(blockBase(cx, base, s.cabW + 4));
  if (s.tower === 'enclosed' || s.tower === 'stone') parts.push(enclosedTower(cx, GROUND - raised, s.cabW + 2, s.tower));
  if (s.tower === 'mast') {
    // One guyed pole with a small railed platform and no cab.
    const top = GROUND - raised;
    const guys = `M${f(cx)} ${f(top + 12)}L${f(cx - 52)} ${GROUND}M${f(cx)} ${f(top + 12)}L${f(cx + 52)} ${GROUND}`;
    const steps = Array.from({ length: Math.floor(raised / 10) }, (_, i) => `M${f(cx + (i % 2 ? 2 : -2))} ${f(GROUND - 6 - i * 10)}h${i % 2 ? 4 : -4}`).join('');
    parts.push(`<path class="sk-thin" d="${guys}"/><path class="sk-timber" d="M${f(cx)} ${GROUND}V${f(top)}${steps}"/>`);
    parts.push(`<path class="sk-line" d="M${f(cx - s.cabW / 2)} ${f(top)}H${f(cx + s.cabW / 2)}M${f(cx - s.cabW / 2)} ${f(top)}v-9M${f(cx + s.cabW / 2)} ${f(top)}v-9M${f(cx - s.cabW / 2)} ${f(top - 9)}H${f(cx + s.cabW / 2)}M${f(cx - 6)} ${f(top)}L${f(cx)} ${f(top + 10)}L${f(cx + 6)} ${f(top)}"/>`);
    parts.push(ground());
    return parts.join('');
  }
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
    parts.push(walls(cx, base, s.cabW, s.cabH, s.walls, s.glazed));
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
  steel_wood_cab: {
    spec: { cabW: 42, cabH: 30, roof: 'hip', tower: 'steel', towerH: 54, catwalk: false, shutters: false, walls: 'frame' },
    alt: 'a short steel lattice tower carrying a large square wooden live-in cab with a pyramid roof',
  },
  steel_cab: {
    spec: { cabW: 46, cabH: 30, roof: 'flat', tower: 'steel', towerH: 76, catwalk: true, shutters: false, walls: 'frame' },
    alt: 'a square live-in cab with a flat overhanging roof and a catwalk on a braced steel tower',
  },
  enclosed_steel: {
    spec: { cabW: 46, cabH: 30, roof: 'hip', tower: 'enclosed', towerH: 54, catwalk: true, shutters: false, walls: 'frame' },
    alt: 'a square cab with a catwalk on top of a closed-in tower with a door at the bottom',
  },
  enclosed_timber: {
    spec: { cabW: 46, cabH: 32, roof: 'hip', tower: 'enclosed', towerH: 28, catwalk: true, shutters: true, walls: 'frame' },
    alt: 'a square cab with a pyramid roof, shutters and a catwalk on a short closed-in timber tower',
  },
  timber_tower: {
    spec: { cabW: 40, cabH: 28, roof: 'hip', tower: 'timber', towerH: 112, catwalk: true, shutters: false, walls: 'frame' },
    alt: 'a tall braced timber tower with a cab and catwalk on top',
  },
  cupola_tower: {
    spec: { cabW: 30, cabH: 26, roof: 'hip', tower: 'timber', towerH: 100, catwalk: false, shutters: false, walls: 'frame' },
    alt: 'a small glassed observation room, the cupola, on top of a tall timber tower',
  },
  r3: {
    spec: { cabW: 44, cabH: 30, roof: 'gable', tower: 'block', towerH: 22, catwalk: false, shutters: false, walls: 'frame', glazed: 0.72 },
    alt: 'a square wooden cab with windows coming down low on every side, on a short concrete-block base',
  },
  house: {
    spec: { cabW: 76, cabH: 30, roof: 'gable', tower: 'footing', towerH: 0, catwalk: false, shutters: false, walls: 'frame', glazed: 0.45 },
    alt: 'a long, low frame house with a gable roof and a band of windows on the lookout room',
  },
  two_story: {
    spec: { cabW: 46, cabH: 30, roof: 'hip', tower: 'none', towerH: 0, catwalk: true, shutters: false, walls: 'frame', lower: { h: 34, walls: 'frame' } },
    alt: 'a two-story building: a plain lower floor with small windows, and a glassed lookout room with a catwalk above',
  },
  stone_two_story: {
    spec: { cabW: 46, cabH: 30, roof: 'hip', tower: 'none', towerH: 0, catwalk: true, shutters: false, walls: 'frame', lower: { h: 34, walls: 'stone' } },
    alt: 'a two-story lookout: a stone lower floor and a wood-framed, glassed lookout room above',
  },
  log_two_story: {
    spec: { cabW: 54, cabH: 30, roof: 'hip', tower: 'none', towerH: 0, catwalk: false, shutters: false, walls: 'log', lower: { h: 34, walls: 'log' } },
    alt: 'a two-story log building with a steep pyramid roof and windows all round the upper floor',
  },
  log_cab: {
    spec: { cabW: 40, cabH: 30, roof: 'hip', tower: 'footing', towerH: 0, catwalk: false, shutters: false, walls: 'log', lower: { h: 18, walls: 'log' } },
    alt: 'a small glazed cab with a hip roof on a low crib of logs',
  },
  ground_cab: {
    spec: { cabW: 54, cabH: 32, roof: 'hip', tower: 'footing', towerH: 0, catwalk: false, shutters: true, walls: 'frame' },
    alt: 'a square one-room cab with windows all round and a steep pyramid roof, standing on the ground',
  },
  mast: {
    spec: { cabW: 22, cabH: 0, roof: 'flat', tower: 'mast', towerH: 128, catwalk: false, shutters: false, walls: 'frame' },
    alt: 'a single tall pole held by guy wires, with a small railed platform on top and steps up the pole',
  },
  stone_tower: {
    spec: { cabW: 38, cabH: 28, roof: 'hip', tower: 'stone', towerH: 72, catwalk: true, shutters: false, walls: 'frame' },
    alt: 'a cab with a catwalk on top of a tapering tower of stone masonry',
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
