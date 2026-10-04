/**
 * Firefinder's own map layers: clustered lookout markers, the selection ring, the optional
 * USGS topo raster and the historical topo overlay, and, in the year view, a dimmed second
 * set of markers for lookouts whose dates are incomplete. `installOverlay` is idempotent and
 * runs after every style load (theme changes swap the whole base style, which drops custom
 * sources, layers and images).
 */
import type { ExpressionSpecification, GeoJSONSource, Map as MlMap, RasterTileSource } from 'maplibre-gl';
import { oldTopoTiles, registerOldTopo } from '../history/oldtopo/client.ts';
import { MIN_ZOOM as OLD_MIN_ZOOM, type Era } from '../history/oldtopo/sheets.ts';
import { FILLS, SHAPES, drawMarker, iconName } from '../lib/icons.ts';
import type { TowerCollection } from '../lib/types.ts';
import type { Basemap } from '../lib/urlstate.ts';
import { BOLD_FONT, LABEL_FONT, type Theme } from './style.ts';

export const SRC = 'ff-towers';
export const SEL_SRC = 'ff-selected';
/** Lookouts that may have stood in the chosen year (dates incomplete), drawn dimmed. */
export const MAYBE_SRC = 'ff-towers-maybe';
const TOPO_SRC = 'ff-usgs-topo';
const OLD_SRC = 'ff-old-topo';
export const L_CLUSTERS = 'ff-clusters';
export const L_CLUSTER_COUNT = 'ff-cluster-count';
export const L_POINTS = 'ff-points';
export const L_MAYBE_CLUSTERS = 'ff-maybe-clusters';
const L_MAYBE_COUNT = 'ff-maybe-count';
export const L_MAYBE_POINTS = 'ff-maybe-points';
const L_SELECTED = 'ff-selected-ring';
const L_TOPO = 'ff-usgs-topo';
const L_OLD = 'ff-old-topo';
/** The lowest of Firefinder's own layers: base rasters go under it. */
const FIRST_OWN_LAYER = L_MAYBE_CLUSTERS;

export interface OldTopoOptions {
  era: Era;
  /** 0..1 */
  opacity: number;
}

function oldAttribution(base: string): string {
  return `Old maps: <a href="https://www.usgs.gov/programs/national-geospatial-program/historical-topographic-maps-preserving-past" target="_blank" rel="noopener">USGS</a> (<a href="${base}about/#sources">credits</a>)`;
}

const ICON_PX = 24;

/** Short on the map (it must not cover the controls on phones); the full USGS credit list is on the About page. */
function usgsAttribution(base: string): string {
  return `<a href="https://www.usgs.gov/programs/national-geospatial-program/national-map" target="_blank" rel="noopener">USGS The National Map</a> (<a href="${base}about/#sources">full credits</a>)`;
}

/** Draw the 24 marker images for this theme (dark mode flips what "hollow" looks like). */
function addIcons(map: MlMap, theme: Theme): void {
  const ratio = 2;
  const px = ICON_PX * ratio;
  const canvas = document.createElement('canvas');
  canvas.width = px;
  canvas.height = px;
  const ctx = canvas.getContext('2d', { willReadFrequently: true })!;
  for (const shape of SHAPES) {
    for (const fill of FILLS) {
      for (const rent of [false, true]) {
        const name = iconName(shape, fill, rent);
        ctx.clearRect(0, 0, px, px);
        drawMarker(ctx, shape, fill, rent, px, theme);
        const image = ctx.getImageData(0, 0, px, px);
        if (map.hasImage(name)) map.updateImage(name, image);
        else map.addImage(name, image, { pixelRatio: ratio });
      }
    }
  }
}

const ICON_EXPR: ExpressionSpecification = [
  'concat',
  'ff-',
  ['match', ['get', 'k'], ['tower', 'enclosed_tower', 'platform'], 'tri', ['ground', 'two_story', 'three_story'], 'house', 'circle'],
  '-',
  ['match', ['get', 's'], 'standing', 'solid', 'gone', 'hollow', 'ruins', 'ruin', 'half'],
  ['case', ['==', ['get', 'rt'], 1], '-rent', ''],
];

/** Draw standing and rentable lookouts on top of gone ones where they overlap. */
const SORT_EXPR: ExpressionSpecification = [
  '+',
  ['match', ['get', 's'], 'standing', 2, 'gone', 0, 1],
  ['case', ['==', ['get', 'rt'], 1], 2, 0],
];

export interface OverlayOptions {
  data: TowerCollection;
  /** Year view: lookouts that may have stood then, drawn dimmed (empty otherwise). */
  maybe: TowerCollection;
  theme: Theme;
  base: string;
  basemap: Basemap;
  old: OldTopoOptions;
  selected: [number, number] | null;
}

