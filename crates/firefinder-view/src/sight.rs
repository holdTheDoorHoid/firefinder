//! Lines of sight from an observer over a curved, refracting earth.
//!
//! The elevation angle of a terrain point seen from the eye is computed from its "apparent
//! slope": `(h - eye) / d - d / (2 R')`, where `R' = R / (1 - k)` is the effective earth radius
//! that folds atmospheric refraction (coefficient k) into the curvature. This is the standard
//! surveying approximation; for d up to a few hundred km its error is far below the size of a
//! terrain pixel. A point is visible when its slope is at least the largest slope of all terrain
//! nearer along the same line.

use crate::dem::HeightField;
use crate::geo::{EARTH_RADIUS_M, Frame, unit};
use crate::panorama::Panorama;

/// Curvature and refraction for slope computations.
#[derive(Clone, Copy, Debug)]
pub struct Earth {
    /// `(1 - k) / (2 R)`: the curvature drop is `d² * inv_2r`.
    pub inv_2r: f64,
}

impl Earth {
    pub fn new(refraction_k: f64) -> Self {
        Earth { inv_2r: (1.0 - refraction_k) / (2.0 * EARTH_RADIUS_M) }
    }
    /// Effective earth radius R' in metres.
    pub fn effective_radius(&self) -> f64 {
        0.5 / self.inv_2r
    }
    #[inline]
    pub fn slope(&self, h: f64, eye: f64, d: f64) -> f64 {
        (h - eye) / d - d * self.inv_2r
    }
}

/// Where the eye is. Built by [`Observer::locate`] from a recorded position.
#[derive(Clone, Copy, Debug)]
pub struct Observer {
    pub frame: Frame,
    pub lat: f64,
    pub lon: f64,
    /// Ground height under the eye, m above sea level (NaN if the terrain is unknown there).
    pub ground_m: f64,
    /// Eye height above the ground, m.
    pub above_ground_m: f64,
    /// How far the observer was moved from the recorded position to the local high point, m.
    pub moved_m: f64,
    /// Ground height at the recorded position itself, m.
    pub recorded_ground_m: f64,
}

impl Observer {
    pub fn eye_m(&self) -> f64 {
        self.ground_m + self.above_ground_m
    }

    /// An observer at a recorded position, optionally moved to the highest ground within
    /// `snap_m`. Lookouts stand on high points, while recorded coordinates can be a few tens of
    /// metres off and coarse terrain rounds summits down; without this the summit the lookout
    /// stands on can hide half the view.
    pub fn locate(field: &impl HeightField, lat: f64, lon: f64, above_ground_m: f64, snap_m: f64) -> Observer {
        let frame = Frame::new(lat, lon);
        let at = field.height(frame.origin, 0.0) as f64;
        let (mut best_h, mut best) = (at, (lat, lon, 0.0));
        if snap_m > 0.0 {
            let spacing = field.spacing_m(0.0).max(1.0);
            let step = (spacing / 3.0).clamp(3.0, snap_m.max(3.0));
            let rings = (snap_m / step).ceil() as usize;
            for ring in 1..=rings {
                let r = (ring as f64 * step).min(snap_m);
                let n = ((std::f64::consts::TAU * r / step).ceil() as usize).max(6);
                for i in 0..n {
                    let az = std::f64::consts::TAU * i as f64 / n as f64;
                    let v = frame.walk(frame.direction(az), r);
                    let h = field.height(v, 0.0) as f64;
                    // Must beat the recorded spot by more than noise to justify moving.
                    if h.is_finite() && (best_h.is_nan() || h > best_h + 0.5) {
                        let (la, lo) = crate::geo::lat_lon(v);
                        best_h = h;
                        best = (la, lo, r);
                    }
                }
            }
        }
        let (la, lo, moved) = best;
        Observer {
            frame: Frame::new(la, lo),
            lat: la,
            lon: lo,
            ground_m: best_h,
            above_ground_m,
            moved_m: moved,
            recorded_ground_m: at,
        }
    }

    /// An observer at an exact spot and absolute ground height (tests, synthetic terrain).
    pub fn at(lat: f64, lon: f64, ground_m: f64, above_ground_m: f64) -> Observer {
        Observer {
            frame: Frame::new(lat, lon),
            lat,
            lon,
            ground_m,
            above_ground_m,
            moved_m: 0.0,
            recorded_ground_m: ground_m,
        }
    }
}

/// Distances at which a ray samples the terrain, shared by every ray of a computation (so the
/// sines and cosines of the arc are computed once).
pub struct Steps {
    pub d: Vec<f64>,
    pub cos: Vec<f64>,
    pub sin: Vec<f64>,
    /// 1 / d, to turn height differences into slopes without dividing.
    pub inv_d: Vec<f64>,
}

impl Steps {
    /// From `start` out to `max`, each step `max(min_step, d * rel_step)` and never more than
    /// the terrain spacing allows when `field` is given.
    pub fn new(start: f64, max: f64, min_step: f64, rel_step: f64, field: Option<&dyn HeightField>) -> Steps {
        let mut d = Vec::new();
        let mut x = start.max(1.0);
        while x < max {
            d.push(x);
            let mut step = (x * rel_step).max(min_step);
            if let Some(f) = field {
                // No finer than ~0.4 terrain pixels (bilinear in between adds nothing), no
                // coarser than one pixel (or a peak could slip between samples).
                let spacing = f.spacing_m(x);
                step = step.max(spacing * 0.4).min(spacing.max(min_step));
            }
            x += step;
        }
        d.push(max);
        Steps::from_distances(d)
    }

