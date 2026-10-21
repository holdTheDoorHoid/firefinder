/**
 * What the view from the cab remembers between visits (localStorage, every access wrapped:
 * blocked storage only means nothing is remembered) and whether this device can draw the
 * satellite view. Tiny on purpose: tower pages read it before any 3D code loads.
 */
import type { CabMode } from './earth-geo.ts';

const MODE_KEY = 'firefinder.cab-view';
const FRAME_KEY = 'firefinder.cab-frame';

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* storage blocked: the choice lasts for this page only */
  }
}

/** The visitor's last choice of view ("satellite" or "drawn"), if any. */
export function storedCabMode(): string | null {
  return read(MODE_KEY);
}

export function saveCabMode(mode: CabMode): void {
  write(MODE_KEY, mode);
}

/** Whether the cab's window frame is drawn over the satellite view (off unless switched on). */
export function storedFrame(): boolean {
  return read(FRAME_KEY) === '1';
}

export function saveFrame(on: boolean): void {
  write(FRAME_KEY, on ? '1' : '0');
}

/** A cheap first guess (no WebGL context is made): the browser knows WebGL 2. */
export function webgl2Likely(): boolean {
  return typeof WebGL2RenderingContext !== 'undefined';
}

let works: boolean | null = null;

/** Whether this device really gives a WebGL 2 context (checked once, the context released). */
export function webgl2Works(): boolean {
  if (works !== null) return works;
  try {
    const gl = document.createElement('canvas').getContext('webgl2');
    works = !!gl;
    gl?.getExtension('WEBGL_lose_context')?.loseContext();
  } catch {
    works = false;
  }
  return works;
}

/**
 * Whether the satellite view asks before downloading its photos: on phones and tablets (no
 * mouse or trackpad, or a small screen), which are the devices most often on metered data, and
 * wherever the browser says the visitor wants to save data. Computers load it straight away.
 */
export function askBeforeSatellite(): boolean {
  try {
    const c = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection;
    if (c?.saveData) return true;
    if (!matchMedia('(any-pointer: fine)').matches) return true;
    const side = Math.min(screen.width, screen.height);
    return side > 0 && side < 600; // some embedded browsers report a screen of 0
  } catch {
    return window.innerWidth < 600;
  }
}

/** The key that turns the wheel into a zoom: ⌘ on Apple devices, Ctrl elsewhere. */
export function zoomKeys(): string {
  return /Mac|iPhone|iPad|iPod/.test(navigator.platform || navigator.userAgent) ? '⌘' : 'Ctrl';
}
