/**
 * Which terrain tiles a view needs, and roughly how much downloading that is. The same tile
 * maths as `tiles_for_disc` in crates/firefinder-view/src/geo.rs (test/view3d.test.ts checks
 * they agree), so the size hint on a button can be shown before any WebAssembly loads.
 */

export const EARTH_RADIUS_M = 6_371_008.8;

/**
 * AWS Terrain Tiles (Mapzen / Tilezen "joerd"), Terrarium-encoded PNG, 256 px, no key, CORS
 * open. In the US the heights come from USGS 3DEP (formerly NED) and SRTM, with GMTED2010 at
 * low zooms and ETOPO1 for the sea floor. Credited on the About page.
 */
export const TERRAIN_URL = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png';

/**
 * Typical Terrarium tile sizes by zoom, measured on 24 tiles in Oregon, Idaho, New York and
 * Pennsylvania (October 2026). Fine zooms carry more detail and compress worse.
 */
export const TILE_BYTES: Record<number, number> = { 8: 88_000, 9: 80_000, 10: 66_000, 11: 100_000, 12: 128_000 };
const DEFAULT_TILE_BYTES = 100_000;

export interface Level {
  z: number;
  /** This level serves distances up to here, m. */
  maxM: number;
}

/**
 * Zoom levels for the view from the cab, finest first. At 45° north: about 27 m terrain spacing
 * in the first 4 km (zoom 12), 110 m out to 40 km (zoom 10), 220 m out to 100 km (zoom 9) and
 * 300 m beyond (zoom 8). Each is roughly as fine as a tenth of a degree of view at that
 * distance. `light` (phones) skips zoom 9: about 1.3 MB less to download, at the cost of sharp
 * distant summits drawn lower than they are.
 */
export function panoramaLevels(maxM: number, detail: 'full' | 'light' = 'full'): Level[] {
  const out: Level[] = [{ z: 12, maxM: Math.min(4_000, maxM) }];
  if (maxM > 4_000) out.push({ z: 10, maxM: Math.min(40_000, maxM) });
  if (detail === 'full' && maxM > 40_000) out.push({ z: 9, maxM: Math.min(100_000, maxM) });
  const reached = out[out.length - 1]!.maxM;
  if (maxM > reached) out.push({ z: 8, maxM });
  return out;
}

/** Zoom levels for a viewshed of the given radius: zoom 12 near the tower, zoom 10 beyond. */
export function viewshedLevels(radiusM: number): Level[] {
  const out: Level[] = [{ z: 12, maxM: Math.min(4_000, radiusM) }];
  if (radiusM > 4_000) out.push({ z: 10, maxM: radiusM });
  return out;
}

export function flatLevels(levels: Level[]): Float64Array {
  return Float64Array.from(levels.flatMap((l) => [l.z, l.maxM]));
}

const rad = (d: number) => (d * Math.PI) / 180;
const deg = (r: number) => (r * 180) / Math.PI;

function mercY(lat: number): number {
  const s = Math.sin(rad(lat));
  const clamped = Math.max(-0.9999999, Math.min(0.9999999, s));
  return 0.5 - Math.atanh(clamped) / (2 * Math.PI);
}

function unmercY(my: number): number {
  return deg(Math.atan(Math.sinh((0.5 - my) * 2 * Math.PI)));
}

/** Great-circle distance, m (spherical, like the Rust core). */
export function distanceM(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const dLat = rad(lat2 - lat1);
  const dLon = rad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(a)));
}

/** Initial great-circle bearing, degrees 0..360. */
export function bearingDeg(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const p1 = rad(lat1);
  const p2 = rad(lat2);
  const dl = rad(lon2 - lon1);
  const y = Math.sin(dl) * Math.cos(p2);
  const x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl);
  return (deg(Math.atan2(y, x)) + 360) % 360;
}

/** The point at a distance and bearing from a start point (spherical). */
export function destination(lat: number, lon: number, bearing: number, distM: number): [number, number] {
  const d = distM / EARTH_RADIUS_M;
  const b = rad(bearing);
  const p1 = rad(lat);
  const l1 = rad(lon);
  const p2 = Math.asin(Math.sin(p1) * Math.cos(d) + Math.cos(p1) * Math.sin(d) * Math.cos(b));
  const l2 = l1 + Math.atan2(Math.sin(b) * Math.sin(d) * Math.cos(p1), Math.cos(d) - Math.sin(p1) * Math.sin(p2));
  return [deg(p2), ((deg(l2) + 540) % 360) - 180];
}

/** Bounding box of a disc in normalised Web Mercator, `[x0, y0, x1, y1]` (x unwrapped). */
export function discBbox(lat: number, lon: number, radiusM: number): [number, number, number, number] {
  const dlat = deg(radiusM / EARTH_RADIUS_M);
  const hi = Math.min(lat + dlat, 85);
  const lo = Math.max(lat - dlat, -85);
  const widest = Math.max(Math.cos(rad(Math.max(Math.abs(hi), Math.abs(lo)))), 0.01);
  const dlon = Math.min(dlat / widest, 179);
  return [(lon - dlon + 180) / 360, mercY(hi), (lon + dlon + 180) / 360, mercY(lo)];
}

export type TileKey = `${number}/${number}/${number}`;

/** Tiles at zoom z that a disc touches (corners farther than the radius left out). */
export function tilesForDisc(lat: number, lon: number, radiusM: number, z: number): [number, number][] {
  const n = 2 ** z;
  const [x0, y0, x1, y1] = discBbox(lat, lon, radiusM);
  const tx0 = Math.floor(x0 * n);
  const tx1 = Math.floor(x1 * n);
  const ty0 = Math.max(0, Math.floor(y0 * n));
  const ty1 = Math.min(n - 1, Math.floor(y1 * n));
  const cx = (lon + 180) / 360;
  const cy = mercY(lat);
  const out: [number, number][] = [];
  for (let ty = ty0; ty <= ty1; ty++) {
    for (let tx = tx0; tx <= tx1; tx++) {
      const left = tx / n;
      const top = ty / n;
      const px = Math.min(Math.max(cx, left), left + 1 / n);
      const py = Math.min(Math.max(cy, top), top + 1 / n);
      const d = distanceM(lat, lon, unmercY(py), (px - 0.5) * 360);
      if (d > radiusM) continue;
      out.push([((tx % n) + n) % n, ty]);
    }
  }
  return out;
}

/** Every tile a set of observers needs for the given levels, without duplicates. */
export function planTiles(points: { lat: number; lon: number }[], levels: Level[]): TileKey[] {
  const keys = new Set<TileKey>();
  for (const p of points) {
    for (const l of levels) {
      for (const [x, y] of tilesForDisc(p.lat, p.lon, l.maxM, l.z)) keys.add(`${l.z}/${x}/${y}`);
    }
  }
  return [...keys];
}

export function tileUrl(key: TileKey, template = TERRAIN_URL): string {
  const [z, x, y] = key.split('/');
  return template.replace('{z}', z!).replace('{x}', x!).replace('{y}', y!);
}

/** Bytes to download for a set of tiles, as an estimate for a button ("about 2.6 MB"). */
export function estimateBytes(keys: TileKey[]): number {
  let total = 0;
  for (const k of keys) total += TILE_BYTES[Number(k.split('/')[0])] ?? DEFAULT_TILE_BYTES;
  return total;
}
