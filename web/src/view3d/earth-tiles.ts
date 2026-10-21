/**
 * The satellite view's two MapLibre custom protocols:
 *
 * - `ffdem://<view>/<lat>/<lon>/{z}/{x}/{y}`: AWS terrain tiles with the earth's curve put in
 *   (every height lowered by d²/2R' from the eye at lat/lon; earth-geo.ts). The eye is in the
 *   URL so tiles made for one lookout are never reused for another.
 * - `ffsat://<view>/{z}/{x}/{y}`: photos from USGS where it has them, EOX elsewhere, and both
 *   in one tile along the border or a coast, so a view across the border has no holes and each
 *   tile is normally downloaded from one source only.
 *
 * MapLibre runs protocol handlers on the main thread. Decoding is the browser's (off the main
 * thread); reading and rewriting the pixels costs about a millisecond a tile.
 */
import { addProtocol } from 'maplibre-gl';
import {
  EOX_IMAGERY_URL,
  USGS_IMAGERY_URL,
  dropTerrariumTile,
  eoxTileFor,
  fillFraction,
  firstImagery,
  isFillPixel,
  usgsVerdict,
  type ImagerySource,
} from './earth-geo.ts';
import { TERRAIN_URL } from './tiles.ts';

const DEM = 'ffdem';
const SAT = 'ffsat';
const SIZE = 256;

/** What a view has used so far (tiles may have come from the browser's cache). */
export interface Tally {
  demTiles: number;
  demBytes: number;
  /** Of those, the bytes of tiles the drawn view had already fetched (the browser keeps them). */
  demSharedBytes: number;
  photoTiles: number;
  photoBytes: number;
  failed: number;
  sources: Set<ImagerySource>;
}

interface ViewEntry {
  tally: Tally;
  onSource: () => void;
  /** Terrain tiles ("z/x/y") the drawn view's engine fetched for this lookout. */
  shared: Set<string>;
}

const views = new Map<string, ViewEntry>();
let registered = false;

function fill(template: string, z: number, x: number, y: number): string {
  return template.replace('{z}', String(z)).replace('{x}', String(x)).replace('{y}', String(y));
}

/* ---------- Pixels ---------- */

let canvas: OffscreenCanvas | HTMLCanvasElement | null = null;
let ctx: OffscreenCanvasRenderingContext2D | CanvasRenderingContext2D | null = null;

function context(): OffscreenCanvasRenderingContext2D | CanvasRenderingContext2D {
  if (ctx) return ctx;
  canvas = typeof OffscreenCanvas === 'function' ? new OffscreenCanvas(SIZE, SIZE) : Object.assign(document.createElement('canvas'), { width: SIZE, height: SIZE });
  ctx = canvas.getContext('2d', { willReadFrequently: true }) as OffscreenCanvasRenderingContext2D | CanvasRenderingContext2D;
  ctx.imageSmoothingQuality = 'high';
  return ctx;
}

/** A tile's pixels (a square of the image, scaled to 256 px). Synchronous, so the one canvas can be shared. */
function pixels(img: ImageBitmap, sx = 0, sy = 0, size = img.width): ImageData {
  const c = context();
  c.clearRect(0, 0, SIZE, SIZE);
  c.drawImage(img, sx, sy, size, size, 0, 0, SIZE, SIZE);
  return c.getImageData(0, 0, SIZE, SIZE);
}

function bitmap(data: ImageData): Promise<ImageBitmap> {
  return createImageBitmap(data, { premultiplyAlpha: 'none', colorSpaceConversion: 'none' });
}

async function fetchBlob(url: string, abort: AbortController): Promise<Blob | null> {
  const res = await fetch(url, { signal: abort.signal });
  if (res.ok) return res.blob();
  if (res.status === 404 || res.status === 403) return null;
  throw new Error(`${res.status} for ${url}`);
}

/* ---------- Terrain ---------- */

const DEM_RE = /^ffdem:\/\/([^/]+)\/(-?[\d.]+)\/(-?[\d.]+)\/(\d+)\/(\d+)\/(\d+)$/;

async function demTile(url: string, abort: AbortController): Promise<{ data: ImageBitmap | ArrayBuffer }> {
  const m = DEM_RE.exec(url);
  if (!m) throw new Error(`bad terrain tile url ${url}`);
  const [lat, lon, z, x, y] = m.slice(2).map(Number) as [number, number, number, number, number];
  const view = views.get(m[1]!);
  const tally = view?.tally;
  const blob = await fetchBlob(fill(TERRAIN_URL, z, x, y), abort).catch((err: unknown) => {
    if (tally && !abort.signal.aborted) tally.failed++;
    throw err;
  });
  // No tile (open sea): MapLibre treats an empty answer as "no heights here".
  if (!blob) return { data: new ArrayBuffer(0) };
  if (view) {
    view.tally.demTiles++;
    view.tally.demBytes += blob.size;
    if (view.shared.has(`${z}/${x}/${y}`)) view.tally.demSharedBytes += blob.size;
  }
  const img = await createImageBitmap(blob, { premultiplyAlpha: 'none', colorSpaceConversion: 'none' });
  const size = img.width;
  const data = pixels(img, 0, 0, size);
  img.close();
  dropTerrariumTile(data.data, SIZE, z, x, y, lat, lon);
  return { data: await bitmap(data) };
}

/* ---------- Photos ---------- */

const SAT_RE = /^ffsat:\/\/([^/]+)\/(\d+)\/(\d+)\/(\d+)$/;

