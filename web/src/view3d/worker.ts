/// <reference lib="webworker" />
/**
 * The terrain Web Worker: one engine (WASM plus tile cache) per page, requests served one at
 * a time so a request never has its tiles evicted by another.
 */
import { TerrainEngine, type PanoramaData, type PanoramaRequest, type Progress, type ViewshedData, type ViewshedRequest } from './engine.ts';

export type WorkerRequest =
  | { id: number; type: 'panorama'; req: PanoramaRequest }
  | { id: number; type: 'viewshed'; req: ViewshedRequest };

export type WorkerReply =
  | { id: number; type: 'progress'; progress: Progress }
  | { id: number; type: 'panorama'; result: PanoramaData }
  | { id: number; type: 'viewshed'; result: ViewshedData }
  | { id: number; type: 'error'; message: string };

declare const self: DedicatedWorkerGlobalScope;

let engine: Promise<TerrainEngine> | null = null;
let queue: Promise<unknown> = Promise.resolve();

self.onmessage = (e: MessageEvent<WorkerRequest>) => {
  const msg = e.data;
  queue = queue.then(async () => {
    const progress = (p: Progress): void => self.postMessage({ id: msg.id, type: 'progress', progress: p } satisfies WorkerReply);
    try {
      if (!engine) {
        progress({ phase: 'engine', done: 0, total: 1 });
        engine = TerrainEngine.create();
      }
      const eng = await engine;
      if (msg.type === 'panorama') {
        const result = await eng.panorama(msg.req, progress);
        const transfer = [result.layersM.buffer, result.horizon.buffer, result.crest.buffer, result.skyline.buffer] as ArrayBuffer[];
        self.postMessage({ id: msg.id, type: 'panorama', result } satisfies WorkerReply, transfer);
      } else {
        const result = await eng.viewshed(msg.req, progress);
        self.postMessage({ id: msg.id, type: 'viewshed', result } satisfies WorkerReply, [result.counts.buffer as ArrayBuffer]);
      }
    } catch (err) {
      // If the engine itself failed to start, let the next request try again.
      if (engine) await engine.catch(() => (engine = null));
      self.postMessage({ id: msg.id, type: 'error', message: err instanceof Error ? err.message : String(err) } satisfies WorkerReply);
    }
  });
};
