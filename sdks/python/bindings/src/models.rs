//! Python-facing data models (Pyo3 bindings) mirroring the core Rust models.
//!
//! These classes are thin wrappers around the internal structs in `crate::models`,
//! keeping field names and camelCase JSON semantics consistent for cross-platform
//! compatibility. Enums are exposed as strings to keep the Python API simple.
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use moss::models as core;

// ---------- MetadataFilter conversion from Python dicts ----------

/// Coerces a Python value (str, int, float) to String.
fn py_value_to_string(v: &Bound<PyAny>) -> PyResult<String> {
    if let Ok(s) = v.extract::<String>() {
        return Ok(s);
    }
    if let Ok(n) = v.extract::<f64>() {
        if n.fract() == 0.0 && n.abs() < (i64::MAX as f64) {
            return Ok(format!("{}", n as i64));
        }
        return Ok(n.to_string());
    }
    Err(pyo3::exceptions::PyTypeError::new_err(
        "Filter value must be a str, int, or float",
    ))
}

fn py_string_vec(v: &Bound<PyAny>) -> PyResult<Vec<String>> {
    let list = v
        .downcast::<PyList>()
        .map_err(|_| pyo3::exceptions::PyTypeError::new_err("$in/$nin value must be a list"))?;
    list.iter().map(|item| py_value_to_string(&item)).collect()
}

/// Maps a single-key Python dict (`{"$op": value}`) to a `FilterCondition`.
fn parse_filter_condition(dict: &Bound<PyDict>) -> PyResult<core::FilterCondition> {
    // Scalar comparison operators
    for (key, ctor) in [
        (
            "$eq",
            core::FilterCondition::Eq as fn(String) -> core::FilterCondition,
        ),
        ("$ne", core::FilterCondition::Ne),
        ("$gt", core::FilterCondition::Gt),
        ("$gte", core::FilterCondition::Gte),
        ("$lt", core::FilterCondition::Lt),
        ("$lte", core::FilterCondition::Lte),
        ("$near", core::FilterCondition::Near),
    ] {
        if let Some(v) = dict.get_item(key)? {
            return Ok(ctor(py_value_to_string(&v)?));
        }
    }

    // List operators
    if let Some(v) = dict.get_item("$in")? {
        return Ok(core::FilterCondition::In(py_string_vec(&v)?));
    }
    if let Some(v) = dict.get_item("$nin")? {
        return Ok(core::FilterCondition::Nin(py_string_vec(&v)?));
    }

    Err(pyo3::exceptions::PyValueError::new_err(
        "Filter condition must contain one of: $eq, $ne, $gt, $gte, $lt, $lte, $in, $nin, $near",
    ))
}

/// Parses a Python dict into a core::MetadataFilter (recursive).
/// Accepted shapes:
///   {"field": "city", "condition": {"$eq": "NYC"}}
///   {"$and": [filter, filter, ...]}
///   {"$or":  [filter, filter, ...]}
pub fn parse_metadata_filter(py: Python<'_>, obj: &Bound<PyAny>) -> PyResult<core::MetadataFilter> {
    let dict: &Bound<PyDict> = obj
        .downcast::<PyDict>()
        .map_err(|_| pyo3::exceptions::PyTypeError::new_err("MetadataFilter must be a dict"))?;

    if let Some(list) = dict.get_item("$and")? {
        let items: &Bound<PyList> = list
            .downcast::<PyList>()
            .map_err(|_| pyo3::exceptions::PyTypeError::new_err("$and value must be a list"))?;
        let filters: Vec<core::MetadataFilter> = items
            .iter()
            .map(|item| parse_metadata_filter(py, &item))
            .collect::<PyResult<_>>()?;
        return Ok(core::MetadataFilter::And(filters));
    }

    if let Some(list) = dict.get_item("$or")? {
        let items: &Bound<PyList> = list
            .downcast::<PyList>()
            .map_err(|_| pyo3::exceptions::PyTypeError::new_err("$or value must be a list"))?;
        let filters: Vec<core::MetadataFilter> = items
            .iter()
            .map(|item| parse_metadata_filter(py, &item))
            .collect::<PyResult<_>>()?;
        return Ok(core::MetadataFilter::Or(filters));
    }

    // Field condition: {"field": "city", "condition": {"$eq": "NYC"}}
    let field = dict
        .get_item("field")?
        .ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err(
                "Filter dict must contain 'field' and 'condition', or '$and'/'$or'",
            )
        })?
        .extract::<String>()?;
    let condition_obj = dict.get_item("condition")?.ok_or_else(|| {
        pyo3::exceptions::PyValueError::new_err("Filter dict must contain 'condition' key")
    })?;
    let condition_dict: &Bound<PyDict> = condition_obj
        .downcast::<PyDict>()
        .map_err(|_| pyo3::exceptions::PyTypeError::new_err("'condition' must be a dict"))?;
    let condition = parse_filter_condition(condition_dict)?;
    Ok(core::MetadataFilter::Field { field, condition })
}

