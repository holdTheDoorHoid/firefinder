//! Elevation data: Terrarium tiles decoded into a small cache, and samplers that read heights
//! along a line of sight, choosing a finer zoom level near the observer and coarser ones far
//! away.
//!
//! Terrarium PNG tiles (AWS Terrain Tiles, Mapterhorn) store height in metres as
//! `R * 256 + G + B / 256 - 32768`. We keep each tile as 16-bit quarter-metres to halve the
//! memory of a 32-bit float tile. Heights below sea level are stored as sea level: the tiles
//! carry ocean depths, and the sea surface is what a lookout sees. (The one cost is that Death
//! Valley and the Salton Sea basin read as 0 m instead of down to -86 m.)

use std::collections::HashMap;

use crate::geo::{Frame, Vec3, mercator_of};
use crate::sight::Steps;

/// Stored value meaning "no data" (a tile that failed to load, or outside the cached tiles).
pub const NODATA: u16 = u16::MAX;
const UNITS_PER_M: f32 = 4.0;

/// A decoded square tile, row-major from the north-west corner.
#[derive(Clone, Debug)]
pub struct Tile {
    pub size: usize,
    pub data: Vec<u16>,
}

impl Tile {
    /// A tile from heights in metres (NaN = no data). Used by tests and for synthetic terrain.
    pub fn from_heights(size: usize, heights: &[f32]) -> Tile {
        assert_eq!(heights.len(), size * size);
        Tile { size, data: heights.iter().map(|&h| quantise(h)).collect() }
    }

    #[inline]
    pub fn height(&self, x: usize, y: usize) -> f32 {
        dequantise(self.data[y * self.size + x])
    }
}

#[inline]
pub fn quantise(h: f32) -> u16 {
    if !h.is_finite() {
        return NODATA;
    }
    (h.max(0.0) * UNITS_PER_M).round().min(f32::from(NODATA - 1)) as u16
}

#[inline]
pub fn dequantise(q: u16) -> f32 {
    if q == NODATA { f32::NAN } else { f32::from(q) / UNITS_PER_M }
}

/// Decode a Terrarium PNG (RGB or RGBA, 8 bits; palette images are expanded).
pub fn decode_terrarium(bytes: &[u8]) -> Result<Tile, String> {
    let mut decoder = png::Decoder::new(std::io::Cursor::new(bytes));
    decoder.set_transformations(png::Transformations::EXPAND | png::Transformations::STRIP_16);
    let mut reader = decoder.read_info().map_err(|e| format!("not a PNG tile: {e}"))?;
    let mut buf = vec![0; reader.output_buffer_size().ok_or("PNG too large")?];
    let info = reader.next_frame(&mut buf).map_err(|e| format!("broken PNG tile: {e}"))?;
    let (w, h) = (info.width as usize, info.height as usize);
    if w != h || w == 0 {
        return Err(format!("tile is {w}x{h}, expected a square"));
    }
    let channels = match info.color_type {
        png::ColorType::Rgb => 3,
        png::ColorType::Rgba => 4,
        other => return Err(format!("unexpected PNG colour type {other:?} for a Terrarium tile")),
    };
    let mut data = Vec::with_capacity(w * h);
    for y in 0..h {
        let row = &buf[y * info.line_size..y * info.line_size + w * channels];
        for px in row.chunks_exact(channels) {
            let m = f32::from(px[0]) * 256.0 + f32::from(px[1]) + f32::from(px[2]) / 256.0 - 32768.0;
            data.push(quantise(m));
        }
    }
    Ok(Tile { size: w, data })
}

/* ---------- Tile cache ---------- */

pub type TileKey = (u8, u32, u32);

struct Entry {
    tile: Option<Tile>,
    used: u64,
}

/// Decoded tiles, keyed by (zoom, x, y). `None` records a tile that could not be loaded, so
/// samplers fall back to a coarser zoom there instead of asking again.
///
/// Eviction is least-recently-used by request: everything touched since the last
/// [`TileStore::begin`] is kept even past the limit, so one request never evicts its own tiles.
pub struct TileStore {
    entries: HashMap<TileKey, Entry>,
    generation: u64,
    max_tiles: usize,
}

impl TileStore {
    pub fn new(max_tiles: usize) -> Self {
        TileStore { entries: HashMap::new(), generation: 1, max_tiles: max_tiles.max(16) }
    }

