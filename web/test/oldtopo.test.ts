import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { CLARKE1866, NAD27_CONUS, georefFromKeys, metresPerPixel, molodensky, project, tileLat, tileLon, toSheetMetres } from '../src/history/oldtopo/proj.ts';
import { cellsFor, geotiffUrl, inRing, parseIndex, rankSheets, scalesForZoom, sheetAt, type Sheet } from '../src/history/oldtopo/sheets.ts';
import { NeedMoreBytes, jpegForTile, parseTiffHeader } from '../src/history/oldtopo/tiff.ts';

describe('projections (Snyder, USGS PP 1395, worked examples)', () => {
  it('transverse Mercator on Clarke 1866', () => {
    const [x, y] = project({ kind: 'tm', ellipsoid: CLARKE1866, lon0: -75, lat0: 0, k0: 0.9996, falseEasting: 0, falseNorthing: 0 }, -73.5, 40.5);
    expect(x).toBeCloseTo(127106.5, 0);
    expect(y).toBeCloseTo(4484124.4, 0);
  });

  it('polyconic on Clarke 1866', () => {
    const [x, y] = project({ kind: 'polyconic', ellipsoid: CLARKE1866, lon0: -96, lat0: 30, k0: 1, falseEasting: 0, falseNorthing: 0 }, -75, 40);
    expect(x).toBeCloseTo(1776774.5, 0);
    expect(y).toBeCloseTo(1319657.8, 0);
  });

  it('shifts WGS84 to NAD27 within a few metres (an Idaho sheet corner at 45°N 116°W NAD27)', () => {
    const [lon, lat] = molodensky(-116.000992, 44.999925, NAD27_CONUS);
    expect(Math.abs(lon + 116) * 78700).toBeLessThan(10);
    expect(Math.abs(lat - 45) * 111100).toBeLessThan(10);
  });

  it('web tiles', () => {
    expect(tileLon(0, 0)).toBe(-180);
    expect(tileLat(0, 0)).toBeCloseTo(85.0511, 3);
    expect(metresPerPixel(0, 0)).toBeCloseTo(156543.03, 1);
  });
});

describe('sheet georeferencing from GeoTIFF keys', () => {
  const base = { 1024: 1, 1025: 1, 2048: 4267, 3072: 32767, 3076: 9001, 3080: -115.75, 3081: 0, 3082: 0, 3083: 0, 3092: 1 };
  it('reads user-defined polyconic and transverse Mercator sheets on NAD27', () => {
    const poly = georefFromKeys({ ...base, 3075: 22 }, -115.75, 44.25);
    expect('unsupported' in poly).toBe(false);
    if (!('unsupported' in poly)) {
      expect(poly.projection.kind).toBe('polyconic');
      expect(poly.shift).toBe(NAD27_CONUS);
    }
    const tm = georefFromKeys({ ...base, 3075: 1 }, -115.75, 44.25);
    expect(!('unsupported' in tm) && tm.projection.kind).toBe('tm');
  });
  it('reads WGS84 sheets without a datum shift, and EPSG UTM codes', () => {
    const wgs = georefFromKeys({ ...base, 2048: 4326, 3075: 1 }, -121, 47.6);
    expect(!('unsupported' in wgs) && wgs.shift).toBeNull();
    const utm = georefFromKeys({ 1024: 1, 3072: 26711 }, -117, 44);
    expect(!('unsupported' in utm) && utm.projection).toMatchObject({ kind: 'tm', lon0: -117, k0: 0.9996, falseEasting: 500000 });
  });
  it('says why a sheet cannot be used rather than guessing', () => {
    expect(georefFromKeys({ ...base, 3075: 8 }, 0, 0)).toEqual({ unsupported: 'projection method 8' });
    expect(georefFromKeys({ ...base, 2048: 4135, 3075: 1 }, -157, 21)).toEqual({ unsupported: 'datum 4135' });
    expect(georefFromKeys({ 1024: 2 }, 0, 0)).toEqual({ unsupported: 'not a projected map' });
  });
});

