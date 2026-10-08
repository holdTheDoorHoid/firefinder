/** The map page: wires data, map, filters, search, side panel, checklist and URL state. */
import 'maplibre-gl/dist/maplibre-gl.css';
import '../styles/map.css';
import {
  AttributionControl,
  GeolocateControl,
  Map as MlMap,
  NavigationControl,
  Popup,
  ScaleControl,
  setWorkerUrl,
  type GeoJSONSource,
  type IControl,
  type MapLayerMouseEvent,
} from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';

import { activeFilterCount, applyFilters, defaultFilters, type Filters } from '../lib/filters.ts';
import { isMaybe, yearState } from '../lib/history.ts';
import { formatCount } from '../lib/format.ts';
import { isNoStructure } from '../lib/vocab.ts';
import { html } from '../lib/html.ts';
import { buildIndex, type SearchEntry } from '../lib/search.ts';
import type { Meta, SourceInfo, TowerCollection, TowerFeature, TowerProps } from '../lib/types.ts';
import { parseState, serializeState, type AppState, type Basemap } from '../lib/urlstate.ts';
import { towerPath, type RenderContext } from '../render/tower.ts';
import { bindChecklistButtons, getChecklist, initChecklistDialog } from '../ui/checklist-ui.ts';
import { initCommon } from '../ui/common.ts';
import { effectiveTheme, onThemeChange } from '../ui/theme.ts';
import siteConfig from '../../site.config.json';
import { renderFilterPanel } from './filters-ui.ts';
import { L_CLUSTERS, L_MAYBE_CLUSTERS, L_MAYBE_POINTS, L_POINTS, MAYBE_SRC, SRC, installOverlay, setBase, setSelection, setTowerData } from './overlay.ts';
import { OldTopoControl } from './oldtopo-ui.ts';
import { YearPanel } from './years-ui.ts';
import { Panel } from './panel.ts';
import { initSearch } from './search-ui.ts';
import { loadBaseStyle } from './style.ts';
import type { SeenLayer } from '../view3d/viewshed-layer.ts';
import type { HistoryCounts, TowerRecord } from '../lib/types.ts';

const BASE = import.meta.env.BASE_URL;
const US_BOUNDS: [[number, number], [number, number]] = [
  [-125.0, 24.4],
  [-66.9, 49.5],
];
const PHONE = matchMedia('(max-width: 899px)');

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return (await res.json()) as T;
}

const BASES: { id: Basemap; label: string; title: string }[] = [
  { id: 'map', label: 'Map', title: 'Street and terrain map (OpenFreeMap)' },
  { id: 'topo', label: 'Topo', title: 'Today\'s USGS topographic map, with contours' },
  { id: 'old', label: 'Old topo', title: 'Historical USGS topo maps, 1880s to 2006: the map from when the lookouts stood' },
];

