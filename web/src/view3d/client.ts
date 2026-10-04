/**
 * Main-thread access to the terrain worker. The worker (and its ~200 KB of WebAssembly) is
 * only created the first time someone asks for a view.
 */
import type { PanoramaData, PanoramaRequest, Progress, ViewshedData, ViewshedRequest } from './engine.ts';
import type { WorkerReply, WorkerRequest } from './worker.ts';

let worker: Worker | null = null;
let seq = 0;
const pending = new Map<number, { resolve: (v: never) => void; reject: (e: Error) => void; progress?: (p: Progress) => void }>();

function getWorker(): Worker {
  if (worker) return worker;
  worker = new Worker(new URL('./worker.ts', import.meta.url), { type: 'module', name: 'firefinder-terrain' });
  worker.onmessage = (e: MessageEvent<WorkerReply>) => {
    const msg = e.data;
    const p = pending.get(msg.id);
    if (!p) return;
    if (msg.type === 'progress') {
      p.progress?.(msg.progress);
      return;
    }
    pending.delete(msg.id);
    if (msg.type === 'error') p.reject(new Error(msg.message));
    else p.resolve(msg.result as never);
  };
  worker.onerror = (e) => {
    for (const p of pending.values()) p.reject(new Error(e.message || 'The terrain worker stopped.'));
    pending.clear();
    worker?.terminate();
    worker = null;
  };
  return worker;
}

function call<T>(msg: Omit<WorkerRequest, 'id'>, progress?: (p: Progress) => void): Promise<T> {
  const id = ++seq;
  return new Promise<T>((resolve, reject) => {
    pending.set(id, { resolve: resolve as (v: never) => void, reject, progress });
    getWorker().postMessage({ ...msg, id } as WorkerRequest);
  });
}

export function requestPanorama(req: PanoramaRequest, progress?: (p: Progress) => void): Promise<PanoramaData> {
  return call<PanoramaData>({ type: 'panorama', req }, progress);
}

export function requestViewshed(req: ViewshedRequest, progress?: (p: Progress) => void): Promise<ViewshedData> {
  return call<ViewshedData>({ type: 'viewshed', req }, progress);
}

/** Absolute URL of the site root, for the worker's fetches. */
export function siteBase(): string {
  return new URL(import.meta.env.BASE_URL, location.href).href;
}

/** One line for a progress message. */
export function progressText(p: Progress): string {
  switch (p.phase) {
    case 'engine':
      return 'Starting the terrain engine…';
    case 'terrain':
      return `Loading terrain: ${p.done} of ${p.total} tiles…`;
    case 'names':
      return 'Looking up peak names and nearby lookouts…';
    case 'computing':
      return 'Tracing lines of sight…';
  }
}
