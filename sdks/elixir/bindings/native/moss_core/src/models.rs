//! Rustler NIF resource types and NifStruct definitions.
//!
//! Resources are opaque BEAM handles wrapping core Rust types.
//! NifStructs are data types that map to/from Elixir structs in `Moss.*`.

use std::collections::HashMap;
use std::sync::Mutex;

use rustler::{types::atom, NifResult, NifStruct, Term};

use moss::manager::IndexManager;
use moss::models as core;

// ---------------------------------------------------------------------------
// Resource types (opaque BEAM handles)
// ---------------------------------------------------------------------------

pub struct SessionResource {
    pub inner: Mutex<moss::session::SessionIndex>,
}

pub struct ManagerResource {
    pub inner: Mutex<IndexManager>,
}

pub struct ManageResource {
    pub inner: Mutex<moss::manage::client::ManageClient>,
}

// ResourceArc<T> requires T: Send + Sync + RefUnwindSafe.
// All mutation is guarded by std::sync::Mutex / tokio::sync::Mutex, so
// it is safe to assert these traits even though inner types (tokio::sync::Mutex,
// reqwest::Client internals) don't auto-derive them.
unsafe impl Send for SessionResource {}
unsafe impl Sync for SessionResource {}
impl std::panic::RefUnwindSafe for SessionResource {}

unsafe impl Send for ManagerResource {}
unsafe impl Sync for ManagerResource {}
impl std::panic::RefUnwindSafe for ManagerResource {}

unsafe impl Send for ManageResource {}
unsafe impl Sync for ManageResource {}
impl std::panic::RefUnwindSafe for ManageResource {}

// ---------------------------------------------------------------------------
// Model parsing helpers
// ---------------------------------------------------------------------------

pub fn parse_moss_model(s: &str) -> Result<core::MossModel, String> {
    match s {
        "moss-minilm" => Ok(core::MossModel::MossMinilm),
        "moss-mediumlm" => Ok(core::MossModel::MossMediumlm),
        "custom" => Ok(core::MossModel::MossCustom),
        other => Err(format!(
            "Invalid MossModel '{}'. Expected 'moss-minilm', 'moss-mediumlm', or 'custom'.",
            other
        )),
    }
}

// ---------------------------------------------------------------------------
// MetadataFilter decoder from Elixir terms
// ---------------------------------------------------------------------------

/// Coerce an Elixir term (binary, integer, float) to String.
fn term_to_string<'a>(term: Term<'a>) -> NifResult<String> {
    if let Ok(s) = term.decode::<String>() {
        return Ok(s);
    }
    if let Ok(n) = term.decode::<f64>() {
        if n.fract() == 0.0 && n.abs() < (i64::MAX as f64) {
            return Ok(format!("{}", n as i64));
        }
        return Ok(n.to_string());
    }
    if let Ok(n) = term.decode::<i64>() {
        return Ok(format!("{}", n));
    }
    Err(rustler::Error::Term(Box::new(
        "Filter value must be a string, integer, or float",
    )))
}

fn decode_string_list<'a>(term: Term<'a>) -> NifResult<Vec<String>> {
    let list: Vec<Term<'a>> = term.decode().map_err(|_| {
        rustler::Error::Term(Box::new("$in/$nin value must be a list"))
    })?;
    list.into_iter().map(term_to_string).collect()
}

fn decode_filter_condition<'a>(map: &HashMap<String, Term<'a>>) -> NifResult<core::FilterCondition> {
    // Scalar comparison operators
    for (op, ctor) in [
        ("$eq", core::FilterCondition::Eq as fn(String) -> core::FilterCondition),
        ("$ne", core::FilterCondition::Ne),
        ("$gt", core::FilterCondition::Gt),
        ("$gte", core::FilterCondition::Gte),
        ("$lt", core::FilterCondition::Lt),
        ("$lte", core::FilterCondition::Lte),
        ("$near", core::FilterCondition::Near),
    ] {
        if let Some(v) = map.get(op) {
            return Ok(ctor(term_to_string(*v)?));
        }
    }
    if let Some(v) = map.get("$in") {
        return Ok(core::FilterCondition::In(decode_string_list(*v)?));
    }
    if let Some(v) = map.get("$nin") {
        return Ok(core::FilterCondition::Nin(decode_string_list(*v)?));
    }
    Err(rustler::Error::Term(Box::new(
        "Filter condition must contain one of: $eq, $ne, $gt, $gte, $lt, $lte, $in, $nin, $near",
    )))
}