export function installOverlay(map: MlMap, o: OverlayOptions): void {
  addIcons(map, o.theme);
  const dark = o.theme === 'dark';
  const ink = dark ? '#dfe7da' : '#24342b';
  const paper = dark ? '#121915' : '#fbf8f1';

  // The year view's "may have stood then" set: under the others, hollow clusters, faded icons.
  if (!map.getSource(MAYBE_SRC)) {
    map.addSource(MAYBE_SRC, { type: 'geojson', data: o.maybe as never, cluster: true, clusterRadius: 44, clusterMaxZoom: 9 });
  }
  if (!map.getLayer(L_MAYBE_CLUSTERS)) {
    map.addLayer({
      id: L_MAYBE_CLUSTERS,
      type: 'circle',
      source: MAYBE_SRC,
      filter: ['has', 'point_count'],
      paint: {
        'circle-color': paper,
        'circle-opacity': 0.8,
        'circle-radius': ['step', ['get', 'point_count'], 13, 10, 16, 50, 19, 200, 23, 1000, 27],
        'circle-stroke-color': ink,
        'circle-stroke-opacity': 0.55,
        'circle-stroke-width': 1.5,
      },
    });
  }
  if (!map.getLayer(L_MAYBE_COUNT)) {
    map.addLayer({
      id: L_MAYBE_COUNT,
      type: 'symbol',
      source: MAYBE_SRC,
      filter: ['has', 'point_count'],
      layout: { 'text-field': ['get', 'point_count_abbreviated'], 'text-font': LABEL_FONT, 'text-size': 12, 'text-allow-overlap': true },
      paint: { 'text-color': ink, 'text-opacity': 0.75 },
    });
  }
  if (!map.getLayer(L_MAYBE_POINTS)) {
    map.addLayer({
      id: L_MAYBE_POINTS,
      type: 'symbol',
      source: MAYBE_SRC,
      filter: ['!', ['has', 'point_count']],
      layout: {
        'icon-image': ICON_EXPR,
        'icon-size': ['interpolate', ['linear'], ['zoom'], 3, 0.65, 8, 0.85, 13, 1.05],
        'icon-allow-overlap': true,
        'icon-ignore-placement': true,
      },
      paint: { 'icon-opacity': 0.4 },
    });
  }

  if (!map.getSource(SRC)) {
    map.addSource(SRC, {
      type: 'geojson',
      data: o.data as never,
      cluster: true,
      clusterRadius: 44,
      clusterMaxZoom: 9,
      attribution: `<a href="${o.base}about/#sources">Lookout data: Firefinder and its sources (ODbL)</a>`,
    });
  }
  if (!map.getSource(SEL_SRC)) {
    map.addSource(SEL_SRC, { type: 'geojson', data: selectionData(o.selected) as never });
  }

  if (!map.getLayer(L_CLUSTERS)) {
    map.addLayer({
      id: L_CLUSTERS,
      type: 'circle',
      source: SRC,
      filter: ['has', 'point_count'],
      paint: {
        'circle-color': ink,
        'circle-opacity': 0.92,
        'circle-radius': ['step', ['get', 'point_count'], 14, 10, 17, 50, 21, 200, 26, 1000, 31],
        'circle-stroke-color': paper,
        'circle-stroke-width': 2.5,
      },
    });
  }
  if (!map.getLayer(L_CLUSTER_COUNT)) {
    map.addLayer({
      id: L_CLUSTER_COUNT,
      type: 'symbol',
      source: SRC,
      filter: ['has', 'point_count'],
      layout: {
        'text-field': ['get', 'point_count_abbreviated'],
        'text-font': BOLD_FONT,
        'text-size': 13,
        'text-allow-overlap': true,
      },
      paint: { 'text-color': paper },
    });
  }
  if (!map.getLayer(L_SELECTED)) {
    map.addLayer({
      id: L_SELECTED,
      type: 'circle',
      source: SEL_SRC,
      paint: {
        'circle-radius': 19,
        'circle-color': 'rgba(0,0,0,0)',
        'circle-stroke-color': dark ? '#ffb38a' : '#b4441a',
        'circle-stroke-width': 3,
      },
    });
  }
  if (!map.getLayer(L_POINTS)) {
    map.addLayer({
      id: L_POINTS,
      type: 'symbol',
      source: SRC,
      filter: ['!', ['has', 'point_count']],
      layout: {
        'icon-image': ICON_EXPR,
        'icon-size': ['interpolate', ['linear'], ['zoom'], 3, 0.75, 8, 0.95, 13, 1.15],
        'icon-allow-overlap': true,
        'icon-ignore-placement': true,
        'symbol-sort-key': SORT_EXPR,
        'text-field': ['step', ['zoom'], '', 9, ['get', 'n']],
        'text-font': LABEL_FONT,
        'text-size': 12,
        'text-offset': [0, 1.25],
        'text-anchor': 'top',
        'text-optional': true,
        'text-max-width': 9,
      },
      paint: {
        'text-color': dark ? '#e6e2d6' : '#26302a',
        'text-halo-color': dark ? 'rgba(18,25,21,0.9)' : 'rgba(251,248,241,0.95)',
        'text-halo-width': 1.6,
      },
    });
  }
  setBase(map, o.basemap, o.theme, o.base, o.old);
}

