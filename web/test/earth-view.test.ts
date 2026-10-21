/**
 * The satellite view's pure geometry (src/view3d/earth-geo.ts): the earth's curve put into
 * Terrarium tiles, the camera placement MapLibre is given, bearings and elevation angles on the
 * screen, imagery choice and the mode that opens.
 */
import { describe, expect, it } from 'vitest';
import {
  EFFECTIVE_RADIUS_M,
  cabFrame,
  cameraSpace,
  chooseMode,
  clipNear,
  curveDropM,
  decodeTerrarium,
  demZoomFor,
  discBounds,
  dropTerrariumTile,
  encodeTerrarium,
  eoxTileFor,
  fillFraction,
  firstImagery,
  focalPx,
  horizontalFov,
  lookTarget,
  mercatorBearing,
  metresPerMercatorUnit,
  nearPlaneM,
  orbitEye,
  project,
  safeTilt,
  satelliteDownload,
  targetDistanceM,
  tileBounds,
  tileDistanceM,
  tileZoomFor,
  unproject,
  usgsVerdict,
  type CabCamera,
} from '../src/view3d/earth-geo.ts';
import { EARTH_RADIUS_M, REFRACTION_K, bearingDeg, distanceM, mercY, panoramaLevels } from '../src/view3d/tiles.ts';

const DESOLATION = { lat: 48.91116, lon: -121.016121 };

/** Web Mercator tile holding a point. */
function tileOf(lat: number, lon: number, z: number): [number, number] {
  const n = 2 ** z;
  return [Math.floor(((lon + 180) / 360) * n), Math.floor(mercY(lat) * n)];
}

describe('the earth curve in the terrain', () => {
  it('uses the drawn view’s earth: R / (1 − k), k = 0.13', () => {
    expect(EFFECTIVE_RADIUS_M).toBeCloseTo(EARTH_RADIUS_M / (1 - REFRACTION_K), 3);
    // the Rust engine's slope term: d² (1 − k) / (2 R)
    expect(curveDropM(10_000)).toBeCloseTo((10_000 ** 2 * (1 - REFRACTION_K)) / (2 * EARTH_RADIUS_M), 9);
  });

  it.each([
    [0, 0],
    [8_000, 4.4],
    [60_000, 246],
    [150_000, 1_537],
  ])('drops the ground %f m away by about %f m', (d, drop) => {
    expect(curveDropM(d)).toBeCloseTo(drop, drop < 10 ? 1 : -1);
  });

  it('round-trips heights through Terrarium to 1/256 m', () => {
    const px = new Uint8Array(4);
    for (const h of [-32768, -11.3, 0, 0.5, 1823.29, 4392.0039, 8848.86, 30000.123]) {
      encodeTerrarium(h, px, 0);
      expect(px[3]).toBe(255);
      expect(Math.abs(decodeTerrarium(px[0]!, px[1]!, px[2]!) - h)).toBeLessThanOrEqual(0.5 / 256 + 1e-9);
    }
    // whole metres and 1/256 steps come back exactly
    for (const h of [0, 1500, -20, 1234 + 37 / 256]) {
      encodeTerrarium(h, px, 0);
      expect(decodeTerrarium(px[0]!, px[1]!, px[2]!)).toBe(h);
    }
    // the fraction rounds up into the next metre without overflowing the blue byte
    encodeTerrarium(99.999, px, 0);
    expect(decodeTerrarium(px[0]!, px[1]!, px[2]!)).toBe(100);
  });

  it('lowers a tile by the drop at each pixel’s distance from the eye, and the eye by nothing', () => {
    const size = 256;
    const fillTile = () => {
      const px = new Uint8Array(size * size * 4);
      for (let i = 0; i < px.length; i += 4) encodeTerrarium(1000, px, i);
      return px;
    };
    // The tile under the eye: the eye's own pixel keeps its height.
    const z = 13;
    const [x, y] = tileOf(DESOLATION.lat, DESOLATION.lon, z);
    const under = fillTile();
    dropTerrariumTile(under, size, z, x, y, DESOLATION.lat, DESOLATION.lon);
    const n = 2 ** z;
    const col = Math.floor((((DESOLATION.lon + 180) / 360) * n - x) * size);
    const row = Math.floor((mercY(DESOLATION.lat) * n - y) * size);
    const i = (row * size + col) * 4;
    expect(1000 - decodeTerrarium(under[i]!, under[i + 1]!, under[i + 2]!)).toBeLessThan(0.01);

    // A tile 60 km east: its pixels sink by about 246 m, each by its own distance.
    const z2 = 10;
    const [x2, y2] = tileOf(DESOLATION.lat, DESOLATION.lon + 60_000 / (111_320 * Math.cos((DESOLATION.lat * Math.PI) / 180)), z2);
    const far = fillTile();
    dropTerrariumTile(far, size, z2, x2, y2, DESOLATION.lat, DESOLATION.lon);
    const [w, s, e, nn] = tileBounds(z2, x2, y2);
    for (const [r, c] of [
      [0, 0],
      [128, 128],
      [255, 255],
    ] as const) {
      const lon = w + ((c + 0.5) / size) * (e - w);
      const lat = Math.atan(Math.sinh((0.5 - (y2 + (r + 0.5) / size) / 2 ** z2) * 2 * Math.PI)) * (180 / Math.PI);
      expect(lat).toBeGreaterThan(s);
      expect(lat).toBeLessThan(nn);
      const k = (r * size + c) * 4;
      const got = 1000 - decodeTerrarium(far[k]!, far[k + 1]!, far[k + 2]!);
      expect(got).toBeCloseTo(curveDropM(distanceM(DESOLATION.lat, DESOLATION.lon, lat, lon)), 1);
    }
  });
});