// ---------- ModelRef ----------

#[pyclass(name = "ModelRef")]
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PyModelRef {
    #[pyo3(get, set)]
    pub id: String,
    #[pyo3(get, set)]
    pub version: String,
}

#[pymethods]
impl PyModelRef {
    #[new]
    pub fn new(id: String, version: String) -> Self {
        Self { id, version }
    }
}

impl From<core::ModelRef> for PyModelRef {
    fn from(m: core::ModelRef) -> Self {
        Self {
            id: m.id,
            version: m.version.unwrap_or_default(),
        }
    }
}

impl From<PyModelRef> for core::ModelRef {
    fn from(p: PyModelRef) -> Self {
        Self {
            id: p.id,
            version: Some(p.version),
        }
    }
}

// ---------- IndexStatus (as strings) ----------

#[pyclass(name = "IndexStatus")]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PyIndexStatus {
    #[pyo3(get, set)]
    pub value: String,
}

#[pymethods]
impl PyIndexStatus {
    #[new]
    pub fn new(value: String) -> Self {
        Self { value }
    }

    #[classattr]
    pub const NotStarted: &'static str = "NotStarted";
    #[classattr]
    pub const Building: &'static str = "Building";
    #[classattr]
    pub const Ready: &'static str = "Ready";
    #[classattr]
    pub const Failed: &'static str = "Failed";
}

impl From<core::IndexStatus> for PyIndexStatus {
    fn from(s: core::IndexStatus) -> Self {
        use core::IndexStatus::*;
        let value = match s {
            NotStarted => "NotStarted",
            Building => "Building",
            Ready => "Ready",
            Failed => "Failed",
        }
        .to_string();
        Self { value }
    }
}

impl TryFrom<PyIndexStatus> for core::IndexStatus {
    type Error = PyErr;
    fn try_from(p: PyIndexStatus) -> Result<Self, Self::Error> {
        use core::IndexStatus::*;
        match p.value.as_str() {
            "NotStarted" => Ok(NotStarted),
            "Building" => Ok(Building),
            "Ready" => Ok(Ready),
            "Failed" => Ok(Failed),
            other => Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Invalid IndexStatus: {}",
                other
            ))),
        }
    }
}

// ---------- IndexInfo ----------

#[pyclass(name = "IndexInfo")]
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PyIndexInfo {
    #[pyo3(get, set)]
    pub id: String,
    #[pyo3(get, set)]
    pub name: String,
    #[pyo3(get, set)]
    pub version: String,
    /// Stored as string; see PyIndexStatus for constants.
    #[pyo3(get, set)]
    pub status: String,
    #[serde(rename = "docCount")]
    #[pyo3(get, set)]
    pub doc_count: usize,
    #[serde(rename = "createdAt")]
    #[pyo3(get, set)]
    pub created_at: String,
    #[serde(rename = "updatedAt")]
    #[pyo3(get, set)]
    pub updated_at: String,
    #[pyo3(get, set)]
    pub model: PyModelRef,
}

#[pymethods]
impl PyIndexInfo {
    #[new]
    #[pyo3(signature = (id, name, version, status, doc_count, created_at, updated_at, model))]
    pub fn new(
        id: String,
        name: String,
        version: String,
        status: String,
        doc_count: usize,
        created_at: String,
        updated_at: String,
        model: PyModelRef,
    ) -> Self {
        Self {
            id,
            name,
            version,
            status,
            doc_count,
            created_at,
            updated_at,
            model,
        }
    }
}

