/**
 * The geometry of the satellite view from the cab (satellite-view.ts): the earth's curve put
 * into the terrain MapLibre draws, where the camera goes, where a bearing and an elevation angle
 * land on the screen, the window frame, which imagery serves a tile, and how much the view
 * downloads. Pure functions, no DOM and no MapLibre, so tower pages can size the download
 * without loading the 3D code; tested in test/earth-view.test.ts.
 */
import { wrap360 } from './describe.ts';
import { EARTH_RADIUS_M, REFRACTION_K, distanceM, mercY, panoramaLevels, unmercY } from './tiles.ts';

const rad = (d: number) => (d * Math.PI) / 180;
const deg = (r: number) => (r * 180) / Math.PI;

/* ---------- The earth's curve ---------- */

/**
 * Effective earth radius with refraction folded in, R' = R / (1 − k): the same earth the drawn
 * view's engine uses (crates/firefinder-view/src/sight.rs).
 */
export const EFFECTIVE_RADIUS_M = EARTH_RADIUS_M / (1 - REFRACTION_K);

/**
 * How far the ground at this distance from the eye sits below the eye's level plane because
 * the earth curves away (less a little for refraction), m: d² / (2 R'). 4 m at 8 km, 246 m at
 * 60 km, 1.5 km at 150 km.
 */
export function curveDropM(distM: number): number {
  return (distM * distM) / (2 * EFFECTIVE_RADIUS_M);
}

/** A Terrarium-encoded height, m. */
export function decodeTerrarium(r: number, g: number, b: number): number {
  return r * 256 + g + b / 256 - 32768;
}

/** Writes a height (m) as Terrarium RGB, opaque, at byte `i`. Clamped to the encodable range. */
export function encodeTerrarium(h: number, out: Uint8ClampedArray | Uint8Array, i: number): void {
  const v = Math.min(Math.max(h + 32768, 0), 65535 + 255 / 256);
  let whole = Math.floor(v);
  let frac = Math.round((v - whole) * 256);
  if (frac === 256) {
    whole = Math.min(whole + 1, 65535);
    frac = whole === 65535 && v >= 65535 + 255 / 256 ? 255 : 0;
  }
  out[i] = whole >> 8;
  out[i + 1] = whole & 255;
  out[i + 2] = frac;
  out[i + 3] = 255;
}

/**
 * Lowers every height in a Terrarium tile (RGBA bytes, `size` × `size`, Web Mercator tile
 * z/x/y) by the curve drop at its distance from the eye. MapLibre draws terrain on a flat map;
 * after this the satellite view shows what a round earth shows: far ridges sink, and a summit the
 * drawn view hides behind a nearer ridge stays hidden. The eye's own spot drops nothing.
 *
 * It runs on the main thread for every terrain tile, so it is written for speed: the haversine
 * term `a` is split into a row part and a column part, d² is taken as (2R)²·a (asin x ≈ x; under
 * 0.01 % off at 200 km, a fifth of a metre of a 2.7 km drop), and heights are handled as whole
 * 1/256 m steps, Terrarium's own resolution, so a tile costs about a millisecond.
 */
export function dropTerrariumTile(px: Uint8ClampedArray | Uint8Array, size: number, z: number, x: number, y: number, eyeLat: number, eyeLon: number): void {
  const n = 2 ** z;
  const phi1 = rad(eyeLat);
  const cos1 = Math.cos(phi1);
  const col = new Float64Array(size);
  for (let c = 0; c < size; c++) {
    const lon = ((x + (c + 0.5) / size) / n) * 360 - 180;
    col[c] = Math.sin(rad(lon - eyeLon) / 2) ** 2;
  }
  // drop = d² / 2R' = (2R)² a / 2R', in 1/256 m steps
  const k256 = ((4 * EARTH_RADIUS_M * EARTH_RADIUS_M) / (2 * EFFECTIVE_RADIUS_M)) * 256;
  for (let r = 0; r < size; r++) {
    const phi2 = rad(unmercY((y + (r + 0.5) / size) / n));
    const a0 = Math.sin((phi2 - phi1) / 2) ** 2;
    const k = cos1 * Math.cos(phi2);
    let i = r * size * 4;
    for (let c = 0; c < size; c++, i += 4) {
      const v = px[i]! * 65536 + px[i + 1]! * 256 + px[i + 2]! - Math.round((a0 + k * col[c]!) * k256);
      const w = v < 0 ? 0 : v;
      px[i] = w >>> 16;
      px[i + 1] = (w >>> 8) & 255;
      px[i + 2] = w & 255;
    }
  }
}

