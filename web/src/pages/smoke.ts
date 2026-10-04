/**
 * "Spot the smoke": a short lesson in cross-shots. Two real lookouts, a smoke placed on ground
 * both can see (worked out with the viewshed engine), a panorama from each with the smoke in
 * it, and a map where the two bearing lines cross.
 */
import 'maplibre-gl/dist/maplibre-gl.css';
import '../styles/view3d.css';
import '../styles/smoke.css';
import { AttributionControl, Map as MlMap, NavigationControl, setWorkerUrl, type GeoJSONSource } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import { html } from '../lib/html.ts';
import type { TowerCollection, TowerFeature, TowerRecord } from '../lib/types.ts';
import { BOLD_FONT, LABEL_FONT, loadBaseStyle } from '../map/style.ts';
import { initChecklistOnPage } from '../ui/checklist-ui.ts';
import { initCommon } from '../ui/common.ts';
import { effectiveTheme, onThemeChange } from '../ui/theme.ts';
import { progressText, requestViewshed } from '../view3d/client.ts';
import { angleDiff, azimuthText, eyeHeight, milesKm, quadrantBearing, wrap360 } from '../view3d/describe.ts';
import { PanoramaView } from '../view3d/panorama-view.ts';
import { crossing, cutAngle, halfDegree, scoreFor, type LatLon } from '../view3d/smoke-geo.ts';
import { bearingDeg, destination, distanceM } from '../view3d/tiles.ts';

const BASE = import.meta.env.BASE_URL;
const $ = <T extends HTMLElement>(sel: string) => document.querySelector<T>(sel)!;

interface Lookout extends LatLon {
  id: string;
  name: string;
  kind: string;
  status: string;
  heightM: number | null;
  elevationM: number | null;
}

interface Round {
  a: Lookout;
  b: Lookout;
  fire: LatLon;
  readings: (number | null)[];
  hints: number;
}

interface Feat {
  type: 'Feature';
  properties: Record<string, unknown>;
  geometry: { type: 'Point'; coordinates: [number, number] } | { type: 'LineString'; coordinates: [number, number][] };
}
interface FC {
  type: 'FeatureCollection';
  features: Feat[];
}

const SMOKE_HEIGHT_M = 600;
const VIEW_RANGE_M = 60_000;

function shuffle<T>(xs: T[]): T[] {
  const a = [...xs];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j]!, a[i]!];
  }
  return a;
}

const ll = (f: TowerFeature): LatLon => ({ lat: f.geometry.coordinates[1], lon: f.geometry.coordinates[0] });

/** Standing lookouts with a partner 12–32 km away, in a cluster of at least three. */
function pickPairs(features: TowerFeature[], n: number): [TowerFeature, TowerFeature][] {
  const standing = features.filter((f) => f.properties.s === 'standing');
  const out: [TowerFeature, TowerFeature][] = [];
  for (const a of shuffle(standing)) {
    const pa = ll(a);
    const near = features.filter((f) => f !== a && Math.abs(f.geometry.coordinates[1] - pa.lat) < 0.4 && distanceM(pa.lat, pa.lon, ll(f).lat, ll(f).lon) < 35_000);
    if (near.length < 2) continue;
    const partners = near.filter((f) => {
      if (f.properties.s !== 'standing') return false;
      const d = distanceM(pa.lat, pa.lon, ll(f).lat, ll(f).lon);
      return d >= 12_000 && d <= 32_000;
    });
    if (!partners.length) continue;
    out.push([a, partners[Math.floor(Math.random() * partners.length)]!]);
    if (out.length >= n) break;
  }
  return out;
}

async function lookout(f: TowerFeature): Promise<Lookout> {
  let rec: TowerRecord | null = null;
  try {
    const r = await fetch(`${BASE}data/t/${f.properties.i}.json`);
    if (r.ok) rec = (await r.json()) as TowerRecord;
  } catch {
    /* typical height then */
  }
  return {
    id: f.properties.i,
    name: f.properties.n,
    kind: f.properties.k,
    status: f.properties.s,
    lat: f.geometry.coordinates[1],
    lon: f.geometry.coordinates[0],
    heightM: rec?.height_m ?? null,
    elevationM: rec?.elevation_m ?? null,
  };
}

