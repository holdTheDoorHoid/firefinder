/**
 * The terrain engine as the Web Worker runs it: fetches elevation tiles, peak names and the
 * lookout list, feeds them to the Rust/WASM core and returns plain data for the UI.
 * No DOM; also runs under Node for tests (see `TerrainEngine.fromBytes`).
 */
import init, { Engine, initSync } from './wasm/firefinder_view.js';
import { EYE_ABOVE_FLOOR_M, typicalFloor } from './describe.ts';
import { distanceM, flatLevels, panoramaLevels, planTiles, tileUrl, viewshedLevels, type Level, type TileKey } from './tiles.ts';

/** Atmospheric refraction coefficient (daytime, over land). */
export const REFRACTION_K = 0.13;
/** Move the eye to the highest ground this close to the recorded position, m. */
export const SNAP_M = 75;
/** Summits: look this far around a GNIS point for its top, m. */
const PEAK_SNAP_M = 120;
const FETCH_CONCURRENCY = 6;
const MAX_TILES = 260;

export interface Progress {
  phase: 'engine' | 'terrain' | 'names' | 'computing';
  done: number;
  total: number;
}
export type OnProgress = (p: Progress) => void;

export interface TileStats {
  needed: number;
  fetched: number;
  failed: number;
  bytes: number;
}

export interface Sighted {
  name: string;
  lat: number;
  lon: number;
  distM: number;
  az: number;
  /** Elevation angle of the top, degrees. */
  angle: number;
  groundM: number;
  /** How far the top clears nearer terrain, degrees (negative: hidden). */
  clearance: number;
  visible: boolean;
}
export interface PeakSight extends Sighted {
  gnisId: number;
}
export interface LookoutSight extends Sighted {
  id: string;
  kind: string;
  status: string;
}

export interface ObserverInfo {
  lat: number;
  lon: number;
  groundM: number;
  eyeM: number;
  movedM: number;
  recordedGroundM: number;
}

export interface PanoramaRequest {
  /** Absolute URL of the site root, e.g. "https://…/firefinder/". */
  base: string;
  lat: number;
  lon: number;
  eyeAboveGroundM: number;
  maxDistM: number;
  azStepDeg: number;
  /** "light" skips the zoom-9 terrain (phones). */
  detail?: 'full' | 'light';
  /** This lookout's id, left out of "other lookouts in view". */
  selfId?: string | null;
  /** Load peak names and other lookouts (default true). */
  labels?: boolean;
  /** Extra points to sight (the smoke in the lesson), returned in order. */
  extra?: { lat: number; lon: number; aboveGroundM: number }[];
  terrainUrl?: string;
}

export interface PanoramaData {
  columns: number;
  azStep: number;
  layersM: Float64Array;
  horizon: Float32Array;
  crest: Float32Array;
  skyline: Float32Array;
  observer: ObserverInfo;
  peaks: PeakSight[];
  lookouts: LookoutSight[];
  extra: Sighted[];
  peaksChecked: number;
  nodataFraction: number;
  samples: number;
  tiles: TileStats;
  ms: { terrain: number; names: number; compute: number; total: number };
}

export interface ViewshedObserver {
  id?: string;
  lat: number;
  lon: number;
  eyeAboveGroundM: number;
}

export interface ViewshedRequest {
  observers: ViewshedObserver[];
  radiusM: number;
  /** Height above the ground that must be seen (0 = the ground; a smoke column ~30 m). */
  targetM: number;
  cellM: number;
  maxCells: number;
  terrainUrl?: string;
}

export interface ViewshedObserverStats extends ObserverInfo {
  id?: string;
  areaM2: number;
  cells: number;
}

export interface ViewshedData {
  width: number;
  height: number;
  mx0: number;
  my0: number;
  cell: number;
  counts: Uint8Array;
  observers: ViewshedObserverStats[];
  radiusM: number;
  tiles: TileStats;
  ms: { terrain: number; compute: number; total: number };
}

interface TowerFeature {
  geometry: { coordinates: [number, number] };
  properties: { i: string; n: string; k: string; s: string };
}

type PeakRow = [string, number, number, number];

const now = () => performance.now();

export class TerrainEngine {
  #engine: Engine;
  #towers = new Map<string, Promise<TowerFeature[]>>();
  #peakIndex = new Map<string, Promise<Set<string>>>();
  #peakCells = new Map<string, Promise<PeakRow[]>>();

  private constructor(engine: Engine) {
    this.#engine = engine;
  }

  /** In the browser: fetch and compile the WASM next to this module. */
  static async create(): Promise<TerrainEngine> {
    await init();
    return new TerrainEngine(new Engine(MAX_TILES));
  }

