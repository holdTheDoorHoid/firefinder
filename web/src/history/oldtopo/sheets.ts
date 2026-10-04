/**
 * Which historical topo sheet to show where. Pure functions, unit-tested.
 *
 * The sheet index is USGS TopoView's own overlay service (the outline of every scanned sheet,
 * with its name, scale and dates); the scans are the USGS Historical Topographic Map
 * Collection's GeoTIFFs on The National Map's public storage. Both are public domain.
 */

export const INDEX_URL = 'https://energy.usgs.gov/arcgis/rest/services/topoview/ustOverlay/MapServer/0/query';
export const GEOTIFF_BASE = 'https://prd-tnm.s3.amazonaws.com/StagedProducts/Maps/HistoricalTopo/GeoTIFF/';

/** Index cells are whole degrees: one query per cell, cached. */
export const CELL_DEG = 1;

export interface Sheet {
  scanId: number;
  name: string;
  /** Scale denominator: 24000 for 1:24,000. */
  scale: number;
  /** The date printed on the map (the survey or edition year). */
  year: number;
  /** The year this copy was printed. */
  imprint: number | null;
  state: string;
  /** GeoTIFF URL. */
  url: string;
  /** Map outline (the neatline), WGS84 [lon, lat], closed or not. */
  ring: [number, number][];
  bbox: [number, number, number, number];
}

export type Era = 'oldest' | 'lookouts' | 'newest';
export const ERAS: Era[] = ['oldest', 'lookouts', 'newest'];

/** The year each era aims for: sheets closest in date are drawn on top. */
export const ERA_TARGET: Record<Era, number> = { oldest: 1850, lookouts: 1940, newest: 2010 };

export const ERA_LABEL: Record<Era, string> = {
  oldest: 'Oldest',
  lookouts: '1930s–50s',
  newest: 'Newest (to 2006)',
};

export function isEra(v: unknown): v is Era {
  return typeof v === 'string' && (ERAS as string[]).includes(v);
}

/** The overlay draws nothing below this zoom (the sheets are local maps). */
export const MIN_ZOOM = 9;

/**
 * Scales drawn at a zoom: broad sheets when zoomed out, detailed ones closer in. At 12 and
 * closer the 1:125,000 sheets stay in, because for many places they are the only old maps.
 */
export function scalesForZoom(z: number): (scale: number) => boolean {
  if (z < MIN_ZOOM) return () => false;
  if (z < 10) return (s) => s >= 100000;
  if (z < 12) return (s) => s >= 48000;
  return (s) => s <= 125000 && s !== 100000;
}

export function cellsFor(bbox: [number, number, number, number]): [number, number][] {
  const cells: [number, number][] = [];
  for (let x = Math.floor(bbox[0] / CELL_DEG); x <= Math.floor((bbox[2] - 1e-9) / CELL_DEG); x++) {
    for (let y = Math.floor(bbox[1] / CELL_DEG); y <= Math.floor((bbox[3] - 1e-9) / CELL_DEG); y++) cells.push([x, y]);
  }
  return cells;
}

/**
 * The index query for one cell: scanned historical sheets only (not the modern US Topo),
 * optionally narrowed by more SQL (a scale band).
 */
export function cellQueryUrl(x: number, y: number, offset = 0, andWhere = ''): string {
  const q = new URLSearchParams({
    geometry: `${x * CELL_DEG},${y * CELL_DEG},${(x + 1) * CELL_DEG},${(y + 1) * CELL_DEG}`,
    geometryType: 'esriGeometryEnvelope',
    inSR: '4326',
    outSR: '4326',
    spatialRel: 'esriSpatialRelIntersects',
    where: `series='HTMC'${andWhere}`,
    outFields: 'map_name,map_scale,date_on_map,imprint_year,scan_id,drg_name,primary_state',
    returnGeometry: 'true',
    geometryPrecision: '5',
    resultOffset: String(offset),
    resultRecordCount: '1000',
    f: 'json',
  });
  return `${INDEX_URL}?${q.toString()}`;
}

interface IndexFeature {
  attributes?: Record<string, unknown>;
  geometry?: { rings?: number[][][] };
}

