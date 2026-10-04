/// <reference lib="webworker" />
/**
 * Old topo maps worker: draws Web Mercator map tiles from the USGS historical topo sheets.
 *
 * For each requested tile it finds the sheets that cover it (TopoView's sheet index, one query
 * per degree cell, cached), ranks them for the chosen era, and, pixel by pixel, takes the
 * best-ranked sheet whose outline contains that point. It then reads just the parts of those
 * sheets' cloud-optimised GeoTIFFs it needs (HTTP range requests for a few JPEG tiles of the
 * right overview), reprojects them (see proj.ts) and returns an ImageBitmap.
 *
 * Messages in:  {type:'tile', id, z, x, y, era} | {type:'abort', id} | {type:'inview', id, bbox, zoom, era}
 * Messages out: {type:'tile', id, bitmap|null, error?} | {type:'inview', id, sheets, failed}
 */
import { georefFromKeys, metresPerPixel, tileLat, tileLon, toSheetMetres, type SheetGeoref } from './proj.ts';
import { cellsFor, cellQueryUrl, MIN_ZOOM, rankSheets, sheetAt, isEra, parseIndex, type Era, type Sheet } from './sheets.ts';
import { jpegForTile, NeedMoreBytes, parseTiffHeader, type TiffHeader } from './tiff.ts';

declare const self: DedicatedWorkerGlobalScope;

const SIZE = 256;

/* ---------- Fetching, politely ---------- */

const MAX_PARALLEL = 6;
let active = 0;
const queue: (() => void)[] = [];
async function limited<T>(fn: () => Promise<T>): Promise<T> {
  if (active >= MAX_PARALLEL) await new Promise<void>((r) => queue.push(r));
  active++;
  try {
    return await fn();
  } finally {
    active--;
    queue.shift()?.();
  }
}

async function fetchRange(url: string, start: number, end: number): Promise<ArrayBuffer> {
  return limited(async () => {
    const res = await fetch(url, { headers: { Range: `bytes=${start}-${end}` }, credentials: 'omit' });
    if (res.status !== 206 && res.status !== 200) throw new Error(`HTTP ${res.status}`);
    const buf = await res.arrayBuffer();
    // A server that ignores Range sends the whole file: cut out the part asked for.
    return res.status === 200 ? buf.slice(start, end + 1) : buf;
  });
}

/* ---------- The sheet index ---------- */

/** Two scale bands so zoomed-out views do not download every detailed sheet's outline. */
function bandFor(z: number): 'broad' | 'detail' {
  return z < 12 ? 'broad' : 'detail';
}
const BAND_WHERE = { broad: ' AND map_scale>=48000', detail: ' AND map_scale<=125000 AND map_scale<>100000' };

const cells = new Map<string, Promise<Sheet[]>>();
let indexFailures = 0;

function loadCell(x: number, y: number, band: 'broad' | 'detail'): Promise<Sheet[]> {
  const key = `${band}:${x}:${y}`;
  let p = cells.get(key);
  if (!p) {
    p = (async () => {
      const out: Sheet[] = [];
      for (let page = 0; page < 6; page++) {
        const url = cellQueryUrl(x, y, page * 1000, BAND_WHERE[band]);
        const json = await limited(async () => {
          const res = await fetch(url, { credentials: 'omit' });
          if (!res.ok) throw new Error(`sheet index HTTP ${res.status}`);
          return res.json();
        });
        if (json?.error) throw new Error(`sheet index: ${json.error.message ?? 'error'}`);
        out.push(...parseIndex(json));
        if (!json.exceededTransferLimit) break;
      }
      return out;
    })();
    cells.set(key, p);
    p.catch(() => {
      cells.delete(key); // try again next time
      indexFailures++;
    });
  }
  return p;
}

async function sheetsIn(bbox: [number, number, number, number], z: number): Promise<Sheet[]> {
  const band = bandFor(z);
  const lists = await Promise.all(cellsFor(bbox).map(([x, y]) => loadCell(x, y, band)));
  const seen = new Set<number>();
  return lists.flat().filter((s) => !seen.has(s.scanId) && (seen.add(s.scanId), true));
}

/* ---------- Sheet headers ---------- */

interface Prepared {
  header: TiffHeader;
  geo: SheetGeoref;
}

const prepared = new Map<string, Promise<Prepared | null>>();
const unusable = new Set<string>();
let sheetFailures = 0;