  /** Under Node: from the .wasm bytes. */
  static fromBytes(bytes: BufferSource): TerrainEngine {
    initSync({ module: bytes });
    return new TerrainEngine(new Engine(MAX_TILES));
  }

  /** Make sure the tiles are decoded and cached. Failed tiles are recorded as missing. */
  async ensureTiles(keys: TileKey[], template: string | undefined, onProgress?: OnProgress): Promise<TileStats> {
    const e = this.#engine;
    e.begin();
    const missing = keys.filter((k) => {
      const [z, x, y] = k.split('/').map(Number) as [number, number, number];
      return !e.hasTile(z, x, y);
    });
    const stats: TileStats = { needed: keys.length, fetched: 0, failed: 0, bytes: 0 };
    let done = keys.length - missing.length;
    onProgress?.({ phase: 'terrain', done, total: keys.length });
    let next = 0;
    const worker = async () => {
      while (next < missing.length) {
        const key = missing[next++]!;
        const [z, x, y] = key.split('/').map(Number) as [number, number, number];
        let bytes: Uint8Array | null = null;
        for (let attempt = 0; attempt < 2 && !bytes; attempt++) {
          try {
            const res = await fetch(tileUrl(key, template), { signal: AbortSignal.timeout(30_000) });
            if (res.ok) bytes = new Uint8Array(await res.arrayBuffer());
            else if (res.status === 404 || res.status === 403) break; // no tile there (open sea)
          } catch {
            /* retry once, then give up on this tile */
          }
        }
        try {
          if (!bytes) throw new Error('not loaded');
          e.addTile(z, x, y, bytes);
          stats.fetched++;
          stats.bytes += bytes.byteLength;
        } catch {
          e.addMissingTile(z, x, y);
          stats.failed++;
        }
        onProgress?.({ phase: 'terrain', done: ++done, total: keys.length });
      }
    };
    await Promise.all(Array.from({ length: Math.min(FETCH_CONCURRENCY, missing.length) }, worker));
    return stats;
  }

  towers(base: string): Promise<TowerFeature[]> {
    let p = this.#towers.get(base);
    if (!p) {
      p = fetch(`${base}data/towers.geojson`)
        .then((r) => (r.ok ? r.json() : { features: [] }))
        .then((g: { features?: TowerFeature[] }) => g.features ?? [])
        .catch(() => []);
      this.#towers.set(base, p);
    }
    return p;
  }

  async peaksNear(base: string, lat: number, lon: number, radiusM: number): Promise<PeakRow[]> {
    let idx = this.#peakIndex.get(base);
    if (!idx) {
      idx = fetch(`${base}data/peaks/index.json`)
        .then((r) => (r.ok ? r.json() : { cells: [] }))
        .then((j: { cells?: string[] }) => new Set(j.cells ?? []))
        .catch(() => new Set<string>());
      this.#peakIndex.set(base, idx);
    }
    const cells = await idx;
    const dlat = (radiusM / 111_000) * 1.01;
    const dlon = dlat / Math.max(Math.cos(((Math.abs(lat) + dlat) * Math.PI) / 180), 0.05);
    const wanted: string[] = [];
    for (let a = Math.floor(lat - dlat); a <= Math.floor(lat + dlat); a++) {
      for (let o = Math.floor(lon - dlon); o <= Math.floor(lon + dlon); o++) {
        const key = `${a}_${o}`;
        if (cells.has(key)) wanted.push(key);
      }
    }
    const rows = await Promise.all(
      wanted.map((key) => {
        const url = `${base}data/peaks/${key}.json`;
        let p = this.#peakCells.get(url);
        if (!p) {
          p = fetch(url)
            .then((r) => (r.ok ? (r.json() as Promise<PeakRow[]>) : []))
            .catch(() => []);
          this.#peakCells.set(url, p);
        }
        return p;
      }),
    );
    return rows.flat().filter((r) => distanceM(lat, lon, r[1], r[2]) <= radiusM);
  }

