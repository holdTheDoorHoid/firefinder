/**
 * Map projections for the USGS historical topo sheets (pure math, unit-tested).
 *
 * The Historical Topographic Map Collection's GeoTIFFs keep each sheet in its own projection:
 * a transverse Mercator or polyconic projection centred on the sheet, on the North American
 * Datum of 1927 (Clarke 1866 ellipsoid), or NAD83/WGS84 for late editions, occasionally UTM.
 * To lay a sheet on the web map we go the other way for every screen pixel: WGS84 lon/lat ->
 * the sheet's datum (Molodensky shift, accurate to a few metres in the lower 48, well inside
 * the accuracy of the maps themselves) -> projected metres -> sheet pixel.
 *
 * Formulas: J. P. Snyder, "Map Projections: A Working Manual", USGS Professional Paper 1395
 * (1987): transverse Mercator (8-9, 8-10), polyconic (18-14, 18-15), and the standard
 * Molodensky datum transformation (DMA TR 8350.2).
 */

const RAD = Math.PI / 180;

export interface Ellipsoid {
  /** Semi-major axis, metres. */
  a: number;
  /** Flattening. */
  f: number;
}

export const WGS84: Ellipsoid = { a: 6378137, f: 1 / 298.257223563 };
export const CLARKE1866: Ellipsoid = { a: 6378206.4, f: 1 / 294.9786982138982 };

/** Shift from WGS84 to a datum, metres (the negated "to WGS84" parameters). */
export interface DatumShift {
  ellipsoid: Ellipsoid;
  dx: number;
  dy: number;
  dz: number;
}

/** NAD27 mean parameters (NIMA TR8350.2): CONUS, and Alaska. */
export const NAD27_CONUS: DatumShift = { ellipsoid: CLARKE1866, dx: 8, dy: -160, dz: -176 };
export const NAD27_ALASKA: DatumShift = { ellipsoid: CLARKE1866, dx: 5, dy: -135, dz: -172 };

/** WGS84 lon/lat (degrees) to another datum's lon/lat, by the standard Molodensky formulas. */
export function molodensky(lon: number, lat: number, to: DatumShift): [number, number] {
  const { a, f } = WGS84;
  const e2 = 2 * f - f * f;
  const da = to.ellipsoid.a - a;
  const df = to.ellipsoid.f - f;
  const phi = lat * RAD;
  const lam = lon * RAD;
  const sp = Math.sin(phi);
  const cp = Math.cos(phi);
  const sl = Math.sin(lam);
  const cl = Math.cos(lam);
  const w = Math.sqrt(1 - e2 * sp * sp);
  const N = a / w;
  const M = (a * (1 - e2)) / (w * w * w);
  const b = a * (1 - f);
  const dPhi =
    (-to.dx * sp * cl - to.dy * sp * sl + to.dz * cp + (da * N * e2 * sp * cp) / a + df * ((M * a) / b + (N * b) / a) * sp * cp) / M;
  const dLam = (-to.dx * sl + to.dy * cl) / (N * cp);
  return [lon + dLam / RAD, lat + dPhi / RAD];
}

/** Meridian distance from the equator, metres. */
export function meridianDistance(phi: number, e: Ellipsoid): number {
  const e2 = 2 * e.f - e.f * e.f;
  const e4 = e2 * e2;
  const e6 = e4 * e2;
  return (
    e.a *
    ((1 - e2 / 4 - (3 * e4) / 64 - (5 * e6) / 256) * phi -
      ((3 * e2) / 8 + (3 * e4) / 32 + (45 * e6) / 1024) * Math.sin(2 * phi) +
      ((15 * e4) / 256 + (45 * e6) / 1024) * Math.sin(4 * phi) -
      ((35 * e6) / 3072) * Math.sin(6 * phi))
  );
}

export interface Projection {
  kind: 'tm' | 'polyconic';
  ellipsoid: Ellipsoid;
  /** Central meridian and latitude of origin, degrees. */
  lon0: number;
  lat0: number;
  k0: number;
  falseEasting: number;
  falseNorthing: number;
}

/** Projects lon/lat (degrees, already on the projection's datum) to metres. */
export function project(p: Projection, lon: number, lat: number): [number, number] {
  const e = p.ellipsoid;
  const e2 = 2 * e.f - e.f * e.f;
  const phi = lat * RAD;
  const dLam = (lon - p.lon0) * RAD;
  const M0 = meridianDistance(p.lat0 * RAD, e);
  const sp = Math.sin(phi);
  const N = e.a / Math.sqrt(1 - e2 * sp * sp);
  if (p.kind === 'polyconic') {
    if (Math.abs(phi) < 1e-12) return [p.falseEasting + e.a * dLam, p.falseNorthing - M0];
    const E = dLam * sp;
    const cot = 1 / Math.tan(phi);
    return [p.falseEasting + N * cot * Math.sin(E), p.falseNorthing + meridianDistance(phi, e) - M0 + N * cot * (1 - Math.cos(E))];
  }
  const ep2 = e2 / (1 - e2);
  const cp = Math.cos(phi);
  const T = Math.tan(phi) ** 2;
  const C = ep2 * cp * cp;
  const A = dLam * cp;
  const M = meridianDistance(phi, e);
  const x = p.k0 * N * (A + ((1 - T + C) * A ** 3) / 6 + ((5 - 18 * T + T * T + 72 * C - 58 * ep2) * A ** 5) / 120);
  const y =
    p.k0 *
    (M - M0 + N * Math.tan(phi) * ((A * A) / 2 + ((5 - T + 9 * C + 4 * C * C) * A ** 4) / 24 + ((61 - 58 * T + T * T + 600 * C - 330 * ep2) * A ** 6) / 720));
  return [p.falseEasting + x, p.falseNorthing + y];
}

