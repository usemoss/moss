//! Rustler NIF bindings for SessionIndex.
//!
//! Mirrors bindings/python/src/sessionindex.rs with Rustler idioms instead
//! of PyO3: ResourceArc instead of RefCell, global Tokio runtime instead of
//! per-object runtime, NifStruct instead of pyclass.
//!
//! Telemetry is owned by the core (moss::telemetry). The NIF layer passes
//! RUNTIME.handle() to the constructor and does not manage flush workers.

use rustler::ResourceArc;

use moss::models::AddDocumentsOptions as CoreAddDocumentsOptions;
use moss::session::SessionIndex;

use crate::models::{
    NifDocumentInfo, NifPushIndexResult, NifSearchResult, SessionResource, decode_optional_filter,
};
use crate::RUNTIME;

rustler::atoms! { ok }

// ---------------------------------------------------------------------------
// NIF functions
// ---------------------------------------------------------------------------

#[rustler::nif(schedule = "DirtyIo")]
pub fn session_new(
    name: String,
    model_id: String,
    project_id: String,
    project_key: String,
    client_id: Option<String>,
) -> Result<ResourceArc<SessionResource>, String> {
    let inner =
        SessionIndex::new(&name, &model_id, project_id, project_key, RUNTIME.handle().clone(), client_id)
            .map_err(|e| format!("{}", e))?;

    Ok(ResourceArc::new(SessionResource {
        inner: std::sync::Mutex::new(inner),
    }))
}

#[rustler::nif]
pub fn session_doc_count(resource: ResourceArc<SessionResource>) -> usize {
    resource.inner.lock().unwrap().doc_count()
}

#[rustler::nif]
pub fn session_name(resource: ResourceArc<SessionResource>) -> String {
    resource.inner.lock().unwrap().name().to_string()
}

#[rustler::nif(schedule = "DirtyCpu")]
pub fn session_add_docs(
    resource: ResourceArc<SessionResource>,
    docs: Vec<NifDocumentInfo>,
    embeddings: Vec<Vec<f32>>,
    upsert: bool,
) -> Result<(usize, usize), String> {
    let core_docs: Vec<moss::models::DocumentInfo> =
        docs.iter().map(|d| moss::models::DocumentInfo {
            id: d.id.clone(),
            text: d.text.clone(),
            metadata: d.metadata.clone(),
            embedding: d.embedding.clone(),
        }).collect();
    let core_opts = CoreAddDocumentsOptions { upsert };

    resource
        .inner
        .lock()
        .unwrap()
        .add_docs(&core_docs, &embeddings, Some(&core_opts))
        .map_err(|e| format!("{}", e))
}

#[rustler::nif(schedule = "DirtyCpu")]
pub fn session_add_docs_text(
    resource: ResourceArc<SessionResource>,
    docs: Vec<NifDocumentInfo>,
    upsert: bool,
) -> Result<(usize, usize), String> {
    let core_docs: Vec<moss::models::DocumentInfo> = docs.into_iter().map(Into::into).collect();
    let core_opts = CoreAddDocumentsOptions { upsert };

    resource
        .inner
        .lock()
        .unwrap()
        .add_docs_text(&core_docs, Some(&core_opts))
        .map_err(|e| format!("{}", e))
}

#[rustler::nif(schedule = "DirtyCpu")]
pub fn session_delete_docs(
    resource: ResourceArc<SessionResource>,
    doc_ids: Vec<String>,
) -> usize {
    resource.inner.lock().unwrap().delete_docs(&doc_ids)
}

#[rustler::nif]
pub fn session_get_docs(
    resource: ResourceArc<SessionResource>,
    doc_ids: Option<Vec<String>>,
) -> Vec<NifDocumentInfo> {
    let opts = doc_ids.map(|ids| moss::models::GetDocumentsOptions { doc_ids: Some(ids) });
    resource
        .inner
        .lock()
        .unwrap()
        .get_docs(opts.as_ref())
        .into_iter()
        .map(NifDocumentInfo::from)
        .collect()
}

#[rustler::nif(schedule = "DirtyCpu")]
pub fn session_query<'a>(
    resource: ResourceArc<SessionResource>,
    query: String,
    top_k: usize,
    embedding: Vec<f32>,
    alpha: f32,
    filter: rustler::Term<'a>,
) -> Result<NifSearchResult, String> {
    let parsed_filter = decode_optional_filter(filter)
        .map_err(|e| format!("{:?}", e))?;

    resource
        .inner
        .lock()
        .unwrap()
        .query(&query, top_k, &embedding, alpha, parsed_filter.as_ref())
        .map(NifSearchResult::from)
        .map_err(|e| format!("{}", e))
}

#[rustler::nif(schedule = "DirtyCpu")]
pub fn session_query_text<'a>(
    resource: ResourceArc<SessionResource>,
    query: String,
    top_k: usize,
    alpha: f32,
    filter: rustler::Term<'a>,
) -> Result<NifSearchResult, String> {
    let parsed_filter = decode_optional_filter(filter).map_err(|e| format!("{:?}", e))?;

    resource
        .inner
        .lock()
        .unwrap()
        .query_text(&query, top_k, alpha, parsed_filter.as_ref())
        .map(NifSearchResult::from)
        .map_err(|e| format!("{}", e))
}

#[rustler::nif(schedule = "DirtyIo")]
pub fn session_load_model(resource: ResourceArc<SessionResource>) -> Result<rustler::Atom, String> {
    resource
        .inner
        .lock()
        .unwrap()
        .load_model()
        .map(|_| ok())
        .map_err(|e| format!("{}", e))
}

#[rustler::nif(schedule = "DirtyIo")]
pub fn session_load_index(
    resource: ResourceArc<SessionResource>,
    index_name: String,
) -> Result<usize, String> {
    RUNTIME
        .block_on(resource.inner.lock().unwrap().load_index(&index_name))
        .map_err(|e| format!("{}", e))
}

#[rustler::nif(schedule = "DirtyIo")]
pub fn session_push_index(
    resource: ResourceArc<SessionResource>,
) -> Result<NifPushIndexResult, String> {
    RUNTIME
        .block_on(resource.inner.lock().unwrap().push_index())
        .map(NifPushIndexResult::from)
        .map_err(|e| format!("{}", e))
}