  async panorama(req: PanoramaRequest, onProgress?: OnProgress): Promise<PanoramaData> {
    const t0 = now();
    const levels = panoramaLevels(req.maxDistM, req.detail);
    const keys = planTiles([req], levels);
    const tiles = await this.ensureTiles(keys, req.terrainUrl, onProgress);
    const t1 = now();

    const labels = req.labels !== false;
    onProgress?.({ phase: 'names', done: 0, total: 1 });
    const [peakRows, towerList] = labels
      ? await Promise.all([this.peaksNear(req.base, req.lat, req.lon, req.maxDistM), this.towers(req.base)])
      : [[] as PeakRow[], [] as TowerFeature[]];
    const others = towerList.filter((f) => {
      if (f.properties.i === req.selfId) return false;
      const [lon, lat] = f.geometry.coordinates;
      const d = distanceM(req.lat, req.lon, lat, lon);
      return d > 150 && d <= req.maxDistM;
    });
    const t2 = now();

    onProgress?.({ phase: 'computing', done: 0, total: 1 });
    const extra = req.extra ?? [];
    const targets = new Float64Array((extra.length + others.length + peakRows.length) * 4);
    let i = 0;
    for (const x of extra) targets.set([x.lat, x.lon, x.aboveGroundM, 0], 4 * i++);
    for (const f of others) {
      const [lon, lat] = f.geometry.coordinates;
      targets.set([lat, lon, typicalFloor(f.properties.k, lon).floorM + EYE_ABOVE_FLOOR_M, 30], 4 * i++);
    }
    for (const p of peakRows) targets.set([p[1], p[2], 0, PEAK_SNAP_M], 4 * i++);

    const r = this.#engine.panorama(
      req.lat,
      req.lon,
      req.eyeAboveGroundM,
      SNAP_M,
      flatLevels(levels),
      req.azStepDeg,
      req.maxDistM,
      REFRACTION_K,
      targets,
    );
    const t3 = now();
    const ob = r.observer;
    const tv = r.targets;
    const sight = (k: number, name: string, lat: number, lon: number): Sighted => ({
      name,
      lat,
      lon,
      distM: tv[6 * k]!,
      az: tv[6 * k + 1]!,
      groundM: tv[6 * k + 2]!,
      angle: tv[6 * k + 3]!,
      clearance: tv[6 * k + 4]!,
      visible: tv[6 * k + 5] === 1,
    });
    let k = 0;
    const extraOut = extra.map((x) => sight(k++, 'extra', x.lat, x.lon));
    const lookouts: LookoutSight[] = others.map((f) => {
      const [lon, lat] = f.geometry.coordinates;
      return { ...sight(k++, f.properties.n, lat, lon), id: f.properties.i, kind: f.properties.k, status: f.properties.s };
    });
    const peaks: PeakSight[] = [];
    for (const p of peakRows) {
      const s = sight(k++, p[0], p[1], p[2]);
      if (s.visible) peaks.push({ ...s, gnisId: p[3] });
    }
    const out: PanoramaData = {
      columns: r.columns,
      azStep: r.azStepDeg,
      layersM: r.layersM,
      horizon: r.horizonDeg,
      crest: r.crestM,
      skyline: r.skylineM,
      observer: { lat: ob[0]!, lon: ob[1]!, groundM: ob[2]!, eyeM: ob[3]!, movedM: ob[4]!, recordedGroundM: ob[5]! },
      peaks,
      lookouts,
      extra: extraOut,
      peaksChecked: peakRows.length,
      nodataFraction: r.nodataFraction,
      samples: r.samples,
      tiles,
      ms: { terrain: t1 - t0, names: t2 - t1, compute: t3 - t2, total: t3 - t0 },
    };
    r.free();
    return out;
  }

  async viewshed(req: ViewshedRequest, onProgress?: OnProgress): Promise<ViewshedData> {
    const t0 = now();
    const levels: Level[] = viewshedLevels(req.radiusM);
    const keys = planTiles(req.observers, levels);
    const tiles = await this.ensureTiles(keys, req.terrainUrl, onProgress);
    const t1 = now();
    onProgress?.({ phase: 'computing', done: 0, total: req.observers.length });
    const obs = Float64Array.from(req.observers.flatMap((o) => [o.lat, o.lon, o.eyeAboveGroundM, SNAP_M]));
    const r = this.#engine.viewshed(obs, flatLevels(levels), req.radiusM, req.targetM, REFRACTION_K, req.cellM, req.maxCells);
    const t2 = now();
    const ov = r.observers;
    const observers: ViewshedObserverStats[] = req.observers.map((o, i) => ({
      id: o.id,
      lat: ov[9 * i]!,
      lon: ov[9 * i + 1]!,
      groundM: ov[9 * i + 2]!,
      eyeM: ov[9 * i + 3]!,
      movedM: ov[9 * i + 4]!,
      recordedGroundM: NaN,
      areaM2: ov[9 * i + 5]!,
      cells: ov[9 * i + 6]!,
    }));
    const out: ViewshedData = {
      width: r.width,
      height: r.height,
      mx0: r.mx0,
      my0: r.my0,
      cell: r.cell,
      counts: r.counts,
      observers,
      radiusM: req.radiusM,
      tiles,
      ms: { terrain: t1 - t0, compute: t2 - t1, total: t2 - t0 },
    };
    r.free();
    return out;
  }
}
