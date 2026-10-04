import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { deflateSync } from 'node:zlib';
import { describe, expect, it } from 'vitest';
import { angleDiff, azimuthText, eyeHeight, quadrantBearing, reconstructionNote, typicalFloor } from '../src/view3d/describe.ts';
import { panoramaLevels, planTiles, tilesForDisc, viewshedLevels, estimateBytes } from '../src/view3d/tiles.ts';
import { paintCounts } from '../src/view3d/viewshed-layer.ts';
import { crossing, scoreFor } from '../src/view3d/smoke-geo.ts';
import { parseState, serializeState } from '../src/lib/urlstate.ts';
import { renderPanel, renderTowerMain, type RenderContext } from '../src/render/tower.ts';
import type { TowerRecord } from '../src/lib/types.ts';

const ctx: RenderContext = { base: '/firefinder/', siteUrl: 'https://example.org/firefinder/', repo: 'o/r', sources: new Map() };

function record(extra: Partial<TowerRecord> = {}): TowerRecord {
  return {
    id: 'us-or-warner-mountain',
    name: 'Warner Mountain Lookout',
    region: 'OR',
    location: { lat: 43.5434, lon: -122.3664 },
    kind: 'tower',
    status: 'standing',
    verification: 'facts',
    ...extra,
  };
}

describe('eye height', () => {
  it('uses the recorded height to the cab floor plus 1.6 m', () => {
    const e = eyeHeight({ kind: 'tower', height_m: 12.2, lon: -116 });
    expect(e.source).toBe('recorded');
    expect(e.eyeM).toBeCloseTo(13.8, 5);
    expect(e.sentence).toContain('recorded height');
  });

  it.each([
    ['ground', -120, 2.5],
    ['two_story', -120, 6],
    ['three_story', -80, 9],
    ['tower', -120, 10.7],
    ['enclosed_tower', -110, 10.7],
    ['tower', -79, 21.6],
    ['platform', -90, 21.6],
  ])('a typical %s at %f° has its eye at %f m', (kind, lon, eye) => {
    const e = eyeHeight({ kind, height_m: null, lon });
    expect(e.source).toBe('typical');
    expect(e.eyeM).toBeCloseTo(eye, 5);
    expect(e.sentence).toContain("the real height isn't recorded");
  });

  it('says so when the kind of structure is unknown', () => {
    expect(eyeHeight({ kind: 'unknown', lon: -115 }).sentence).toContain("kind of structure isn't recorded");
    expect(typicalFloor('unknown', -70).floorM).toBe(20);
  });

  it('takes a height the visitor sets, within reason', () => {
    expect(eyeHeight({ kind: 'tower', height_m: 30, lon: -120 }, 4).eyeM).toBe(4);
    expect(eyeHeight({ kind: 'tower', lon: -120 }, 5000).eyeM).toBe(500);
    expect(eyeHeight({ kind: 'tower', lon: -120 }, -3).source).toBe('typical');
  });

  it('marks gone lookouts as reconstructed', () => {
    expect(reconstructionNote('gone', 'typical')).toMatch(/gone.*reconstructed.*typical height/);
    expect(reconstructionNote('ruins', 'recorded')).toContain('recorded height');
    expect(reconstructionNote('standing', 'typical')).toBeNull();
  });
});

describe('bearings', () => {
  it.each([
    [45, 'N 45° E'],
    [135, 'S 45° E'],
    [200, 'S 20° W'],
    [315, 'N 45° W'],
    [0, 'due north'],
    [90, 'due east'],
    [359.6, 'due north'],
    [-30, 'N 30° W'],
  ])('%f° reads %s', (az, text) => expect(quadrantBearing(az)).toBe(text));

  it('formats azimuths the way the ring reads', () => {
    expect(azimuthText(5)).toBe('005°');
    expect(azimuthText(213.46, 1)).toBe('213.5°');
    expect(azimuthText(360)).toBe('000°');
    expect(angleDiff(350, 10)).toBe(20);
    expect(angleDiff(10, 350)).toBe(-20);
  });
});