describe('bearings on the flat map', () => {
  it('is north and east along the map’s axes', () => {
    expect(mercatorBearing(48, -121, 49, -121)).toBeCloseTo(0, 9);
    expect(mercatorBearing(48.9, -121, 48.9, -120)).toBeCloseTo(90, 9);
    expect(mercatorBearing(48.9, -121, 48.9, -122)).toBeCloseTo(270, 9);
  });

  it('drifts from the great-circle bearing far off, as the notes say (0.3° at 60 km east, 49° N)', () => {
    const lon2 = DESOLATION.lon + 60_000 / (111_320 * Math.cos((DESOLATION.lat * Math.PI) / 180));
    const drift = mercatorBearing(DESOLATION.lat, DESOLATION.lon, DESOLATION.lat, lon2) - bearingDeg(DESOLATION.lat, DESOLATION.lon, DESOLATION.lat, lon2);
    expect(drift).toBeGreaterThan(0.25);
    expect(drift).toBeLessThan(0.4);
    // and agrees closely nearby
    const near = DESOLATION.lon + 0.02;
    expect(Math.abs(mercatorBearing(DESOLATION.lat, DESOLATION.lon, DESOLATION.lat + 0.01, near) - bearingDeg(DESOLATION.lat, DESOLATION.lon, DESOLATION.lat + 0.01, near))).toBeLessThan(0.01);
  });
});

