/**
 * Marker design. Status is never told by colour alone:
 *
 *   shape = what kind of structure      fill = whether it still stands
 *   ▲ triangle  cab/platform on a tower  solid      standing
 *   ⌂ house     a building: ground cab,  hollow     gone
 *               2-3 stories, rooftop     hollow+dot ruins (footings/remains)
 *               cab, trailer             half       moved, replica, or unknown
 *   ● circle    type unknown
 *   ◆ diamond   no structure: camp, lookout tree, bare point
 *   amber dot at the top right = rentable
 *
 * "Hollow" means the inside matches the background, so the palette flips with the theme: in
 * dark mode a standing marker is a bright solid shape and a gone one a dark shape with a light
 * outline. Otherwise "solid" would look hollow on a dark map.
 *
 * The same geometry draws the map markers (canvas, in the browser) and the inline SVGs in the
 * legend, filters, badges and tower pages. The SVGs carry the light palette as attributes and
 * classes that base.css recolours (--mk-* tokens) for dark mode; keep the two palettes equal.
 */

export type Shape = 'tri' | 'house' | 'circle' | 'diamond';
export type Fill = 'solid' | 'hollow' | 'ruin' | 'half';
export type MarkerTheme = 'light' | 'dark';

export const SHAPES: readonly Shape[] = ['tri', 'house', 'circle', 'diamond'];
export const FILLS: readonly Fill[] = ['solid', 'hollow', 'ruin', 'half'];

/** Kinds drawn with each shape; any other kind (unknown, or one added later) is a circle. */
export const SHAPE_KINDS: Record<Exclude<Shape, 'circle'>, readonly string[]> = {
  tri: ['tower', 'enclosed_tower', 'platform'],
  house: ['ground', 'two_story', 'three_story', 'rooftop', 'mobile'],
  diamond: ['camp', 'tree', 'point'],
};

export function shapeFor(kind: string): Shape {
  for (const shape of ['tri', 'house', 'diamond'] as const) if (SHAPE_KINDS[shape].includes(kind)) return shape;
  return 'circle';
}

export function fillFor(status: string): Fill {
  if (status === 'standing') return 'solid';
  if (status === 'gone') return 'hollow';
  if (status === 'ruins') return 'ruin';
  return 'half';
}

export function iconName(shape: Shape, fill: Fill, rentable: boolean): string {
  return `ff-${shape}-${fill}${rentable ? '-rent' : ''}`;
}

/** Geometry in a 24 x 24 box. */
const OUTLINE: Record<Shape, string> = {
  tri: 'M12 2.6L21.6 20.4H2.4Z',
  house: 'M3.2 10.4L12 3L20.8 10.4V20.6H3.2Z',
  circle: 'M3.6 12A8.4 8.4 0 1 0 20.4 12A8.4 8.4 0 1 0 3.6 12Z',
  diamond: 'M12 2.4L21.6 12L12 21.6L2.4 12Z',
};
const LOWER_HALF: Record<Shape, string> = {
  tri: 'M7.04 11.8H16.96L21.6 20.4H2.4Z',
  house: 'M3.2 13.2H20.8V20.6H3.2Z',
  circle: 'M3.6 12A8.4 8.4 0 0 0 20.4 12Z',
  diamond: 'M2.4 12H21.6L12 21.6Z',
};
const DOT: Record<Shape, [number, number]> = { tri: [12, 14.6], house: [12, 14.6], circle: [12, 12], diamond: [12, 12] };
const BADGE: [number, number, number] = [18.9, 5.0, 3.6];

export interface MarkerPalette {
  halo: string;
  standing: string;
  standingEdge: string;
  hollow: string;
  gone: string;
  other: string;
  otherEdge: string;
  rent: string;
  rentEdge: string;
}

/** Keep in step with the --mk-* tokens in src/styles/base.css. */
export const MARKER_PALETTE: Record<MarkerTheme, MarkerPalette> = {
  light: {
    halo: '#fbf8f1',
    standing: '#2f6b4a',
    standingEdge: '#143523',
    hollow: '#fbf8f1',
    gone: '#7b5a43',
    other: '#4f6787',
    otherEdge: '#2b3c55',
    rent: '#e2a325',
    rentEdge: '#5a3b00',
  },
  dark: {
    halo: '#0e1411',
    standing: '#7ccb9c',
    standingEdge: '#0e2619',
    hollow: '#18211c',
    gone: '#dcae8c',
    other: '#9fb7da',
    otherEdge: '#9fb7da',
    rent: '#f2b63e',
    rentEdge: '#2a1b00',
  },
};