class BasemapControl implements IControl {
  #el: HTMLDivElement | null = null;
  #get: () => Basemap;
  #set: (b: Basemap) => void;
  constructor(get: () => Basemap, set: (b: Basemap) => void) {
    this.#get = get;
    this.#set = set;
  }
  onAdd(): HTMLElement {
    const el = document.createElement('div');
    el.className = 'maplibregl-ctrl maplibregl-ctrl-group ff-basemap';
    el.setAttribute('role', 'group');
    el.setAttribute('aria-label', 'Base map');
    el.innerHTML = html`${BASES.map((b) => html`<button type="button" data-base="${b.id}" title="${b.title}">${b.label}</button>`)}`.value;
    el.addEventListener('click', (e) => {
      const b = (e.target as Element).closest<HTMLElement>('[data-base]');
      if (b) this.#set(BASES.find((x) => x.id === b.dataset.base)?.id ?? 'map');
    });
    this.#el = el;
    this.sync();
    return el;
  }
  onRemove(): void {
    this.#el?.remove();
  }
  sync(): void {
    for (const b of this.#el?.querySelectorAll<HTMLElement>('[data-base]') ?? []) {
      b.setAttribute('aria-pressed', String(b.dataset.base === this.#get()));
    }
  }
}

async function main(): Promise<void> {
  initCommon();
  setWorkerUrl(workerUrl);

  const state: AppState = parseState(location.search);
  const checklist = getChecklist();
  initChecklistDialog(checklist);

  const countEl = $('count');
  const filtersEl = $('filters');
  const filtersBody = $('filters-body');
  const openFiltersBtn = $<HTMLButtonElement>('open-filters');
  const showResultsBtn = $<HTMLButtonElement>('show-results');
  const filterCountEl = $('filter-count');
  const mapMessage = $('map-message');
  const mapbox = document.querySelector<HTMLElement>('.mapbox')!;
  const searchEl = document.querySelector<HTMLElement>('.search')!;

  let features: TowerFeature[] = [];
  let filteredNoYear: TowerFeature[] = [];
  let historyCounts: HistoryCounts | null = null;
  const thisYear = new Date().getFullYear();
  let byId = new Map<string, TowerFeature>();
  let shownIds = new Set<string>();
  let index: SearchEntry[] = [];
  let collection: TowerCollection = { type: 'FeatureCollection', features: [] };
  let maybeCollection: TowerCollection = { type: 'FeatureCollection', features: [] };
  let map: MlMap | null = null;
  let viewTouched = !!state.view;

  const ctx: RenderContext = { base: BASE, siteUrl: siteConfig.siteUrl, repo: siteConfig.repo, sources: new Map() };

  /* ---------- URL ---------- */
  let urlTimer = 0;
  const writeUrl = () => {
    clearTimeout(urlTimer);
    urlTimer = window.setTimeout(() => {
      if (map && viewTouched) {
        const c = map.getCenter();
        state.view = { zoom: map.getZoom(), lat: c.lat, lon: c.lng };
      }
      history.replaceState(history.state, '', location.pathname + serializeState(state) + location.hash);
    }, 200);
  };

  /* ---------- Panel ---------- */
  const panel = new Panel({
    el: $('panel'),
    body: $('panel-body'),
    closeBtn: $<HTMLButtonElement>('panel-close'),
    ctx,
    isHiddenByFilters: (id) => features.length > 0 && !shownIds.has(id),
    yearView: () => state.year !== null,
    onRender: (root) => {
      bindChecklistButtons(root, checklist);
      syncSeenButtons(root);
    },
    onClose: () => {
      state.selected = null;
      if (map) setSelection(map, null);
      writeUrl();
    },
  });

  const select = (id: string, opts: { fly: boolean; focus: boolean }) => {
    const f = byId.get(id);
    state.selected = id;
    void panel.open(id, f?.properties ?? null, { focus: opts.focus });
    if (map && f) {
      const coords = f.geometry.coordinates;
      setSelection(map, coords);
      const cover = panel.coverage();
      const padding = { top: PHONE.matches ? 80 : 40, left: 40, right: 40 + cover.right, bottom: 40 + cover.bottom };
      if (opts.fly) {
        viewTouched = true;
        map.flyTo({ center: coords, zoom: Math.max(map.getZoom(), 11), padding, essential: true });
      } else {
        // Don't leave the lookout you just picked hidden under the panel or the search box.
        const p = map.project(coords);
        const box = map.getContainer();
        const hidden = p.x < padding.left - 20 || p.y < padding.top - 20 || p.x > box.clientWidth - padding.right + 20 || p.y > box.clientHeight - padding.bottom + 20;
        if (hidden) map.easeTo({ center: coords, padding, duration: 500 });
      }
    }
    writeUrl();
  };

  /* ---------- Filters ---------- */
  let syncFilters = () => {};
  const update = () => {
    const filtered = applyFilters(features, state.filters, checklist);
    filteredNoYear = filtered;
    // The year view narrows the map to lookouts standing that year; with "show faded" on, the
    // ones whose dates are incomplete go to a second, faded layer.
    let shown = filtered;
    let maybe: TowerFeature[] = [];
    if (state.year !== null) {
      shown = [];
      for (const f of filtered) {
        const st = yearState(f.properties, state.year, thisYear);
        if (st === 'stood') shown.push(f);
        else if (state.yearMaybe && isMaybe(st)) maybe.push(f);
      }
    }
    shownIds = new Set([...shown, ...maybe].map((f) => f.properties.i));
    collection = { type: 'FeatureCollection', features: shown };
    maybeCollection = { type: 'FeatureCollection', features: maybe };
    if (map?.getSource(SRC)) setTowerData(map, collection, maybeCollection);
    const n = shown.length;
    // Sites with no structure (camps, lookout trees, bare points) count only when switched on,
    // and the count says which it is.
    const withNs = state.filters.noStructure;
    const noStructureTotal = features.filter((f) => isNoStructure(f.properties.k)).length;
    const total = withNs ? features.length : features.length - noStructureTotal;
    const what = withNs ? 'lookout sites' : 'towers and buildings';
    if (state.year !== null) {
      const when = state.year >= thisYear ? 'today' : `in ${state.year}`;
      countEl.textContent =
        `${formatCount(n)} ${what} standing ${when}` + (maybe.length ? `, ${formatCount(maybe.length)} faded` : '') + (filtered.length !== total ? ' (filtered)' : '');
    } else {
      const ns = withNs && noStructureTotal ? `, including ${formatCount(noStructureTotal)} with no structure` : '';
      countEl.textContent =
        features.length === 0 ? 'No lookouts loaded' : n === 0 ? 'No lookouts match your filters' : n === total ? `All ${formatCount(total)} ${what} shown${ns}` : `${formatCount(n)} of ${formatCount(total)} ${what} shown`;
    }
    countEl.classList.toggle('is-empty', n + maybe.length === 0 && features.length > 0);
    const active = activeFilterCount(state.filters);
    filterCountEl.textContent = active ? ` (${active})` : '';
    $('reset-map').hidden = active === 0;
    showResultsBtn.textContent = n === 0 ? 'No lookouts match: close' : `Show ${formatCount(n)} lookout${n === 1 ? '' : 's'}`;
    syncFilters();
    years.refresh();
    panel.refresh();
    writeUrl();
  };
  const setFilters = (f: Filters) => {
    state.filters = f;
    update();
  };

  document.addEventListener('click', (e) => {
    const t = e.target as Element;
    if (t.closest('[data-reset-filters], [data-action="reset-filters"]')) setFilters(defaultFilters());
  });

  /* ---------- Then and now: lookouts standing in a year ---------- */
  const yearsBtn = $<HTMLButtonElement>('open-years');
  const years = new YearPanel({
    host: mapbox,
    thisYear,
    history: () => historyCounts,
    all: () => features,
    filtered: () => filteredNoYear,
    // Switching on sites with no structure is said separately, not as "your filters".
    filtersActive: () => activeFilterCount(state.filters) - (state.filters.noStructure ? 1 : 0) > 0,
    withNoStructure: () => state.filters.noStructure,
    onChange: (year, maybe) => {
      const was = state.year;
      state.year = year;
      state.yearMaybe = year !== null && maybe;
      yearsBtn.setAttribute('aria-pressed', String(year !== null));
      if (year === null && was !== null) yearsBtn.focus();
      update();
    },
  });
  yearsBtn.addEventListener('click', () => {
    if (years.isOpen) years.close();
    else years.open(state.year ?? 1935, state.yearMaybe, true);
  });

  /* ---------- Phone filter sheet ---------- */
  const setSheet = (open: boolean) => {
    filtersEl.toggleAttribute('data-open', open);
    openFiltersBtn.setAttribute('aria-expanded', String(open));
    for (const el of [mapbox, searchEl, $('panel')]) el.inert = open;
    if (open) filtersEl.querySelector<HTMLElement>('.filters-close')?.focus();
    else openFiltersBtn.focus();
  };
  openFiltersBtn.addEventListener('click', () => setSheet(true));
  for (const b of filtersEl.querySelectorAll('[data-close-filters]')) b.addEventListener('click', () => setSheet(false));
  PHONE.addEventListener('change', () => {
    if (!PHONE.matches && filtersEl.hasAttribute('data-open')) setSheet(false);
  });
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape' || document.querySelector('dialog[open]')) return;
    if (filtersEl.hasAttribute('data-open')) setSheet(false);
    else if (panel.isOpen && !(e.target as Element).closest?.('.search')) panel.close();
  });

