/**
 * Main-thread side of the old topo maps: a MapLibre custom protocol ("fftopo://z/x/y?era=…")
 * whose tiles are drawn by the worker (worker.ts), and a query for which sheets are in view.
 */
import { addProtocol } from 'maplibre-gl';
import type { Era } from './sheets.ts';

export const PROTOCOL = 'fftopo';

export interface SheetInView {
  name: string;
  scale: number;
  year: number;
  imprint: number | null;
  state: string;
  /** Share of the view this sheet covers (0..1, sampled). */
  share: number;
}

export interface InView {
  sheets: SheetInView[];
  /** True when zoomed out too far for the old maps to draw. */
  tooFar: boolean;
  failed: boolean;
}

type Pending = { resolve: (v: unknown) => void; reject: (e: Error) => void };

let worker: Worker | null = null;
let nextId = 1;
const pending = new Map<number, Pending>();
let registered = false;
const failureListeners = new Set<(f: { index: number; sheets: number }) => void>();

function getWorker(): Worker {
  if (worker) return worker;
  worker = new Worker(new URL('./worker.ts', import.meta.url), { type: 'module', name: 'firefinder-old-topo' });
  worker.onmessage = (e: MessageEvent) => {
    const m = e.data;
    if (m?.failures) for (const l of failureListeners) l(m.failures);
    const p = pending.get(m?.id);
    if (!p) return;
    pending.delete(m.id);
    if (m.error) p.reject(new Error(m.error));
    else p.resolve(m);
  };
  worker.onerror = () => {
    for (const p of pending.values()) p.reject(new Error('The old-maps worker stopped'));
    pending.clear();
    worker = null;
  };
  return worker;
}

function ask<T>(message: Record<string, unknown>, abort?: AbortController): Promise<T> {
  const id = nextId++;
  const w = getWorker();
  return new Promise<T>((resolve, reject) => {
    pending.set(id, { resolve: resolve as (v: unknown) => void, reject });
    abort?.signal.addEventListener('abort', () => {
      w.postMessage({ type: 'abort', id });
      pending.delete(id);
      reject(new DOMException('Aborted', 'AbortError'));
    });
    w.postMessage({ ...message, id });
  });
}

async function blankTile(): Promise<ImageBitmap> {
  return createImageBitmap(new ImageData(256, 256));
}

/** Registers the fftopo:// protocol once. */
export function registerOldTopo(): void {
  if (registered) return;
  registered = true;
  addProtocol(PROTOCOL, async (params, abort) => {
    const m = /^fftopo:\/\/(\d+)\/(\d+)\/(\d+)(?:\?era=([a-z]+))?/.exec(params.url);
    if (!m) throw new Error(`bad old-topo tile url ${params.url}`);
    const r = await ask<{ bitmap: ImageBitmap | null }>({ type: 'tile', z: Number(m[1]), x: Number(m[2]), y: Number(m[3]), era: m[4] ?? 'lookouts' }, abort);
    return { data: r.bitmap ?? (await blankTile()) };
  });
}

export function oldTopoTiles(era: Era): string[] {
  return [`${PROTOCOL}://{z}/{x}/{y}?era=${era}`];
}

export function sheetsInView(bbox: [number, number, number, number], zoom: number, era: Era): Promise<InView> {
  return ask<InView>({ type: 'inview', bbox, zoom, era });
}

/** Called with running totals of sheet-index and sheet failures (to tell the visitor). */
export function onOldTopoFailures(cb: (f: { index: number; sheets: number }) => void): () => void {
  failureListeners.add(cb);
  return () => failureListeners.delete(cb);
}