function selectionData(coords: [number, number] | null) {
  return {
    type: 'FeatureCollection',
    features: coords ? [{ type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: coords } }] : [],
  };
}

export function setSelection(map: MlMap, coords: [number, number] | null): void {
  (map.getSource(SEL_SRC) as GeoJSONSource | undefined)?.setData(selectionData(coords) as never);
}

export function setTowerData(map: MlMap, data: TowerCollection, maybe?: TowerCollection): void {
  (map.getSource(SRC) as GeoJSONSource | undefined)?.setData(data as never);
  if (maybe) (map.getSource(MAYBE_SRC) as GeoJSONSource | undefined)?.setData(maybe as never);
}

/**
 * The base map: the vector map, the modern USGS topo raster (vector layers hidden under it), or
 * the vector map with the historical USGS topo sheets laid over it at the chosen opacity.
 */
export function setBase(map: MlMap, basemap: Basemap, theme: Theme, base: string, old: OldTopoOptions): void {
  setTopo(map, basemap === 'topo', theme, base);
  setOldTopo(map, basemap === 'old' ? old : null, theme, base);
}

function setOldTopo(map: MlMap, old: OldTopoOptions | null, theme: Theme, base: string): void {
  if (!map.getStyle()) return;
  if (!old) {
    if (map.getLayer(L_OLD)) map.removeLayer(L_OLD);
    if (map.getSource(OLD_SRC)) map.removeSource(OLD_SRC);
    return;
  }
  registerOldTopo();
  const tiles = oldTopoTiles(old.era);
  const src = map.getSource(OLD_SRC) as RasterTileSource | undefined;
  if (!src) {
    map.addSource(OLD_SRC, { type: 'raster', tiles, tileSize: 256, minzoom: OLD_MIN_ZOOM, maxzoom: 16, attribution: oldAttribution(base) });
  } else if (src.tiles?.[0] !== tiles[0]) {
    src.setTiles(tiles);
  }
  // The scans are vividly coloured (bright green woodland tint): soften them a little so the
  // markers on top stay readable. Dark mode also dims them, as it does the modern topo.
  const dim = theme === 'dark' ? { 'raster-brightness-max': 0.7, 'raster-saturation': -0.4 } : { 'raster-saturation': -0.3 };
  if (!map.getLayer(L_OLD)) {
    map.addLayer({ id: L_OLD, type: 'raster', source: OLD_SRC, paint: { 'raster-opacity': old.opacity, 'raster-fade-duration': 150, ...dim } }, map.getLayer(FIRST_OWN_LAYER) ? FIRST_OWN_LAYER : undefined);
  } else {
    map.setPaintProperty(L_OLD, 'raster-opacity', old.opacity);
  }
}

/** USGS topo raster on or off. When on, the vector base layers are hidden underneath it. */
function setTopo(map: MlMap, on: boolean, theme: Theme, base: string): void {
  const style = map.getStyle();
  if (!style) return;
  if (on && !map.getSource(TOPO_SRC)) {
    map.addSource(TOPO_SRC, {
      type: 'raster',
      tiles: ['https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}'],
      tileSize: 256,
      maxzoom: 16,
      attribution: usgsAttribution(base),
    });
  }
  if (on && !map.getLayer(L_TOPO)) {
    // Dimmed in dark mode, so the dark-mode markers (bright = standing) still read correctly.
    const paint = theme === 'dark' ? { 'raster-fade-duration': 150, 'raster-brightness-max': 0.58, 'raster-saturation': -0.2 } : { 'raster-fade-duration': 150 };
    map.addLayer({ id: L_TOPO, type: 'raster', source: TOPO_SRC, paint }, map.getLayer(FIRST_OWN_LAYER) ? FIRST_OWN_LAYER : L_CLUSTERS);
  }
  if (!on && map.getLayer(L_TOPO)) map.removeLayer(L_TOPO);
  if (!on && map.getSource(TOPO_SRC)) map.removeSource(TOPO_SRC);
  for (const layer of style.layers) {
    if (layer.id.startsWith('ff-') && layer.id !== 'ff-base-relief') continue;
    map.setLayoutProperty(layer.id, 'visibility', on ? 'none' : 'visible');
  }
}