  /* ---------- 3D: view from the cab, what it could see ---------- */
  let seen: SeenLayer | null = null;
  let seenLoading: Promise<SeenLayer | null> | null = null;
  function syncSeenButtons(root: ParentNode = document): void {
    for (const b of root.querySelectorAll<HTMLButtonElement>('[data-action="viewshed"]')) {
      const on = !!seen?.has(b.dataset.id!);
      b.setAttribute('aria-pressed', String(on));
      const label = b.querySelector('[data-viewshed-label]');
      if (label) label.textContent = on ? 'Hide what it could see' : seen?.ids.length ? 'Add what it could see' : 'What it could see';
    }
  }
  const getSeen = (): Promise<SeenLayer | null> => {
    if (seen || !map) return Promise.resolve(seen);
    const m = map;
    seenLoading ??= import('../view3d/viewshed-layer.ts').then(({ SeenLayer }) => {
      seen = new SeenLayer({
        map: m,
        host: mapbox,
        base: BASE,
        tower: (id) => byId.get(id),
        towers: () => features,
        theme: () => theme,
        onChange: (ids, km) => {
          state.seen = ids;
          state.seenKm = ids.length && km !== 40 ? km : null;
          writeUrl();
          syncSeenButtons();
        },
      });
      return seen;
    });
    return seenLoading;
  };
  const openCab = async (id: string) => {
    let dlg = document.getElementById('cab-dialog') as HTMLDialogElement | null;
    if (!dlg) {
      dlg = document.createElement('dialog');
      dlg.id = 'cab-dialog';
      dlg.className = 'dialog dialog-wide';
      dlg.setAttribute('aria-labelledby', 'cab-dialog-h');
      document.body.append(dlg);
    }
    const f = byId.get(id);
    dlg.innerHTML = html`<div class="dialog-inner">
      <div class="dialog-head"><h2 id="cab-dialog-h">View from the cab: ${f?.properties.n ?? 'lookout'}</h2>
        <button type="button" class="icon-btn" data-close-cab aria-label="Close the view">
          <svg width="18" height="18" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="m5 5 10 10M15 5 5 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
        </button></div>
      <div data-cab-host><p class="muted">Loading…</p></div>
      <p class="fine">More about this lookout on <a href="${towerPath(id, ctx)}">its own page</a>.</p>
    </div>`.value;
    dlg.querySelector('[data-close-cab]')!.addEventListener('click', () => dlg!.close());
    dlg.showModal();
    try {
      const [rec, { PanoramaView }] = await Promise.all([
        getJson<TowerRecord>(`data/t/${id}.json`),
        import('../view3d/panorama-view.ts'),
      ]);
      const view = new PanoramaView(dlg.querySelector<HTMLElement>('[data-cab-host]')!, {
        tower: { id, name: rec.name, lat: rec.location.lat, lon: rec.location.lon, kind: rec.kind, status: rec.status, height_m: rec.height_m, elevation_m: rec.elevation_m },
      });
      dlg.addEventListener('close', () => view.destroy(), { once: true });
      view.el.querySelector<HTMLElement>('.pv-viewport')?.focus();
      await view.start();
    } catch (err) {
      console.error(err);
      const host = dlg.querySelector('[data-cab-host]');
      if (host) host.innerHTML = '<p class="notice tone-caution">The view could not be loaded. Check your connection and try again.</p>';
    }
  };
  document.addEventListener('click', async (e) => {
    const b = (e.target as Element).closest<HTMLButtonElement>('[data-action="view-cab"], [data-action="viewshed"]');
    if (!b?.dataset.id) return;
    if (b.dataset.action === 'view-cab') {
      void openCab(b.dataset.id);
      return;
    }
    const s = await getSeen();
    if (!s) {
      mapMessage.hidden = false;
      mapMessage.textContent = 'The map is not available in this browser, so the view cannot be drawn on it.';
      return;
    }
    const first = s.ids.length === 0;
    // On phones the details sheet would cover the shading: close it (tapping a marker reopens it).
    if (PHONE.matches && !s.has(b.dataset.id)) panel.close();
    await s.toggle(b.dataset.id);
    if (first) s.fit(panel.coverage().right);
  });