/** GeoTIFF URL for a sheet: its file name is the PDF's, in a folder named for its state. */
export function geotiffUrl(drgName: string): string | null {
  const m = /^([A-Z]{2})_.+_geo\.pdf$/i.exec(drgName.trim());
  if (!m) return null;
  return `${GEOTIFF_BASE}${m[1]!.toUpperCase()}/${encodeURIComponent(drgName.trim().replace(/\.pdf$/i, '.tif'))}`;
}

export function parseIndex(json: unknown): Sheet[] {
  const feats = (json as { features?: IndexFeature[] })?.features;
  if (!Array.isArray(feats)) return [];
  const out: Sheet[] = [];
  for (const f of feats) {
    const a = f.attributes ?? {};
    const ring = f.geometry?.rings?.[0];
    const scale = Number(a.map_scale);
    const year = Number(a.date_on_map);
    const scanId = Number(a.scan_id);
    const url = typeof a.drg_name === 'string' ? geotiffUrl(a.drg_name) : null;
    if (!ring || ring.length < 4 || !url || !Number.isFinite(scale) || !Number.isFinite(year) || !Number.isFinite(scanId)) continue;
    const pts = ring.map((p) => [Number(p[0]), Number(p[1])] as [number, number]);
    const xs = pts.map((p) => p[0]);
    const ys = pts.map((p) => p[1]);
    out.push({
      scanId,
      name: String(a.map_name ?? 'Unnamed'),
      scale,
      year,
      imprint: Number.isFinite(Number(a.imprint_year)) && a.imprint_year !== null ? Number(a.imprint_year) : null,
      state: String(a.primary_state ?? ''),
      url,
      ring: pts,
      bbox: [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)],
    });
  }
  return out;
}

export function bboxIntersects(a: readonly number[], b: readonly number[]): boolean {
  return a[0]! < b[2]! && a[2]! > b[0]! && a[1]! < b[3]! && a[3]! > b[1]!;
}

/** Even-odd point-in-polygon test. */
export function inRing(ring: readonly (readonly [number, number])[], lon: number, lat: number): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i]!;
    const [xj, yj] = ring[j]!;
    if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/**
 * Candidate sheets for an area, best first: the date closest to the era's target year, then
 * the more detailed scale, then the earliest printing (the copy closest to its own date).
 * Reprints of one edition (same name, scale and date) count once.
 */
export function rankSheets(sheets: readonly Sheet[], era: Era, z: number, bbox: readonly number[]): Sheet[] {
  const ok = scalesForZoom(z);
  const target = ERA_TARGET[era];
  const best = new Map<string, Sheet>();
  for (const s of sheets) {
    if (!ok(s.scale) || !bboxIntersects(s.bbox, bbox)) continue;
    const key = `${s.name}|${s.scale}|${s.year}|${s.bbox.map((v) => v.toFixed(2)).join(',')}`;
    const prev = best.get(key);
    if (!prev || (s.imprint ?? 9999) < (prev.imprint ?? 9999) || ((s.imprint ?? 9999) === (prev.imprint ?? 9999) && s.scanId < prev.scanId)) best.set(key, s);
  }
  return [...best.values()].sort(
    (a, b) =>
      Math.abs(a.year - target) - Math.abs(b.year - target) ||
      (era === 'newest' ? b.year - a.year : a.year - b.year) ||
      a.scale - b.scale ||
      (a.imprint ?? 9999) - (b.imprint ?? 9999) ||
      a.scanId - b.scanId,
  );
}

/** The sheet drawn at a point: the best-ranked one whose outline contains it. */
export function sheetAt(ranked: readonly Sheet[], lon: number, lat: number): Sheet | null {
  for (const s of ranked) {
    if (lon >= s.bbox[0] && lon <= s.bbox[2] && lat >= s.bbox[1] && lat <= s.bbox[3] && inRing(s.ring, lon, lat)) return s;
  }
  return null;
}

/** "1:24,000" */
export function scaleLabel(scale: number): string {
  return `1:${new Intl.NumberFormat('en-US').format(scale)}`;
}