/* ---------- From GeoTIFF keys ---------- */

export type GeoKeys = Record<number, number | number[] | string>;

const num = (v: GeoKeys[number] | undefined): number | undefined => (typeof v === 'number' ? v : Array.isArray(v) ? v[0] : undefined);

/** Linear units to metres (GeoTIFF ProjLinearUnitsGeoKey). */
const UNIT_METRES: Record<number, number> = { 9001: 1, 9002: 0.3048, 9003: 1200 / 3937 };

export interface SheetGeoref {
  projection: Projection;
  /** Datum shift from WGS84, or null when the sheet is already on WGS84/NAD83. */
  shift: DatumShift | null;
  /** Projected metres per linear unit of the raster's coordinates. */
  unit: number;
}

/**
 * The sheet's projection and datum from its GeoTIFF keys, or a reason it cannot be used. Handles
 * what the collection contains: user-defined transverse Mercator (3075 = 1) and polyconic (22)
 * on NAD27, NAD83 or WGS84, and EPSG UTM codes (NAD27 267zz, NAD83 269zz, WGS84 326zz).
 */
export function georefFromKeys(keys: GeoKeys, approxLon: number, approxLat: number): SheetGeoref | { unsupported: string } {
  if (num(keys[1024]) !== 1) return { unsupported: 'not a projected map' };
  const unit = UNIT_METRES[num(keys[3076]) ?? 9001];
  if (unit === undefined) return { unsupported: `linear unit ${keys[3076]}` };
  const pcs = num(keys[3072]);
  const gcs = num(keys[2048]);
  let datum: 'nad27' | 'wgs84' | null = null;
  let projection: Projection | null = null;

  const utm = pcs !== undefined && pcs !== 32767 ? /^(267|269|326)(\d\d)$/.exec(String(pcs)) : null;
  if (utm) {
    datum = utm[1] === '267' ? 'nad27' : 'wgs84';
    const zone = Number(utm[2]);
    projection = {
      kind: 'tm',
      ellipsoid: datum === 'nad27' ? CLARKE1866 : WGS84,
      lon0: -183 + 6 * zone,
      lat0: 0,
      k0: 0.9996,
      falseEasting: 500000,
      falseNorthing: 0,
    };
  } else if (pcs === 32767 || pcs === undefined) {
    if (gcs === 4267) datum = 'nad27';
    else if (gcs === 4269 || gcs === 4326 || gcs === 4152) datum = 'wgs84';
    else if (gcs === undefined || gcs === 32767) {
      const a = num(keys[2057]);
      if (a !== undefined && Math.abs(a - 6378206.4) < 0.5) datum = 'nad27';
      else if (a !== undefined && Math.abs(a - 6378137) < 0.5) datum = 'wgs84';
    }
    if (!datum) return { unsupported: `datum ${gcs ?? keys[2049] ?? 'unknown'}` };
    const trans = num(keys[3075]);
    const kind = trans === 1 ? 'tm' : trans === 22 ? 'polyconic' : null;
    if (!kind) return { unsupported: `projection method ${trans ?? 'unknown'}` };
    const lon0 = num(keys[3080]) ?? num(keys[3088]);
    if (lon0 === undefined) return { unsupported: 'no central meridian' };
    projection = {
      kind,
      ellipsoid: datum === 'nad27' ? CLARKE1866 : WGS84,
      lon0,
      lat0: num(keys[3081]) ?? num(keys[3089]) ?? 0,
      k0: num(keys[3092]) ?? 1,
      falseEasting: (num(keys[3082]) ?? 0) * unit,
      falseNorthing: (num(keys[3083]) ?? 0) * unit,
    };
  } else {
    return { unsupported: `coordinate system EPSG:${pcs}` };
  }
  const alaska = approxLat > 51 && approxLon < -129;
  return { projection, shift: datum === 'nad27' ? (alaska ? NAD27_ALASKA : NAD27_CONUS) : null, unit };
}

/** WGS84 lon/lat to the sheet's projected metres. */
export function toSheetMetres(g: SheetGeoref, lon: number, lat: number): [number, number] {
  const [l, p] = g.shift ? molodensky(lon, lat, g.shift) : [lon, lat];
  return project(g.projection, l, p);
}

/* ---------- Web Mercator tiles ---------- */

export function tileLon(x: number, z: number): number {
  return (x / 2 ** z) * 360 - 180;
}

export function tileLat(y: number, z: number): number {
  const n = Math.PI - (2 * Math.PI * y) / 2 ** z;
  return Math.atan(Math.sinh(n)) / RAD;
}

/** Ground metres per pixel of a 256 px tile at this zoom and latitude. */
export function metresPerPixel(z: number, lat: number): number {
  return (40075016.686 * Math.cos(lat * RAD)) / (256 * 2 ** z);
}