    fn from_distances(d: Vec<f64>) -> Steps {
        let cos = d.iter().map(|x| (x / EARTH_RADIUS_M).cos()).collect();
        let sin = d.iter().map(|x| (x / EARTH_RADIUS_M).sin()).collect();
        let inv_d = d.iter().map(|x| 1.0 / x).collect();
        Steps { d, cos, sin, inv_d }
    }

    /// Slope of terrain height `h` at step `i` seen from `eye`.
    #[inline]
    pub fn slope(&self, earth: &Earth, i: usize, h: f64, eye: f64) -> f64 {
        (h - eye) * self.inv_d[i] - self.d[i] * earth.inv_2r
    }

    /// The schedule for a view out to `max_m`: 10 m steps near the eye, then 0.3% of the
    /// distance, never coarser than the terrain spacing.
    pub fn for_view(field: &dyn HeightField, start: f64, max_m: f64) -> Steps {
        Steps::new(start, max_m, 10.0, 0.003, Some(field))
    }

    /// Evenly spaced steps (viewsheds).
    pub fn uniform(step: f64, count: usize) -> Steps {
        Steps::from_distances((1..=count).map(|k| k as f64 * step).collect())
    }

    pub fn len(&self) -> usize {
        self.d.len()
    }

    pub fn is_empty(&self) -> bool {
        self.d.is_empty()
    }
}

/// A point to test for visibility (a summit, another lookout's cab).
#[derive(Clone, Copy, Debug)]
pub struct Target {
    pub lat: f64,
    pub lon: f64,
    /// Height of the thing above the ground (a cab's windows), m.
    pub above_ground_m: f64,
    /// Search this far around the point for its highest ground (summits), m. 0 = exact.
    pub snap_m: f64,
}

#[derive(Clone, Copy, Debug, Default)]
pub struct TargetSight {
    pub dist_m: f64,
    pub az_deg: f64,
    /// Ground height at the target, m (NaN when unknown).
    pub ground_m: f64,
    /// Elevation angle of the target's top seen from the eye, degrees.
    pub angle_deg: f64,
    /// How far the target's top clears the highest nearer terrain, degrees (negative: hidden).
    pub clearance_deg: f64,
    pub visible: bool,
}

/// Which targets the observer can see. A target counts as visible when its top is not below
/// the terrain between, ignoring the last stretch before it (2% of the distance, 150 m to
/// 1.5 km) so a mountain is not hidden by its own near slope. `steps` is the marching schedule
/// (normally the panorama's, see [`Steps::for_view`]); `pano`, when given, rejects targets
/// that are plainly hidden without marching to them.
pub fn sight_targets(
    field: &impl HeightField,
    obs: &Observer,
    earth: Earth,
    targets: &[Target],
    max_dist_m: f64,
    steps: &Steps,
    pano: Option<&Panorama>,
) -> Vec<TargetSight> {
    let eye = obs.eye_m();
    let mut heights = vec![0f32; steps.len()];
    targets
        .iter()
        .map(|t| {
            let v = unit(t.lat, t.lon);
            let (dist, az) = obs.frame.inverse(v);
            let mut out = TargetSight { dist_m: dist, az_deg: az.to_degrees(), ground_m: f64::NAN, ..Default::default() };
            out.angle_deg = f64::NAN;
            out.clearance_deg = f64::NAN;
            if !(dist > 1.0) || dist > max_dist_m || !eye.is_finite() {
                return out;
            }
            // Highest ground near the target.
            let mut ground = field.height(v, dist) as f64;
            if t.snap_m > 0.0 {
                let tf = Frame::new(t.lat, t.lon);
                for ring in [0.5, 1.0] {
                    for i in 0..8 {
                        let a = std::f64::consts::TAU * i as f64 / 8.0;
                        let h = field.height(tf.walk(tf.direction(a), t.snap_m * ring), dist) as f64;
                        if h.is_finite() && (ground.is_nan() || h > ground) {
                            ground = h;
                        }
                    }
                }
            }
            out.ground_m = ground;
            if ground.is_nan() {
                return out;
            }
            let top = earth.slope(ground + t.above_ground_m, eye, dist);
            let guard = (dist * 0.02).clamp(150.0, 1_500.0);
            // Quick rejection from the panorama: the horizon of the layers wholly in front of
            // the target, on the columns either side of it, less a quarter-degree margin. It can
            // only under-estimate what hides the target, so nothing visible is rejected.
            if let Some(p) = pano {
                if let Some(j) = p.layers_m.iter().rposition(|&b| b <= dist - guard) {
                    let cf = out.az_deg / p.az_step_deg;
                    let c0 = (cf.floor() as usize) % p.columns;
                    let c1 = (c0 + 1) % p.columns;
                    let h = f64::from(p.horizon(j, c0).min(p.horizon(j, c1)));
                    let angle = top.atan().to_degrees();
                    if angle < h - 0.25 {
                        out.angle_deg = angle;
                        out.clearance_deg = angle - h;
                        return out;
                    }
                }
            }
            let n = steps.d.partition_point(|&d| d < dist - guard);
            field.heights_along(&obs.frame, obs.frame.direction(az), steps, n, &mut heights);
            let mut max = f64::NEG_INFINITY;
            for i in 0..n {
                let h = heights[i] as f64;
                if h.is_finite() {
                    let sl = steps.slope(&earth, i, h, eye);
                    if sl > max {
                        max = sl;
                    }
                }
            }
            out.angle_deg = top.atan().to_degrees();
            out.clearance_deg = if max.is_finite() { out.angle_deg - max.atan().to_degrees() } else { 90.0 };
            out.visible = out.clearance_deg >= -0.002;
            out
        })
        .collect()
}