  /* ---------- Search ---------- */
  initSearch({
    input: $<HTMLInputElement>('q'),
    list: $<HTMLUListElement>('q-results'),
    status: $('q-status'),
    index: () => index,
    onPick: (entry) => {
      if (!map) {
        location.href = towerPath(entry.props.i, ctx);
        return;
      }
      select(entry.props.i, { fly: true, focus: true });
    },
  });

  /* ---------- Checklist ---------- */
  checklist.subscribe(() => {
    bindChecklistButtons(document, checklist);
    if (state.filters.mine) update();
    else syncFilters();
  });

  /* ---------- Data (in parallel with the base map; neither waits for the other) ---------- */
  const dataTask = (async (): Promise<boolean> => {
    let geo: TowerCollection;
    let meta: Meta | null;
    try {
      [geo, meta] = await Promise.all([
        getJson<TowerCollection>('data/towers.geojson'),
        getJson<Meta>('data/meta.json').catch(() => null),
      ]);
    } catch (err) {
      console.error(err);
      countEl.textContent = 'Could not load the lookouts';
      mapMessage.hidden = false;
      mapMessage.textContent = 'The list of lookouts could not be loaded. Check your connection and reload the page.';
      filtersBody.innerHTML = '<p class="muted">Filters are unavailable until the lookouts load.</p>';
      return false;
    }
    features = geo.features;
    byId = new Map(features.map((f) => [f.properties.i, f]));
    index = buildIndex(features);
    if (meta) {
      historyCounts = meta.history ?? null;
      ctx.sources = new Map<string, SourceInfo>(meta.sources.map((s) => [s.id, s]));
      if (meta.fixtures) $('fixture-banner').hidden = false;
    }
    $<HTMLInputElement>('q').placeholder = `Search ${formatCount(features.length)} lookout sites, e.g. Hirz Mountain`;
    syncFilters = renderFilterPanel({
      root: filtersBody,
      features: () => features,
      filters: () => state.filters,
      checklist,
      onChange: setFilters,
    });
    if (state.year !== null) years.open(state.year, state.yearMaybe);
    else update();
    return true;
  })();