impl From<core::IndexInfo> for PyIndexInfo {
    fn from(i: core::IndexInfo) -> Self {
        Self {
            id: i.id,
            name: i.name,
            version: i.version.unwrap_or_default(),
            status: PyIndexStatus::from(i.status).value,
            doc_count: i.doc_count,
            created_at: i.created_at.unwrap_or_default(),
            updated_at: i.updated_at.unwrap_or_default(),
            model: i.model.into(),
        }
    }
}

impl TryFrom<PyIndexInfo> for core::IndexInfo {
    type Error = PyErr;
    fn try_from(p: PyIndexInfo) -> Result<Self, Self::Error> {
        Ok(Self {
            id: p.id,
            name: p.name,
            version: Some(p.version),
            status: PyIndexStatus { value: p.status }.try_into()?,
            doc_count: p.doc_count,
            created_at: Some(p.created_at),
            updated_at: Some(p.updated_at),
            model: p.model.into(),
        })
    }
}

// ---------- DocumentInfo ----------

#[pyclass(name = "DocumentInfo")]
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PyDocumentInfo {
    #[pyo3(get, set)]
    pub id: String,
    #[pyo3(get, set)]
    pub text: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    #[pyo3(get, set)]
    pub metadata: Option<HashMap<String, String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    #[pyo3(get, set)]
    pub embedding: Option<Vec<f32>>,
}

#[pymethods]
impl PyDocumentInfo {
    #[new]
    #[pyo3(signature = (id, text, metadata=None, embedding=None))]
    pub fn new(
        id: String,
        text: String,
        metadata: Option<HashMap<String, String>>,
        embedding: Option<Vec<f32>>,
    ) -> Self {
        Self {
            id,
            text,
            metadata,
            embedding,
        }
    }
}

impl From<core::DocumentInfo> for PyDocumentInfo {
    fn from(d: core::DocumentInfo) -> Self {
        Self {
            id: d.id,
            text: d.text,
            metadata: d.metadata,
            embedding: d.embedding,
        }
    }
}

impl From<PyDocumentInfo> for core::DocumentInfo {
    fn from(p: PyDocumentInfo) -> Self {
        Self {
            id: p.id,
            text: p.text,
            metadata: p.metadata,
            embedding: p.embedding,
        }
    }
}

// ---------- QueryResultDocumentInfo ----------

#[pyclass(name = "QueryResultDocumentInfo")]
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PyQueryResultDocumentInfo {
    #[pyo3(get, set)]
    pub id: String,
    #[pyo3(get, set)]
    pub text: String,
    #[pyo3(get, set)]
    pub metadata: Option<HashMap<String, String>>,
    #[pyo3(get, set)]
    pub score: f32,
}

#[pymethods]
impl PyQueryResultDocumentInfo {
    #[new]
    #[pyo3(signature = (id, text, metadata=None, score=0.0))]
    pub fn new(
        id: String,
        text: String,
        metadata: Option<HashMap<String, String>>,
        score: f32,
    ) -> Self {
        Self {
            id,
            text,
            metadata,
            score,
        }
    }
}

impl From<core::QueryResultDocumentInfo> for PyQueryResultDocumentInfo {
    fn from(q: core::QueryResultDocumentInfo) -> Self {
        Self {
            id: q.doc.id,
            text: q.doc.text,
            metadata: q.doc.metadata,
            score: q.score,
        }
    }
}

impl From<PyQueryResultDocumentInfo> for core::QueryResultDocumentInfo {
    fn from(p: PyQueryResultDocumentInfo) -> Self {
        core::QueryResultDocumentInfo {
            doc: core::DocumentInfo {
                id: p.id,
                text: p.text,
                metadata: p.metadata,
                embedding: None,
            },
            score: p.score,
        }
    }
}

// ---------- SearchResult ----------

#[pyclass(name = "SearchResult")]
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PySearchResult {
    #[pyo3(get, set)]
    pub docs: Vec<PyQueryResultDocumentInfo>,
    #[pyo3(get, set)]
    pub query: String,
    #[pyo3(get, set)]
    pub index_name: Option<String>,
    #[pyo3(get, set)]
    pub time_taken_ms: Option<u64>,
}