/** Recently fetched zoom-14 EOX tiles, shared by the zoom-15 and 16 tiles cut from them. */
const eoxBlobs = new Map<string, Promise<Blob | null>>();
const EOX_CACHE = 48;

function eoxBlob(url: string, abort: AbortController, tally: Tally | undefined): Promise<Blob | null> {
  let p = eoxBlobs.get(url);
  if (p) {
    eoxBlobs.delete(url);
    eoxBlobs.set(url, p);
    return p;
  }
  // A shared fetch must not die with the first tile that asked for it.
  const own = new AbortController();
  p = fetchBlob(url, own).then((b) => {
    if (b && tally) tally.photoBytes += b.size;
    return b;
  });
  p.catch(() => eoxBlobs.delete(url));
  eoxBlobs.set(url, p);
  while (eoxBlobs.size > EOX_CACHE) eoxBlobs.delete(eoxBlobs.keys().next().value!);
  abort.signal.throwIfAborted();
  return p;
}

/** The EOX picture for a tile, cut from its zoom-14 ancestor past zoom 14. */
async function eoxImage(z: number, x: number, y: number, abort: AbortController, tally: Tally | undefined): Promise<ImageBitmap | null> {
  const t = eoxTileFor(z, x, y);
  const blob = await eoxBlob(fill(EOX_IMAGERY_URL, t.z, t.x, t.y), abort, tally);
  abort.signal.throwIfAborted();
  if (!blob) return null;
  const img = await createImageBitmap(blob);
  if (t.size === SIZE) return img;
  const cut = pixels(img, t.sx, t.sy, t.size);
  img.close();
  return bitmap(cut);
}

function noteSource(id: string, s: ImagerySource): void {
  const v = views.get(id);
  if (!v || v.tally.sources.has(s)) return;
  v.tally.sources.add(s);
  v.onSource();
}

async function satTile(url: string, abort: AbortController): Promise<{ data: ImageBitmap | ArrayBuffer }> {
  const m = SAT_RE.exec(url);
  if (!m) throw new Error(`bad photo tile url ${url}`);
  const id = m[1]!;
  const [z, x, y] = m.slice(2).map(Number) as [number, number, number];
  const tally = views.get(id)?.tally;
  try {
    if (firstImagery(z, x, y) === 'usgs') {
      // A USGS failure falls through to EOX rather than leaving a hole.
      const blob = await fetchBlob(fill(USGS_IMAGERY_URL, z, x, y), abort).catch((err: unknown) => {
        if (abort.signal.aborted) throw err;
        return null;
      });
      if (blob) {
        if (tally) tally.photoBytes += blob.size;
        const img = await createImageBitmap(blob);
        const usgs = pixels(img);
        const verdict = usgsVerdict(fillFraction(usgs.data, 3));
        if (verdict === 'usgs') {
          if (tally) tally.photoTiles++;
          noteSource(id, 'usgs');
          return { data: img };
        }
        img.close();
        if (verdict === 'blend') {
          const eox = await eoxImage(z, x, y, abort, tally);
          if (eox) {
            // EOX under, USGS on top where it has photos.
            const under = pixels(eox);
            eox.close();
            const u = usgs.data;
            const e = under.data;
            for (let i = 0; i < u.length; i += 4) {
              if (isFillPixel(u[i]!, u[i + 1]!, u[i + 2]!)) {
                u[i] = e[i]!;
                u[i + 1] = e[i + 1]!;
                u[i + 2] = e[i + 2]!;
              }
            }
            noteSource(id, 'eox');
          }
          if (tally) tally.photoTiles++;
          noteSource(id, 'usgs');
          return { data: await bitmap(usgs) };
        }
      }
    }
    const eox = await eoxImage(z, x, y, abort, tally);
    if (tally) tally.photoTiles++;
    if (!eox) return { data: new ArrayBuffer(0) };
    noteSource(id, 'eox');
    return { data: eox };
  } catch (err) {
    if (tally && !abort.signal.aborted) tally.failed++;
    throw err;
  }
}

/* ---------- Registration ---------- */

function register(): void {
  if (registered) return;
  registered = true;
  addProtocol(DEM, (params, abort) => demTile(params.url, abort));
  addProtocol(SAT, (params, abort) => satTile(params.url, abort));
}

export interface EarthSources {
  /** Tile URL template for the raster-dem source. */
  dem: string;
  /** Tile URL template for the photo source. */
  sat: string;
  tally: Tally;
  release(): void;
}

let seq = 0;

/**
 * Tile URLs for one satellite view, its eye at lat/lon. `onSource` is called when a photo source
 * is used for the first time (to show its credit); `shared` lists the terrain tiles the drawn
 * view fetched, so the notes can say how much was new.
 */
export function earthSources(lat: number, lon: number, onSource: () => void, shared: Iterable<string> = []): EarthSources {
  register();
  const id = `v${++seq}`;
  const tally: Tally = { demTiles: 0, demBytes: 0, demSharedBytes: 0, photoTiles: 0, photoBytes: 0, failed: 0, sources: new Set() };
  views.set(id, { tally, onSource, shared: new Set(shared) });
  return {
    dem: `${DEM}://${id}/${lat.toFixed(7)}/${lon.toFixed(7)}/{z}/{x}/{y}`,
    sat: `${SAT}://${id}/{z}/{x}/{y}`,
    tally,
    release: () => views.delete(id),
  };
}