  /* ---------- Map ---------- */
  let theme = effectiveTheme();
  const { style, ok: styleOk } = await loadBaseStyle(theme);
  const oldOpts = () => ({ era: state.era, opacity: state.oldOpacity });
  const applyBase = () => {
    basemapCtl.sync();
    oldTopoCtl.sync(state.basemap === 'old');
    if (map) setBase(map, state.basemap, theme, BASE, oldOpts());
    writeUrl();
  };
  const basemapCtl = new BasemapControl(
    () => state.basemap,
    (b) => {
      state.basemap = b;
      applyBase();
    },
  );
  const oldTopoCtl = new OldTopoControl({
    era: () => state.era,
    opacity: () => state.oldOpacity,
    onEra: (era) => {
      state.era = era;
      applyBase();
    },
    onOpacity: (op) => {
      state.oldOpacity = op;
      if (map) setBase(map, state.basemap, theme, BASE, oldOpts());
      writeUrl();
    },
  });
  try {
    map = new MlMap({
      container: 'map',
      style,
      bounds: state.view ? undefined : US_BOUNDS,
      fitBoundsOptions: { padding: 20 },
      center: state.view ? [state.view.lon, state.view.lat] : undefined,
      zoom: state.view?.zoom,
      minZoom: 2,
      maxZoom: 18,
      dragRotate: false,
      pitchWithRotate: false,
      touchPitch: false,
      attributionControl: false,
    });
  } catch (err) {
    console.error(err);
    map = null;
    mapMessage.hidden = false;
    mapMessage.innerHTML = html`<p><strong>The map could not start.</strong> Your browser may have WebGL switched off. You can still find a lookout with the search box and open its page.</p>`.value;
  }

