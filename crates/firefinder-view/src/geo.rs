//! Geometry on a spherical earth: unit vectors, great-circle paths and Web Mercator tiles.
//!
//! Over the distances a lookout can see (up to ~200 km) a sphere of mean radius is accurate to
//! a few tenths of a percent in distance and a small fraction of a degree in bearing, which is
//! finer than the terrain data we sample. Every computation in this crate uses the same model,
//! so a peak's bearing and the terrain drawn behind it always agree.

use std::f64::consts::TAU;

/// Mean earth radius (IUGG), metres.
pub const EARTH_RADIUS_M: f64 = 6_371_008.8;

/// Coefficient of atmospheric refraction used by default. 0.13 is the textbook value for
/// daytime lines of sight over land (surveying and geodesy texts give 0.13–0.14).
pub const DEFAULT_REFRACTION: f64 = 0.13;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Vec3 {
    pub x: f64,
    pub y: f64,
    pub z: f64,
}

impl Vec3 {
    pub const fn new(x: f64, y: f64, z: f64) -> Self {
        Self { x, y, z }
    }
    #[inline]
    pub fn dot(self, o: Vec3) -> f64 {
        self.x * o.x + self.y * o.y + self.z * o.z
    }
    #[inline]
    pub fn cross(self, o: Vec3) -> Vec3 {
        Vec3::new(self.y * o.z - self.z * o.y, self.z * o.x - self.x * o.z, self.x * o.y - self.y * o.x)
    }
    #[inline]
    pub fn scale(self, k: f64) -> Vec3 {
        Vec3::new(self.x * k, self.y * k, self.z * k)
    }
    #[inline]
    pub fn add(self, o: Vec3) -> Vec3 {
        Vec3::new(self.x + o.x, self.y + o.y, self.z + o.z)
    }
    #[inline]
    pub fn norm(self) -> f64 {
        self.dot(self).sqrt()
    }
    /// `self * a + o * b`, the workhorse of great-circle stepping.
    #[inline]
    pub fn combine(self, a: f64, o: Vec3, b: f64) -> Vec3 {
        Vec3::new(self.x * a + o.x * b, self.y * a + o.y * b, self.z * a + o.z * b)
    }
}

/// Unit vector of a latitude/longitude in degrees.
pub fn unit(lat_deg: f64, lon_deg: f64) -> Vec3 {
    let (sp, cp) = lat_deg.to_radians().sin_cos();
    let (sl, cl) = lon_deg.to_radians().sin_cos();
    Vec3::new(cp * cl, cp * sl, sp)
}

/// Latitude and longitude in degrees of a (not necessarily unit) vector.
pub fn lat_lon(v: Vec3) -> (f64, f64) {
    let lat = v.z.atan2((v.x * v.x + v.y * v.y).sqrt()).to_degrees();
    let lon = v.y.atan2(v.x).to_degrees();
    (lat, lon)
}

/// The local frame at a point: its unit vector and the unit vectors pointing north and east.
#[derive(Clone, Copy, Debug)]
pub struct Frame {
    pub origin: Vec3,
    pub north: Vec3,
    pub east: Vec3,
}

impl Frame {
    pub fn new(lat_deg: f64, lon_deg: f64) -> Self {
        let (sp, cp) = lat_deg.to_radians().sin_cos();
        let (sl, cl) = lon_deg.to_radians().sin_cos();
        Frame {
            origin: Vec3::new(cp * cl, cp * sl, sp),
            north: Vec3::new(-sp * cl, -sp * sl, cp),
            east: Vec3::new(-sl, cl, 0.0),
        }
    }

    /// Unit tangent for a true azimuth in radians (0 = north, clockwise).
    #[inline]
    pub fn direction(&self, az_rad: f64) -> Vec3 {
        let (s, c) = az_rad.sin_cos();
        self.north.combine(c, self.east, s)
    }

    /// The point `dist_m` along the great circle leaving in direction `dir`.
    #[inline]
    pub fn walk(&self, dir: Vec3, dist_m: f64) -> Vec3 {
        let (s, c) = (dist_m / EARTH_RADIUS_M).sin_cos();
        self.origin.combine(c, dir, s)
    }

    /// Great-circle distance (m) and true azimuth (radians, 0..2π) from the origin to `v`.
    #[inline]
    pub fn inverse(&self, v: Vec3) -> (f64, f64) {
        let c = self.origin.dot(v);
        let s = self.origin.cross(v).norm();
        let dist = s.atan2(c) * EARTH_RADIUS_M;
        let mut az = v.dot(self.east).atan2(v.dot(self.north));
        if az < 0.0 {
            az += TAU;
        }
        (dist, az)
    }
}

