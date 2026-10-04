//! "What it could see": which ground within a radius is in a lookout's line of sight, drawn
//! into a Web Mercator grid that the map overlays directly.
//!
//! Rays leave the eye about one grid cell apart at the outer edge and march in steps of
//! one cell, keeping the running maximum apparent slope (the horizon so far) at every step.
//! Each grid cell inside the radius then looks up the horizon of the two rays either side of
//! it, just before its own distance, and is visible if its ground (plus an optional target
//! height, such as a smoke column) reaches above it. Several lookouts add into one count grid,
//! which is how the map shades "seen by 2 or more".

use std::f64::consts::TAU;

use crate::dem::HeightField;
use crate::geo::{Vec3, metres_per_mercator_unit, unmercator};
use crate::sight::{Earth, Observer, Steps};

/// A north-up grid in normalised Web Mercator coordinates (row 0 is the north edge).
#[derive(Clone, Copy, Debug)]
pub struct Grid {
    pub mx0: f64,
    pub my0: f64,
    /// Cell size in normalised Mercator units.
    pub cell: f64,
    pub width: usize,
    pub height: usize,
}

impl Grid {
    /// A grid covering the given Mercator box with cells of about `cell_m` metres at `lat`,
    /// growing the cells if needed to stay under `max_cells`.
    pub fn covering(mx0: f64, my0: f64, mx1: f64, my1: f64, lat: f64, cell_m: f64, max_cells: usize) -> Grid {
        let per_unit = metres_per_mercator_unit(lat);
        let mut cell = cell_m / per_unit;
        let (w, h) = (mx1 - mx0, my1 - my0);
        let cells = (w / cell).ceil() * (h / cell).ceil();
        if cells > max_cells as f64 {
            cell *= (cells / max_cells as f64).sqrt() * 1.001;
        }
        Grid {
            mx0,
            my0,
            cell,
            width: ((w / cell).ceil() as usize).max(1),
            height: ((h / cell).ceil() as usize).max(1),
        }
    }

    pub fn cell_center(&self, ix: usize, iy: usize) -> (f64, f64) {
        (self.mx0 + (ix as f64 + 0.5) * self.cell, self.my0 + (iy as f64 + 0.5) * self.cell)
    }

    /// Size of a cell on the ground at a latitude, m.
    pub fn cell_m(&self, lat: f64) -> f64 {
        self.cell * metres_per_mercator_unit(lat)
    }
}

#[derive(Clone, Debug)]
pub struct ViewshedParams {
    pub radius_m: f64,
    /// Height above the ground that must be visible (0 = the ground itself), m.
    pub target_m: f64,
    pub refraction_k: f64,
}

#[derive(Clone, Copy, Debug, Default)]
pub struct ViewshedStats {
    pub rays: usize,
    pub steps: usize,
    pub cells_in_radius: usize,
    pub cells_visible: usize,
    /// Visible ground area, m².
    pub visible_area_m2: f64,
}

/// Add 1 to `counts` (row-major, `grid.width × grid.height`) for every cell the observer sees.
pub fn viewshed_into(field: &impl HeightField, obs: &Observer, grid: &Grid, p: &ViewshedParams, counts: &mut [u8]) -> ViewshedStats {
    assert_eq!(counts.len(), grid.width * grid.height);
    let earth = Earth::new(p.refraction_k);
    let eye = obs.eye_m();
    let cell_m = grid.cell_m(obs.lat).max(1.0);
    let step = cell_m;
    let k_count = (p.radius_m / step).ceil() as usize + 1;
    let rays = ((TAU * p.radius_m / cell_m).ceil() as usize).max(64);
    let steps = Steps::uniform(step, k_count);
    let mut stats = ViewshedStats { rays, steps: k_count, ..Default::default() };
    if !eye.is_finite() {
        return stats;
    }

    // horizon[r * k_count + k]: largest slope among samples 0..k (exclusive) on ray r.
    let mut horizon = vec![f32::NEG_INFINITY; rays * k_count];
    let mut heights = vec![0f32; k_count];
    for r in 0..rays {
        let dir = obs.frame.direction(TAU * r as f64 / rays as f64);
        field.heights_along(&obs.frame, dir, &steps, k_count, &mut heights);
        let mut run = f64::NEG_INFINITY;
        let row = &mut horizon[r * k_count..(r + 1) * k_count];
        for k in 0..k_count {
            row[k] = run as f32;
            let h = heights[k] as f64;
            if h.is_finite() {
                let s = steps.slope(&earth, k, h, eye);
                if s > run {
                    run = s;
                }
            }
        }
    }

    // Only the cells in the radius's bounding box.
    let (bx0, by0, bx1, by1) = crate::geo::disc_bbox(obs.lat, obs.lon, p.radius_m);
    let ix0 = ((bx0 - grid.mx0) / grid.cell).floor().max(0.0) as usize;
    let iy0 = ((by0 - grid.my0) / grid.cell).floor().max(0.0) as usize;
    let ix1 = (((bx1 - grid.mx0) / grid.cell).ceil().max(0.0) as usize).min(grid.width);
    let iy1 = (((by1 - grid.my0) / grid.cell).ceil().max(0.0) as usize).min(grid.height);
    // Cell centres as unit vectors from per-row latitude and per-column longitude terms.
    let cols: Vec<(f64, f64)> = (ix0..ix1)
        .map(|ix| {
            let (mx, _) = grid.cell_center(ix, 0);
            ((mx - 0.5) * TAU).sin_cos()
        })
        .collect();
    for iy in iy0..iy1 {
        let (_, my) = grid.cell_center(0, iy);
        let (row_lat, _) = unmercator(0.5, my);
        let (slat, clat) = row_lat.to_radians().sin_cos();
        let cell_area = grid.cell_m(row_lat).powi(2);
        for ix in ix0..ix1 {
            let (slon, clon) = cols[ix - ix0];
            let v = Vec3::new(clat * clon, clat * slon, slat);
            let (d, az) = obs.frame.inverse(v);
            if d > p.radius_m {
                continue;
            }
            stats.cells_in_radius += 1;
            let visible = if d < step {
                true
            } else {
                let (mx, _) = grid.cell_center(ix, iy);
                let h = field.height_mercator(mx, my, v, d) as f64;
                if h.is_nan() {
                    false
                } else {
                    let s = earth.slope(h + p.target_m, eye, d);
                    let rf = az / TAU * rays as f64;
                    let r0 = (rf.floor() as usize) % rays;
                    let r1 = (r0 + 1) % rays;
                    let t = (rf - rf.floor()) as f32;
                    // The last sample at or before the cell is the cell's own ground; look
                    // at the horizon formed by everything nearer than that.
                    let k = ((d / step).floor() as usize).saturating_sub(1).min(k_count - 1);
                    let h0 = horizon[r0 * k_count + k];
                    let h1 = horizon[r1 * k_count + k];
                    let hz = if h0.is_finite() && h1.is_finite() {
                        h0 * (1.0 - t) + h1 * t
                    } else if h0.is_finite() {
                        h0
                    } else {
                        h1
                    };
                    !(hz.is_finite()) || s as f32 >= hz
                }
            };
            if visible {
                let i = iy * grid.width + ix;
                counts[i] = counts[i].saturating_add(1);
                stats.cells_visible += 1;
                stats.visible_area_m2 += cell_area;
            }
        }
    }
    stats
}
