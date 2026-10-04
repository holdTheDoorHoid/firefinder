//! Synthetic terrain for tests: heights defined on a local east/north plane around an origin,
//! measured as true distances on the sphere (so a "flat plane" is a sphere at sea level and
//! earth curvature is still in play).

use crate::dem::HeightField;
use crate::geo::{Frame, Vec3};
use crate::panorama::{PanoramaParams, panorama};
use crate::sight::{Earth, Observer, Target, sight_targets};
use crate::viewshed::{Grid, ViewshedParams, viewshed_into};

pub struct Synthetic<F: Fn(f64, f64) -> f64> {
    pub frame: Frame,
    pub f: F,
}

impl<F: Fn(f64, f64) -> f64> Synthetic<F> {
    pub fn new(lat: f64, lon: f64, f: F) -> Self {
        Synthetic { frame: Frame::new(lat, lon), f }
    }
}

impl<F: Fn(f64, f64) -> f64> HeightField for Synthetic<F> {
    fn height(&self, v: Vec3, _dist: f64) -> f32 {
        let (d, az) = self.frame.inverse(v);
        (self.f)(d * az.sin(), d * az.cos()) as f32
    }
    fn spacing_m(&self, _dist: f64) -> f64 {
        10.0
    }
}

const LAT: f64 = 45.0;
const LON: f64 = -116.0;
const K: f64 = 0.13;

fn r_eff() -> f64 {
    Earth::new(K).effective_radius()
}

fn params(max: f64, az_step: f64) -> PanoramaParams {
    PanoramaParams { az_step_deg: az_step, max_dist_m: max, refraction_k: K, ..Default::default() }
}

fn cone(cx: f64, cy: f64, height: f64, radius: f64) -> impl Fn(f64, f64) -> f64 {
    move |e, n| {
        let r = ((e - cx).powi(2) + (n - cy).powi(2)).sqrt();
        (height * (1.0 - r / radius)).max(0.0)
    }
}

/// Column index of an azimuth in a panorama.
fn col(az: f64, step: f64) -> usize {
    (az / step).round() as usize
}

#[test]
fn flat_earth_horizon_matches_the_analytic_distance_and_dip() {
    for (eye, k) in [(100.0, K), (100.0, 0.0), (1_500.0, K)] {
        let field = Synthetic::new(LAT, LON, |_, _| 0.0);
        let obs = Observer::at(LAT, LON, 0.0, eye);
        let p = PanoramaParams { az_step_deg: 30.0, max_dist_m: 250_000.0, refraction_k: k, ..Default::default() };
        let pano = panorama(&field, &obs, &p);
        let r = Earth::new(k).effective_radius();
        // Distance to the horizon over a sphere of radius R': sqrt(2 R' h) (to 1 part in 10⁴).
        let expect_d = (2.0 * r * eye).sqrt();
        // Dip of the horizon: arccos(R' / (R' + h)).
        let expect_dip = -(r / (r + eye)).acos().to_degrees();
        for c in 0..pano.columns {
            let d = pano.skyline_m[c] as f64;
            assert!((d - expect_d).abs() / expect_d < 0.01, "eye {eye} k {k}: horizon at {d:.0} m, expected {expect_d:.0} m");
            let dip = pano.skyline(c) as f64;
            assert!((dip - expect_dip).abs() < 0.002, "eye {eye} k {k}: dip {dip:.4}°, expected {expect_dip:.4}°");
        }
    }
    // The textbook number: from 100 m with k = 0.13 the horizon is about 38.3 km away.
    assert!(((2.0 * r_eff() * 100.0).sqrt() - 38_270.0).abs() < 100.0);
}