interface Paint {
  fill: string;
  stroke: string;
  width: number;
  half?: string;
  dot?: string;
}

function paintFor(fill: Fill, c: MarkerPalette): Paint {
  switch (fill) {
    case 'solid':
      return { fill: c.standing, stroke: c.standingEdge, width: 1.6 };
    case 'hollow':
      return { fill: c.hollow, stroke: c.gone, width: 2.1 };
    case 'ruin':
      return { fill: c.hollow, stroke: c.gone, width: 2.1, dot: c.gone };
    case 'half':
      return { fill: c.hollow, stroke: c.otherEdge, width: 2.1, half: c.other };
  }
}

/** Inline SVG markup for a marker. Decorative: always pair it with a text label. */
export function markerSvg(shape: Shape, fill: Fill, opts: { rentable?: boolean; size?: number; className?: string } = {}): string {
  const c = MARKER_PALETTE.light;
  const p = paintFor(fill, c);
  const size = opts.size ?? 20;
  const cls = `mk mk-${fill}${opts.className ? ` ${opts.className}` : ''}`;
  let body = `<path class="mk-halo" d="${OUTLINE[shape]}" fill="none" stroke="${c.halo}" stroke-width="4.2" stroke-linejoin="round"/>`;
  body += `<path class="mk-body" d="${OUTLINE[shape]}" fill="${p.fill}"/>`;
  if (p.half) body += `<path class="mk-half" d="${LOWER_HALF[shape]}" fill="${p.half}"/>`;
  if (p.dot) body += `<circle class="mk-dot" cx="${DOT[shape][0]}" cy="${DOT[shape][1]}" r="2.5" fill="${p.dot}"/>`;
  body += `<path class="mk-edge" d="${OUTLINE[shape]}" fill="none" stroke="${p.stroke}" stroke-width="${p.width}" stroke-linejoin="round"/>`;
  if (opts.rentable) {
    const [x, y, r] = BADGE;
    body += `<circle class="mk-rent-halo" cx="${x}" cy="${y}" r="${r + 1.3}" fill="${c.halo}"/><circle class="mk-rent" cx="${x}" cy="${y}" r="${r}" fill="${c.rent}" stroke="${c.rentEdge}" stroke-width="1.2"/>`;
  }
  return `<svg class="${cls}" width="${size}" height="${size}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${body}</svg>`;
}

/** The marker palette as CSS custom properties (the --mk-* tokens in base.css, which follow the theme). */
const PALETTE_VARS: MarkerPalette = {
  halo: 'var(--mk-halo)',
  standing: 'var(--mk-standing)',
  standingEdge: 'var(--mk-standing-edge)',
  hollow: 'var(--mk-hollow)',
  gone: 'var(--mk-gone)',
  other: 'var(--mk-other)',
  otherEdge: 'var(--mk-other-edge)',
  rent: 'var(--mk-rent)',
  rentEdge: 'var(--mk-rent-edge)',
};

/** Id of a marker's `<symbol>` in the sprite from `markerSprite`. */
export function markerSymbolId(shape: Shape, fill: Fill): string {
  return `mkr-${shape}-${fill}`;
}

/**
 * One `<symbol>` per shape and fill. Same geometry as `markerSvg`, but each part is painted by an
 * inline `style` using the --mk-* tokens, so a marker drawn with `markerUse` follows the theme
 * without any selector having to reach into the `<use>` shadow tree (engines differ on that). The
 * light palette stays in the attributes as the fallback.
 */
