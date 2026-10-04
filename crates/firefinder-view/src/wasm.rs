//! Browser bindings. The page's Web Worker fetches Terrarium tiles, hands the PNG bytes to
//! [`Engine::add_tile`], then asks for a panorama or a viewshed. Arrays cross the boundary as
//! flat typed arrays; the layouts are documented on each method and mirrored in
//! `web/src/view3d/engine.ts`.

use wasm_bindgen::prelude::*;

use crate::dem::{Level, TileSampler, TileStore, decode_terrarium};
use crate::geo::{disc_bbox, pixel_size_m, tile_window};
use crate::panorama::{PanoramaParams, panorama};
use crate::sight::{Earth, Observer, Target, sight_targets};
use crate::viewshed::{Grid, ViewshedParams, viewshed_into};

/// Terrain tiles are 256 px (AWS Terrain Tiles).
pub const TILE_SIZE: usize = 256;

/// The tiles `[x0, y0, x1, y1, ...]` at zoom `z` a disc touches.
#[wasm_bindgen(js_name = tilesForDisc)]
pub fn tiles_for_disc(lat: f64, lon: f64, radius_m: f64, z: u8) -> Vec<u32> {
    crate::geo::tiles_for_disc(lat, lon, radius_m, z).into_iter().flat_map(|(x, y)| [x, y]).collect()
}

/// Ground size of a tile pixel at a zoom and latitude, m.
#[wasm_bindgen(js_name = pixelSize)]
pub fn pixel_size(z: u8, lat: f64) -> f64 {
    pixel_size_m(z, TILE_SIZE as u32, lat)
}

#[wasm_bindgen]
pub struct Engine {
    store: TileStore,
}

fn sampler<'a>(store: &'a TileStore, lat: f64, lon: f64, levels: &[f64]) -> TileSampler<'a> {
    let levels = levels
        .chunks_exact(2)
        .map(|l| {
            let z = l[0] as u8;
            let max = l[1];
            let window = tile_window(lat, lon, max, z);
            Level::new(store, z, max, pixel_size_m(z, TILE_SIZE as u32, lat), window, TILE_SIZE)
        })
        .collect();
    TileSampler { levels }
}

#[wasm_bindgen]
impl Engine {
    /// `max_tiles`: how many decoded tiles to keep between requests (each ~128 KB).
    #[wasm_bindgen(constructor)]
    pub fn new(max_tiles: usize) -> Engine {
        Engine { store: TileStore::new(max_tiles) }
    }

    /// Start a request: tiles touched from now on stay cached until it is done.
    pub fn begin(&mut self) {
        self.store.begin();
    }

    /// Whether a tile is already cached (or known to be missing). Marks it in use.
    #[wasm_bindgen(js_name = hasTile)]
    pub fn has_tile(&mut self, z: u8, x: u32, y: u32) -> bool {
        self.store.touch((z, x, y))
    }

    /// Decode and cache a Terrarium PNG tile.
    #[wasm_bindgen(js_name = addTile)]
    pub fn add_tile(&mut self, z: u8, x: u32, y: u32, png: &[u8]) -> Result<(), JsError> {
        let tile = decode_terrarium(png).map_err(|e| JsError::new(&e))?;
        if tile.size != TILE_SIZE {
            return Err(JsError::new(&format!("tile is {} px, expected {TILE_SIZE}", tile.size)));
        }
        self.store.insert((z, x, y), Some(tile));
        Ok(())
    }

    /// Record a tile that could not be loaded, so sampling falls back to a coarser zoom.
    #[wasm_bindgen(js_name = addMissingTile)]
    pub fn add_missing_tile(&mut self, z: u8, x: u32, y: u32) {
        self.store.insert((z, x, y), None);
    }

    #[wasm_bindgen(js_name = tileCount)]
    pub fn tile_count(&self) -> usize {
        self.store.len()
    }

