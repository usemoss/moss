use napi::bindgen_prelude::*;
use napi_derive::napi;
use std::collections::HashMap;

use ::moss::models as core;

// ---------- Helpers ----------

/// Helper to cast core f32 vectors to JS f64 vectors
fn vec_f32_to_f64(v: Vec<f32>) -> Vec<f64> {
    v.into_iter().map(|x| x as f64).collect()
}

/// Helper to cast JS f64 vectors to core f32 vectors
fn vec_f64_to_f32(v: Vec<f64>) -> Vec<f32> {
    v.into_iter().map(|x| x as f32).collect()
}

// ---------- MetadataFilter conversion from JS objects ----------

fn json_value_to_string(v: &serde_json::Value) -> std::result::Result<String, Error> {
    match v {
        serde_json::Value::String(s) => Ok(s.clone()),
        serde_json::Value::Number(n) => Ok(n.to_string()),
        _ => Err(Error::new(
            Status::InvalidArg,
            "Filter value must be a string or number",
        )),
    }
}

fn json_string_vec(v: &serde_json::Value) -> std::result::Result<Vec<String>, Error> {
    let arr = v.as_array().ok_or_else(|| {
        Error::new(Status::InvalidArg, "$in/$nin value must be an array")
    })?;
    arr.iter().map(json_value_to_string).collect()
}

fn parse_filter_condition(
    obj: &serde_json::Map<String, serde_json::Value>,
) -> std::result::Result<core::FilterCondition, Error> {
    for (key, ctor) in [
        ("$eq", core::FilterCondition::Eq as fn(String) -> core::FilterCondition),
        ("$ne", core::FilterCondition::Ne),
        ("$gt", core::FilterCondition::Gt),
        ("$gte", core::FilterCondition::Gte),
        ("$lt", core::FilterCondition::Lt),
        ("$lte", core::FilterCondition::Lte),
        ("$near", core::FilterCondition::Near),
    ] {
        if let Some(v) = obj.get(key) {
            return Ok(ctor(json_value_to_string(v)?));
        }
    }
    if let Some(v) = obj.get("$in") {
        return Ok(core::FilterCondition::In(json_string_vec(v)?));
    }
    if let Some(v) = obj.get("$nin") {
        return Ok(core::FilterCondition::Nin(json_string_vec(v)?));
    }
    Err(Error::new(
        Status::InvalidArg,
        "Filter condition must contain one of: $eq, $ne, $gt, $gte, $lt, $lte, $in, $nin, $near",
    ))
}

/// Parse a JS object into a core::MetadataFilter (recursive).
/// Accepted shapes:
///   { field: "city", condition: { $eq: "NYC" } }
///   { $and: [filter, filter, ...] }
///   { $or:  [filter, filter, ...] }
pub fn parse_metadata_filter(
    obj: &serde_json::Value,
) -> std::result::Result<core::MetadataFilter, Error> {
    let map = obj.as_object().ok_or_else(|| {
        Error::new(Status::InvalidArg, "MetadataFilter must be an object")
    })?;

    if let Some(list) = map.get("$and") {
        let arr = list.as_array().ok_or_else(|| {
            Error::new(Status::InvalidArg, "$and value must be an array")
        })?;
        let filters: Vec<core::MetadataFilter> = arr
            .iter()
            .map(parse_metadata_filter)
            .collect::<std::result::Result<_, _>>()?;
        return Ok(core::MetadataFilter::And(filters));
    }

    if let Some(list) = map.get("$or") {
        let arr = list.as_array().ok_or_else(|| {
            Error::new(Status::InvalidArg, "$or value must be an array")
        })?;
        let filters: Vec<core::MetadataFilter> = arr
            .iter()
            .map(parse_metadata_filter)
            .collect::<std::result::Result<_, _>>()?;
        return Ok(core::MetadataFilter::Or(filters));
    }

    let field = map
        .get("field")
        .and_then(|v| v.as_str())
        .ok_or_else(|| {
            Error::new(
                Status::InvalidArg,
                "Filter must contain 'field' and 'condition', or '$and'/'$or'",
            )
        })?
        .to_string();

    let condition_obj = map
        .get("condition")
        .and_then(|v| v.as_object())
        .ok_or_else(|| {
            Error::new(Status::InvalidArg, "Filter must contain a 'condition' object")
        })?;

    let condition = parse_filter_condition(condition_obj)?;
    Ok(core::MetadataFilter::Field { field, condition })
}