/* ---------- Bearings on the flat map ---------- */

/**
 * The bearing of a point as the satellite view draws it: straight across the Web Mercator map,
 * as MapLibre aims its camera. At the eye this is the true bearing; toward far points it drifts
 * from the great-circle bearing the drawn view uses by about half the longitude difference times
 * the sine of the latitude (0.3° for a peak 60 km due east at 49° N).
 */
export function mercatorBearing(lat1: number, lon1: number, lat2: number, lon2: number): number {
  let dx = (lon2 - lon1) / 360;
  dx -= Math.round(dx);
  const dy = mercY(lat2) - mercY(lat1);
  return wrap360(deg(Math.atan2(dx, -dy)));
}

/* ---------- The camera in the cab ---------- */

export interface CabCamera {
  /** Bearing the view faces, degrees. */
  bearing: number;
  /** Elevation angle of the view's centre, degrees (0 level, negative looking down). */
  tilt: number;
  /** Vertical field of view, degrees. */
  fov: number;
  width: number;
  height: number;
}

/** Focal length in CSS px. */
export function focalPx(cam: CabCamera): number {
  return cam.height / 2 / Math.tan(rad(cam.fov) / 2);
}

/**
 * A direction or a point relative to the eye (metres east, north and up) in the camera's own
 * axes: [right, up, forward]. MapLibre's camera has no roll, so this is a turn by the bearing
 * and a tilt about the right-hand axis.
 */
export function cameraSpace(east: number, north: number, up: number, cam: CabCamera): [number, number, number] {
  const b = rad(cam.bearing);
  const t = rad(cam.tilt);
  const ahead = east * Math.sin(b) + north * Math.cos(b);
  const right = east * Math.cos(b) - north * Math.sin(b);
  return [right, -ahead * Math.sin(t) + up * Math.cos(t), ahead * Math.cos(t) + up * Math.sin(t)];
}

/** Screen position of a camera-space point (in front of the eye). */
export function toScreen(p: [number, number, number], cam: CabCamera): { x: number; y: number } {
  const f = focalPx(cam);
  return { x: cam.width / 2 + (p[0] / p[2]) * f, y: cam.height / 2 - (p[1] / p[2]) * f };
}

/**
 * Where a bearing and an elevation angle (degrees) land on the screen of a pinhole camera that
 * matches MapLibre's: no roll, the vertical field of view across the full height, the centre of
 * the view in the middle. Null when the direction is behind the eye.
 */
export function project(az: number, elev: number, cam: CabCamera): { x: number; y: number } | null {
  const a = rad(az);
  const e = rad(elev);
  const p = cameraSpace(Math.sin(a) * Math.cos(e), Math.cos(a) * Math.cos(e), Math.sin(e), cam);
  if (p[2] <= 1e-6) return null;
  return toScreen(p, cam);
}

/** The bearing and elevation angle (degrees) seen at a screen point: the inverse of `project`. */
export function unproject(x: number, y: number, cam: CabCamera): { az: number; elev: number } {
  const f = focalPx(cam);
  const r = x - cam.width / 2;
  const u = cam.height / 2 - y;
  const t = rad(cam.tilt);
  // Camera axes back to level ones: ahead (horizontal, along the bearing), right, up.
  const ahead = f * Math.cos(t) - u * Math.sin(t);
  const up = f * Math.sin(t) + u * Math.cos(t);
  return { az: wrap360(cam.bearing + deg(Math.atan2(r, ahead))), elev: deg(Math.atan2(up, Math.hypot(r, ahead))) };
}

