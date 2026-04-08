//! Rustler NIF bindings for IndexManager.
//!
//! Mirrors bindings/python/src/indexmanager.rs with Rustler idioms.
//!
//! Telemetry is owned by the core (moss::telemetry). The NIF layer passes
//! RUNTIME.handle() to the constructor and does not manage flush workers.

use rustler::ResourceArc;

use moss::manager::{IndexManager, LoadIndexOptions};

use crate::models::{decode_optional_filter, ManagerResource, NifIndexInfo, NifRefreshResult, NifSearchResult};
use crate::RUNTIME;

rustler::atoms! { ok }

// ---------------------------------------------------------------------------
// NIF functions
// ---------------------------------------------------------------------------

#[rustler::nif]
pub fn manager_new(
    project_id: String,
    project_key: String,
    base_url: Option<String>,
    client_id: Option<String>,
) -> Result<ResourceArc<ManagerResource>, String> {
    let inner = match base_url {
        Some(url) => IndexManager::with_base_url(project_id, project_key, url, RUNTIME.handle().clone(), client_id),
        None => IndexManager::new(project_id, project_key, RUNTIME.handle().clone(), client_id),
    };

    Ok(ResourceArc::new(ManagerResource {
        inner: std::sync::Mutex::new(inner),
    }))
}

#[rustler::nif(schedule = "DirtyIo")]
pub fn manager_load_index(
    resource: ResourceArc<ManagerResource>,
    index_name: String,
    auto_refresh: bool,
    polling_interval: u64,
) -> Result<NifIndexInfo, String> {
    let options = if auto_refresh {
        Some(LoadIndexOptions {
            auto_refresh: true,
            polling_interval_in_seconds: polling_interval,
            cache_path: None,
        })
    } else {
        None
    };

    RUNTIME
        .block_on(resource.inner.lock().unwrap().load_index(&index_name, options))
        .map(NifIndexInfo::from)
        .map_err(|e| format!("{}", e))
}

#[rustler::nif(schedule = "DirtyIo")]
pub fn manager_unload_index(
    resource: ResourceArc<ManagerResource>,
    index_name: String,
) -> Result<rustler::Atom, String> {
    RUNTIME
        .block_on(resource.inner.lock().unwrap().unload_index(&index_name))
        .map(|_| ok())
        .map_err(|e| format!("{}", e))
}

#[rustler::nif(schedule = "DirtyIo")]
pub fn manager_has_index(
    resource: ResourceArc<ManagerResource>,
    index_name: String,
) -> bool {
    RUNTIME.block_on(resource.inner.lock().unwrap().has_index(&index_name))
}

#[rustler::nif(schedule = "DirtyCpu")]
pub fn manager_query<'a>(
    resource: ResourceArc<ManagerResource>,
    index_name: String,
    query: String,
    embedding: Vec<f32>,
    top_k: usize,
    alpha: f32,
    filter: rustler::Term<'a>,
) -> Result<NifSearchResult, String> {
    let parsed_filter = decode_optional_filter(filter)
        .map_err(|e| format!("{:?}", e))?;

    RUNTIME
        .block_on(resource.inner.lock().unwrap().query(
            &index_name,
            &query,
            &embedding,
            top_k,
            alpha,
            parsed_filter.as_ref(),
        ))
        .map(NifSearchResult::from)
        .map_err(|e| format!("{}", e))
}

#[rustler::nif(schedule = "DirtyCpu")]
pub fn manager_query_text<'a>(
    resource: ResourceArc<ManagerResource>,
    index_name: String,
    query: String,
    top_k: usize,
    alpha: f32,
    filter: rustler::Term<'a>,
) -> Result<NifSearchResult, String> {
    let parsed_filter = decode_optional_filter(filter)
        .map_err(|e| format!("{:?}", e))?;

    RUNTIME
        .block_on(resource.inner.lock().unwrap().query_text(
            &index_name,
            &query,
            top_k,
            alpha,
            parsed_filter.as_ref(),
        ))
        .map(NifSearchResult::from)
        .map_err(|e| format!("{}", e))
}

#[rustler::nif(schedule = "DirtyIo")]
pub fn manager_load_query_model(
    resource: ResourceArc<ManagerResource>,
    index_name: String,
) -> Result<rustler::Atom, String> {
    RUNTIME
        .block_on(resource.inner.lock().unwrap().load_query_model(&index_name))
        .map(|_| ok())
        .map_err(|e| format!("{}", e))
}

#[rustler::nif(schedule = "DirtyIo")]
pub fn manager_refresh_index(
    resource: ResourceArc<ManagerResource>,
    index_name: String,
) -> Result<NifRefreshResult, String> {
    RUNTIME
        .block_on(resource.inner.lock().unwrap().refresh_index(&index_name))
        .map(NifRefreshResult::from)
        .map_err(|e| format!("{}", e))
}

#[rustler::nif(schedule = "DirtyIo")]
pub fn manager_get_index_info(
    resource: ResourceArc<ManagerResource>,
    index_name: String,
) -> Result<NifIndexInfo, String> {
    RUNTIME
        .block_on(resource.inner.lock().unwrap().get_index_info(&index_name))
        .map(NifIndexInfo::from)
        .map_err(|e| format!("{}", e))
}