describe('bearing and elevation onto the screen', () => {
  const cam: CabCamera = { bearing: 200, tilt: 0, fov: 40, width: 800, height: 400 };

  it('puts the view’s centre in the middle and the edges of the field of view at the edges', () => {
    const c = project(200, 0, cam)!;
    expect(c.x).toBeCloseTo(400, 9);
    expect(c.y).toBeCloseTo(200, 9);
    expect(project(200, 20, cam)!.y).toBeCloseTo(0, 6);
    expect(project(200, -20, cam)!.y).toBeCloseTo(400, 6);
    // along the level: x = W/2 + f tan(Δaz)
    const f = focalPx(cam);
    expect(project(215, 0, cam)!.x).toBeCloseTo(400 + f * Math.tan((15 * Math.PI) / 180), 6);
    expect(horizontalFov(cam)).toBeCloseTo(2 * Math.atan(400 / f) * (180 / Math.PI), 6);
  });

  it('leaves out what is behind the eye', () => {
    expect(project(20, 0, cam)).toBeNull();
    expect(project(200, 0, cam)).not.toBeNull();
  });

  it('tilts: looking down raises the horizon on the screen', () => {
    const down = { ...cam, tilt: -10 };
    expect(project(200, 0, down)!.y).toBeLessThan(200);
    expect(project(200, -10, down)!.y).toBeCloseTo(200, 6);
  });

  it.each([
    [0, 0, 0],
    [12, 3, -8],
    [-25, 15, 5],
    [33, -18, 30],
  ])('unprojects what it projects (Δaz %f, elev %f, tilt %f)', (daz, elev, tilt) => {
    const c = { ...cam, tilt };
    const p = project(cam.bearing + daz, elev, c)!;
    const back = unproject(p.x, p.y, c);
    expect(back.az).toBeCloseTo(cam.bearing + daz, 6);
    expect(back.elev).toBeCloseTo(elev, 6);
  });

  it('has camera axes that match a level view', () => {
    // a point straight ahead along the bearing lands on the forward axis
    const b = (cam.bearing * Math.PI) / 180;
    const [r, u, f] = cameraSpace(Math.sin(b) * 10, Math.cos(b) * 10, 0, cam);
    expect(r).toBeCloseTo(0, 9);
    expect(u).toBeCloseTo(0, 9);
    expect(f).toBeCloseTo(10, 9);
  });

  it('never looks exactly level (MapLibre’s pitch of 90° degenerates)', () => {
    expect(safeTilt(0)).not.toBe(0);
    expect(Math.abs(safeTilt(0))).toBeLessThan(0.02);
    expect(safeTilt(-3)).toBe(-3);
  });
});

describe('placing MapLibre’s camera', () => {
  /** MapLibre's calculateCameraOptionsFromTo (mercator_transform.ts), bearing and pitch only. */
  function maplibreAim(from: { lat: number; lon: number; altM: number }, to: { lat: number; lon: number; altM: number }) {
    const merc = (p: { lat: number; lon: number; altM: number }) => ({ x: (p.lon + 180) / 360, y: mercY(p.lat), z: p.altM / metresPerMercatorUnit(p.lat) });
    const a = merc(from);
    const b = merc(to);
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const dz = b.z - a.z;
    const ground = Math.hypot(dx, dy);
    const d3 = Math.hypot(dx, dy, dz);
    let pitch = (Math.acos(ground / d3) * 180) / Math.PI;
    pitch = dz < 0 ? 90 - pitch : 90 + pitch;
    return { bearing: ((Math.atan2(dx, -dy) * 180) / Math.PI + 360) % 360, pitch };
  }

  const eye = { ...DESOLATION, altM: 1882 };

  it.each([
    [0, -0.01],
    [200, -4],
    [95, 8],
    [315, -35],
  ])('aims exactly at bearing %f, tilt %f, with the target 400 m out', (bearing, tilt) => {
    const t = lookTarget(eye, bearing, tilt, 400);
    const aim = maplibreAim(eye, t);
    expect(aim.bearing).toBeCloseTo(bearing, 6);
    expect(aim.pitch).toBeCloseTo(90 + tilt, 6);
    expect(Math.hypot(distanceM(eye.lat, eye.lon, t.lat, t.lon), t.altM - eye.altM)).toBeCloseTo(400, -0.5);
  });

  it('keeps MapLibre’s near plane inside a third of the eye height, and the centre within 400 m', () => {
    for (const eyeM of [2.5, 6, 11, 21.6, 40]) {
      for (const fov of [4, 10, 40, 60]) {
        const d = targetDistanceM(eyeM, fov);
        expect(d).toBeLessThanOrEqual(400);
        expect(d).toBeGreaterThanOrEqual(40);
        if (d > 40) expect(nearPlaneM(d, fov)).toBeLessThanOrEqual(eyeM / 3 + 1e-9);
      }
    }
    // a 20 km centre, as MapLibre's own placement gives, puts the near plane ~140 m out
    expect(nearPlaneM(20_000, 40)).toBeGreaterThan(100);
  });

  it('circles the lookout from outside: the camera is the set distance from its foot', () => {
    const foot = { ...DESOLATION, altM: 1880 };
    const cam = orbitEye(foot, 30, 60, 700);
    const ground = distanceM(foot.lat, foot.lon, cam.lat, cam.lon);
    expect(Math.hypot(ground, cam.altM - foot.altM)).toBeCloseTo(700, -1);
    expect(cam.altM - foot.altM).toBeCloseTo(350, 3);
    expect(bearingDeg(cam.lat, cam.lon, foot.lat, foot.lon)).toBeCloseTo(30, 1);
  });
});