// ---------- MossModel (Internal - Not Exported) ----------
//
// Note: Unlike Python bindings, we don't export a MossModel enum to JavaScript.
// The Index constructor accepts string values ("moss-minilm", "moss-mediumlm", "custom")
// which are validated and converted internally. This keeps the API simple and consistent
// with Python, while maintaining type safety within the Rust layer.

// ---------- ModelRef ----------
// JsModelRef doesn't use Serialize/Deserialize because it relies on #[napi(object)] for JavaScript bindings, 
// which directly maps Rust structs to JS objects.
// Same is true for CamelCase naming
/// Reference to the embedding model powering a Moss index.
#[napi(object, js_name = "ModelRef")]
#[derive(Clone, Debug)]
pub struct JsModelRef {
    /// Model identifier string.
    pub id: String,
    /// Semantic version or build identifier of the model.
    pub version: Option<String>,
}

impl From<core::ModelRef> for JsModelRef {
    fn from(m: core::ModelRef) -> Self {
        Self { id: m.id, version: m.version }
    }
}

impl From<JsModelRef> for core::ModelRef {
    fn from(p: JsModelRef) -> Self {
        Self { id: p.id, version: p.version }
    }
}

// ---------- IndexStatus (String Enum) ----------

/// Lifecycle status for background index creation processes.
#[napi(string_enum, js_name = "IndexStatus")]
#[derive(Debug, Clone)]
pub enum JsIndexStatus {
    NotStarted,
    Building,
    Ready,
    Failed,
}

impl From<core::IndexStatus> for JsIndexStatus {
    fn from(s: core::IndexStatus) -> Self {
        match s {
            core::IndexStatus::NotStarted => JsIndexStatus::NotStarted,
            core::IndexStatus::Building => JsIndexStatus::Building,
            core::IndexStatus::Ready => JsIndexStatus::Ready,
            core::IndexStatus::Failed => JsIndexStatus::Failed,
        }
    }
}

impl From<JsIndexStatus> for core::IndexStatus {
    fn from(s: JsIndexStatus) -> Self {
        match s {
            JsIndexStatus::NotStarted => core::IndexStatus::NotStarted,
            JsIndexStatus::Building => core::IndexStatus::Building,
            JsIndexStatus::Ready => core::IndexStatus::Ready,
            JsIndexStatus::Failed => core::IndexStatus::Failed,
        }
    }
}

// ---------- IndexInfo ----------

/// Information about a persisted index including status and model metadata.
#[napi(object, js_name = "IndexInfo")]
#[derive(Clone, Debug)]
pub struct JsIndexInfo {
    /// Unique identifier of the index.
    pub id: String,
    /// Human-readable index name.
    pub name: String,
    /// Index build or schema version string.
    pub version: Option<String>,
    /// Current lifecycle status of the index build.
    pub status: JsIndexStatus,
    /// Number of documents stored in the index.
    pub doc_count: u32,
    /// RFC 3339 timestamp indicating when the index was created.
    pub created_at: Option<String>,
    /// RFC 3339 timestamp indicating the last update time.
    pub updated_at: Option<String>,
    /// Embedding model details bound to the index.
    pub model: JsModelRef,
}

impl From<core::IndexInfo> for JsIndexInfo {
    fn from(i: core::IndexInfo) -> Self {
        Self {
            id: i.id,
            name: i.name,
            version: i.version,
            status: i.status.into(),
            doc_count: i.doc_count as u32,
            created_at: i.created_at,
            updated_at: i.updated_at,
            model: i.model.into(),
        }
    }
}

