//! # firefinder-view
//!
//! The number-crunching behind Firefinder's 3D features, compiled to WebAssembly:
//!
//! - **The view from the cab** ([`panorama`]): a 360° panorama at eye height, as layered
//!   skylines by distance, plus which peaks and other lookouts are in sight
//!   ([`sight::sight_targets`]).
//! - **What it could see** ([`viewshed`]): the ground within a radius in a lookout's line of
//!   sight, counted over several lookouts.
//!
//! Terrain comes from Terrarium elevation tiles ([`dem`]) that the browser fetches; this crate
//! decodes them and marches lines of sight over a spherical earth with atmospheric refraction
//! ([`sight`]). The browser bindings live in [`wasm`].

pub mod dem;
pub mod geo;
pub mod panorama;
pub mod sight;
pub mod viewshed;
pub mod wasm;

#[cfg(test)]
mod synthetic;
