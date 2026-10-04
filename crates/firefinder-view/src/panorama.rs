//! The 360° view from an eye: layered skylines by distance.
//!
//! For every azimuth column we march outward and keep the running maximum apparent slope. At
//! each layer boundary `B_j` we record `H_j`, the horizon formed by all terrain nearer than
//! `B_j`. Because `H_j` can only rise as `j` grows, drawing the layers from the farthest to the
//! nearest (each filled from its line down) colours every pixel by the nearest terrain that
//! reaches it: exactly what the eye would see, with each band shaded by distance like a classic
//! lookout panorama drawing. `crest_j` gives the distance of the ridge that forms `H_j` when
//! that ridge lies inside layer j (NaN when the layer adds nothing new to the view).

use crate::dem::HeightField;
use crate::sight::{Earth, Observer, Steps};

/// Layer boundaries in metres: fine near the cab, about 15% apart beyond 10 km.
pub const DEFAULT_LAYERS_M: &[f64] = &[
    150.0, 300.0, 500.0, 750.0, 1_000.0, 1_500.0, 2_000.0, 2_750.0, 3_500.0, 4_500.0, 5_500.0, 7_000.0, 8_500.0,
    10_000.0, 12_000.0, 14_000.0, 16_500.0, 19_000.0, 22_000.0, 25_000.0, 29_000.0, 33_000.0, 38_000.0,
    44_000.0, 50_000.0, 57_000.0, 65_000.0, 75_000.0, 86_000.0, 100_000.0, 115_000.0, 130_000.0, 150_000.0,
    175_000.0, 200_000.0, 250_000.0,
];

#[derive(Clone, Debug)]
pub struct PanoramaParams {
    pub az_step_deg: f64,
    pub max_dist_m: f64,
    /// Smallest marching step, m.
    pub min_step_m: f64,
    /// Step as a fraction of distance (capped by the terrain spacing).
    pub rel_step: f64,
    pub refraction_k: f64,
    /// Where to start marching (the cab floor hides the ground right under you), m.
    pub start_m: f64,
}

impl Default for PanoramaParams {
    fn default() -> Self {
        PanoramaParams {
            az_step_deg: 0.1,
            max_dist_m: 150_000.0,
            min_step_m: 10.0,
            rel_step: 0.003,
            refraction_k: crate::geo::DEFAULT_REFRACTION,
            start_m: 20.0,
        }
    }
}

#[derive(Clone, Debug)]
pub struct Panorama {
    pub columns: usize,
    pub az_step_deg: f64,
    /// Outer edge of each layer, m (the last is the maximum distance).
    pub layers_m: Vec<f64>,
    /// `layers × columns` horizon elevation angles in degrees, layer-major. -90 where a
    /// layer has no terrain at all (no data).
    pub horizon_deg: Vec<f32>,
    /// `layers × columns` distance (m) of the crest that forms the horizon when it lies within
    /// that layer, else NaN.
    pub crest_m: Vec<f32>,
    /// Per column, distance (m) of the farthest visible skyline point.
    pub skyline_m: Vec<f32>,
    /// Fraction of samples that had no terrain data.
    pub nodata_fraction: f32,
    pub samples: u64,
}

impl Panorama {
    pub fn layer_count(&self) -> usize {
        self.layers_m.len()
    }
    pub fn horizon(&self, layer: usize, column: usize) -> f32 {
        self.horizon_deg[layer * self.columns + column]
    }
    /// The full skyline angle at a column (all terrain out to the maximum distance).
    pub fn skyline(&self, column: usize) -> f32 {
        self.horizon(self.layer_count() - 1, column)
    }
}

pub fn panorama(field: &impl HeightField, obs: &Observer, p: &PanoramaParams) -> Panorama {
    let earth = Earth::new(p.refraction_k);
    let eye = obs.eye_m();
    let columns = (360.0 / p.az_step_deg).round().max(1.0) as usize;
    let az_step = 360.0 / columns as f64;
    let mut layers: Vec<f64> = DEFAULT_LAYERS_M.iter().copied().filter(|&b| b < p.max_dist_m).collect();
    layers.push(p.max_dist_m);
    let nl = layers.len();
    let steps = Steps::new(p.start_m, p.max_dist_m, p.min_step_m, p.rel_step, Some(field as &dyn HeightField));
    let mut horizon = vec![-90f32; nl * columns];
    let mut crest = vec![f32::NAN; nl * columns];
    let mut skyline = vec![f32::NAN; columns];
    let mut nodata = 0u64;
    let mut samples = 0u64;

    for c in 0..columns {
        let az = (c as f64 * az_step).to_radians();
        let dir = obs.frame.direction(az);
        let mut run = f64::NEG_INFINITY;
        let mut arg = f64::NAN;
        let mut layer = 0usize;
        let mut layer_start = 0.0f64;
        let emit = |layer: usize, run: f64, arg: f64, layer_start: f64, horizon: &mut Vec<f32>, crest: &mut Vec<f32>| {
            if run.is_finite() {
                horizon[layer * columns + c] = run.atan().to_degrees() as f32;
                if arg > layer_start {
                    crest[layer * columns + c] = arg as f32;
                }
            }
        };
        for i in 0..steps.len() {
            let d = steps.d[i];
            while layer < nl && d > layers[layer] {
                emit(layer, run, arg, layer_start, &mut horizon, &mut crest);
                layer_start = layers[layer];
                layer += 1;
            }
            let v = obs.frame.origin.combine(steps.cos[i], dir, steps.sin[i]);
            let h = field.height(v, d) as f64;
            samples += 1;
            if h.is_nan() || !eye.is_finite() {
                nodata += 1;
                continue;
            }
            let s = earth.slope(h, eye, d);
            if s > run {
                run = s;
                arg = d;
            }
        }
        while layer < nl {
            emit(layer, run, arg, layer_start, &mut horizon, &mut crest);
            layer_start = layers[layer];
            layer += 1;
        }
        skyline[c] = arg as f32;
    }

    Panorama {
        columns,
        az_step_deg: az_step,
        layers_m: layers,
        horizon_deg: horizon,
        crest_m: crest,
        skyline_m: skyline,
        nodata_fraction: if samples > 0 { nodata as f32 / samples as f32 } else { 0.0 },
        samples,
    }
}