impl From<JsIndexInfo> for core::IndexInfo {
    fn from(p: JsIndexInfo) -> Self {
        Self {
            id: p.id,
            name: p.name,
            version: p.version,
            status: p.status.into(),
            doc_count: p.doc_count as usize,
            created_at: p.created_at,
            updated_at: p.updated_at,
            model: p.model.into(),
        }
    }
}

// ---------- DocumentInfo ----------

/// Document payload that can be indexed and later retrieved.
#[napi(object, js_name = "DocumentInfo")]
#[derive(Clone, Debug)]
pub struct JsDocumentInfo {
    /// Unique identifier within the index.
    pub id: String,
    /// Canonical text content used for embedding generation.
    pub text: String,
    /// Optional metadata map persisted alongside the document.
    pub metadata: Option<HashMap<String, String>>,
    /// Optional precomputed embedding vector (f64 for JS compatibility).
    pub embedding: Option<Vec<f64>>,
}

impl From<core::DocumentInfo> for JsDocumentInfo {
    fn from(d: core::DocumentInfo) -> Self {
        Self {
            id: d.id,
            text: d.text,
            metadata: d.metadata,
            embedding: d.embedding.map(vec_f32_to_f64),
        }
    }
}

impl From<JsDocumentInfo> for core::DocumentInfo {
    fn from(p: JsDocumentInfo) -> Self {
        Self {
            id: p.id,
            text: p.text,
            metadata: p.metadata,
            embedding: p.embedding.map(vec_f64_to_f32),
        }
    }
}

// ---------- QueryResultDocumentInfo ----------

/// Document returned from a query with similarity metadata.
#[napi(object, js_name = "QueryResultDocumentInfo")]
#[derive(Clone, Debug)]
pub struct JsQueryResultDocumentInfo {
    /// Document identifier.
    pub id: String,
    /// Original document text.
    pub text: String,
    /// Optional metadata associated with the document.
    pub metadata: Option<HashMap<String, String>>,
    /// Similarity score between 0 and 1 (higher is more relevant).
    pub score: f64, // JS only works in f64
}

impl From<core::QueryResultDocumentInfo> for JsQueryResultDocumentInfo {
    fn from(q: core::QueryResultDocumentInfo) -> Self {
        Self {
            id: q.doc.id,
            text: q.doc.text,
            metadata: q.doc.metadata,
            score: q.score as f64,
        }
    }
}

// No reverse impl needed, as this is an output type

// ---------- SearchResult ----------

/// Result payload returned by a semantic query operation.
#[napi(object, js_name = "SearchResult")]
#[derive(Clone, Debug)]
pub struct JsSearchResult {
    /// Matching documents ordered by similarity.
    pub docs: Vec<JsQueryResultDocumentInfo>,
    /// Original query string for reference.
    pub query: String,
    /// Optional index name when available.
    pub index_name: Option<String>,
    /// Optional execution time in milliseconds.
    pub time_taken_in_ms: Option<u32>,
}

impl From<core::SearchResult> for JsSearchResult {
    fn from(s: core::SearchResult) -> Self {
        Self {
            docs: s.docs.into_iter().map(Into::into).collect(),
            query: s.query,
            index_name: s.index_name,
            time_taken_in_ms: s.time_taken_ms.map(|t| t as u32),
        }
    }
}

// No reverse impl needed, as this is an output type

// ---------- QueryOptions ----------

/// Options for query operations.
#[napi(object, js_name = "QueryOptions")]
#[derive(Clone, Debug, Default)]
pub struct JsQueryOptions {
    /// Caller-provided embedding vector. When supplied, skips embedding generation.
    pub embedding: Option<Vec<f64>>,
    /// Number of top results to return.
    pub top_k: Option<u32>,
    /// Weight for hybrid search fusion (0.0 to 1.0). Default 0.8.
    pub alpha: Option<f64>,
    /// Optional metadata filter for narrowing results.
    pub filter: Option<serde_json::Value>,
}

impl From<core::QueryOptions> for JsQueryOptions {
    fn from(o: core::QueryOptions) -> Self {
        Self {
            embedding: o.embedding.map(vec_f32_to_f64),
            top_k: o.top_k.map(|v| v as u32),
            alpha: o.alpha.map(|v| v as f64),
            filter: None, // core→JS: filter not round-tripped back
        }
    }
}

