/**
 * Geometry for the smoke-spotting lesson: where two bearings cross (a "cross-shot"), and how
 * good a fix is. Pure functions, tested in test/view3d.test.ts.
 */
import { bearingDeg, distanceM } from './tiles.ts';

export interface LatLon {
  lat: number;
  lon: number;
}

type V3 = [number, number, number];
const rad = (d: number) => (d * Math.PI) / 180;
const deg = (r: number) => (r * 180) / Math.PI;
const cross = (a: V3, b: V3): V3 => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const dot = (a: V3, b: V3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const norm = (a: V3): V3 => {
  const n = Math.hypot(...a);
  return [a[0] / n, a[1] / n, a[2] / n];
};

function unit(p: LatLon): V3 {
  const f = rad(p.lat);
  const l = rad(p.lon);
  return [Math.cos(f) * Math.cos(l), Math.cos(f) * Math.sin(l), Math.sin(f)];
}

/** Unit vector of the direction a bearing leaves a point in. */
function heading(p: LatLon, bearing: number): V3 {
  const f = rad(p.lat);
  const l = rad(p.lon);
  const north: V3 = [-Math.sin(f) * Math.cos(l), -Math.sin(f) * Math.sin(l), Math.cos(f)];
  const east: V3 = [-Math.sin(l), Math.cos(l), 0];
  const b = rad(bearing);
  return [north[0] * Math.cos(b) + east[0] * Math.sin(b), north[1] * Math.cos(b) + east[1] * Math.sin(b), north[2] * Math.cos(b) + east[2] * Math.sin(b)];
}

/**
 * Where the line of sight from `a` on bearing `ba` crosses the one from `b` on `bb` (great
 * circles), or null when they do not cross ahead of both lookouts within `maxM`.
 */
export function crossing(a: LatLon, ba: number, b: LatLon, bb: number, maxM = 150_000): LatLon | null {
  const pa = unit(a);
  const pb = unit(b);
  const da = heading(a, ba);
  const db = heading(b, bb);
  const na = cross(pa, da);
  const nb = cross(pb, db);
  const c = cross(na, nb);
  if (Math.hypot(...c) < 1e-12) return null; // the same line
  for (const sign of [1, -1]) {
    const i = norm([c[0] * sign, c[1] * sign, c[2] * sign]);
    if (dot(i, da) > 0 && dot(i, db) > 0) {
      const p = { lat: deg(Math.asin(i[2])), lon: deg(Math.atan2(i[1], i[0])) };
      if (distanceM(a.lat, a.lon, p.lat, p.lon) > maxM || distanceM(b.lat, b.lon, p.lat, p.lon) > maxM) return null;
      return p;
    }
  }
  return null;
}

/** The angle between the two lines of sight at the fire, degrees (90 is the best fix). */
export function cutAngle(a: LatLon, b: LatLon, fire: LatLon): number {
  const ba = bearingDeg(fire.lat, fire.lon, a.lat, a.lon);
  const bb = bearingDeg(fire.lat, fire.lon, b.lat, b.lon);
  const d = Math.abs(((ba - bb + 540) % 360) - 180);
  return d;
}

export interface Score {
  stars: 0 | 1 | 2 | 3;
  verdict: string;
}

/** How a fix this far from the fire would have served a fire crew. */
export function scoreFor(errorM: number): Score {
  if (errorM < 400) return { stars: 3, verdict: 'Right on it. A crew could walk straight to this smoke.' };
  if (errorM < 1_500) return { stars: 2, verdict: 'Close. The crew would find it with a short search.' };
  if (errorM < 5_000) return { stars: 1, verdict: 'In the right area, but the crew would have a long search.' };
  return { stars: 0, verdict: 'Too far off to send a crew. Take your time lining up the sight on the base of the smoke.' };
}

/** Round a reading as lookouts reported it: to the nearest half degree. */
export function halfDegree(az: number): number {
  const r = Math.round(az * 2) / 2;
  return r >= 360 ? r - 360 : r;
}