/// Decode an optional filter. Returns `None` when the term is the nil atom.
///
/// **Why not `Option<Term<'a>>`?**  Rustler 0.37's `Option<T>` decoder tries
/// `T::decode()` first.  Because `Term<'a>` can decode *any* term (including
/// nil), nil would be decoded as `Some(nil_atom_term)` rather than `None`,
/// causing `decode_filter` to fail with "MetadataFilter must be a map".
/// This helper performs the nil check before delegating to `decode_filter`.
pub fn decode_optional_filter<'a>(term: Term<'a>) -> NifResult<Option<core::MetadataFilter>> {
    if let Ok(a) = term.decode::<atom::Atom>() {
        if a == atom::nil() {
            return Ok(None);
        }
    }
    decode_filter(term).map(Some)
}

/// Decode an Elixir map term into a core::MetadataFilter (recursive).
///
/// Accepted shapes:
///   %{"field" => "city", "condition" => %{"$eq" => "NYC"}}
///   %{"$and" => [filter, ...]}
///   %{"$or"  => [filter, ...]}
pub fn decode_filter<'a>(term: Term<'a>) -> NifResult<core::MetadataFilter> {
    let map: HashMap<String, Term<'a>> = term.decode().map_err(|_| {
        rustler::Error::Term(Box::new("MetadataFilter must be a map"))
    })?;

    if let Some(list_term) = map.get("$and") {
        let items: Vec<Term<'a>> = list_term.decode().map_err(|_| {
            rustler::Error::Term(Box::new("$and value must be a list"))
        })?;
        let filters: NifResult<Vec<_>> = items.into_iter().map(decode_filter).collect();
        return Ok(core::MetadataFilter::And(filters?));
    }

    if let Some(list_term) = map.get("$or") {
        let items: Vec<Term<'a>> = list_term.decode().map_err(|_| {
            rustler::Error::Term(Box::new("$or value must be a list"))
        })?;
        let filters: NifResult<Vec<_>> = items.into_iter().map(decode_filter).collect();
        return Ok(core::MetadataFilter::Or(filters?));
    }

    let field: String = map.get("field")
        .ok_or_else(|| {
            rustler::Error::Term(Box::new(
                "Filter map must contain 'field' + 'condition', or '$and'/'$or'",
            ))
        })?
        .decode()
        .map_err(|_| rustler::Error::Term(Box::new("'field' must be a string")))?;

    let condition_term = *map.get("condition").ok_or_else(|| {
        rustler::Error::Term(Box::new("Filter map must contain 'condition' key"))
    })?;
    let condition_map: HashMap<String, Term<'a>> = condition_term.decode().map_err(|_| {
        rustler::Error::Term(Box::new("'condition' must be a map"))
    })?;
    let condition = decode_filter_condition(&condition_map)?;
    Ok(core::MetadataFilter::Field { field, condition })
}

// ---------------------------------------------------------------------------
// NifStruct types — map to Elixir structs defined in elixir/lib/moss/models.ex
// ---------------------------------------------------------------------------

#[derive(NifStruct)]
#[module = "Moss.ModelRef"]
pub struct NifModelRef {
    pub id: String,
    pub version: Option<String>,
}

impl From<core::ModelRef> for NifModelRef {
    fn from(m: core::ModelRef) -> Self {
        Self { id: m.id, version: m.version }
    }
}

#[derive(NifStruct)]
#[module = "Moss.DocumentInfo"]
pub struct NifDocumentInfo {
    pub id: String,
    pub text: String,
    pub metadata: Option<HashMap<String, String>>,
    pub embedding: Option<Vec<f32>>,
}

impl From<core::DocumentInfo> for NifDocumentInfo {
    fn from(d: core::DocumentInfo) -> Self {
        Self { id: d.id, text: d.text, metadata: d.metadata, embedding: d.embedding }
    }
}

impl From<NifDocumentInfo> for core::DocumentInfo {
    fn from(n: NifDocumentInfo) -> Self {
        Self { id: n.id, text: n.text, metadata: n.metadata, embedding: n.embedding }
    }
}

#[derive(NifStruct)]
#[module = "Moss.QueryResultDoc"]
pub struct NifQueryResultDoc {
    pub id: String,
    pub text: String,
    pub metadata: Option<HashMap<String, String>>,
    pub score: f32,
}

impl From<core::QueryResultDocumentInfo> for NifQueryResultDoc {
    fn from(q: core::QueryResultDocumentInfo) -> Self {
        Self {
            id: q.doc.id,
            text: q.doc.text,
            metadata: q.doc.metadata,
            score: q.score,
        }
    }
}

#[derive(NifStruct)]
#[module = "Moss.SearchResult"]
pub struct NifSearchResult {
    pub docs: Vec<NifQueryResultDoc>,
    pub query: String,
    pub index_name: Option<String>,
    pub time_taken_ms: Option<u64>,
}