describe('terrain tiles', () => {
  it('plans a few dozen tiles for a 150 km view, fewer on phones', () => {
    const full = planTiles([{ lat: 43.5434, lon: -122.3664 }], panoramaLevels(150_000));
    const light = planTiles([{ lat: 43.5434, lon: -122.3664 }], panoramaLevels(150_000, 'light'));
    expect(full.length).toBeGreaterThan(30);
    expect(full.length).toBeLessThan(60);
    expect(light.length).toBeLessThan(full.length);
    expect(light.some((k) => k.startsWith('9/'))).toBe(false);
    expect(estimateBytes(full)).toBeGreaterThan(2e6);
    expect(viewshedLevels(40_000).map((l) => l.z)).toEqual([12, 10]);
  });

  it('shares tiles between nearby lookouts', () => {
    const a = planTiles([{ lat: 46.84, lon: -115.39 }], viewshedLevels(40_000));
    const both = planTiles([{ lat: 46.84, lon: -115.39 }, { lat: 46.63, lon: -115.55 }], viewshedLevels(40_000));
    expect(both.length).toBeLessThan(2 * a.length);
  });
});

const WASM = resolve(import.meta.dirname, '../src/view3d/wasm/firefinder_view_bg.wasm');
const hasWasm = existsSync(WASM);

/** A minimal RGB PNG (Terrarium heights), so the WASM decoder can be tested without network. */
function terrariumPng(size: number, height: (x: number, y: number) => number): Uint8Array {
  const raw = Buffer.alloc(size * (size * 3 + 1));
  for (let y = 0; y < size; y++) {
    raw[y * (size * 3 + 1)] = 0;
    for (let x = 0; x < size; x++) {
      const v = height(x, y) + 32768;
      const r = Math.floor(v / 256);
      const g = Math.floor(v) % 256;
      const b = Math.round((v - Math.floor(v)) * 256);
      raw.set([r, g, b], y * (size * 3 + 1) + 1 + x * 3);
    }
  }
  const crcTable = Array.from({ length: 256 }, (_, n) => {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
  });
  const crc = (buf: Buffer) => {
    let c = 0xffffffff;
    for (const b of buf) c = crcTable[(c ^ b) & 0xff]! ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const chunk = (type: string, data: Buffer) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type, 'ascii'), data]);
    const c = Buffer.alloc(4);
    c.writeUInt32BE(crc(td));
    return Buffer.concat([len, td, c]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr.set([8, 2, 0, 0, 0], 8);
  return new Uint8Array(
    Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr), chunk('IDAT', deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]),
  );
}

describe.skipIf(!hasWasm)('the WebAssembly engine (run `npm run wasm` first)', async () => {
  const wasm = hasWasm ? await import('../src/view3d/wasm/firefinder_view.js') : null;
  if (wasm) wasm.initSync({ module: readFileSync(WASM) });

  it('agrees with the TypeScript tile plan', () => {
    for (const [lat, lon, r, z] of [
      [43.5434, -122.3664, 150_000, 8],
      [43.5434, -122.3664, 40_000, 10],
      [46.84, -115.39, 4_000, 12],
      [42.1774, -74.2306, 100_000, 9],
    ] as const) {
      const ts = tilesForDisc(lat, lon, r, z).map(([x, y]) => `${x}/${y}`).sort();
      const flat = wasm!.tilesForDisc(lat, lon, r, z);
      const rs: string[] = [];
      for (let i = 0; i < flat.length; i += 2) rs.push(`${flat[i]}/${flat[i + 1]}`);
      expect(rs.sort()).toEqual(ts);
    }
  });

  it('decodes Terrarium tiles and sees a flat horizon where the maths says', () => {
    const e = new wasm!.Engine(64);
    e.begin();
    // A level plateau at 1,000 m over every tile the view needs.
    const flat = terrariumPng(256, () => 1000);
    const lat = 45;
    const lon = -116;
    const levels = new Float64Array([10, 60_000]);
    for (const [x, y] of tilesForDisc(lat, lon, 60_000, 10)) e.addTile(10, x, y, flat);
    expect(() => e.addTile(10, 0, 0, new Uint8Array([1, 2, 3]))).toThrow();
    const r = e.panorama(lat, lon, 100, 0, levels, 10, 60_000, 0.13, new Float64Array([lat + 0.1, lon, 0, 0]));
    const obs = r.observer;
    expect(obs[2]).toBeCloseTo(1000, 3); // ground
    expect(obs[3]).toBeCloseTo(1100, 3); // eye
    const nl = r.layersM.length;
    const sky = r.horizonDeg[(nl - 1) * r.columns]!;
    const rEff = 6_371_008.8 / (1 - 0.13);
    expect(sky).toBeCloseTo((-Math.acos(rEff / (rEff + 100)) * 180) / Math.PI, 2);
    expect(r.skylineM[0]).toBeGreaterThan(37_500);
    expect(r.skylineM[0]).toBeLessThan(39_000);
    // The target 11 km north on the plateau is in sight, due north.
    const t = r.targets;
    expect(t[5]).toBe(1);
    expect(t[1]! < 0.01 || t[1]! > 359.99).toBe(true);
    r.free();
    // Viewshed over the same plateau: a disc out to the horizon.
    const v = e.viewshed(new Float64Array([lat, lon, 100, 0]), levels, 50_000, 0, 0.13, 250, 1_000_000);
    const area = v.observers[5]!;
    const dh = Math.sqrt(2 * rEff * 100);
    expect(area / (Math.PI * dh * dh)).toBeGreaterThan(0.96);
    expect(area / (Math.PI * dh * dh)).toBeLessThan(1.04);
    v.free();
    e.free();
  });
});