/// Distance (m) and initial true azimuth (degrees) between two points.
pub fn distance_azimuth(lat1: f64, lon1: f64, lat2: f64, lon2: f64) -> (f64, f64) {
    let (d, az) = Frame::new(lat1, lon1).inverse(unit(lat2, lon2));
    (d, az.to_degrees())
}

/// The point at a distance (m) and true azimuth (degrees) from a start point.
pub fn destination(lat: f64, lon: f64, az_deg: f64, dist_m: f64) -> (f64, f64) {
    let f = Frame::new(lat, lon);
    lat_lon(f.walk(f.direction(az_deg.to_radians()), dist_m))
}

/* ---------- Web Mercator ---------- */

/// Normalised Web Mercator coordinates (0..1 from the antimeridian west edge and from the
/// north edge of the square world) of a unit vector. Works straight from the vector: no
/// latitude round trip in the hot loop.
#[inline]
pub fn mercator_of(v: Vec3) -> (f64, f64) {
    let lon = v.y.atan2(v.x);
    let my = v.z.clamp(-0.999_999_9, 0.999_999_9).atanh();
    (lon / TAU + 0.5, 0.5 - my / TAU)
}

pub fn mercator(lat_deg: f64, lon_deg: f64) -> (f64, f64) {
    mercator_of(unit(lat_deg, lon_deg))
}

/// Latitude and longitude (degrees) of normalised Web Mercator coordinates.
pub fn unmercator(mx: f64, my: f64) -> (f64, f64) {
    let lon = (mx - 0.5) * 360.0;
    let lat = ((0.5 - my) * TAU).sinh().atan().to_degrees();
    (lat, lon)
}

/// Ground metres per normalised Mercator unit at a latitude.
pub fn metres_per_mercator_unit(lat_deg: f64) -> f64 {
    TAU * EARTH_RADIUS_M * lat_deg.to_radians().cos()
}

/// Ground size (m) of one pixel of a `tile_size` tile at zoom `z` and latitude.
pub fn pixel_size_m(z: u8, tile_size: u32, lat_deg: f64) -> f64 {
    metres_per_mercator_unit(lat_deg) / (f64::from(tile_size) * f64::from(1u32 << z))
}

/// Bounding box of a disc in normalised Web Mercator coordinates, `(x0, y0, x1, y1)`.
/// x is not wrapped: it may run below 0 or above 1 near the antimeridian.
pub fn disc_bbox(lat: f64, lon: f64, radius_m: f64) -> (f64, f64, f64, f64) {
    let dlat = (radius_m / EARTH_RADIUS_M).to_degrees();
    let lat_hi = (lat + dlat).min(85.0);
    let lat_lo = (lat - dlat).max(-85.0);
    let widest = lat_hi.abs().max(lat_lo.abs()).to_radians().cos().max(0.01);
    let dlon = (dlat / widest).min(179.0);
    let x = |lo: f64| (lo + 180.0) / 360.0;
    let y = |la: f64| mercator(la, 0.0).1;
    (x(lon - dlon), y(lat_hi), x(lon + dlon), y(lat_lo))
}

/// The window of tiles `(x0, y0, x1, y1)` at zoom `z` covering a disc (x unwrapped).
pub fn tile_window(lat: f64, lon: f64, radius_m: f64, z: u8) -> (i64, i64, i64, i64) {
    let n = f64::from(1u32 << z);
    let (x0, y0, x1, y1) = disc_bbox(lat, lon, radius_m);
    let max = (1i64 << z) - 1;
    (
        (x0 * n).floor() as i64,
        ((y0 * n).floor() as i64).clamp(0, max),
        (x1 * n).floor() as i64,
        ((y1 * n).floor() as i64).clamp(0, max),
    )
}

/// The tiles at zoom `z` that a disc of `radius_m` around a point touches, as (x, y) pairs,
/// in row order. Tiles whose nearest point is farther than the radius are left out.
pub fn tiles_for_disc(lat: f64, lon: f64, radius_m: f64, z: u8) -> Vec<(u32, u32)> {
    let n = 1i64 << z;
    let nf = n as f64;
    let (tx0, ty0, tx1, ty1) = tile_window(lat, lon, radius_m, z);
    let frame = Frame::new(lat, lon);
    let (cx, cy) = ((lon + 180.0) / 360.0, mercator(lat, lon).1);
    let mut out = Vec::new();
    for ty in ty0..=ty1 {
        for tx in tx0..=tx1 {
            // Nearest point of the tile to the centre, in Mercator space, then measured on the sphere.
            let left = tx as f64 / nf;
            let top = ty as f64 / nf;
            let px = cx.clamp(left, left + 1.0 / nf);
            let py = cy.clamp(top, top + 1.0 / nf);
            let (plat, plon) = unmercator(px, py);
            let (d, _) = frame.inverse(unit(plat, plon));
            if d > radius_m {
                continue;
            }
            out.push((tx.rem_euclid(n) as u32, ty as u32));
        }
    }
    out
}