describe('tile detail', () => {
  it('matches photo pixels to screen pixels at the centre’s distance', () => {
    // (1 unit = 1,000 km, so these tiles are 1 and 2 km away)
    expect(tileZoomFor(18, 0.001, 0, 0.001, 1_000_000, 0)).toBeCloseTo(18, 9);
    expect(tileZoomFor(18, 0.001, 0, 0.001, 1_000_000, -0.25)).toBeCloseTo(17.75, 9);
    // twice as far: a zoom coarser
    expect(tileZoomFor(18, 0.002, 0, 0.001, 1_000_000, 0)).toBeCloseTo(17, 9);
    // past 15 km a little coarser still
    const d = 60_000 / 30_000_000;
    expect(tileZoomFor(18, d, 0, 0.001, 30_000_000, 0)).toBeCloseTo(18 - Math.log2(d / 0.001) - 1, 9);
  });

  it('takes the terrain at the drawn view’s zooms, plus 13 for the summit', () => {
    expect(demZoomFor(500, false)).toBe(13);
    for (const light of [false, true]) {
      for (const l of panoramaLevels(150_000, light ? 'light' : 'full')) {
        expect(demZoomFor(Math.max(l.maxM - 1, 1_600), light)).toBe(l.z);
      }
    }
    expect(demZoomFor(70_000, true)).toBe(8);
    expect(demZoomFor(70_000, false)).toBe(9);
  });

  it('measures how far a tile is from the eye', () => {
    const [x, y] = tileOf(DESOLATION.lat, DESOLATION.lon, 12);
    expect(tileDistanceM(12, x, y, DESOLATION.lat, DESOLATION.lon)).toBe(0);
    expect(tileDistanceM(12, x + 20, y, DESOLATION.lat, DESOLATION.lon)).toBeGreaterThan(100_000);
    const [w, s, e, n] = discBounds(DESOLATION.lat, DESOLATION.lon, 170_000);
    expect(n - DESOLATION.lat).toBeCloseTo(1.53, 1);
    expect(e - DESOLATION.lon).toBeGreaterThan(2.2);
    expect(w).toBeLessThan(DESOLATION.lon);
    expect(s).toBeLessThan(DESOLATION.lat);
  });
});

describe('imagery', () => {
  it.each([
    ['Desolation Peak, Washington', 48.911, -121.016, 14, 'usgs'],
    // the strip just north of the border is tried on USGS first, which answers with fill or a 404 there
    ['the border strip', 49.3, -121.0, 14, 'usgs'],
    ['British Columbia', 49.6, -121.0, 14, 'eox'],
    ['Alberta', 51.0, -115.0, 12, 'eox'],
    ['Alaska', 61.2, -149.9, 14, 'eox'],
    ['Hawaii', 19.8, -155.5, 16, 'usgs'],
    ['Pennsylvania', 41.317, -78.994, 15, 'usgs'],
    ['the Pacific far offshore', 47.5, -130.5, 12, 'eox'],
  ])('%s asks %s first', (_name, lat, lon, z, src) => {
    const [x, y] = tileOf(lat, lon, z);
    expect(firstImagery(z, x, y)).toBe(src);
  });

  it('cuts zoom 15 and 16 EOX tiles from their zoom-14 ancestor', () => {
    expect(eoxTileFor(13, 100, 200)).toEqual({ z: 13, x: 100, y: 200, sx: 0, sy: 0, size: 256 });
    expect(eoxTileFor(16, 10740, 22423)).toEqual({ z: 14, x: 2685, y: 5605, sx: 0, sy: 192, size: 64 });
    expect(eoxTileFor(15, 5371, 11210)).toEqual({ z: 14, x: 2685, y: 5605, sx: 128, sy: 0, size: 128 });
  });

  it('tells USGS fill from photos', () => {
    const tile = (fill: number) => {
      const px = new Uint8Array(100 * 4);
      for (let i = 0; i < 100; i++) {
        const v = i < fill ? 255 : 90 + (i % 40);
        px.set([v, v === 255 ? 255 : 120, v === 255 ? 255 : 70, 255], i * 4);
      }
      return px;
    };
    expect(fillFraction(tile(0))).toBe(0);
    expect(fillFraction(tile(100))).toBe(1);
    expect(usgsVerdict(fillFraction(tile(0)))).toBe('usgs');
    expect(usgsVerdict(fillFraction(tile(100)))).toBe('eox');
    expect(usgsVerdict(fillFraction(tile(40)))).toBe('blend');
    // black fill (USGS at zoom 13 outside the US) counts too
    const black = new Uint8Array(400).fill(0);
    for (let i = 3; i < 400; i += 4) black[i] = 255;
    expect(usgsVerdict(fillFraction(black))).toBe('eox');
  });
});