describe('viewshed shading', () => {
  it('stripes ground seen by two or more, so it does not rely on colour', () => {
    const counts = new Uint8Array(7 * 7).fill(2);
    counts[0] = 0;
    counts[1] = 1;
    const px = paintCounts(counts, 7, 7, 'light', true);
    expect(px[3]).toBe(0); // unseen: transparent
    const colours = new Set<string>();
    for (let i = 2; i < 49; i++) colours.add(Array.from(px.slice(i * 4, i * 4 + 4)).join(','));
    expect(colours.size).toBe(2); // stripes
    const single = paintCounts(new Uint8Array([2, 2]), 2, 1, 'light', false);
    expect(Array.from(single.slice(0, 4))).toEqual(Array.from(paintCounts(new Uint8Array([1]), 1, 1, 'light', false)));
  });
});

describe('map URL', () => {
  it('keeps the lookouts whose views are shown, and the radius', () => {
    const s = parseState('?vs=us-id-a,us-id-b,bad id,us-id-a&vr=60');
    expect(s.seen).toEqual(['us-id-a', 'us-id-b']);
    expect(s.seenKm).toBe(60);
    expect(serializeState(s)).toBe('?vs=us-id-a,us-id-b&vr=60');
    expect(parseState('?vr=33').seenKm).toBeNull();
    expect(serializeState(parseState(''))).toBe('');
  });
});

describe('tower page and panel', () => {
  it('offers the view from the cab with a download size and the record it needs', () => {
    const page = renderTowerMain(record({ elevation_m: 1727.3 }), ctx).value;
    expect(page).toContain('id="view"');
    expect(page).toMatch(/Downloads about \d+(\.\d)? MB of terrain data/);
    expect(page).toContain('data-pano="{&quot;id&quot;:&quot;us-or-warner-mountain&quot;');
    expect(page).toContain('&amp;vs=us-or-warner-mountain');
    expect(page).toContain('href="#view"');
  });

  it('says plainly when the view is reconstructed', () => {
    const page = renderTowerMain(record({ status: 'gone' }), ctx).value;
    expect(page).toContain('The view is reconstructed from its recorded site and a typical height');
  });

  it('has the two 3D buttons in the side panel', () => {
    const panel = renderPanel(record(), ctx).value;
    expect(panel).toContain('data-action="view-cab"');
    expect(panel).toContain('data-action="viewshed"');
  });
});

describe('cross-shots', () => {
  it('finds where two bearings cross', () => {
    // Two lookouts 20 km apart east-west, both sighting a point 10 km north of the midpoint.
    const a = { lat: 45, lon: -116.127 };
    const b = { lat: 45, lon: -115.873 };
    const fire = { lat: 45.09, lon: -116 };
    const bearing = (p: { lat: number; lon: number }) => {
      const y = Math.sin(((fire.lon - p.lon) * Math.PI) / 180) * Math.cos((fire.lat * Math.PI) / 180);
      const x =
        Math.cos((p.lat * Math.PI) / 180) * Math.sin((fire.lat * Math.PI) / 180) -
        Math.sin((p.lat * Math.PI) / 180) * Math.cos((fire.lat * Math.PI) / 180) * Math.cos(((fire.lon - p.lon) * Math.PI) / 180);
      return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
    };
    const fix = crossing(a, bearing(a), b, bearing(b));
    expect(fix).not.toBeNull();
    expect(fix!.lat).toBeCloseTo(fire.lat, 4);
    expect(fix!.lon).toBeCloseTo(fire.lon, 4);
    // Lines that diverge never cross in front of the lookouts.
    expect(crossing(a, 270, b, 90)).toBeNull();
  });

  it('scores by how far off the fix is', () => {
    expect(scoreFor(150).stars).toBe(3);
    expect(scoreFor(900).stars).toBe(2);
    expect(scoreFor(3000).stars).toBe(1);
    expect(scoreFor(20000).stars).toBe(0);
  });
});
