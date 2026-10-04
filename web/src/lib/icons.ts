/**
 * Marker design. Status is never told by colour alone:
 *
 *   shape = what kind of structure      fill = whether it still stands
 *   ▲ triangle  cab/platform on a tower  solid      standing
 *   ⌂ house     ground-level building    hollow     gone
 *   ● circle    type unknown             hollow+dot ruins (footings/remains)
 *                                        half       moved, replica, or unknown
 *   amber dot at the top right = rentable
 *
 * The same geometry draws the map markers (canvas, in the browser) and the inline SVGs in the
 * legend, filters, badges and tower pages, so the key always matches the map.
 */

export type Shape = 'tri' | 'house' | 'circle';
export type Fill = 'solid' | 'hollow' | 'ruin' | 'half';

export const SHAPES: readonly Shape[] = ['tri', 'house', 'circle'];
export const FILLS: readonly Fill[] = ['solid', 'hollow', 'ruin', 'half'];

export function shapeFor(kind: string): Shape {
  if (kind === 'tower' || kind === 'enclosed_tower' || kind === 'platform') return 'tri';
  if (kind === 'ground' || kind === 'two_story' || kind === 'three_story') return 'house';
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
};
const LOWER_HALF: Record<Shape, string> = {
  tri: 'M7.04 11.8H16.96L21.6 20.4H2.4Z',
  house: 'M3.2 13.2H20.8V20.6H3.2Z',
  circle: 'M3.6 12A8.4 8.4 0 0 0 20.4 12Z',
};
const DOT: Record<Shape, [number, number]> = { tri: [12, 14.6], house: [12, 14.6], circle: [12, 12] };
const BADGE: [number, number, number] = [18.9, 5.0, 3.6];

export const MARKER_COLORS = {
  halo: '#fbf8f1',
  paper: '#fbf8f1',
  standing: '#2f6b4a',
  standingEdge: '#143523',
  gone: '#7b5a43',
  other: '#4f6787',
  otherEdge: '#2b3c55',
  rent: '#e2a325',
  rentEdge: '#5a3b00',
} as const;

interface Paint {
  fill: string;
  stroke: string;
  half?: string;
  dot?: string;
}

function paintFor(fill: Fill): Paint {
  const c = MARKER_COLORS;
  switch (fill) {
    case 'solid':
      return { fill: c.standing, stroke: c.standingEdge };
    case 'hollow':
      return { fill: c.paper, stroke: c.gone };
    case 'ruin':
      return { fill: c.paper, stroke: c.gone, dot: c.gone };
    case 'half':
      return { fill: c.paper, stroke: c.otherEdge, half: c.other };
  }
}

/** Inline SVG markup for a marker. Decorative: always pair it with a text label. */
export function markerSvg(shape: Shape, fill: Fill, opts: { rentable?: boolean; size?: number; className?: string } = {}): string {
  const p = paintFor(fill);
  const size = opts.size ?? 20;
  const cls = opts.className ? ` class="${opts.className}"` : '';
  let body = `<path d="${OUTLINE[shape]}" fill="none" stroke="${MARKER_COLORS.halo}" stroke-width="4.2" stroke-linejoin="round"/>`;
  body += `<path d="${OUTLINE[shape]}" fill="${p.fill}"/>`;
  if (p.half) body += `<path d="${LOWER_HALF[shape]}" fill="${p.half}"/>`;
  if (p.dot) body += `<circle cx="${DOT[shape][0]}" cy="${DOT[shape][1]}" r="2.5" fill="${p.dot}"/>`;
  body += `<path d="${OUTLINE[shape]}" fill="none" stroke="${p.stroke}" stroke-width="${fill === 'solid' ? 1.6 : 2.1}" stroke-linejoin="round"/>`;
  if (opts.rentable) {
    const [x, y, r] = BADGE;
    body += `<circle cx="${x}" cy="${y}" r="${r + 1.3}" fill="${MARKER_COLORS.halo}"/><circle cx="${x}" cy="${y}" r="${r}" fill="${MARKER_COLORS.rent}" stroke="${MARKER_COLORS.rentEdge}" stroke-width="1.2"/>`;
  }
  return `<svg${cls} width="${size}" height="${size}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${body}</svg>`;
}

/** Just the rentable badge, for legends. */
export function rentBadgeSvg(size = 14): string {
  return `<svg width="${size}" height="${size}" viewBox="0 0 12 12" aria-hidden="true" focusable="false"><circle cx="6" cy="6" r="5.4" fill="${MARKER_COLORS.halo}"/><circle cx="6" cy="6" r="4.3" fill="${MARKER_COLORS.rent}" stroke="${MARKER_COLORS.rentEdge}" stroke-width="1.2"/></svg>`;
}

/** Browser only: draw a marker into a canvas context scaled so the 24-unit box fills `px`. */
export function drawMarker(ctx: CanvasRenderingContext2D, shape: Shape, fill: Fill, rentable: boolean, px: number): void {
  const p = paintFor(fill);
  const s = px / 24;
  ctx.save();
  ctx.scale(s, s);
  ctx.lineJoin = 'round';
  const outline = new Path2D(OUTLINE[shape]);
  ctx.strokeStyle = MARKER_COLORS.halo;
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
  ctx.lineWidth = fill === 'solid' ? 1.6 : 2.1;
  ctx.stroke(outline);
  if (rentable) {
    const [x, y, r] = BADGE;
    ctx.fillStyle = MARKER_COLORS.halo;
    ctx.beginPath();
    ctx.arc(x, y, r + 1.3, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = MARKER_COLORS.rent;
    ctx.strokeStyle = MARKER_COLORS.rentEdge;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }
  ctx.restore();
}