/** The bearing on the eye's level at screen column x (the inverse of `project` at elevation 0). */
export function azimuthAtX(x: number, cam: CabCamera): number {
  return wrap360(cam.bearing + deg(Math.atan(((x - cam.width / 2) * Math.cos(rad(cam.tilt))) / focalPx(cam))));
}

/** Horizontal field of view across the eye's level, degrees. */
export function horizontalFov(cam: CabCamera): number {
  return 2 * deg(Math.atan((cam.width / 2 / focalPx(cam)) * Math.cos(rad(cam.tilt))));
}

/** Degrees per CSS px at the centre of the view (for dragging). */
export function degPerPx(cam: CabCamera): number {
  return cam.fov / cam.height;
}

/** The camera never looks exactly level: MapLibre's pitch of exactly 90° degenerates. */
export function safeTilt(tilt: number): number {
  return Math.abs(tilt) < 0.01 ? (tilt < 0 ? -0.01 : 0.01) : tilt;
}

/**
 * How far along the line of sight to put MapLibre's map centre, m. MapLibre clips everything
 * nearer than its near plane, height/50 px from the camera, which is distance × tan(fov/2) / 25
 * m: with a centre 20 km out that is ~200 m, and the summit under the cab is cut away. Here the
 * near plane stays within a third of the eye's height above the ground (so the ground at the
 * foot of the tower is drawn) and the centre within 400 m.
 */
export function targetDistanceM(eyeAboveGroundM: number, fovDeg: number): number {
  const fromNear = ((Math.max(eyeAboveGroundM, 1.5) / 3) * 25) / Math.tan(rad(fovDeg) / 2);
  return Math.min(Math.max(fromNear, 40), 400);
}

/** MapLibre's near plane for a centre at this distance, m (see `targetDistanceM`). */
export function nearPlaneM(targetM: number, fovDeg: number): number {
  return (targetM * Math.tan(rad(fovDeg) / 2)) / 25;
}

/**
 * The tile zoom MapLibre should load for a tile in the satellite view (its `calculateTileZoom`
 * hook; distances in Web Mercator units, `metresPerUnit` at the view's latitude). MapLibre's own
 * rule thins tiles out by the camera's pitch measured against the map centre's height; with the
 * centre at eye level, a few hundred metres ahead, that leaves the whole view blurred. Here a
 * tile gets about one photo pixel per screen pixel at its distance (`bias` 0; −1 is half as
 * sharp, a quarter of the tiles), a little less beyond 15 km, where the haze takes over.
 */
export function tileZoomFor(centerZoom: number, dist2D: number, distZ: number, distCenter3D: number, metresPerUnit: number, bias: number): number {
  const d = Math.max(Math.hypot(dist2D, distZ), 1e-12);
  return centerZoom + Math.log2(distCenter3D / d) + bias - 0.5 * Math.max(0, Math.log2((d * metresPerUnit) / 15_000));
}

/**
 * The terrain zoom for a tile this far from the eye, m: the drawn view's own levels (zoom 12 to
 * 4 km, 10 to 40 km, 9 to 100 km, 8 beyond; phones skip 9), so the satellite view reuses the
 * tiles the drawn view already downloaded (the browser keeps them), plus zoom 13 for the
 * summit under the cab. Its silhouettes then come from the same heights the names were worked
 * out from, and each name sits on its peak.
 */
export function demZoomFor(distM: number, light: boolean): number {
  if (distM <= 1_500) return 13;
  for (const l of panoramaLevels(150_000, light ? 'light' : 'full')) if (distM <= l.maxM) return l.z;
  return 8;
}

/** Metres in one normalised Web Mercator unit at a latitude (the world's width there). */
export function metresPerMercatorUnit(lat: number): number {
  return 2 * Math.PI * EARTH_RADIUS_M * Math.cos(rad(lat));
}

export interface GeoPoint {
  lat: number;
  lon: number;
  /** Metres above sea level. */
  altM: number;
}

