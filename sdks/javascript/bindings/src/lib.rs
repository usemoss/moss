// This macro is required to generate the binding logic
#[macro_use]
extern crate napi_derive;

// We must declare the modules so Rust compiles them.
// NAPI-RS will scan these modules for any public items tagged with #[napi].
pub mod indexmanager;
pub mod manage;
pub mod models;

use ::moss::constants;

// --- Constants ---
// In NAPI-RS, we export constants by tagging them directly.
// These will be available as `import { MODEL_DOWNLOAD_URL } from 'moss'`

#[napi]
/// Public CDN endpoint for downloading Moss embedding models locally.
pub const MODEL_DOWNLOAD_URL: &str = constants::MODEL_DOWNLOAD_URL;

#[napi]
/// Semantic version identifier for the Moss JavaScript core bindings.
pub const SDK_VERSION_NUMBER: &str = constants::SDK_VERSION_NUMBER;

#[napi]
/// Default REST endpoint for Moss Cloud operations.
pub const CLOUD_API_MANAGE_URL: &str = constants::CLOUD_API_MANAGE_URL;