#[pymethods]
impl PySearchResult {
    #[new]
    #[pyo3(signature = (docs, query, index_name=None, time_taken_ms=None))]
    pub fn new(
        docs: Vec<PyQueryResultDocumentInfo>,
        query: String,
        index_name: Option<String>,
        time_taken_ms: Option<u64>,
    ) -> Self {
        Self {
            docs,
            query,
            index_name,
            time_taken_ms,
        }
    }
}

impl From<core::SearchResult> for PySearchResult {
    fn from(s: core::SearchResult) -> Self {
        Self {
            docs: s.docs.into_iter().map(Into::into).collect(),
            query: s.query,
            index_name: s.index_name,
            time_taken_ms: s.time_taken_ms,
        }
    }
}

impl From<PySearchResult> for core::SearchResult {
    fn from(p: PySearchResult) -> Self {
        Self {
            docs: p.docs.into_iter().map(Into::into).collect(),
            query: p.query,
            index_name: p.index_name,
            time_taken_ms: p.time_taken_ms,
        }
    }
}

// ---------- Query / Index Options ----------

#[pyclass(name = "QueryOptions")]
#[derive(Debug, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PyQueryOptions {
    #[serde(skip_serializing_if = "Option::is_none")]
    #[pyo3(get, set)]
    pub embedding: Option<Vec<f32>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    #[pyo3(get, set)]
    pub top_k: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    #[pyo3(get, set)]
    pub alpha: Option<f32>,
    #[serde(skip)]
    #[pyo3(get, set)]
    pub filter: Option<Py<PyAny>>,
}

impl Clone for PyQueryOptions {
    fn clone(&self) -> Self {
        Python::attach(|py| Self {
            embedding: self.embedding.clone(),
            top_k: self.top_k,
            alpha: self.alpha,
            filter: self.filter.as_ref().map(|f| f.clone_ref(py)),
        })
    }
}

#[pymethods]
impl PyQueryOptions {
    #[new]
    #[pyo3(signature = (embedding=None, top_k=None, alpha=None, filter=None))]
    pub fn new(
        embedding: Option<Vec<f32>>,
        top_k: Option<usize>,
        alpha: Option<f32>,
        filter: Option<Py<PyAny>>,
    ) -> Self {
        Self {
            embedding,
            top_k,
            alpha,
            filter,
        }
    }
}

impl From<core::QueryOptions> for PyQueryOptions {
    fn from(o: core::QueryOptions) -> Self {
        Self {
            embedding: o.embedding,
            top_k: o.top_k,
            alpha: o.alpha,
            filter: None,
        }
    }
}

impl From<PyQueryOptions> for core::QueryOptions {
    fn from(p: PyQueryOptions) -> Self {
        Self {
            embedding: p.embedding,
            top_k: p.top_k,
            alpha: p.alpha,
            filter: None, // filter is parsed separately at call site
        }
    }
}

// ---------- AddDocumentsOptions ----------

#[pyclass(name = "AddDocumentsOptions")]
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PyAddDocumentsOptions {
    #[pyo3(get, set)]
    pub upsert: bool,
}

#[pymethods]
impl PyAddDocumentsOptions {
    #[new]
    #[pyo3(signature = (upsert=true))]
    pub fn new(upsert: bool) -> Self {
        Self { upsert }
    }
}

impl From<core::AddDocumentsOptions> for PyAddDocumentsOptions {
    fn from(o: core::AddDocumentsOptions) -> Self {
        Self { upsert: o.upsert }
    }
}

impl From<PyAddDocumentsOptions> for core::AddDocumentsOptions {
    fn from(p: PyAddDocumentsOptions) -> Self {
        Self { upsert: p.upsert }
    }
}

// ---------- GetDocumentsOptions ----------

#[pyclass(name = "GetDocumentsOptions")]
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PyGetDocumentsOptions {
    #[pyo3(get, set)]
    pub doc_ids: Option<Vec<String>>,
}

#[pymethods]
impl PyGetDocumentsOptions {
    #[new]
    #[pyo3(signature = (doc_ids=None))]
    pub fn new(doc_ids: Option<Vec<String>>) -> Self {
        Self { doc_ids }
    }
}