describe('cloud-optimised GeoTIFF header (a real USGS sheet: Garden Valley, Idaho, 1909, 1:125,000)', () => {
  const bytes = readFileSync(resolve(import.meta.dirname, 'data/htmc-garden-valley-1909-header.tif'));
  const buf = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  const h = parseTiffHeader(buf);

  it('finds the full image and its overviews, tiled and JPEG-compressed', () => {
    expect(h.images).toHaveLength(8);
    expect(h.images[0]).toMatchObject({ width: 4525, height: 5863, tileWidth: 512, tileHeight: 512, compression: 7, photometric: 6 });
    expect(h.images[0]!.tileOffsets).toHaveLength(9 * 12);
    expect(h.images[1]!.width).toBe(2263);
    expect(h.images[0]!.jpegTables?.length).toBeGreaterThan(100);
  });

  it('reads the georeferencing keys', () => {
    expect(h.geoKeys[3075]).toBe(22);
    expect(h.geoKeys[3080]).toBe(-115.75);
    expect(h.geoKeys[2049]).toBe('NAD27');
    expect(h.pixelScale[0]).toBeCloseTo(10.5833, 3);
  });

  it('puts the sheet neatline corners where the scan shows them (checked by eye on the image)', () => {
    const g = georefFromKeys(h.geoKeys, -115.75, 44.25);
    if ('unsupported' in g) throw new Error(g.unsupported);
    const [, , , tx, ty] = h.tiepoint as [number, number, number, number, number];
    const px = (lon: number, lat: number) => {
      const [x, y] = toSheetMetres(g, lon, lat);
      return [(x - tx) / h.pixelScale[0]!, (ty - y) / h.pixelScale[1]!];
    };
    // NW corner 44°30'N 116°W (NAD27) is drawn at about column 310, row 316 of the scan.
    const [c, r] = px(-116.00098, 44.49993);
    expect(Math.abs(c! - 310)).toBeLessThan(4);
    expect(Math.abs(r! - 316)).toBeLessThan(4);
  });

  it('asks for more bytes when the header is cut short', () => {
    expect(() => parseTiffHeader(buf.slice(0, 2000))).toThrow(NeedMoreBytes);
  });

  it('splices the shared JPEG tables onto a tile', () => {
    const tables = new Uint8Array([0xff, 0xd8, 1, 2, 0xff, 0xd9]);
    const tile = new Uint8Array([0xff, 0xd8, 9, 9, 0xff, 0xd9]);
    expect([...jpegForTile(tables, tile)]).toEqual([0xff, 0xd8, 1, 2, 9, 9, 0xff, 0xd9]);
  });
});

describe('choosing sheets', () => {
  const sheet = (scanId: number, name: string, scale: number, year: number, imprint: number, box: [number, number, number, number]): Sheet => ({
    scanId,
    name,
    scale,
    year,
    imprint,
    state: 'ID',
    url: `https://example.test/${scanId}.tif`,
    ring: [
      [box[0], box[1]],
      [box[0], box[3]],
      [box[2], box[3]],
      [box[2], box[1]],
    ],
    bbox: box,
  });
  const old125 = sheet(1, 'Garden Valley', 125000, 1909, 1909, [-116, 44, -115.5, 44.5]);
  const reprint = sheet(2, 'Garden Valley', 125000, 1909, 1948, [-116, 44, -115.5, 44.5]);
  const mid62 = sheet(3, 'Garden Valley', 62500, 1959, 1961, [-115.75, 44, -115.5, 44.25]);
  const new24 = sheet(4, 'Placerville', 24000, 1998, 2002, [-115.875, 44, -115.75, 44.125]);
  const all = [old125, reprint, mid62, new24];
  const view = [-115.9, 44.05, -115.6, 44.2];

  it('puts the era\'s closest dates on top and counts reprints once', () => {
    expect(rankSheets(all, 'oldest', 13, view).map((s) => s.scanId)).toEqual([1, 3, 4]);
    expect(rankSheets(all, 'lookouts', 13, view).map((s) => s.scanId)).toEqual([3, 1, 4]);
    expect(rankSheets(all, 'newest', 13, view).map((s) => s.scanId)).toEqual([4, 3, 1]);
  });

  it('uses broad sheets zoomed out and detailed ones close in', () => {
    expect(rankSheets(all, 'newest', 9, view).map((s) => s.scanId)).toEqual([1]);
    expect(scalesForZoom(8)(125000)).toBe(false);
    expect(scalesForZoom(13)(250000)).toBe(false);
    expect(scalesForZoom(13)(24000)).toBe(true);
  });

  it('draws, at each point, the best sheet whose outline contains it', () => {
    const ranked = rankSheets(all, 'newest', 13, view);
    expect(sheetAt(ranked, -115.8, 44.1)?.scanId).toBe(4);
    expect(sheetAt(ranked, -115.7, 44.1)?.scanId).toBe(3);
    expect(sheetAt(ranked, -115.95, 44.3)?.scanId).toBe(1);
    expect(sheetAt(ranked, -114, 44.3)).toBeNull();
    expect(inRing(old125.ring, -115.7, 44.2)).toBe(true);
  });

  it('reads the TopoView sheet index and builds the GeoTIFF address', () => {
    const json = {
      features: [
        {
          attributes: { map_name: 'Garden Valley', map_scale: 125000, date_on_map: 1909, imprint_year: 1909, scan_id: 239502, drg_name: 'ID_Garden Valley_239502_1909_125000_geo.pdf', primary_state: 'ID' },
          geometry: { rings: [[[-116.00098, 43.99993], [-116.00098, 44.49993], [-115.50097, 44.49993], [-115.50096, 43.99994], [-116.00098, 43.99993]]] },
        },
        { attributes: { map_name: 'Broken', map_scale: 24000 }, geometry: { rings: [] } },
      ],
    };
    const sheets = parseIndex(json);
    expect(sheets).toHaveLength(1);
    expect(sheets[0]!.url).toBe('https://prd-tnm.s3.amazonaws.com/StagedProducts/Maps/HistoricalTopo/GeoTIFF/ID/ID_Garden%20Valley_239502_1909_125000_geo.tif');
    expect(sheets[0]!.bbox[0]).toBeCloseTo(-116.00098, 5);
    expect(geotiffUrl('not a sheet')).toBeNull();
    expect(cellsFor([-116.2, 43.9, -115.1, 44.1])).toEqual([[-117, 43], [-117, 44], [-116, 43], [-116, 44]]);
  });
});