/** Metres to normalised Web Mercator units at a latitude (MapLibre's earth radius is the same). */
function mercPerMetre(lat: number): number {
  return 1 / metresPerMercatorUnit(lat);
}

/**
 * The point `distM` along the line of sight from `from` (bearing and elevation angle, degrees),
 * laid out on the Web Mercator map as MapLibre measures it. Handing `from` and this point to
 * `map.calculateCameraOptionsFromTo` puts the camera exactly at `from`, facing exactly
 * `bearing`, `tilt`: the target's height is scaled for MapLibre's latitude-dependent
 * metres-per-unit, a correction of well under a metre.
 */
export function lookTarget(from: GeoPoint, bearing: number, tilt: number, distM: number): GeoPoint {
  const b = rad(bearing);
  const t = rad(tilt);
  const u = mercPerMetre(from.lat);
  const h = distM * Math.cos(t) * u;
  const mx = (from.lon + 180) / 360 + Math.sin(b) * h;
  const my = mercY(from.lat) - Math.cos(b) * h;
  const lat = unmercY(my);
  const lon = ((((mx * 360) % 360) + 360) % 360) - 180;
  const altM = (from.altM + distM * Math.sin(t)) * (Math.cos(rad(lat)) / Math.cos(rad(from.lat)));
  return { lat, lon, altM };
}

/**
 * Where the camera hangs when you step outside: `distM` from a point on the ground, `pitch`
 * degrees from straight down, looking along `bearing` at it.
 */
export function orbitEye(center: GeoPoint, bearing: number, pitch: number, distM: number): GeoPoint {
  const back = lookTarget({ ...center }, wrap360(bearing + 180), 0, distM * Math.sin(rad(pitch)));
  return { lat: back.lat, lon: back.lon, altM: center.altM + distM * Math.cos(rad(pitch)) };
}

/* ---------- The cab's window frame ---------- */

export type FramePart = 'post' | 'sill' | 'wall';

export interface FrameQuad {
  part: FramePart;
  /** Corners, metres east, north and up from the eye. */
  pts: [number, number, number][];
}

/**
 * A typical cab to look out of: the Forest Service's L-4, a room 14 ft (4.27 m) square, walls
 * facing north, east, south and west, windows from 0.95 m above the floor to the roof, each wall
 * in three sashes. The eye stands in the middle, 1.6 m above the floor. Posts run up past the top
 * of any view; the roof is left off so it does not cover the names.
 */
export function cabFrame(eyeAboveFloorM = 1.6): FrameQuad[] {
  const half = 4.27 / 2;
  const sill = 0.95 - eyeAboveFloorM;
  const floor = -eyeAboveFloorM - 0.3;
  const top = 6;
  const out: FrameQuad[] = [];
  // Each wall in its own axes: `a` along it (left to right as seen from inside), `half` out.
  for (const wall of [0, 90, 180, 270]) {
    const b = rad(wall);
    const out_ = [Math.sin(b), Math.cos(b)];
    const along = [Math.cos(b), -Math.sin(b)];
    const at = (a: number, d: number, u: number): [number, number, number] => [out_[0]! * d + along[0]! * a, out_[1]! * d + along[1]! * a, u];
    out.push({ part: 'wall', pts: [at(-half, half, floor), at(half, half, floor), at(half, half, sill), at(-half, half, sill)] });
    out.push({ part: 'sill', pts: [at(-half, half - 0.12, sill), at(half, half - 0.12, sill), at(half, half, sill + 0.035), at(-half, half, sill + 0.035)] });
    for (const a of [-half / 3, half / 3]) {
      const w = 0.045;
      out.push({ part: 'post', pts: [at(a - w, half, sill), at(a + w, half, sill), at(a + w, half, top), at(a - w, half, top)] });
    }
    // The corner post on this wall's right-hand end (the next wall's left).
    const w = 0.07;
    out.push({ part: 'post', pts: [at(half - w, half, sill), at(half + 0.01, half, sill), at(half + 0.01, half, top), at(half - w, half, top)] });
  }
  return out;
}