function markerSymbol(shape: Shape, fill: Fill): string {
  const c = MARKER_PALETTE.light;
  const p = paintFor(fill, c);
  const v = paintFor(fill, PALETTE_VARS);
  const d = OUTLINE[shape];
  let body = `<path d="${d}" fill="none" stroke="${c.halo}" stroke-width="4.2" stroke-linejoin="round" style="stroke:${PALETTE_VARS.halo}"/>`;
  body += `<path d="${d}" fill="${p.fill}" style="fill:${v.fill}"/>`;
  if (p.half) body += `<path d="${LOWER_HALF[shape]}" fill="${p.half}" style="fill:${v.half}"/>`;
  if (p.dot) body += `<circle cx="${DOT[shape][0]}" cy="${DOT[shape][1]}" r="2.5" fill="${p.dot}" style="fill:${v.dot}"/>`;
  body += `<path d="${d}" fill="none" stroke="${p.stroke}" stroke-width="${p.width}" stroke-linejoin="round" style="stroke:${v.stroke}"/>`;
  return `<symbol id="${markerSymbolId(shape, fill)}" viewBox="0 0 24 24">${body}</symbol>`;
}

/**
 * A hidden sprite holding the markers a long page uses, drawn once. Put it anywhere in the page
 * (it takes no room and is hidden from assistive technology) and draw each marker with
 * `markerUse`; `extraSymbols` adds the page's own `<symbol>`s to the same sprite. A page with thousands of markers, such as the designs guide, is about half as
 * large this way as with `markerSvg` on every entry.
 */
export function markerSprite(pairs: Iterable<readonly [Shape, Fill]>, extraSymbols = ''): string {
  const seen = new Set<string>();
  const symbols: string[] = [];
  for (const [shape, fill] of pairs) {
    const id = markerSymbolId(shape, fill);
    if (seen.has(id)) continue;
    seen.add(id);
    symbols.push(markerSymbol(shape, fill));
  }
  if (!symbols.length && !extraSymbols) return '';
  // Zero size rather than display:none, which some browsers treat as "do not draw what this holds".
  return `<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false">${symbols.join('')}${extraSymbols}</svg>`;
}

/**
 * A marker that points at the sprite. Decorative like `markerSvg`: always pair it with a text label.
 * It has no size of its own, so the page's CSS must give the `className` a width and height.
 */
export function markerUse(shape: Shape, fill: Fill, className = ''): string {
  return `<svg${className ? ` class="${className}"` : ''} aria-hidden="true"><use href="#${markerSymbolId(shape, fill)}"/></svg>`;
}

/** Just the rentable badge, for legends. */
export function rentBadgeSvg(size = 14): string {
  const c = MARKER_PALETTE.light;
  return `<svg class="mk" width="${size}" height="${size}" viewBox="0 0 12 12" aria-hidden="true" focusable="false"><circle class="mk-rent-halo" cx="6" cy="6" r="5.4" fill="${c.halo}"/><circle class="mk-rent" cx="6" cy="6" r="4.3" fill="${c.rent}" stroke="${c.rentEdge}" stroke-width="1.2"/></svg>`;
}

/** Browser only: draw a marker into a canvas context scaled so the 24-unit box fills `px`. */
export function drawMarker(ctx: CanvasRenderingContext2D, shape: Shape, fill: Fill, rentable: boolean, px: number, theme: MarkerTheme = 'light'): void {
  const c = MARKER_PALETTE[theme];
  const p = paintFor(fill, c);
  const s = px / 24;
  ctx.save();
  ctx.scale(s, s);
  ctx.lineJoin = 'round';
  const outline = new Path2D(OUTLINE[shape]);
  ctx.strokeStyle = c.halo;
  ctx.lineWidth = 4.2;
  ctx.stroke(outline);
  ctx.fillStyle = p.fill;
  ctx.fill(outline);
  if (p.half) {
    ctx.fillStyle = p.half;
    ctx.fill(new Path2D(LOWER_HALF[shape]));
  }
  if (p.dot) {
    ctx.fillStyle = p.dot;
    ctx.beginPath();
    ctx.arc(DOT[shape][0], DOT[shape][1], 2.5, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.strokeStyle = p.stroke;
  ctx.lineWidth = p.width;
  ctx.stroke(outline);
  if (rentable) {
    const [x, y, r] = BADGE;
    ctx.fillStyle = c.halo;
    ctx.beginPath();
    ctx.arc(x, y, r + 1.3, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = c.rent;
    ctx.strokeStyle = c.rentEdge;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }
  ctx.restore();
}