    /// Start a new request: tiles touched from now on are protected from eviction.
    pub fn begin(&mut self) {
        self.generation += 1;
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    /// Whether the store knows this tile (loaded or known missing). Marks it as in use.
    pub fn touch(&mut self, key: TileKey) -> bool {
        match self.entries.get_mut(&key) {
            Some(e) => {
                e.used = self.generation;
                true
            }
            None => false,
        }
    }

    pub fn insert(&mut self, key: TileKey, tile: Option<Tile>) {
        self.entries.insert(key, Entry { tile, used: self.generation });
        if self.entries.len() > self.max_tiles {
            self.evict();
        }
    }

    pub fn get(&self, key: &TileKey) -> Option<&Tile> {
        self.entries.get(key).and_then(|e| e.tile.as_ref())
    }

    fn evict(&mut self) {
        let mut old: Vec<(u64, TileKey)> =
            self.entries.iter().filter(|(_, e)| e.used < self.generation).map(|(k, e)| (e.used, *k)).collect();
        old.sort_unstable();
        let excess = self.entries.len().saturating_sub(self.max_tiles);
        for (_, k) in old.into_iter().take(excess) {
            self.entries.remove(&k);
        }
    }
}

/* ---------- Sampling ---------- */

/// Anything that gives a terrain height (m above sea level, NaN if unknown) at a point.
/// `dist_m` is the distance from the observer: tile samplers use it to pick a zoom level.
pub trait HeightField {
    fn height(&self, v: Vec3, dist_m: f64) -> f32;
    /// Roughly how far apart the height samples are at this distance, in metres.
    fn spacing_m(&self, dist_m: f64) -> f64;
    /// Heights at the first `n` step distances along a great circle leaving `frame`'s origin in
    /// direction `dir`. Tile samplers override this with a faster path.
    fn heights_along(&self, frame: &Frame, dir: Vec3, steps: &Steps, n: usize, out: &mut [f32]) {
        for i in 0..n {
            let v = frame.origin.combine(steps.cos[i], dir, steps.sin[i]);
            out[i] = self.height(v, steps.d[i]);
        }
    }
    /// Height at normalised Web Mercator coordinates (`v` is the same point as a unit vector).
    fn height_mercator(&self, _mx: f64, _my: f64, v: Vec3, dist_m: f64) -> f32 {
        self.height(v, dist_m)
    }
}

/// One zoom level of a sampler: a window of tiles plus the distance it serves up to.
pub struct Level<'a> {
    pub z: u8,
    pub max_dist_m: f64,
    pub spacing_m: f64,
    size: usize,
    shift: u32,
    world_px: f64,
    world_tiles: i64,
    tx0: i64,
    ty0: i64,
    nx: i64,
    ny: i64,
    tiles: Vec<Option<&'a Tile>>,
}

impl<'a> Level<'a> {
    /// A level reading tiles `(z, x, y)` from the store over the given tile window
    /// (x may run past the antimeridian; it is wrapped when looking tiles up).
    pub fn new(
        store: &'a TileStore,
        z: u8,
        max_dist_m: f64,
        spacing_m: f64,
        window: (i64, i64, i64, i64),
        tile_size: usize,
    ) -> Self {
        let (tx0, ty0, tx1, ty1) = window;
        let nx = (tx1 - tx0 + 1).max(0);
        let ny = (ty1 - ty0 + 1).max(0);
        let world_tiles = 1i64 << z;
        let mut tiles = Vec::with_capacity((nx * ny) as usize);
        for ty in ty0..=ty1 {
            for tx in tx0..=tx1 {
                let key = (z, tx.rem_euclid(world_tiles) as u32, ty as u32);
                tiles.push(store.get(&key).filter(|t| t.size == tile_size));
            }
        }
        assert!(tile_size.is_power_of_two(), "tile size must be a power of two");
        Level {
            z,
            max_dist_m,
            spacing_m,
            size: tile_size,
            shift: tile_size.trailing_zeros(),
            world_px: (world_tiles as f64) * tile_size as f64,
            world_tiles,
            tx0,
            ty0,
            nx,
            ny,
            tiles,
        }
    }

    #[inline]
    fn pixel(&self, ix: i64, iy: i64) -> f32 {
        let size = self.size as i64;
        let world = self.world_tiles * size;
        let iy = iy.clamp(0, world - 1);
        let mut tx = ix.div_euclid(size) - self.tx0;
        if tx < 0 || tx >= self.nx {
            // The window may be expressed east or west of the antimeridian.
            tx = (ix.div_euclid(size)).rem_euclid(self.world_tiles) - self.tx0.rem_euclid(self.world_tiles);
            if tx < 0 {
                tx += self.world_tiles;
            }
            if tx >= self.nx {
                return f32::NAN;
            }
        }
        let ty = iy.div_euclid(size) - self.ty0;
        if ty < 0 || ty >= self.ny {
            return f32::NAN;
        }
        match self.tiles[(ty * self.nx + tx) as usize] {
            Some(t) => t.height(ix.rem_euclid(size) as usize, iy.rem_euclid(size) as usize),
            None => f32::NAN,
        }
    }