impl From<core::SearchResult> for NifSearchResult {
    fn from(s: core::SearchResult) -> Self {
        Self {
            docs: s.docs.into_iter().map(Into::into).collect(),
            query: s.query,
            index_name: s.index_name,
            time_taken_ms: s.time_taken_ms,
        }
    }
}

#[derive(NifStruct)]
#[module = "Moss.IndexInfo"]
pub struct NifIndexInfo {
    pub id: String,
    pub name: String,
    pub version: Option<String>,
    pub status: String,
    pub doc_count: usize,
    pub created_at: Option<String>,
    pub updated_at: Option<String>,
    pub model: NifModelRef,
}

fn index_status_to_str(s: core::IndexStatus) -> String {
    use core::IndexStatus::*;
    match s {
        NotStarted => "NotStarted",
        Building => "Building",
        Ready => "Ready",
        Failed => "Failed",
    }
    .to_string()
}

impl From<core::IndexInfo> for NifIndexInfo {
    fn from(i: core::IndexInfo) -> Self {
        Self {
            id: i.id,
            name: i.name,
            version: i.version,
            status: index_status_to_str(i.status),
            doc_count: i.doc_count,
            created_at: i.created_at,
            updated_at: i.updated_at,
            model: i.model.into(),
        }
    }
}

#[derive(NifStruct)]
#[module = "Moss.PushIndexResult"]
pub struct NifPushIndexResult {
    pub job_id: String,
    pub index_name: String,
    pub doc_count: usize,
    pub status: String,
}

impl From<moss::session::PushIndexResult> for NifPushIndexResult {
    fn from(r: moss::session::PushIndexResult) -> Self {
        Self {
            job_id: r.job_id,
            index_name: r.index_name,
            doc_count: r.doc_count,
            status: r.status,
        }
    }
}

#[derive(NifStruct)]
#[module = "Moss.RefreshResult"]
pub struct NifRefreshResult {
    pub index_name: String,
    pub previous_updated_at: String,
    pub new_updated_at: String,
    pub was_updated: bool,
}

impl From<moss::manager::RefreshResult> for NifRefreshResult {
    fn from(r: moss::manager::RefreshResult) -> Self {
        Self {
            index_name: r.index_name,
            previous_updated_at: r.previous_updated_at,
            new_updated_at: r.new_updated_at,
            was_updated: r.was_updated,
        }
    }
}

// ---------------------------------------------------------------------------
// Manage client NifStructs
// ---------------------------------------------------------------------------

#[derive(NifStruct)]
#[module = "Moss.MutationResult"]
pub struct NifMutationResult {
    pub job_id: String,
    pub index_name: String,
    pub doc_count: usize,
}

impl From<moss::manage::types::MutationResult> for NifMutationResult {
    fn from(r: moss::manage::types::MutationResult) -> Self {
        Self { job_id: r.job_id, index_name: r.index_name, doc_count: r.doc_count }
    }
}

#[derive(NifStruct)]
#[module = "Moss.JobStatusResponse"]
pub struct NifJobStatusResponse {
    pub job_id: String,
    pub status: String,
    pub progress: f64,
    pub current_phase: Option<String>,
    pub error: Option<String>,
    pub created_at: String,
    pub updated_at: String,
    pub completed_at: Option<String>,
}

fn job_status_to_str(s: moss::manage::types::JobStatus) -> String {
    use moss::manage::types::JobStatus::*;
    match s {
        PendingUpload => "pending_upload",
        Uploading => "uploading",
        Building => "building",
        Completed => "completed",
        Failed => "failed",
    }
    .to_string()
}

fn job_phase_to_str(p: moss::manage::types::JobPhase) -> String {
    use moss::manage::types::JobPhase::*;
    match p {
        Downloading => "downloading",
        Deserializing => "deserializing",
        GeneratingEmbeddings => "generating_embeddings",
        BuildingIndex => "building_index",
        Uploading => "uploading",
        Cleanup => "cleanup",
    }
    .to_string()
}

impl From<moss::manage::types::JobStatusResponse> for NifJobStatusResponse {
    fn from(r: moss::manage::types::JobStatusResponse) -> Self {
        Self {
            job_id: r.job_id,
            status: job_status_to_str(r.status),
            progress: r.progress,
            current_phase: r.current_phase.map(job_phase_to_str),
            error: r.error,
            created_at: r.created_at,
            updated_at: r.updated_at,
            completed_at: r.completed_at,
        }
    }
}

#[derive(NifStruct)]
#[module = "Moss.CredentialsInfo"]
pub struct NifCredentialsInfo {
    pub project_name: String,
    pub project_id: String,
}

impl From<moss::manage::types::ValidateCredentialsResponse> for NifCredentialsInfo {
    fn from(r: moss::manage::types::ValidateCredentialsResponse) -> Self {
        Self { project_name: r.project_name, project_id: r.project_id }
    }
}