#[test]
fn a_cone_rises_where_expected_and_hides_what_is_behind_it() {
    // A 1,000 m cone, 3 km in radius, 10 km due east.
    let field = Synthetic::new(LAT, LON, cone(10_000.0, 0.0, 1_000.0, 3_000.0));
    let obs = Observer::at(LAT, LON, 0.0, 20.0);
    let step = 0.5;
    let pano = panorama(&field, &obs, &params(60_000.0, step));
    let east = col(90.0, step);
    let expect = ((1_000.0 - 20.0) / 10_000.0 - 10_000.0 / (2.0 * r_eff())).atan().to_degrees();
    let got = pano.skyline(east) as f64;
    assert!((got - expect).abs() < 0.05, "cone top at {got:.3}°, expected {expect:.3}°");
    assert!((pano.skyline_m[east] as f64 - 10_000.0).abs() < 60.0, "crest at {} m", pano.skyline_m[east]);
    // North: flat ground to the horizon (dip for 20 m).
    let north = pano.skyline(0) as f64;
    let dip = -(r_eff() / (r_eff() + 20.0)).acos().to_degrees();
    assert!((north - dip).abs() < 0.003, "{north} vs {dip}");
    // Half the cone's width away from its axis the skyline is lower but still above the horizon.
    let flank = pano.skyline(col(90.0 + 8.0, step)) as f64;
    assert!(flank > dip + 0.5 && flank < got, "flank {flank}");

    let targets = [
        // Behind the cone on the ground: hidden.
        Target { lat: 0.0, lon: 0.0, above_ground_m: 0.0, snap_m: 0.0 },
        // The cone's summit itself: visible.
        Target { lat: 0.0, lon: 0.0, above_ground_m: 0.0, snap_m: 0.0 },
        // Open ground 10 km north (horizon is 17 km away from 20 m): visible.
        Target { lat: 0.0, lon: 0.0, above_ground_m: 0.0, snap_m: 0.0 },
        // A 3 km mast behind the cone pokes out above it.
        Target { lat: 0.0, lon: 0.0, above_ground_m: 3_000.0, snap_m: 0.0 },
        // Ground 25 km north: beyond the horizon.
        Target { lat: 0.0, lon: 0.0, above_ground_m: 0.0, snap_m: 0.0 },
    ];
    let place = [(90.0, 20_000.0), (90.0, 10_000.0), (0.0, 10_000.0), (90.0, 20_000.0), (0.0, 25_000.0)];
    let targets: Vec<Target> = targets
        .iter()
        .zip(place)
        .map(|(t, (az, d))| {
            let (lat, lon) = crate::geo::destination(LAT, LON, az, d);
            Target { lat, lon, ..*t }
        })
        .collect();
    let seen = sight_targets(&field, &obs, Earth::new(K), &targets, 60_000.0);
    let vis: Vec<bool> = seen.iter().map(|s| s.visible).collect();
    assert_eq!(vis, vec![false, true, true, true, false]);
    assert!((seen[1].az_deg - 90.0).abs() < 1e-6 && (seen[1].dist_m - 10_000.0).abs() < 1e-3);
    assert!((seen[1].ground_m - 1_000.0).abs() < 1.0);
}

#[test]
fn ridges_make_layers_and_shadows() {
    // A 500 m ridge 5 km east and a 2,000 m ridge 15 km east, both running north-south.
    let ridge = |at: f64, h: f64| move |e: f64| (h * (1.0 - (e - at).abs() / 1_000.0)).max(0.0);
    let (r1, r2) = (ridge(5_000.0, 500.0), ridge(15_000.0, 2_000.0));
    let field = Synthetic::new(LAT, LON, move |e, _| r1(e).max(r2(e)));
    let obs = Observer::at(LAT, LON, 0.0, 10.0);
    let step = 1.0;
    let pano = panorama(&field, &obs, &params(40_000.0, step));
    let east = col(90.0, step);
    // Each ridge is the crest of the layer it falls in.
    let crest_in = |d: f64| {
        let j = pano.layers_m.iter().position(|&b| b >= d).unwrap();
        pano.crest_m[j * pano.columns + east] as f64
    };
    assert!((crest_in(5_000.0) - 5_000.0).abs() < 30.0, "near ridge crest {}", crest_in(5_000.0));
    assert!((crest_in(15_000.0) - 15_000.0).abs() < 30.0, "far ridge crest {}", crest_in(15_000.0));
    // The layer horizons rise monotonically with distance.
    for c in 0..pano.columns {
        for j in 1..pano.layer_count() {
            assert!(pano.horizon(j, c) >= pano.horizon(j - 1, c));
        }
    }

    // Viewshed: the valley between the ridges is in shadow, the far ridge's face is seen.
    let radius = 20_000.0;
    let (x0, y0, x1, y1) = crate::geo::disc_bbox(LAT, LON, radius);
    let grid = Grid::covering(x0, y0, x1, y1, LAT, 100.0, 2_000_000);
    let mut counts = vec![0u8; grid.width * grid.height];
    let stats = viewshed_into(&field, &obs, &grid, &ViewshedParams { radius_m: radius, target_m: 0.0, refraction_k: K }, &mut counts);
    assert!(stats.cells_visible > 0);
    let seen_at = |east: f64, north: f64| {
        let (d, az) = ((east * east + north * north).sqrt(), east.atan2(north).to_degrees());
        let (lat, lon) = crate::geo::destination(LAT, LON, az, d);
        let (mx, my) = crate::geo::mercator(lat, lon);
        let ix = ((mx - grid.mx0) / grid.cell) as usize;
        let iy = ((my - grid.my0) / grid.cell) as usize;
        counts[iy * grid.width + ix]
    };
    assert_eq!(seen_at(-8_000.0, 0.0), 1, "open ground to the west");
    assert_eq!(seen_at(4_500.0, 0.0), 1, "the near ridge's west face");
    for e in [6_500.0, 8_000.0, 10_000.0, 12_000.0] {
        assert_eq!(seen_at(e, 1_000.0), 0, "valley at {e} m east is hidden");
    }
    assert_eq!(seen_at(14_850.0, 0.0), 1, "the far ridge's upper west face");
    assert_eq!(seen_at(14_600.0, 0.0), 0, "the far ridge's lower west face is below the near ridge");
    assert_eq!(seen_at(17_000.0, 0.0), 0, "behind the far ridge");
}