function lonLat(mx: number, my: number): LatLon {
  return { lon: (mx - 0.5) * 360, lat: (Math.atan(Math.sinh((0.5 - my) * 2 * Math.PI)) * 180) / Math.PI };
}

/** A smoke on ground both lookouts see, 4–28 km from each, where the lines cut well. */
async function placeSmoke(a: Lookout, b: Lookout, onStatus: (s: string) => void): Promise<LatLon | null> {
  const eye = (l: Lookout) => eyeHeight({ kind: l.kind, height_m: l.heightM, lon: l.lon }).eyeM;
  const v = await requestViewshed(
    {
      observers: [
        { lat: a.lat, lon: a.lon, eyeAboveGroundM: eye(a) },
        { lat: b.lat, lon: b.lon, eyeAboveGroundM: eye(b) },
      ],
      radiusM: 30_000,
      targetM: 0,
      cellM: 120,
      maxCells: 1_200_000,
    },
    (p) => onStatus(p.phase === 'terrain' ? `Finding ground both lookouts can see. ${progressText(p)}` : 'Finding ground both lookouts can see…'),
  );
  const spots: LatLon[] = [];
  for (let i = 0; i < v.counts.length; i++) {
    if (v.counts[i]! < 2) continue;
    const x = i % v.width;
    const y = Math.floor(i / v.width);
    const p = lonLat(v.mx0 + (x + 0.2 + Math.random() * 0.6) * v.cell, v.my0 + (y + 0.2 + Math.random() * 0.6) * v.cell);
    const da = distanceM(a.lat, a.lon, p.lat, p.lon);
    const db = distanceM(b.lat, b.lon, p.lat, p.lon);
    if (da < 4_000 || db < 4_000 || da > 28_000 || db > 28_000) continue;
    const cut = cutAngle(a, b, p);
    if (cut < 35 || cut > 145) continue;
    spots.push(p);
  }
  if (spots.length < 10) return null;
  return spots[Math.floor(Math.random() * spots.length)]!;
}

/* ---------- The Firefinder ring ---------- */

function ringSvg(): string {
  const ticks: string[] = [];
  for (let a = 0; a < 360; a += 5) {
    const long = a % 30 === 0;
    const r1 = long ? 40 : 43;
    const t = ((a - 90) * Math.PI) / 180;
    ticks.push(`<line x1="${(50 + r1 * Math.cos(t)).toFixed(2)}" y1="${(50 + r1 * Math.sin(t)).toFixed(2)}" x2="${(50 + 46 * Math.cos(t)).toFixed(2)}" y2="${(50 + 46 * Math.sin(t)).toFixed(2)}" stroke-width="${long ? 1.4 : 0.8}"/>`);
  }
  const labels = [0, 90, 180, 270]
    .map((a) => {
      const t = ((a - 90) * Math.PI) / 180;
      return `<text x="${(50 + 33 * Math.cos(t)).toFixed(2)}" y="${(50 + 33 * Math.sin(t) + 3.5).toFixed(2)}">${a === 0 ? 'N' : a === 90 ? 'E' : a === 180 ? 'S' : 'W'}</text>`;
    })
    .join('');
  // The sights turn on the ring: the pointed front sight toward the smoke, the slotted rear
  // sight at the lookout's eye.
  return `<svg viewBox="0 0 100 100" width="132" height="132" class="ring-svg">
    <circle cx="50" cy="50" r="47" class="ring-rim"/>
    <circle cx="50" cy="50" r="38" class="ring-map"/>
    <g class="ring-ticks">${ticks.join('')}</g>
    <g class="ring-labels">${labels}</g>
    <g class="ring-sight" data-sight>
      <line x1="50" y1="88" x2="50" y2="14" class="ring-bar"/>
      <path d="M50 3 55 13H45Z" class="ring-front"/>
      <rect x="47" y="86" width="6" height="8" rx="1" class="ring-rear"/>
    </g>
    <circle cx="50" cy="50" r="2.6" class="ring-pin"/>
  </svg>`;
}

/* ---------- Map ---------- */

class LessonMap {
  map: MlMap | null = null;
  #theme = effectiveTheme();
  #data = { points: fc([]), lines: fc([]), result: fc([]) };

