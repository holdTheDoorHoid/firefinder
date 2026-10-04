/**
 * Firefinder's own map layers: clustered lookout markers, the selection ring and the optional
 * USGS topo raster. `installOverlay` is idempotent and runs after every style load (theme
 * changes swap the whole base style, which drops custom sources, layers and images).
 */
import type { ExpressionSpecification, GeoJSONSource, Map as MlMap } from 'maplibre-gl';
import { FILLS, SHAPES, drawMarker, iconName } from '../lib/icons.ts';
import type { TowerCollection } from '../lib/types.ts';
import { BOLD_FONT, LABEL_FONT, type Theme } from './style.ts';

export const SRC = 'ff-towers';
export const SEL_SRC = 'ff-selected';
const TOPO_SRC = 'ff-usgs-topo';
export const L_CLUSTERS = 'ff-clusters';
export const L_CLUSTER_COUNT = 'ff-cluster-count';
export const L_POINTS = 'ff-points';
const L_SELECTED = 'ff-selected-ring';
const L_TOPO = 'ff-usgs-topo';

const ICON_PX = 24;

const USGS_ATTRIBUTION =
  '<a href="https://www.usgs.gov/programs/national-geospatial-program/national-map" target="_blank" rel="noopener">USGS The National Map</a>: National Boundaries Dataset, 3DEP Elevation Program, Geographic Names Information System, National Hydrography Dataset, National Land Cover Database, National Structures Dataset, and National Transportation Dataset; USGS Global Ecosystems; U.S. Census Bureau TIGER/Line data; USFS Road data; Natural Earth Data; U.S. Department of State HIU; NOAA National Centers for Environmental Information';

function addIcons(map: MlMap): void {
  const ratio = 2;
  const px = ICON_PX * ratio;
  for (const shape of SHAPES) {
    for (const fill of FILLS) {
      for (const rent of [false, true]) {
        const name = iconName(shape, fill, rent);
        if (map.hasImage(name)) continue;
        const canvas = document.createElement('canvas');
        canvas.width = px;
        canvas.height = px;
        const ctx = canvas.getContext('2d')!;
        drawMarker(ctx, shape, fill, rent, px);
        map.addImage(name, ctx.getImageData(0, 0, px, px), { pixelRatio: ratio });
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
  theme: Theme;
  base: string;
  topo: boolean;
  selected: [number, number] | null;
}

export function installOverlay(map: MlMap, o: OverlayOptions): void {
  addIcons(map);
  const dark = o.theme === 'dark';
  const ink = dark ? '#dfe7da' : '#24342b';
  const paper = dark ? '#121915' : '#fbf8f1';

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
  setTopo(map, o.topo);
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

export function setTowerData(map: MlMap, data: TowerCollection): void {
  (map.getSource(SRC) as GeoJSONSource | undefined)?.setData(data as never);
}

/** USGS topo raster on or off. When on, the vector base layers are hidden underneath it. */
export function setTopo(map: MlMap, on: boolean): void {
  const style = map.getStyle();
  if (!style) return;
  if (on && !map.getSource(TOPO_SRC)) {
    map.addSource(TOPO_SRC, {
      type: 'raster',
      tiles: ['https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}'],
      tileSize: 256,
      maxzoom: 16,
      attribution: USGS_ATTRIBUTION,
    });
  }
  if (on && !map.getLayer(L_TOPO)) {
    map.addLayer({ id: L_TOPO, type: 'raster', source: TOPO_SRC, paint: { 'raster-fade-duration': 150 } }, L_CLUSTERS);
  }
  if (!on && map.getLayer(L_TOPO)) map.removeLayer(L_TOPO);
  if (!on && map.getSource(TOPO_SRC)) map.removeSource(TOPO_SRC);
  for (const layer of style.layers) {
    if (layer.id.startsWith('ff-') && layer.id !== 'ff-base-relief') continue;
    map.setLayoutProperty(layer.id, 'visibility', on ? 'none' : 'visible');
  }
}

