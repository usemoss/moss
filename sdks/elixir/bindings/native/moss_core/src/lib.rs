//! Rustler NIF entry point for the moss_core crate.
//!
//! Registers resource types and exports all NIF functions to Elixir.
//! Uses Rustler 0.29+ auto-registration: #[rustler::nif] functions in
//! each module are collected via `inventory` — no explicit listing needed.

mod manage;
mod manager;
pub mod models;
mod session;

use once_cell::sync::Lazy;
use rustler::{Env, Term};

/// Global Tokio runtime shared by all NIF calls.
/// Avoids creating one runtime per resource and keeps thread pools sane.
pub(crate) static RUNTIME: Lazy<tokio::runtime::Runtime> = Lazy::new(|| {
    tokio::runtime::Runtime::new().expect("Failed to create global Tokio runtime")
});

#[allow(non_local_definitions)]
fn on_load(env: Env, _: Term) -> bool {
    let _ = rustler::resource!(models::SessionResource, env);
    let _ = rustler::resource!(models::ManagerResource, env);
    let _ = rustler::resource!(models::ManageResource, env);
    true
}

rustler::init!("Elixir.MossCore.Nif", load = on_load);