/**
 * Clips a polygon in camera space to the part in front of the near plane (Sutherland–Hodgman
 * against z = near), so a post beside or behind the eye draws correctly.
 */
export function clipNear(poly: [number, number, number][], near = 0.05): [number, number, number][] {
  const out: [number, number, number][] = [];
  for (let i = 0; i < poly.length; i++) {
    const a = poly[i]!;
    const b = poly[(i + 1) % poly.length]!;
    const ina = a[2] >= near;
    const inb = b[2] >= near;
    if (ina) out.push(a);
    if (ina !== inb) {
      const t = (near - a[2]) / (b[2] - a[2]);
      out.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, near]);
    }
  }
  return out;
}

/* ---------- Choosing the mode ---------- */

export type CabMode = 'satellite' | 'drawn';

/**
 * Which view opens: Satellite wherever it is offered and the device can draw it, unless the
 * visitor last chose Drawn. `unavailable` says the satellite view was offered but this device
 * cannot show it (the page says so).
 */
export function chooseMode(o: { offered: boolean; capable: boolean; stored: string | null | undefined }): { mode: CabMode; unavailable: boolean } {
  if (!o.offered) return { mode: 'drawn', unavailable: false };
  if (!o.capable) return { mode: 'drawn', unavailable: true };
  return { mode: o.stored === 'drawn' ? 'drawn' : 'satellite', unavailable: false };
}

/* ---------- Imagery ---------- */

/**
 * USGS The National Map, "USGS Imagery Only": public domain; mostly NAIP aerial photos (about 1 m)
 * in the lower 48, other imagery in Hawaii; Landsat and Blue Marble when zoomed far out. Tiles to
 * zoom 16. Outside the United States it answers with white tiles (zooms 9–12), black ones (13)
 * and 404s (14 and finer), so it cannot simply sit on top of another source.
 */
export const USGS_IMAGERY_URL = 'https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}';
export const USGS_MAX_ZOOM = 16;

/**
 * EOX Sentinel-2 cloudless 2024 (CC BY-NC-SA 4.0), about 10 m, worldwide. The service answers
 * any zoom, but past 14 it only enlarges the zoom-14 tiles, so those are fetched and enlarged here.
 */
export const EOX_IMAGERY_URL = 'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2024_3857/default/g/{z}/{y}/{x}.jpg';
export const EOX_MAX_ZOOM = 14;

/** The credits the view shows, by source (EOX's wording is theirs, required by the licence). */
export const IMAGERY_CREDITS = {
  usgs: { text: 'Imagery: U.S. Geological Survey, The National Map', href: 'https://www.usgs.gov/programs/national-geospatial-program/national-map' },
  eox: { text: 'EOxCloudless https://cloudless.eox.at by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2024)', href: 'https://cloudless.eox.at' },
} as const;

export type ImagerySource = 'usgs' | 'eox';

/**
 * Where the USGS photos are worth asking for: the lower 48 (with the border strip and the
 * Northwest Angle) and Hawaii, as west, south, east, north. Alaska and Canada are EOX's (the
 * owner's choice: USGS shows Alaska only as 10 m SPOT imagery it may not pass on).
 */
export const USGS_COVERAGE: [number, number, number, number][] = [
  [-125.0, 24.3, -66.8, 49.45],
  [-160.5, 18.8, -154.6, 22.4],
];

/** A Web Mercator tile's bounds: west, south, east, north. */
export function tileBounds(z: number, x: number, y: number): [number, number, number, number] {
  const n = 2 ** z;
  return [(x / n) * 360 - 180, unmercY((y + 1) / n), ((x + 1) / n) * 360 - 180, unmercY(y / n)];
}

/** Distance from a point to the nearest part of a tile, m (0 inside it). */
export function tileDistanceM(z: number, x: number, y: number, lat: number, lon: number): number {
  const [w, s, e, n] = tileBounds(z, x, y);
  return distanceM(lat, lon, Math.min(Math.max(lat, s), n), Math.min(Math.max(lon, w), e));
}