    /// Bilinear height at normalised Mercator coordinates. Pixel values sit at pixel centres.
    #[inline]
    pub fn sample(&self, mx: f64, my: f64) -> f32 {
        let px = mx * self.world_px - 0.5;
        let py = my * self.world_px - 0.5;
        let x0 = px.floor();
        let y0 = py.floor();
        let fx = (px - x0) as f32;
        let fy = (py - y0) as f32;
        let (ix, iy) = (x0 as i64, y0 as i64);
        // Fast path: all four pixels in one tile (tile sizes are powers of two).
        let mask = self.size as i64 - 1;
        let (lx, ly) = (ix & mask, iy & mask);
        if lx < mask && ly < mask && iy >= 0 {
            let tx = (ix >> self.shift) - self.tx0;
            let ty = (iy >> self.shift) - self.ty0;
            if tx >= 0 && tx < self.nx && ty >= 0 && ty < self.ny {
                if let Some(t) = self.tiles[(ty * self.nx + tx) as usize] {
                    let i = ly as usize * self.size + lx as usize;
                    let (q00, q10, q01, q11) = (t.data[i], t.data[i + 1], t.data[i + self.size], t.data[i + self.size + 1]);
                    if q00 != NODATA && q10 != NODATA && q01 != NODATA && q11 != NODATA {
                        let top = f32::from(q00) * (1.0 - fx) + f32::from(q10) * fx;
                        let bottom = f32::from(q01) * (1.0 - fx) + f32::from(q11) * fx;
                        return (top * (1.0 - fy) + bottom * fy) / UNITS_PER_M;
                    }
                }
            }
        }
        let h00 = self.pixel(ix, iy);
        let h10 = self.pixel(ix + 1, iy);
        let h01 = self.pixel(ix, iy + 1);
        let h11 = self.pixel(ix + 1, iy + 1);
        let v = (h00 * (1.0 - fx) + h10 * fx) * (1.0 - fy) + (h01 * (1.0 - fx) + h11 * fx) * fy;
        if v.is_nan() {
            // Edge of the data: use the nearest pixel that exists.
            let near = match (fx < 0.5, fy < 0.5) {
                (true, true) => h00,
                (false, true) => h10,
                (true, false) => h01,
                (false, false) => h11,
            };
            return near;
        }
        v
    }
}

/// Heights from cached tiles over several zoom levels, finest first.
pub struct TileSampler<'a> {
    pub levels: Vec<Level<'a>>,
}

impl HeightField for TileSampler<'_> {
    #[inline]
    fn height(&self, v: Vec3, dist_m: f64) -> f32 {
        let (mx, my) = mercator_of(v);
        let mut started = false;
        for level in &self.levels {
            if !started && dist_m > level.max_dist_m {
                continue;
            }
            started = true;
            let h = level.sample(mx, my);
            if !h.is_nan() {
                return h;
            }
        }
        f32::NAN
    }

    fn spacing_m(&self, dist_m: f64) -> f64 {
        self.levels.iter().find(|l| dist_m <= l.max_dist_m).or(self.levels.last()).map_or(30.0, |l| l.spacing_m)
    }

    #[inline]
    fn height_mercator(&self, mx: f64, my: f64, _v: Vec3, dist_m: f64) -> f32 {
        let mut started = false;
        for level in &self.levels {
            if !started && dist_m > level.max_dist_m {
                continue;
            }
            started = true;
            let h = level.sample(mx, my);
            if !h.is_nan() {
                return h;
            }
        }
        f32::NAN
    }

    /// Mercator coordinates are computed exactly every [`KNOT`] steps and interpolated in
    /// between (a great circle is so nearly straight in Mercator over a few km that the error
    /// is centimetres), and the zoom level advances with distance instead of being searched.
    fn heights_along(&self, frame: &Frame, dir: Vec3, steps: &Steps, n: usize, out: &mut [f32]) {
        if n == 0 || self.levels.is_empty() {
            return;
        }
        let merc = |i: usize| mercator_of(frame.origin.combine(steps.cos[i], dir, steps.sin[i]));
        let mut li = 0usize;
        let mut sample = |mx: f64, my: f64, d: f64| -> f32 {
            while li + 1 < self.levels.len() && d > self.levels[li].max_dist_m {
                li += 1;
            }
            for level in &self.levels[li..] {
                let h = level.sample(mx, my);
                if !h.is_nan() {
                    return h;
                }
            }
            f32::NAN
        };
        let (mut ax, mut ay) = merc(0);
        out[0] = sample(ax, ay, steps.d[0]);
        let mut a = 0usize;
        while a + 1 < n {
            let b = (a + KNOT).min(n - 1);
            let (bx, by) = merc(b);
            let mut bxu = bx;
            if bxu - ax > 0.5 {
                bxu -= 1.0;
            } else if bxu - ax < -0.5 {
                bxu += 1.0;
            }
            let (da, span) = (steps.d[a], steps.d[b] - steps.d[a]);
            for t in a + 1..=b {
                let f = (steps.d[t] - da) / span;
                let mut mx = ax + (bxu - ax) * f;
                if mx < 0.0 {
                    mx += 1.0;
                } else if mx >= 1.0 {
                    mx -= 1.0;
                }
                out[t] = sample(mx, ay + (by - ay) * f, steps.d[t]);
            }
            a = b;
            ax = bx;
            ay = by;
        }
    }
}