impl From<core::GetDocumentsOptions> for PyGetDocumentsOptions {
    fn from(o: core::GetDocumentsOptions) -> Self {
        Self { doc_ids: o.doc_ids }
    }
}

impl From<PyGetDocumentsOptions> for core::GetDocumentsOptions {
    fn from(p: PyGetDocumentsOptions) -> Self {
        Self { doc_ids: p.doc_ids }
    }
}

// ---------- SerializedIndex ----------

#[pyclass(name = "SerializedIndex")]
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PySerializedIndex {
    #[pyo3(get, set)]
    pub name: String,
    #[pyo3(get, set)]
    pub version: String,
    #[pyo3(get, set)]
    pub model: PyModelRef,
    #[pyo3(get, set)]
    pub dimension: usize,
    #[pyo3(get, set)]
    pub embeddings: Vec<Vec<f32>>,
    #[serde(rename = "docIds")]
    #[pyo3(get, set)]
    pub doc_ids: Vec<String>,
}

#[pymethods]
impl PySerializedIndex {
    #[new]
    #[pyo3(signature = (name, version, model, dimension, embeddings, doc_ids))]
    pub fn new(
        name: String,
        version: String,
        model: PyModelRef,
        dimension: usize,
        embeddings: Vec<Vec<f32>>,
        doc_ids: Vec<String>,
    ) -> Self {
        Self {
            name,
            version,
            model,
            dimension,
            embeddings,
            doc_ids,
        }
    }
}

impl From<core::SerializedIndex> for PySerializedIndex {
    fn from(s: core::SerializedIndex) -> Self {
        Self {
            name: s.name,
            version: s.version,
            model: s.model.into(),
            dimension: s.dimension,
            embeddings: s.embeddings,
            doc_ids: s.doc_ids,
        }
    }
}

impl From<PySerializedIndex> for core::SerializedIndex {
    fn from(p: PySerializedIndex) -> Self {
        Self {
            name: p.name,
            version: p.version,
            model: p.model.into(),
            dimension: p.dimension,
            embeddings: p.embeddings,
            doc_ids: p.doc_ids,
        }
    }
}

// ---------- RefreshResult ----------

#[pyclass(name = "RefreshResult")]
#[derive(Clone, Debug)]
pub struct PyRefreshResult {
    #[pyo3(get)]
    pub index_name: String,
    #[pyo3(get)]
    pub previous_updated_at: String,
    #[pyo3(get)]
    pub new_updated_at: String,
    #[pyo3(get)]
    pub was_updated: bool,
}

#[pymethods]
impl PyRefreshResult {
    #[new]
    pub fn new(
        index_name: String,
        previous_updated_at: String,
        new_updated_at: String,
        was_updated: bool,
    ) -> Self {
        Self {
            index_name,
            previous_updated_at,
            new_updated_at,
            was_updated,
        }
    }
}

impl From<::moss::manager::RefreshResult> for PyRefreshResult {
    fn from(r: ::moss::manager::RefreshResult) -> Self {
        Self {
            index_name: r.index_name,
            previous_updated_at: r.previous_updated_at,
            new_updated_at: r.new_updated_at,
            was_updated: r.was_updated,
        }
    }
}

// ---------- Module registration ----------

/// Register all model classes into a Python module/submodule.
pub fn register_models(_py: Python<'_>, m: &Bound<PyModule>) -> PyResult<()> {
    m.add_class::<PyModelRef>()?;
    m.add_class::<PyIndexStatus>()?;
    m.add_class::<PyIndexInfo>()?;
    m.add_class::<PyDocumentInfo>()?;
    m.add_class::<PyQueryResultDocumentInfo>()?;
    m.add_class::<PySearchResult>()?;
    m.add_class::<PyQueryOptions>()?;
    m.add_class::<PyGetDocumentsOptions>()?;

    // Optional convenience: expose a dict of enum constants
    let status = PyDict::new(m.py());
    status.set_item("NotStarted", PyIndexStatus::NotStarted)?;
    status.set_item("Building", PyIndexStatus::Building)?;
    status.set_item("Ready", PyIndexStatus::Ready)?;
    status.set_item("Failed", PyIndexStatus::Failed)?;
    m.add("IndexStatusValues", status)?;

    Ok(())
}
