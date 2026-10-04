/**
 * A small reader for the headers of tiled (cloud-optimised) GeoTIFFs: enough to find each
 * overview's tiles and the georeferencing, so the browser can fetch just the tiles it needs
 * with HTTP range requests. Pure, unit-tested against a real sheet header in test/oldtopo.test.ts.
 */
import type { GeoKeys } from './proj.ts';

export interface TiffImage {
  width: number;
  height: number;
  tileWidth: number;
  tileHeight: number;
  tileOffsets: number[];
  tileByteCounts: number[];
  compression: number;
  photometric: number;
  samplesPerPixel: number;
  /** Shared JPEG quantisation and Huffman tables (TIFF tag 347), when present. */
  jpegTables: Uint8Array | null;
}

export interface TiffHeader {
  /** Full resolution first, then the overviews. */
  images: TiffImage[];
  /** ModelTiepointTag (I, J, K, X, Y, Z) and ModelPixelScaleTag (Sx, Sy, Sz) of the full image. */
  tiepoint: number[];
  pixelScale: number[];
  geoKeys: GeoKeys;
}

export class NeedMoreBytes extends Error {
  readonly bytes: number;
  constructor(bytes: number) {
    super(`TIFF header needs ${bytes} bytes`);
    this.bytes = bytes;
  }
}

const TYPE_SIZE: Record<number, number> = { 1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 16: 8, 17: 8, 18: 8 };

type Value = number[] | Uint8Array | string;

/**
 * Parses the IFD chain from the first bytes of a TIFF. Throws NeedMoreBytes when a tag's data
 * lies past the end of `buf` (fetch that many bytes and try again), and Error for files this
 * reader does not handle (BigTIFF, untiled images).
 */
export function parseTiffHeader(buf: ArrayBuffer): TiffHeader {
  const dv = new DataView(buf);
  const need = (end: number) => {
    if (end > buf.byteLength) throw new NeedMoreBytes(Math.max(end, buf.byteLength * 2));
  };
  need(8);
  const order = dv.getUint16(0);
  if (order !== 0x4949 && order !== 0x4d4d) throw new Error('not a TIFF');
  const le = order === 0x4949;
  const magic = dv.getUint16(2, le);
  if (magic === 43) throw new Error('BigTIFF is not supported');
  if (magic !== 42) throw new Error('not a TIFF');

  const read = (type: number, count: number, at: number): Value => {
    const size = (TYPE_SIZE[type] ?? 1) * count;
    need(at + size);
    if (type === 2) return new TextDecoder('latin1').decode(new Uint8Array(buf, at, size));
    if (type === 1 || type === 7 || type === 6) return new Uint8Array(buf.slice(at, at + size));
    const out: number[] = new Array(count);
    for (let i = 0; i < count; i++) {
      const p = at + i * (TYPE_SIZE[type] ?? 1);
      out[i] =
        type === 3 ? dv.getUint16(p, le)
        : type === 4 ? dv.getUint32(p, le)
        : type === 8 ? dv.getInt16(p, le)
        : type === 9 ? dv.getInt32(p, le)
        : type === 11 ? dv.getFloat32(p, le)
        : type === 12 ? dv.getFloat64(p, le)
        : type === 5 ? dv.getUint32(p, le) / (dv.getUint32(p + 4, le) || 1)
        : type === 10 ? dv.getInt32(p, le) / (dv.getInt32(p + 4, le) || 1)
        : type === 16 ? Number(dv.getBigUint64(p, le))
        : 0;
    }
    return out;
  };

  const ifds: Map<number, Value>[] = [];
  let off = dv.getUint32(4, le);
  const seen = new Set<number>();
  while (off && !seen.has(off) && ifds.length < 64) {
    seen.add(off);
    need(off + 2);
    const n = dv.getUint16(off, le);
    need(off + 2 + n * 12 + 4);
    const tags = new Map<number, Value>();
    for (let i = 0; i < n; i++) {
      const e = off + 2 + i * 12;
      const tag = dv.getUint16(e, le);
      const type = dv.getUint16(e + 2, le);
      const count = dv.getUint32(e + 4, le);
      const size = (TYPE_SIZE[type] ?? 1) * count;
      tags.set(tag, read(type, count, size <= 4 ? e + 8 : dv.getUint32(e + 8, le)));
    }
    ifds.push(tags);
    off = dv.getUint32(off + 2 + n * 12, le);
  }

  const first = (t: Map<number, Value>, tag: number, fallback?: number): number => {
    const v = t.get(tag);
    if (Array.isArray(v) && typeof v[0] === 'number') return v[0];
    if (fallback !== undefined) return fallback;
    throw new Error(`TIFF tag ${tag} missing`);
  };
  const images: TiffImage[] = [];
  for (const t of ifds) {
    const subfile = first(t, 254, 0);
    if (subfile & 4) continue; // a transparency mask, not an image
    if (!t.has(322)) throw new Error('the TIFF is not tiled');
    const tables = t.get(347);
    images.push({
      width: first(t, 256),
      height: first(t, 257),
      tileWidth: first(t, 322),
      tileHeight: first(t, 323),
      tileOffsets: t.get(324) as number[],
      tileByteCounts: t.get(325) as number[],
      compression: first(t, 259, 1),
      photometric: first(t, 262, 2),
      samplesPerPixel: first(t, 277, 1),
      jpegTables: tables instanceof Uint8Array ? tables : null,
    });
  }
  if (!images.length) throw new Error('no images in the TIFF');
  images.sort((a, b) => b.width - a.width);

  const t0 = ifds[0]!;
  const keys: GeoKeys = {};
  const dir = t0.get(34735) as number[] | undefined;
  const doubles = (t0.get(34736) as number[] | undefined) ?? [];
  const ascii = typeof t0.get(34737) === 'string' ? (t0.get(34737) as string) : '';
  if (dir) {
    for (let i = 0; i < dir[3]!; i++) {
      const [id, loc, count, value] = dir.slice(4 + i * 4, 8 + i * 4) as [number, number, number, number];
      if (loc === 0) keys[id] = value;
      else if (loc === 34736) keys[id] = count > 1 ? doubles.slice(value, value + count) : doubles[value]!;
      else if (loc === 34737) keys[id] = ascii.slice(value, value + count).replace(/\|$/, '');
    }
  }
  return {
    images,
    tiepoint: (t0.get(33922) as number[] | undefined) ?? [],
    pixelScale: (t0.get(33550) as number[] | undefined) ?? [],
    geoKeys: keys,
  };
}

/**
 * A standalone JPEG for one tile: the shared tables (without their end marker) followed by the
 * tile's own data (without its start marker), the way TIFF stores "new-style" JPEG.
 */
export function jpegForTile(tables: Uint8Array | null, tile: Uint8Array): Uint8Array {
  if (!tables || tables.length < 4) return tile;
  const out = new Uint8Array(tables.length - 2 + tile.length - 2);
  out.set(tables.subarray(0, tables.length - 2), 0);
  out.set(tile.subarray(2), tables.length - 2);
  return out;
}