  if (map) {
    const m = map;
    m.touchZoomRotate.disableRotation();
    m.keyboard.disableRotation();
    m.addControl(new AttributionControl({ compact: true }), 'bottom-right');
    m.addControl(basemapCtl, 'top-right');
    m.addControl(oldTopoCtl, 'top-right');
    oldTopoCtl.sync(state.basemap === 'old');
    m.addControl(new NavigationControl({ showCompass: false }), 'top-right');
    m.addControl(new GeolocateControl({ positionOptions: { enableHighAccuracy: false }, trackUserLocation: false }), 'top-right');
    m.addControl(new ScaleControl({ unit: 'imperial', maxWidth: 110 }), 'bottom-left');
    if (!styleOk) {
      mapMessage.hidden = false;
      mapMessage.textContent = 'The background map could not be loaded, so only the lookouts are shown. Try reloading later.';
    }

    m.on('style.load', () => {
      const sel = state.selected ? byId.get(state.selected)?.geometry.coordinates ?? null : null;
      installOverlay(m, { data: collection, maybe: maybeCollection, theme, base: BASE, basemap: state.basemap, old: oldOpts(), selected: sel });
      seen?.reinstall();
    });
    onThemeChange(async (eff) => {
      if (eff === theme) return;
      theme = eff;
      const next = await loadBaseStyle(eff);
      m.setStyle(next.style, { diff: false });
    });

    m.on('movestart', (e) => {
      if ((e as { originalEvent?: unknown }).originalEvent) viewTouched = true;
    });
    m.on('moveend', writeUrl);

    for (const layer of [L_POINTS, L_MAYBE_POINTS]) {
      m.on('click', layer, (e: MapLayerMouseEvent) => {
        const f = e.features?.[0];
        if (f) select(String(f.properties.i), { fly: false, focus: false });
      });
    }
    for (const [layer, source] of [[L_CLUSTERS, SRC], [L_MAYBE_CLUSTERS, MAYBE_SRC]] as const) {
      m.on('click', layer, async (e: MapLayerMouseEvent) => {
        const f = e.features?.[0];
        if (!f) return;
        const src = m.getSource(source) as GeoJSONSource;
        const zoom = await src.getClusterExpansionZoom(Number(f.properties.cluster_id));
        m.easeTo({ center: (f.geometry as unknown as { coordinates: [number, number] }).coordinates, zoom: Math.min(zoom + 0.5, 14) });
      });
    }
    for (const layer of [L_POINTS, L_CLUSTERS, L_MAYBE_POINTS, L_MAYBE_CLUSTERS]) {
      m.on('mouseenter', layer, () => (m.getCanvas().style.cursor = 'pointer'));
      m.on('mouseleave', layer, () => (m.getCanvas().style.cursor = ''));
    }
    if (matchMedia('(hover: hover)').matches) {
      const tip = new Popup({ closeButton: false, closeOnClick: false, offset: 14, className: 'ff-tip', maxWidth: '260px' });
      for (const layer of [L_POINTS, L_MAYBE_POINTS]) {
        m.on('mousemove', layer, (e: MapLayerMouseEvent) => {
          const f = e.features?.[0];
          if (!f) return;
          const p = f.properties as TowerProps;
          const faded = layer === L_MAYBE_POINTS ? ' (dates incomplete)' : '';
          tip.setLngLat((f.geometry as unknown as { coordinates: [number, number] }).coordinates).setText(p.n + faded).addTo(m);
        });
        m.on('mouseleave', layer, () => tip.remove());
      }
    }
  }

  /* ---------- Both ready: open a lookout named in the URL ---------- */
  if (!(await dataTask)) return;
  if (state.seen.length && map) {
    const ids = state.seen;
    const km = state.seenKm ?? 40;
    const m = map;
    const go = async () => (await getSeen())?.set(ids, km);
    if (m.isStyleLoaded()) void go();
    else m.once('load', () => void go());
  }
  if (state.selected) {
    const f = byId.get(state.selected);
    if (f) {
      select(state.selected, { fly: !state.view, focus: false });
    } else {
      state.selected = null;
      writeUrl();
    }
  }
}

void main();