#[test]
fn flat_viewshed_is_a_disc_out_to_the_horizon() {
    let field = Synthetic::new(LAT, LON, |_, _| 0.0);
    let obs = Observer::at(LAT, LON, 0.0, 100.0);
    let radius = 50_000.0;
    let (x0, y0, x1, y1) = crate::geo::disc_bbox(LAT, LON, radius);
    let grid = Grid::covering(x0, y0, x1, y1, LAT, 250.0, 2_000_000);
    let mut counts = vec![0u8; grid.width * grid.height];
    let stats = viewshed_into(&field, &obs, &grid, &ViewshedParams { radius_m: radius, target_m: 0.0, refraction_k: K }, &mut counts);
    let dh = (2.0 * r_eff() * 100.0).sqrt();
    let area = std::f64::consts::PI * dh * dh;
    assert!((stats.visible_area_m2 - area).abs() / area < 0.03, "{} vs {}", stats.visible_area_m2, area);
    for iy in 0..grid.height {
        for ix in 0..grid.width {
            let (mx, my) = grid.cell_center(ix, iy);
            let (lat, lon) = crate::geo::unmercator(mx, my);
            let (d, _) = crate::geo::distance_azimuth(LAT, LON, lat, lon);
            let c = counts[iy * grid.width + ix];
            if d < 0.97 * dh {
                assert_eq!(c, 1, "inside the horizon at {d:.0} m");
            } else if d > 1.03 * dh {
                assert_eq!(c, 0, "beyond the horizon at {d:.0} m");
            }
        }
    }
}

#[test]
fn two_lookouts_count_into_one_grid() {
    let field = Synthetic::new(LAT, LON, |_, _| 0.0);
    let a = Observer::at(LAT, LON, 0.0, 100.0);
    let (blat, blon) = crate::geo::destination(LAT, LON, 90.0, 30_000.0);
    let b = Observer::at(blat, blon, 0.0, 100.0);
    let radius = 45_000.0;
    let (ax0, ay0, ax1, ay1) = crate::geo::disc_bbox(LAT, LON, radius);
    let (bx0, by0, bx1, by1) = crate::geo::disc_bbox(blat, blon, radius);
    let grid = Grid::covering(ax0.min(bx0), ay0.min(by0), ax1.max(bx1), ay1.max(by1), LAT, 300.0, 2_000_000);
    let mut counts = vec![0u8; grid.width * grid.height];
    let p = ViewshedParams { radius_m: radius, target_m: 0.0, refraction_k: K };
    viewshed_into(&field, &a, &grid, &p, &mut counts);
    viewshed_into(&field, &b, &grid, &p, &mut counts);
    let at = |az: f64, d: f64| {
        let (lat, lon) = crate::geo::destination(LAT, LON, az, d);
        let (mx, my) = crate::geo::mercator(lat, lon);
        counts[((my - grid.my0) / grid.cell) as usize * grid.width + ((mx - grid.mx0) / grid.cell) as usize]
    };
    assert_eq!(at(90.0, 15_000.0), 2, "between the two");
    assert_eq!(at(270.0, 20_000.0), 1, "west of A, out of B's sight");
    assert_eq!(at(270.0, 42_000.0), 0, "beyond A's horizon");
}

#[test]
fn observer_moves_to_the_local_high_point() {
    // A small summit 40 m east of the recorded position.
    let (slat, slon) = crate::geo::destination(LAT, LON, 90.0, 40.0);
    let field = Synthetic::new(slat, slon, cone(0.0, 0.0, 300.0, 2_000.0));
    let obs = Observer::locate(&field, LAT, LON, 10.0, 75.0);
    assert!(obs.moved_m > 25.0 && obs.moved_m < 55.0, "moved {}", obs.moved_m);
    assert!(obs.ground_m > obs.recorded_ground_m + 3.0);
    assert!((obs.ground_m - 300.0).abs() < 8.0, "ground {}", obs.ground_m);
    // No snapping asked for: stays put.
    let still = Observer::locate(&field, LAT, LON, 10.0, 0.0);
    assert_eq!(still.moved_m, 0.0);
}