function prepare(sheet: Sheet): Promise<Prepared | null> {
  let p = prepared.get(sheet.url);
  if (!p) {
    p = (async () => {
      let bytes = 65536;
      for (let tries = 0; tries < 4; tries++) {
        const buf = await fetchRange(sheet.url, 0, bytes - 1);
        try {
          const header = parseTiffHeader(buf);
          const cx = (sheet.bbox[0] + sheet.bbox[2]) / 2;
          const cy = (sheet.bbox[1] + sheet.bbox[3]) / 2;
          const geo = georefFromKeys(header.geoKeys, cx, cy);
          if ('unsupported' in geo || header.tiepoint.length < 6 || header.pixelScale.length < 2) return null;
          if (header.images.some((im) => im.compression !== 7)) return null;
          return { header, geo };
        } catch (err) {
          if (err instanceof NeedMoreBytes && buf.byteLength >= bytes) {
            bytes = Math.min(err.bytes, 4 << 20);
            continue;
          }
          return null;
        }
      }
      return null;
    })().catch(() => {
      prepared.delete(sheet.url);
      sheetFailures++;
      return null;
    });
    prepared.set(sheet.url, p);
    void p.then((v) => {
      if (v === null) unusable.add(sheet.url);
    });
  }
  return p;
}

/* ---------- Decoded GeoTIFF tiles (LRU by bytes) ---------- */

interface Pixels {
  w: number;
  h: number;
  data: Uint8ClampedArray;
}

const tiles = new Map<string, Promise<Pixels | null>>();
const sizes = new Map<string, number>();
let cacheBytes = 0;
const CACHE_MAX = 96 << 20;

function remember(key: string, bytes: number): void {
  sizes.set(key, bytes);
  cacheBytes += bytes;
  for (const [k, b] of sizes) {
    if (cacheBytes <= CACHE_MAX) break;
    sizes.delete(k);
    tiles.delete(k);
    cacheBytes -= b;
  }
}

let canvas: OffscreenCanvas | null = null;
async function decodeJpeg(bytes: Uint8Array): Promise<Pixels> {
  const bmp = await createImageBitmap(new Blob([bytes as BlobPart], { type: 'image/jpeg' }));
  if (!canvas || canvas.width < bmp.width || canvas.height < bmp.height) canvas = new OffscreenCanvas(Math.max(bmp.width, 512), Math.max(bmp.height, 512));
  const ctx = canvas.getContext('2d', { willReadFrequently: true })!;
  ctx.clearRect(0, 0, bmp.width, bmp.height);
  ctx.drawImage(bmp, 0, 0);
  const img = ctx.getImageData(0, 0, bmp.width, bmp.height);
  bmp.close();
  return { w: img.width, h: img.height, data: img.data };
}

/** Fetches and decodes several tiles of one image, merging requests for neighbouring bytes. */
function loadTiles(sheet: Sheet, prep: Prepared, level: number, indices: number[]): void {
  const im = prep.header.images[level]!;
  const want = indices
    .filter((i) => !tiles.has(`${sheet.url}|${level}|${i}`) && im.tileByteCounts[i]! > 0)
    .sort((a, b) => im.tileOffsets[a]! - im.tileOffsets[b]!);
  // Group tiles whose bytes are close together into one range request.
  const groups: number[][] = [];
  for (const i of want) {
    const g = groups.at(-1);
    const last = g?.at(-1);
    if (g && last !== undefined && im.tileOffsets[i]! - (im.tileOffsets[last]! + im.tileByteCounts[last]!) < 16384 && g.length < 8) g.push(i);
    else groups.push([i]);
  }
  for (const g of groups) {
    const start = im.tileOffsets[g[0]!]!;
    const end = Math.max(...g.map((i) => im.tileOffsets[i]! + im.tileByteCounts[i]!)) - 1;
    const bytes = fetchRange(sheet.url, start, end);
    for (const i of g) {
      const key = `${sheet.url}|${level}|${i}`;
      const p = bytes
        .then((buf) => decodeJpeg(jpegForTile(im.jpegTables, new Uint8Array(buf, im.tileOffsets[i]! - start, im.tileByteCounts[i]!))))
        .then((px) => {
          remember(key, px.data.byteLength);
          return px;
        })
        .catch(() => {
          tiles.delete(key);
          return null;
        });
      tiles.set(key, p);
    }
  }
}

/* ---------- Drawing one map tile ---------- */

const cancelled = new Set<number>();

function overviewFor(prep: Prepared, outMetres: number): number {
  const ims = prep.header.images;
  const px = Math.abs(prep.header.pixelScale[0]!) * prep.geo.unit;
  let best = 0;
  for (let i = 1; i < ims.length; i++) {
    const factor = ims[0]!.width / ims[i]!.width;
    if (px * factor <= outMetres * 1.25) best = i;
  }
  return best;
}