/// Exact Mercator positions every this many steps along a ray; interpolated between.
const KNOT: usize = 16;

#[cfg(test)]
mod tests {
    use super::*;
    use crate::geo::{unit, unmercator};

    #[test]
    fn quantise_round_trip() {
        for h in [0.0f32, 0.25, 123.5, 4_421.0, 6_190.5] {
            assert_eq!(dequantise(quantise(h)), h);
        }
        assert_eq!(dequantise(quantise(-50.0)), 0.0, "below sea level reads as sea level");
        assert!(dequantise(quantise(f32::NAN)).is_nan());
    }

    fn encode_png(size: u32, pixel: impl Fn(u32, u32) -> [u8; 3]) -> Vec<u8> {
        let mut out = Vec::new();
        {
            let mut enc = png::Encoder::new(&mut out, size, size);
            enc.set_color(png::ColorType::Rgb);
            enc.set_depth(png::BitDepth::Eight);
            let mut w = enc.write_header().unwrap();
            let mut data = Vec::new();
            for y in 0..size {
                for x in 0..size {
                    data.extend_from_slice(&pixel(x, y));
                }
            }
            w.write_image_data(&data).unwrap();
        }
        out
    }

    #[test]
    fn decodes_terrarium_png() {
        // 1500.5 m = 32768 + 1500.5 = 34268.5 -> R=133 (34048), G=220, B=128.
        let png = encode_png(4, |x, _| if x == 0 { [133, 220, 128] } else { [128, 0, 0] });
        let t = decode_terrarium(&png).unwrap();
        assert_eq!(t.size, 4);
        assert_eq!(t.height(0, 0), 1500.5);
        assert_eq!(t.height(1, 3), 0.0);
        assert!(decode_terrarium(b"not a png").is_err());
    }

    #[test]
    fn store_evicts_oldest_requests_only() {
        let mut s = TileStore::new(16);
        let tile = Tile::from_heights(1, &[1.0]);
        for i in 0..16 {
            s.insert((1, i, 0), Some(tile.clone()));
        }
        s.begin();
        for i in 16..20 {
            s.insert((1, i, 0), Some(tile.clone()));
        }
        assert_eq!(s.len(), 16);
        assert!(!s.touch((1, 0, 0)), "the oldest tiles went first");
        assert!(s.touch((1, 19, 0)));
        // A request bigger than the limit keeps all of its own tiles.
        s.begin();
        for i in 100..130 {
            s.insert((1, i, 0), Some(tile.clone()));
        }
        assert!((100..130).all(|i| s.touch((1, i, 0))));
    }

    #[test]
    fn samples_bilinearly_across_tile_edges() {
        // Zoom 1: four 4x4 tiles whose height is the global pixel column x 10 m.
        let mut store = TileStore::new(64);
        for tx in 0..2u32 {
            for ty in 0..2u32 {
                let h: Vec<f32> = (0..16).map(|i| ((tx * 4 + i % 4) * 10) as f32).collect();
                store.insert((1, tx, ty), Some(Tile::from_heights(4, &h)));
            }
        }
        let level = Level::new(&store, 1, 1e9, 1.0, (0, 0, 1, 1), 4);
        // Pixel centre of global column 3 is at x = 3.5 / 8.
        assert_eq!(level.sample(3.5 / 8.0, 0.3), 30.0);
        // Halfway between columns 3 and 4 (which sit in different tiles).
        assert_eq!(level.sample(4.0 / 8.0, 0.3), 35.0);
        let sampler = TileSampler { levels: vec![level] };
        let (lat, lon) = unmercator(4.0 / 8.0, 0.3);
        assert!((sampler.height(unit(lat, lon), 0.0) - 35.0).abs() < 1e-3);
    }

    #[test]
    fn falls_back_to_coarser_level_where_fine_tiles_are_missing() {
        let mut store = TileStore::new(64);
        store.insert((2, 0, 0), None);
        store.insert((1, 0, 0), Some(Tile::from_heights(2, &[7.0; 4])));
        let fine = Level::new(&store, 2, 1e9, 1.0, (0, 0, 0, 0), 2);
        let coarse = Level::new(&store, 1, 1e9, 2.0, (0, 0, 0, 0), 2);
        let s = TileSampler { levels: vec![fine, coarse] };
        let (lat, lon) = unmercator(0.1, 0.1);
        assert_eq!(s.height(unit(lat, lon), 0.0), 7.0);
    }
}