impl JsQueryOptions {
    /// Convert to core QueryOptions, parsing the JS filter object.
    pub fn into_core(self) -> std::result::Result<core::QueryOptions, Error> {
        let filter = self
            .filter
            .as_ref()
            .map(parse_metadata_filter)
            .transpose()?;
        Ok(core::QueryOptions {
            embedding: self.embedding.map(vec_f64_to_f32),
            top_k: self.top_k.map(|v| v as usize),
            alpha: self.alpha.map(|v| v as f32),
            filter,
        })
    }
}

// ---------- GetDocumentsOptions ----------

/// Optional filters when retrieving documents from an index.
#[napi(object, js_name = "GetDocumentsOptions")]
#[derive(Clone, Debug, Default)]
pub struct JsGetDocumentsOptions {
    /// List of document IDs to fetch; omitted returns all documents.
    pub doc_ids: Option<Vec<String>>,
}

impl From<core::GetDocumentsOptions> for JsGetDocumentsOptions {
    fn from(o: core::GetDocumentsOptions) -> Self {
        Self { doc_ids: o.doc_ids }
    }
}

impl From<JsGetDocumentsOptions> for core::GetDocumentsOptions {
    fn from(p: JsGetDocumentsOptions) -> Self {
        Self { doc_ids: p.doc_ids }
    }
}

// ---------- LoadIndexOptions ----------

/// Options for loading an index with auto-refresh configuration.
#[napi(object, js_name = "LoadIndexOptions")]
#[derive(Clone, Debug)]
pub struct JsLoadIndexOptions {
    /// Enable auto-refresh polling for this index.
    #[napi(js_name = "autoRefresh")]
    pub auto_refresh: Option<bool>,
    /// Polling interval in seconds (default: 600 / 10 minutes).
    #[napi(js_name = "pollingIntervalInSeconds")]
    pub polling_interval_in_seconds: Option<u32>,
    /// Optional filesystem path for caching index data to disk.
    #[napi(js_name = "cachePath")]
    pub cache_path: Option<String>,
}

impl From<::moss::manager::LoadIndexOptions> for JsLoadIndexOptions {
    fn from(opts: ::moss::manager::LoadIndexOptions) -> Self {
        Self {
            auto_refresh: Some(opts.auto_refresh),
            polling_interval_in_seconds: Some(opts.polling_interval_in_seconds as u32),
            cache_path: opts.cache_path,
        }
    }
}

impl From<JsLoadIndexOptions> for ::moss::manager::LoadIndexOptions {
    fn from(opts: JsLoadIndexOptions) -> Self {
        Self {
            auto_refresh: opts.auto_refresh.unwrap_or(false),
            polling_interval_in_seconds: opts.polling_interval_in_seconds.unwrap_or(600) as u64,
            cache_path: opts.cache_path,
        }
    }
}

// ---------- RefreshResult ----------

/// Result of an index refresh operation.
#[napi(object, js_name = "RefreshResult")]
#[derive(Clone, Debug)]
pub struct JsRefreshResult {
    /// Name of the index that was refreshed.
    #[napi(js_name = "indexName")]
    pub index_name: String,
    /// Timestamp before the refresh operation.
    #[napi(js_name = "previousUpdatedAt")]
    pub previous_updated_at: String,
    /// Timestamp after the refresh operation.
    #[napi(js_name = "newUpdatedAt")]
    pub new_updated_at: String,
    /// Whether the index was actually updated (true if cloud had newer version).
    #[napi(js_name = "wasUpdated")]
    pub was_updated: bool,
}

impl From<::moss::manager::RefreshResult> for JsRefreshResult {
    fn from(r: ::moss::manager::RefreshResult) -> Self {
        Self {
            index_name: r.index_name,
            previous_updated_at: r.previous_updated_at,
            new_updated_at: r.new_updated_at,
            was_updated: r.was_updated,
        }
    }
}

// Model Registration is handled by Napi Macros glue. We dont need to manually register them here.