    /// The view from an eye `above_ground_m` over the highest ground within `snap_m` of a
    /// position. `levels` is `[zoom, max distance m, ...]`, finest first. `targets` is
    /// `[lat, lon, height above ground m, snap m, ...]` (peaks, other lookouts).
    #[allow(clippy::too_many_arguments)]
    pub fn panorama(
        &self,
        lat: f64,
        lon: f64,
        above_ground_m: f64,
        snap_m: f64,
        levels: &[f64],
        az_step_deg: f64,
        max_dist_m: f64,
        refraction_k: f64,
        targets: &[f64],
    ) -> PanoramaResult {
        let field = sampler(&self.store, lat, lon, levels);
        let obs = Observer::locate(&field, lat, lon, above_ground_m, snap_m);
        let params = PanoramaParams { az_step_deg, max_dist_m, refraction_k, ..Default::default() };
        let pano = panorama(&field, &obs, &params);
        let targets: Vec<Target> = targets
            .chunks_exact(4)
            .map(|t| Target { lat: t[0], lon: t[1], above_ground_m: t[2], snap_m: t[3] })
            .collect();
        let sights = sight_targets(&field, &obs, Earth::new(refraction_k), &targets, max_dist_m);
        PanoramaResult {
            columns: pano.columns,
            az_step_deg: pano.az_step_deg,
            layers_m: pano.layers_m,
            horizon_deg: pano.horizon_deg,
            crest_m: pano.crest_m,
            skyline_m: pano.skyline_m,
            observer: vec![obs.lat, obs.lon, obs.ground_m, obs.eye_m(), obs.moved_m, obs.recorded_ground_m],
            targets: sights
                .iter()
                .flat_map(|s| [s.dist_m, s.az_deg, s.ground_m, s.angle_deg, s.clearance_deg, if s.visible { 1.0 } else { 0.0 }])
                .collect(),
            nodata_fraction: pano.nodata_fraction,
            samples: pano.samples as f64,
        }
    }

    /// Count, for every cell of a Web Mercator grid, how many observers see it.
    /// `observers` is `[lat, lon, eye above ground m, snap m, ...]`; each uses `levels` around
    /// itself. The grid covers all their discs with cells of about `cell_m` (larger if needed to
    /// stay under `max_cells`).
    #[allow(clippy::too_many_arguments)]
    pub fn viewshed(
        &self,
        observers: &[f64],
        levels: &[f64],
        radius_m: f64,
        target_m: f64,
        refraction_k: f64,
        cell_m: f64,
        max_cells: usize,
    ) -> ViewshedResult {
        let obs_list: Vec<&[f64]> = observers.chunks_exact(4).collect();
        let (mut x0, mut y0, mut x1, mut y1) = (f64::MAX, f64::MAX, f64::MIN, f64::MIN);
        let mut lat_mid = 0.0;
        for o in &obs_list {
            let (a, b, c, d) = disc_bbox(o[0], o[1], radius_m);
            x0 = x0.min(a);
            y0 = y0.min(b);
            x1 = x1.max(c);
            y1 = y1.max(d);
            lat_mid += o[0] / obs_list.len() as f64;
        }
        if obs_list.is_empty() {
            return ViewshedResult::default();
        }
        let grid = Grid::covering(x0, y0, x1, y1, lat_mid, cell_m, max_cells);
        let mut counts = vec![0u8; grid.width * grid.height];
        let params = ViewshedParams { radius_m, target_m, refraction_k };
        let mut per_observer = Vec::new();
        for o in &obs_list {
            let field = sampler(&self.store, o[0], o[1], levels);
            let obs = Observer::locate(&field, o[0], o[1], o[2], o[3]);
            let stats = viewshed_into(&field, &obs, &grid, &params, &mut counts);
            per_observer.extend_from_slice(&[
                obs.lat,
                obs.lon,
                obs.ground_m,
                obs.eye_m(),
                obs.moved_m,
                stats.visible_area_m2,
                stats.cells_visible as f64,
                stats.rays as f64,
                stats.steps as f64,
            ]);
        }
        ViewshedResult {
            width: grid.width,
            height: grid.height,
            mx0: grid.mx0,
            my0: grid.my0,
            cell: grid.cell,
            counts,
            observers: per_observer,
        }
    }
}