/// Angle in degrees normalised to 0..360.
pub fn wrap_deg(a: f64) -> f64 {
    let r = a.rem_euclid(360.0);
    if r >= 360.0 { 0.0 } else { r }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn close(a: f64, b: f64, tol: f64) -> bool {
        (a - b).abs() <= tol
    }

    #[test]
    fn walk_and_inverse_round_trip() {
        let f = Frame::new(43.5434, -122.3664);
        for &az in &[0.0, 37.0, 90.0, 181.5, 270.0, 359.0] {
            for &d in &[30.0, 1_000.0, 25_000.0, 150_000.0] {
                let v = f.walk(f.direction((az as f64).to_radians()), d);
                let (d2, az2) = f.inverse(v);
                assert!(close(d, d2, 1e-6 * d.max(1.0)), "distance {d} -> {d2}");
                let daz = (az2.to_degrees() - az + 540.0).rem_euclid(360.0) - 180.0;
                assert!(daz.abs() < 1e-7, "azimuth {az} -> {}", az2.to_degrees());
            }
        }
    }

    #[test]
    fn cardinal_bearings() {
        // Due north along a meridian, due east along the equator.
        let (d, az) = distance_azimuth(10.0, 20.0, 11.0, 20.0);
        assert!(close(az, 0.0, 1e-9));
        assert!(close(d, EARTH_RADIUS_M * 1f64.to_radians(), 1e-6));
        let (_, az) = distance_azimuth(0.0, 20.0, 0.0, 21.0);
        assert!(close(az, 90.0, 1e-9));
        let (_, az) = distance_azimuth(0.0, 20.0, -1.0, 20.0);
        assert!(close(az, 180.0, 1e-9));
    }

    #[test]
    fn known_distance_portland_to_mount_hood() {
        // Pioneer Courthouse Square to the summit of Mount Hood: about 80 km, bearing about 92°.
        let (d, az) = distance_azimuth(45.5189, -122.6794, 45.3736, -121.6959);
        assert!(close(d, 78_200.0, 1_000.0), "{d}");
        assert!(close(az, 101.5, 1.5), "{az}");
    }

    #[test]
    fn destination_matches_inverse() {
        let (lat, lon) = destination(46.0, -115.0, 123.0, 42_000.0);
        let (d, az) = distance_azimuth(46.0, -115.0, lat, lon);
        assert!(close(d, 42_000.0, 1e-3));
        assert!(close(az, 123.0, 1e-7));
    }

    #[test]
    fn mercator_round_trip() {
        for &(lat, lon) in &[(0.0, 0.0), (45.0, -122.0), (-33.9, 151.2), (64.8, -147.7)] {
            let (x, y) = mercator(lat, lon);
            let (lat2, lon2) = unmercator(x, y);
            assert!(close(lat, lat2, 1e-9) && close(lon, lon2, 1e-9));
        }
        assert!(close(mercator(0.0, 0.0).0, 0.5, 1e-12));
        assert!(close(mercator(0.0, 0.0).1, 0.5, 1e-12));
    }

    #[test]
    fn disc_tiles_cover_the_point_and_stay_small() {
        let (x, y) = mercator(43.5434, -122.3664);
        let tiles = tiles_for_disc(43.5434, -122.3664, 5_000.0, 12);
        let own = ((x * 4096.0) as u32, (y * 4096.0) as u32);
        assert!(tiles.contains(&own));
        assert!(tiles.len() <= 9, "{} tiles", tiles.len());
        // 150 km at zoom 8 (tiles ~110 km wide here): a 3x3 to 4x4 block.
        let t8 = tiles_for_disc(43.5434, -122.3664, 150_000.0, 8);
        assert!((9..=16).contains(&t8.len()), "{} tiles", t8.len());
    }

    #[test]
    fn pixel_size_is_sensible() {
        // Zoom 12, 256 px tiles at 45°: about 27 m.
        let p = pixel_size_m(12, 256, 45.0);
        assert!(close(p, 27.0, 0.3), "{p}");
    }
}