async function renderTile(id: number, z: number, x: number, y: number, era: Era): Promise<ImageBitmap | null> {
  if (z < MIN_ZOOM) return null;
  const bbox: [number, number, number, number] = [tileLon(x, z), tileLat(y + 1, z), tileLon(x + 1, z), tileLat(y, z)];
  const ranked = rankSheets(await sheetsIn(bbox, z), era, z, bbox).slice(0, 24);
  if (!ranked.length || cancelled.has(id)) return null;

  const lons = new Float64Array(SIZE);
  const lats = new Float64Array(SIZE);
  for (let i = 0; i < SIZE; i++) {
    lons[i] = tileLon(x + (i + 0.5) / SIZE, z);
    lats[i] = tileLat(y + (i + 0.5) / SIZE, z);
  }

  // Pixel -> sheet, skipping sheets that turn out unusable (then the next one shows through).
  const owner = new Int16Array(SIZE * SIZE);
  let usable = ranked;
  let preps = new Map<Sheet, Prepared>();
  for (let round = 0; round < 3; round++) {
    owner.fill(-1);
    const used = new Set<number>();
    for (let r = 0; r < SIZE; r++) {
      for (let c = 0; c < SIZE; c++) {
        const s = sheetAt(usable, lons[c]!, lats[r]!);
        if (s) {
          const k = usable.indexOf(s);
          owner[r * SIZE + c] = k;
          used.add(k);
        }
      }
    }
    if (!used.size) return null;
    const results = await Promise.all([...used].map(async (k) => [usable[k]!, await prepare(usable[k]!)] as const));
    if (cancelled.has(id)) return null;
    const bad = results.filter(([, p]) => !p).map(([s]) => s);
    preps = new Map(results.filter(([, p]) => p).map(([s, p]) => [s, p!]));
    if (!bad.length) break;
    usable = usable.filter((s) => !bad.includes(s));
    if (round === 2) break;
  }

  const out = new Uint8ClampedArray(SIZE * SIZE * 4);
  const midLat = (bbox[1] + bbox[3]) / 2;
  const outMetres = metresPerPixel(z, midLat);
  const G = 16;
  const N = SIZE / G + 1;
  let drew = false;

  for (const [sheet, prep] of preps) {
    const k = usable.indexOf(sheet);
    const level = overviewFor(prep, outMetres);
    const im = prep.header.images[level]!;
    const factor = prep.header.images[0]!.width / im.width;
    const [ti, tj, , tx, ty] = prep.header.tiepoint as [number, number, number, number, number];
    const sx = Math.abs(prep.header.pixelScale[0]!);
    const sy = Math.abs(prep.header.pixelScale[1]!);
    // Sheet pixel coordinates on a coarse grid; pixels in between are interpolated.
    const gc = new Float64Array(N * N);
    const gr = new Float64Array(N * N);
    for (let gy = 0; gy < N; gy++) {
      for (let gx = 0; gx < N; gx++) {
        const lon = tileLon(x + (gx * G) / SIZE, z);
        const lat = tileLat(y + (gy * G) / SIZE, z);
        const [mx, my] = toSheetMetres(prep.geo, lon, lat);
        gc[gy * N + gx] = ((mx / prep.geo.unit - tx) / sx + ti) / factor;
        gr[gy * N + gx] = ((ty - my / prep.geo.unit) / sy + tj) / factor;
      }
    }
    const colAt = (c: number, r: number, g: Float64Array) => {
      const fx = (c + 0.5) / G;
      const fy = (r + 0.5) / G;
      const x0 = Math.min(Math.floor(fx), N - 2);
      const y0 = Math.min(Math.floor(fy), N - 2);
      const u = fx - x0;
      const v = fy - y0;
      const i = y0 * N + x0;
      return (g[i]! * (1 - u) + g[i + 1]! * u) * (1 - v) + (g[i + N]! * (1 - u) + g[i + N + 1]! * u) * v;
    };
    const across = Math.ceil(im.width / im.tileWidth);
    const down = Math.ceil(im.height / im.tileHeight);
    const tileOf = (cc: number, rr: number) => {
      const a = Math.min(Math.max(Math.floor(Math.min(Math.max(cc, 0), im.width - 1) / im.tileWidth), 0), across - 1);
      const b = Math.min(Math.max(Math.floor(Math.min(Math.max(rr, 0), im.height - 1) / im.tileHeight), 0), down - 1);
      return b * across + a;
    };
    const srcC = new Float32Array(SIZE * SIZE);
    const srcR = new Float32Array(SIZE * SIZE);
    const need = new Set<number>();
    for (let r = 0; r < SIZE; r++) {
      for (let c = 0; c < SIZE; c++) {
        const p = r * SIZE + c;
        if (owner[p] !== k) continue;
        const sc = colAt(c, r, gc) - 0.5;
        const sr = colAt(c, r, gr) - 0.5;
        srcC[p] = sc;
        srcR[p] = sr;
        if (sc < -0.5 || sr < -0.5 || sc > im.width - 0.5 || sr > im.height - 0.5) continue;
        const c0 = Math.floor(sc);
        const r0 = Math.floor(sr);
        need.add(tileOf(c0, r0));
        need.add(tileOf(c0 + 1, r0));
        need.add(tileOf(c0, r0 + 1));
        need.add(tileOf(c0 + 1, r0 + 1));
      }
    }
    loadTiles(sheet, prep, level, [...need]);
    const px = new Map<number, Pixels | null>();
    await Promise.all([...need].map(async (i) => px.set(i, (await tiles.get(`${sheet.url}|${level}|${i}`)) ?? null)));
    if (cancelled.has(id)) return null;

    const sample = (sc: number, sr: number, ch: number): number => {
      const t = px.get(tileOf(sc, sr));
      if (!t) return -1;
      const cc = Math.min(Math.max(sc, 0), im.width - 1);
      const rr = Math.min(Math.max(sr, 0), im.height - 1);
      const lx = Math.min(cc % im.tileWidth, t.w - 1);
      const ly = Math.min(rr % im.tileHeight, t.h - 1);
      return t.data[(ly * t.w + lx) * 4 + ch]!;
    };
    for (let p = 0; p < SIZE * SIZE; p++) {
      if (owner[p] !== k) continue;
      const sc = srcC[p]!;
      const sr = srcR[p]!;
      if (sc < -0.5 || sr < -0.5 || sc > im.width - 0.5 || sr > im.height - 0.5) continue;
      const c0 = Math.floor(sc);
      const r0 = Math.floor(sr);
      const u = sc - c0;
      const v = sr - r0;
      let ok = true;
      for (let ch = 0; ch < 3; ch++) {
        const a = sample(c0, r0, ch);
        const b = sample(c0 + 1, r0, ch);
        const c = sample(c0, r0 + 1, ch);
        const d = sample(c0 + 1, r0 + 1, ch);
        if (a < 0 || b < 0 || c < 0 || d < 0) {
          ok = false;
          break;
        }
        out[p * 4 + ch] = (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v;
      }
      if (ok) {
        out[p * 4 + 3] = 255;
        drew = true;
      }
    }
  }
  if (!drew) return null;
  return createImageBitmap(new ImageData(out, SIZE, SIZE));
}

/* ---------- Which sheets are in view ---------- */

async function sheetsInView(bbox: [number, number, number, number], zoom: number, era: Era) {
  const z = Math.floor(zoom);
  if (z < MIN_ZOOM) return { sheets: [], tooFar: true };
  const ranked = rankSheets(await sheetsIn(bbox, z), era, z, bbox);
  const counts = new Map<Sheet, number>();
  const COLS = 9;
  const ROWS = 7;
  for (let i = 0; i < COLS; i++) {
    for (let j = 0; j < ROWS; j++) {
      const lon = bbox[0] + ((i + 0.5) / COLS) * (bbox[2] - bbox[0]);
      const lat = bbox[1] + ((j + 0.5) / ROWS) * (bbox[3] - bbox[1]);
      const s = sheetAt(ranked.filter((r) => !unusable.has(r.url)), lon, lat);
      if (s) counts.set(s, (counts.get(s) ?? 0) + 1);
    }
  }
  const sheets = [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].year - b[0].year)
    .map(([s, n]) => ({ name: s.name, scale: s.scale, year: s.year, imprint: s.imprint, state: s.state, share: n / (COLS * ROWS) }));
  return { sheets, tooFar: false };
}

/* ---------- Messages ---------- */

self.onmessage = async (e: MessageEvent) => {
  const m = e.data;
  if (m?.type === 'abort') {
    cancelled.add(m.id);
    return;
  }
  const era: Era = isEra(m?.era) ? m.era : 'lookouts';
  if (m?.type === 'tile') {
    try {
      const bitmap = await renderTile(m.id, m.z, m.x, m.y, era);
      self.postMessage({ type: 'tile', id: m.id, bitmap, failures: { index: indexFailures, sheets: sheetFailures } }, bitmap ? [bitmap] : []);
    } catch (err) {
      self.postMessage({ type: 'tile', id: m.id, bitmap: null, error: String((err as Error)?.message ?? err), failures: { index: indexFailures, sheets: sheetFailures } });
    } finally {
      cancelled.delete(m.id);
    }
  } else if (m?.type === 'inview') {
    try {
      const r = await sheetsInView(m.bbox, m.zoom, era);
      self.postMessage({ type: 'inview', id: m.id, ...r, failed: false });
    } catch {
      self.postMessage({ type: 'inview', id: m.id, sheets: [], tooFar: false, failed: true });
    }
  }
};