describe('which view opens', () => {
  it('opens on Satellite where it is offered and the device can draw it', () => {
    expect(chooseMode({ offered: true, capable: true, stored: null })).toEqual({ mode: 'satellite', unavailable: false });
    expect(chooseMode({ offered: true, capable: true, stored: 'satellite' })).toEqual({ mode: 'satellite', unavailable: false });
  });

  it('remembers a visitor who chose Drawn', () => {
    expect(chooseMode({ offered: true, capable: true, stored: 'drawn' }).mode).toBe('drawn');
    // anything else stored is ignored
    expect(chooseMode({ offered: true, capable: true, stored: 'globe' }).mode).toBe('satellite');
  });

  it('falls back to Drawn, and says so, where the device cannot', () => {
    expect(chooseMode({ offered: true, capable: false, stored: 'satellite' })).toEqual({ mode: 'drawn', unavailable: true });
  });

  it('stays Drawn where it is not offered (the smoke lesson)', () => {
    expect(chooseMode({ offered: false, capable: true, stored: 'satellite' })).toEqual({ mode: 'drawn', unavailable: false });
  });
});

describe('the cab’s window frame', () => {
  it('has posts at the corners and two in each wall, the sill below the eye', () => {
    const quads = cabFrame();
    const posts = quads.filter((q) => q.part === 'post');
    expect(posts).toHaveLength(12);
    const bearings = posts.map((q) => {
      const [e, n] = q.pts[0]!;
      return ((Math.atan2(e, n) * 180) / Math.PI + 360) % 360;
    });
    // a sash post on the north wall about 18° east of north, a corner post near 45°
    expect(bearings.some((b) => Math.abs(b - 18) < 2)).toBe(true);
    expect(bearings.some((b) => Math.abs(b - 44) < 2)).toBe(true);
    for (const q of quads.filter((q) => q.part === 'sill')) for (const p of q.pts) expect(p[2]).toBeLessThan(0);
  });

  it('clips a post that reaches behind the eye', () => {
    const poly: [number, number, number][] = [
      [-1, 0, -2],
      [1, 0, -2],
      [1, 0, 2],
      [-1, 0, 2],
    ];
    const out = clipNear(poly, 0.05);
    expect(out.length).toBe(4);
    for (const p of out) expect(p[2]).toBeGreaterThanOrEqual(0.05 - 1e-12);
    expect(clipNear(poly.map(([x, y]) => [x, y, -1] as [number, number, number]))).toHaveLength(0);
  });
});

describe('the download estimate', () => {
  it('is larger looking all round than to start, and includes the 3D code', () => {
    for (const light of [false, true]) {
      const d = satelliteDownload(light);
      expect(d.around).toBeGreaterThan(d.start);
      expect(d.start).toBeGreaterThan(1_000_000);
      expect(d.around).toBeLessThan(20_000_000);
    }
  });
});