/** West, south, east, north of the square around a disc (a source's `bounds`). */
export function discBounds(lat: number, lon: number, radiusM: number): [number, number, number, number] {
  const dlat = deg(radiusM / EARTH_RADIUS_M);
  const s = Math.max(lat - dlat, -85);
  const n = Math.min(lat + dlat, 85);
  const dlon = Math.min(dlat / Math.max(Math.cos(rad(Math.max(Math.abs(s), Math.abs(n)))), 0.01), 180);
  return [Math.max(lon - dlon, -180), s, Math.min(lon + dlon, 180), n];
}

/** Which source to try first for a tile: USGS where it may have photos, EOX everywhere else. */
export function firstImagery(z: number, x: number, y: number): ImagerySource {
  const [w, s, e, n] = tileBounds(z, x, y);
  return USGS_COVERAGE.some(([cw, cs, ce, cn]) => w < ce && e > cw && s < cn && n > cs) ? 'usgs' : 'eox';
}

/**
 * The EOX tile that serves tile z/x/y, and the square of it to use (px of its 256): the tile
 * itself up to zoom 14, a corner of its zoom-14 ancestor beyond.
 */
export function eoxTileFor(z: number, x: number, y: number): { z: number; x: number; y: number; sx: number; sy: number; size: number } {
  if (z <= EOX_MAX_ZOOM) return { z, x, y, sx: 0, sy: 0, size: 256 };
  const k = z - EOX_MAX_ZOOM;
  const f = 2 ** k;
  const size = 256 / f;
  return { z: EOX_MAX_ZOOM, x: x >> k, y: y >> k, sx: (x % f) * size, sy: (y % f) * size, size };
}

/** USGS's fill outside its coverage: flat white (zooms 9–12) or flat black (13). */
export function isFillPixel(r: number, g: number, b: number): boolean {
  return (r >= 250 && g >= 250 && b >= 250) || (r <= 3 && g <= 3 && b <= 3);
}

/**
 * Share of a tile's pixels that are USGS fill, from every `step`th pixel (every one by default;
 * the photo protocol samples every third, enough to tell a fill tile from a photo).
 */
export function fillFraction(px: Uint8ClampedArray | Uint8Array, step = 1): number {
  let fill = 0;
  let seen = 0;
  for (let i = 0; i < px.length; i += 4 * step) {
    seen++;
    if (isFillPixel(px[i]!, px[i + 1]!, px[i + 2]!)) fill++;
  }
  return seen ? fill / seen : 1;
}

/**
 * What to do with a USGS tile: use it, replace it with EOX (nearly all fill: outside the US), or
 * lay it over EOX with its fill made clear (it straddles the border or a coast).
 */
export function usgsVerdict(fill: number): 'usgs' | 'eox' | 'blend' {
  if (fill >= 0.985) return 'eox';
  if (fill <= 0.01) return 'usgs';
  return 'blend';
}

/* ---------- How much it downloads ---------- */

/**
 * What the satellite view downloads beyond the drawn view's terrain (whose tiles it reuses),
 * measured in the browser in October 2026 at Desolation Peak, Washington (high mountains, the
 * dearest case: terrain tiles there run to 100 KB) with a 750 px view on a computer and a 343 px
 * one on a phone: photo and terrain tiles for the first look, and for turning once all the way
 * round; plus the 3D map code (MapLibre GL and its worker, about 0.45 MB compressed), which
 * tower pages load only for this view. A flat eastern view (Hays Lot, Pennsylvania) took about 2 MB to start.
 * DESIGN.md 4.1, "Satellite mode", has the figures.
 */
export const SATELLITE_BYTES = {
  start: { full: 2_900_000, light: 2_600_000 },
  around: { full: 9_600_000, light: 9_200_000 },
  code: 450_000,
} as const;

/** About how much the satellite view downloads to start, and in all after a full turn. */
export function satelliteDownload(light: boolean): { start: number; around: number } {
  const k = light ? 'light' : 'full';
  return { start: SATELLITE_BYTES.start[k] + SATELLITE_BYTES.code, around: SATELLITE_BYTES.around[k] + SATELLITE_BYTES.code };
}