  async init(el: HTMLElement): Promise<void> {
    setWorkerUrl(workerUrl);
    const { style } = await loadBaseStyle(this.#theme);
    try {
      this.map = new MlMap({ container: el, style, center: [-115, 45], zoom: 6, attributionControl: false, dragRotate: false, pitchWithRotate: false });
    } catch {
      el.innerHTML = '<p class="notice tone-caution">The map needs WebGL, which is switched off in this browser. The result is given in words below.</p>';
      this.map = null;
      return;
    }
    const m = this.map;
    m.touchZoomRotate.disableRotation();
    m.addControl(new AttributionControl({ compact: true }), 'bottom-right');
    m.addControl(new NavigationControl({ showCompass: false }), 'top-right');
    m.on('style.load', () => this.#install());
    onThemeChange(async (t) => {
      if (t === this.#theme) return;
      this.#theme = t;
      m.setStyle((await loadBaseStyle(t)).style, { diff: false });
    });
  }

  #install(): void {
    const m = this.map!;
    const dark = this.#theme === 'dark';
    const ink = dark ? '#e9e5d9' : '#1c2620';
    const paper = dark ? '#121915' : '#fbf8f1';
    const ember = dark ? '#ffa577' : '#a9441b';
    for (const [id, data] of Object.entries(this.#data)) {
      if (!m.getSource(`lesson-${id}`)) m.addSource(`lesson-${id}`, { type: 'geojson', data: data as never });
    }
    const add = (layer: Parameters<MlMap['addLayer']>[0]) => {
      if (!m.getLayer(layer.id)) m.addLayer(layer);
    };
    add({ id: 'lesson-line-a', type: 'line', source: 'lesson-lines', filter: ['==', ['get', 'who'], 'A'], paint: { 'line-color': ink, 'line-width': 2.5 } });
    add({ id: 'lesson-line-b', type: 'line', source: 'lesson-lines', filter: ['==', ['get', 'who'], 'B'], paint: { 'line-color': ink, 'line-width': 2.5, 'line-dasharray': [2.5, 1.6] } });
    add({ id: 'lesson-line-true', type: 'line', source: 'lesson-lines', filter: ['==', ['get', 'who'], 'true'], paint: { 'line-color': ember, 'line-width': 1.2, 'line-dasharray': [1, 2], 'line-opacity': 0.8 } });
    add({ id: 'lesson-pts', type: 'circle', source: 'lesson-points', paint: { 'circle-radius': 12, 'circle-color': ink, 'circle-stroke-color': paper, 'circle-stroke-width': 2.5 } });
    add({
      id: 'lesson-pts-label',
      type: 'symbol',
      source: 'lesson-points',
      layout: { 'text-field': ['get', 'letter'], 'text-font': BOLD_FONT, 'text-size': 13, 'text-allow-overlap': true },
      paint: { 'text-color': paper },
    });
    add({
      id: 'lesson-pts-name',
      type: 'symbol',
      source: 'lesson-points',
      layout: { 'text-field': ['get', 'name'], 'text-font': LABEL_FONT, 'text-size': 12, 'text-offset': [0, 1.5], 'text-anchor': 'top', 'text-max-width': 10 },
      paint: { 'text-color': ink, 'text-halo-color': paper, 'text-halo-width': 1.6 },
    });
    add({
      id: 'lesson-result',
      type: 'circle',
      source: 'lesson-result',
      paint: {
        'circle-radius': ['match', ['get', 'kind'], 'fire', 9, 7],
        'circle-color': ['match', ['get', 'kind'], 'fire', ember, 'rgba(0,0,0,0)'],
        'circle-stroke-color': ['match', ['get', 'kind'], 'fire', paper, ink],
        'circle-stroke-width': ['match', ['get', 'kind'], 'fire', 2.5, 3],
      },
    });
    add({
      id: 'lesson-result-label',
      type: 'symbol',
      source: 'lesson-result',
      layout: {
        'text-field': ['get', 'label'],
        'text-font': BOLD_FONT,
        'text-size': 13,
        // The fire's name to its upper right, the fix's to its lower left, so they never overlap.
        'text-anchor': ['match', ['get', 'kind'], 'fire', 'bottom-left', 'top-right'],
        'text-offset': ['match', ['get', 'kind'], 'fire', ['literal', [0.7, -0.5]], ['literal', [-0.7, 0.5]]],
        'text-allow-overlap': true,
      },
      paint: { 'text-color': ['match', ['get', 'kind'], 'fire', ember, ink], 'text-halo-color': paper, 'text-halo-width': 2 },
    });
  }

  set(kind: 'points' | 'lines' | 'result', data: FC): void {
    this.#data[kind] = data;
    (this.map?.getSource(`lesson-${kind}`) as GeoJSONSource | undefined)?.setData(data as never);
  }

  /** Show these points, with `bufferM` of country around each (where the lines will run). */
  fit(points: LatLon[], bufferM = 0): void {
    if (!this.map || !points.length) return;
    const all = bufferM ? points.flatMap((p) => [0, 90, 180, 270].map((b) => destination(p.lat, p.lon, b, bufferM))).map(([lat, lon]) => ({ lat, lon })) : points;
    const lats = all.map((p) => p.lat);
    const lons = all.map((p) => p.lon);
    this.map.fitBounds([Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)], {
      padding: { top: 40, left: 40, right: 50, bottom: 50 },
      duration: 700,
      maxZoom: 11,
    });
  }
}

function fc(features: Feat[]): FC {
  return { type: 'FeatureCollection', features };
}
function point(p: LatLon, props: Record<string, unknown>): Feat {
  return { type: 'Feature', properties: props, geometry: { type: 'Point', coordinates: [p.lon, p.lat] } };
}
function ray(from: LatLon, bearing: number, lengthM: number, props: Record<string, unknown>): Feat {
  const coords: [number, number][] = [];
  for (let d = 0; d <= lengthM; d += lengthM / 40) {
    const [lat, lon] = destination(from.lat, from.lon, bearing, d);
    coords.push([lon, lat]);
  }
  return { type: 'Feature', properties: props, geometry: { type: 'LineString', coordinates: coords } };
}

/* ---------- The lesson ---------- */

async function main(): Promise<void> {
  initCommon();
  initChecklistOnPage();
  const status = $('[data-status]');
  const hint = $('[data-hint]');
  const title = $('[data-view-title]');
  const host = $('[data-view-host]');
  const reading = $('[data-reading]');
  const take = $<HTMLButtonElement>('[data-take]');
  const hintBtn = $<HTMLButtonElement>('[data-hint-btn]');
  const result = $('[data-result]');
  const mapKey = $('[data-map-key]');
  $('[data-ring]').innerHTML = ringSvg();
  const sight = document.querySelector<SVGGElement>('[data-sight]')!;

  const lessonMap = new LessonMap();
  void lessonMap.init($('[data-map]'));

  let towers: TowerFeature[];
  try {
    const res = await fetch(`${BASE}data/towers.geojson`);
    towers = ((await res.json()) as TowerCollection).features;
  } catch {
    status.textContent = 'The lookouts could not be loaded. Check your connection and reload the page.';
    return;
  }

  let round: Round | null = null;
  let step = 0;
  let view: PanoramaView | null = null;

  const setStep = (n: number) => {
    step = n;
    for (const li of document.querySelectorAll<HTMLElement>('[data-steps] li')) {
      const s = Number(li.dataset.step);
      if (s === n) li.setAttribute('aria-current', 'step');
      else li.removeAttribute('aria-current');
      li.classList.toggle('is-done', s < n);
    }
  };

  const showReading = (az: number) => {
    reading.textContent = azimuthText(halfDegree(az), 1);
    sight.setAttribute('transform', `rotate(${az.toFixed(2)} 50 50)`);
  };

  const mapPoints = (r: Round) =>
    lessonMap.set('points', fc([point(r.a, { letter: 'A', name: r.a.name }), point(r.b, { letter: 'B', name: r.b.name })]));

  const mapLines = (r: Round, withTruth: boolean) => {
    const lines: Feat[] = [];
    r.readings.forEach((az, i) => {
      if (az === null) return;
      const from = i === 0 ? r.a : r.b;
      lines.push(ray(from, az, 45_000, { who: i === 0 ? 'A' : 'B' }));
      if (withTruth) lines.push(ray(from, bearingDeg(from.lat, from.lon, r.fire.lat, r.fire.lon), distanceM(from.lat, from.lon, r.fire.lat, r.fire.lon), { who: 'true' }));
    });
    lessonMap.set('lines', fc(lines));
  };

  const sightFrom = async (who: 0 | 1) => {
    const r = round!;
    const l = who === 0 ? r.a : r.b;
    setStep(who);
    view?.destroy();
    take.disabled = true;
    title.textContent = `From ${l.name} (lookout ${who === 0 ? 'A' : 'B'})`;
    hint.textContent =
      who === 0
        ? 'Somewhere in the circle there is a smoke. Turn the view (drag it, or use the arrow keys; Shift turns faster) until the orange sighting hair sits on the base of the smoke, then take the reading.'
        : `Now the second lookout. ${l.name} sees the same smoke from another side. Find it, sight it and take the reading.`;
    const trueAz = bearingDeg(l.lat, l.lon, r.fire.lat, r.fire.lon);
    const start = wrap360(trueAz + (Math.random() < 0.5 ? -1 : 1) * (60 + Math.random() * 100));
    view = new PanoramaView(host, {
      tower: { id: l.id, name: l.name, lat: l.lat, lon: l.lon, kind: l.kind, status: l.status, height_m: l.heightM, elevation_m: l.elevationM },
      maxDistM: VIEW_RANGE_M,
      initialAz: start,
      lists: false,
      eyeControl: false,
      stepDeg: 0.5,
      smoke: { lat: r.fire.lat, lon: r.fire.lon, heightM: SMOKE_HEIGHT_M },
      onTurn: showReading,
      onReady: () => {
        take.disabled = false;
        status.textContent = `You are in the cab of ${l.name}, facing ${quadrantBearing(start)}. Find the smoke.`;
      },
    });
    showReading(start);
    hintBtn.hidden = false;
    hintBtn.disabled = false;
    view.el.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.target as Element).closest('.pv-viewport') && !take.disabled) {
        e.preventDefault();
        take.click();
      }
    });
    await view.start();
  };

  hintBtn.addEventListener('click', () => {
    const az = view?.smokeAz;
    if (az === null || az === undefined || !view) return;
    // Near it, not on it: the last few degrees are the lookout's job.
    const off = (Math.random() < 0.5 ? -1 : 1) * (3 + Math.random() * 4);
    view.turnTo(az + off, true);
    hintBtn.disabled = true;
    if (round) round.hints++;
    status.textContent = 'The smoke is within a few degrees of the sight now. Line the hair up on its base.';
    view.el.querySelector<HTMLElement>('.pv-viewport')?.focus({ preventScroll: true });
  });

  take.addEventListener('click', () => {
    if (!round || !view) return;
    const az = halfDegree(view.az);
    round.readings[step] = az;
    mapLines(round, false);
    status.textContent = `Reading from ${step === 0 ? round.a.name : round.b.name}: ${azimuthText(az, 1)}. ${step === 0 ? 'Its line is on the map.' : ''}`;
    if (step === 0) void sightFrom(1);
    else finish();
  });

  const finish = () => {
    const r = round!;
    setStep(2);
    take.disabled = true;
    const [ra, rb] = r.readings as [number, number];
    const fix = crossing(r.a, ra, r.b, rb);
    const trueA = bearingDeg(r.a.lat, r.a.lon, r.fire.lat, r.fire.lon);
    const trueB = bearingDeg(r.b.lat, r.b.lon, r.fire.lat, r.fire.lon);
    mapLines(r, true);
    const res: Feat[] = [point(r.fire, { kind: 'fire', label: 'Fire' })];
    if (fix) res.push(point(fix, { kind: 'fix', label: 'Your fix' }));
    lessonMap.set('result', fc(res));
    lessonMap.fit([r.a, r.b, r.fire, ...(fix ? [fix] : [])], 3_000);
    const err = fix ? distanceM(fix.lat, fix.lon, r.fire.lat, r.fire.lon) : null;
    const score = err === null ? null : scoreFor(err);
    const off = (mine: number, truth: number) => {
      const d = Math.abs(angleDiff(truth, mine));
      return d < 0.05 ? 'spot on' : `${d.toFixed(1)}° ${angleDiff(truth, mine) > 0 ? 'clockwise' : 'anticlockwise'} of it`;
    };
    const stars = score ? '★'.repeat(score.stars) + '☆'.repeat(3 - score.stars) : '';
    result.innerHTML = html`
      <h3>${err === null ? 'Your lines do not cross ahead of both lookouts' : html`Your fix is ${milesKm(err)} from the fire`}</h3>
      ${r.hints ? html`<p class="fine">You used the hint ${r.hints === 1 ? 'once' : 'twice'}; the lining up was yours.</p>` : ''}
      ${score ? html`<p class="game-score"><span class="game-stars" aria-hidden="true">${stars}</span> <span class="visually-hidden">${score.stars} out of 3. </span>${score.verdict}</p>` : html`<p>One of the bearings points away from the other lookout's line. Look again at where the smoke rises.</p>`}
      <dl class="kv">
        <div><dt>From A, ${r.a.name}</dt><dd>You read ${azimuthText(ra, 1)}; the fire was at ${azimuthText(trueA, 1)} (${off(ra, trueA)}), ${milesKm(distanceM(r.a.lat, r.a.lon, r.fire.lat, r.fire.lon))} away.</dd></div>
        <div><dt>From B, ${r.b.name}</dt><dd>You read ${azimuthText(rb, 1)}; the fire was at ${azimuthText(trueB, 1)} (${off(rb, trueB)}), ${milesKm(distanceM(r.b.lat, r.b.lon, r.fire.lat, r.fire.lon))} away.</dd></div>
      </dl>
      <p class="fine">On the map: your lines (A solid, B dashed), the true bearings dotted, the fire as a filled circle and your fix as an open ring. A lookout would have reported: “${r.a.name}, smoke at ${azimuthText(ra, 1)}, origin in sight.” The dispatcher crossed it with the second shot on the string map and sent a crew to the township, range and section.</p>
      <p><button type="button" class="btn btn-primary" data-again>Play again with two other lookouts</button>
        <a class="btn" href="${BASE}t/${r.a.id}/">About ${r.a.name}</a></p>`.value;
    result.hidden = false;
    mapKey.textContent = 'Solid line: your bearing from A. Dashed: from B. Dotted: the true bearings. Filled circle: the fire. Open ring: your fix.';
    $<HTMLElement>('[data-map]').setAttribute(
      'aria-label',
      err === null ? 'Map: your two bearing lines do not cross ahead of both lookouts.' : `Map: your bearing lines cross ${milesKm(err)} from the fire.`,
    );
    status.textContent = err === null ? 'Your lines do not cross. See the result below the map.' : `Your fix is ${milesKm(err)} from the fire. See the result below the map.`;
    result.querySelector<HTMLButtonElement>('[data-again]')?.focus();
  };

  result.addEventListener('click', (e) => {
    if ((e.target as Element).closest('[data-again]')) void newRound();
  });

  const newRound = async () => {
    result.hidden = true;
    lessonMap.set('lines', fc([]));
    lessonMap.set('result', fc([]));
    mapKey.textContent = 'Lookout A and lookout B are marked with their letters. Your line from A is solid, your line from B is dashed.';
    setStep(0);
    take.disabled = true;
    hintBtn.hidden = true;
    status.textContent = 'Picking two lookouts…';
    for (const [fa, fb] of pickPairs(towers, 6)) {
      const [a, b] = await Promise.all([lookout(fa), lookout(fb)]);
      lessonMap.set('points', fc([]));
      try {
        const fire = await placeSmoke(a, b, (s) => (status.textContent = s));
        if (!fire) continue;
        round = { a, b, fire, readings: [null, null], hints: 0 };
        mapPoints(round);
        lessonMap.fit([a, b], 12_000);
        await sightFrom(0);
        return;
      } catch (err) {
        console.error(err);
        status.innerHTML = html`The terrain could not be loaded. Check your connection, then <button type="button" class="linklike" data-retry>try again</button>.`.value;
        status.querySelector('[data-retry]')?.addEventListener('click', () => void newRound());
        return;
      }
    }
    status.innerHTML = html`Could not find a good pair of lookouts this time. <button type="button" class="linklike" data-retry>Try again</button>.`.value;
    status.querySelector('[data-retry]')?.addEventListener('click', () => void newRound());
  };

  await newRound();
}

void main();