#[wasm_bindgen]
pub struct PanoramaResult {
    columns: usize,
    az_step_deg: f64,
    layers_m: Vec<f64>,
    horizon_deg: Vec<f32>,
    crest_m: Vec<f32>,
    skyline_m: Vec<f32>,
    observer: Vec<f64>,
    targets: Vec<f64>,
    nodata_fraction: f32,
    samples: f64,
}

#[wasm_bindgen]
impl PanoramaResult {
    #[wasm_bindgen(getter)]
    pub fn columns(&self) -> usize {
        self.columns
    }
    #[wasm_bindgen(getter, js_name = azStepDeg)]
    pub fn az_step_deg(&self) -> f64 {
        self.az_step_deg
    }
    #[wasm_bindgen(getter, js_name = layersM)]
    pub fn layers_m(&self) -> Vec<f64> {
        self.layers_m.clone()
    }
    /// `layers × columns` elevation angles (degrees), layer-major.
    #[wasm_bindgen(getter, js_name = horizonDeg)]
    pub fn horizon_deg(&self) -> Vec<f32> {
        self.horizon_deg.clone()
    }
    /// `layers × columns` crest distances (m, NaN where the layer adds nothing).
    #[wasm_bindgen(getter, js_name = crestM)]
    pub fn crest_m(&self) -> Vec<f32> {
        self.crest_m.clone()
    }
    #[wasm_bindgen(getter, js_name = skylineM)]
    pub fn skyline_m(&self) -> Vec<f32> {
        self.skyline_m.clone()
    }
    /// `[lat, lon, ground m, eye m, moved m, ground at the recorded position m]`.
    #[wasm_bindgen(getter)]
    pub fn observer(&self) -> Vec<f64> {
        self.observer.clone()
    }
    /// Per target `[distance m, azimuth°, ground m, angle°, clearance°, visible 0/1]`.
    #[wasm_bindgen(getter)]
    pub fn targets(&self) -> Vec<f64> {
        self.targets.clone()
    }
    #[wasm_bindgen(getter, js_name = nodataFraction)]
    pub fn nodata_fraction(&self) -> f32 {
        self.nodata_fraction
    }
    #[wasm_bindgen(getter)]
    pub fn samples(&self) -> f64 {
        self.samples
    }
}

#[wasm_bindgen]
#[derive(Default)]
pub struct ViewshedResult {
    width: usize,
    height: usize,
    mx0: f64,
    my0: f64,
    cell: f64,
    counts: Vec<u8>,
    observers: Vec<f64>,
}

#[wasm_bindgen]
impl ViewshedResult {
    #[wasm_bindgen(getter)]
    pub fn width(&self) -> usize {
        self.width
    }
    #[wasm_bindgen(getter)]
    pub fn height(&self) -> usize {
        self.height
    }
    /// Normalised Web Mercator x of the grid's west edge.
    #[wasm_bindgen(getter)]
    pub fn mx0(&self) -> f64 {
        self.mx0
    }
    /// Normalised Web Mercator y of the grid's north edge.
    #[wasm_bindgen(getter)]
    pub fn my0(&self) -> f64 {
        self.my0
    }
    /// Cell size in normalised Mercator units.
    #[wasm_bindgen(getter)]
    pub fn cell(&self) -> f64 {
        self.cell
    }
    /// How many observers see each cell, row-major from the north-west.
    #[wasm_bindgen(getter)]
    pub fn counts(&self) -> Vec<u8> {
        self.counts.clone()
    }
    /// Per observer `[lat, lon, ground m, eye m, moved m, visible area m², visible cells, rays, steps]`.
    #[wasm_bindgen(getter)]
    pub fn observers(&self) -> Vec<f64> {
        self.observers.clone()
    }
}
