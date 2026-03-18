//! Pyo3 bindings for the core `Index` type.
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use std::cell::RefCell;

use moss::index::Index as CoreIndex;
use moss::models as core;

use crate::models::{
    parse_metadata_filter, PyAddDocumentsOptions, PyDocumentInfo, PyGetDocumentsOptions,
    PyIndexInfo, PySearchResult, PySerializedIndex,
};

fn parse_moss_model(s: &str) -> Result<core::MossModel, PyErr> {
    match s {
        "moss-minilm" => Ok(core::MossModel::MossMinilm),
        "moss-mediumlm" => Ok(core::MossModel::MossMediumlm),
        "custom" => Ok(core::MossModel::MossCustom),
        other => Err(PyValueError::new_err(format!(
            "Invalid MossModel '{}'. Expected 'moss-minilm', 'moss-mediumlm', or 'custom'.",
            other
        ))),
    }
}

#[pyclass(name = "Index", unsendable)]
pub struct PyIndex {
    inner: RefCell<CoreIndex>,
}

#[pymethods]
impl PyIndex {
    /// Create a new Index.
    ///
    /// Args:
    ///     name: Index name.
    ///     model_id: One of `"moss-minilm"`, `"moss-mediumlm"`, or `"custom"`.
    #[new]
    pub fn new(name: String, model_id: &str) -> PyResult<Self> {
        let model = parse_moss_model(model_id)?;
        Ok(Self {
            inner: RefCell::new(CoreIndex::new(name, model)),
        })
    }

    // ---------- Index info ----------

    /// Get metadata about this index.
    pub fn get_info(&self) -> PyResult<PyIndexInfo> {
        let info = self.inner.borrow().get_info();
        Ok(info.into())
    }

    // ---------- Document operations ----------

    /// Add or update documents in the index.
    ///
    /// Embeddings **must** be precomputed and provided.
    ///
    /// Returns:
    ///     (added, updated)
    #[pyo3(signature = (docs, embeddings, options=None))]
    pub fn add_documents(
        &self,
        docs: Vec<PyDocumentInfo>,
        embeddings: Vec<Vec<f32>>,
        options: Option<PyAddDocumentsOptions>,
    ) -> PyResult<(usize, usize)> {
        let mut idx = self.inner.borrow_mut();
        let core_docs: Vec<core::DocumentInfo> = docs.into_iter().map(Into::into).collect();
        let core_opts: Option<core::AddDocumentsOptions> = options.map(Into::into);

        idx.add_documents(&core_docs, Some(&embeddings), core_opts.as_ref())
            .map_err(PyValueError::new_err)
    }

    /// Delete documents by their IDs. Returns the number deleted.
    pub fn delete_documents(&self, doc_ids: Vec<String>) -> PyResult<usize> {
        let mut idx = self.inner.borrow_mut();
        Ok(idx.delete_documents(&doc_ids))
    }

    /// Get documents (optionally filtered by IDs).
    #[pyo3(signature = (options=None))]
    pub fn get_documents(
        &self,
        options: Option<PyGetDocumentsOptions>,
    ) -> PyResult<Vec<PyDocumentInfo>> {
        let idx = self.inner.borrow();
        let core_opts: Option<core::GetDocumentsOptions> = options.map(Into::into);
        let docs = idx
            .get_documents(core_opts.as_ref())
            .into_iter()
            .map(Into::into)
            .collect();
        Ok(docs)
    }

    // ---------- Querying ----------

    /// Perform a semantic search using a **precomputed** query embedding.
    ///
    /// Args:
    ///     query: The search text.
    ///     top_k: Max number of results (default 5).
    ///     query_embedding: Precomputed embedding vector for `query`.
    ///     alpha: Weight for hybrid search fusion (default 0.8). A value of 0.8 favors
    ///         semantic search over keyword search. Higher values (closer to 1.0) give
    ///         more weight to semantic search, while lower values (closer to 0.0) favor
    ///         keyword search.
    #[pyo3(signature = (query, top_k, query_embedding, alpha = None, filter = None))]
    pub fn query(
        &self,
        py: Python<'_>,
        query: String,
        top_k: usize,
        query_embedding: Vec<f32>,
        alpha: Option<f32>,
        filter: Option<Py<PyAny>>,
    ) -> PyResult<PySearchResult> {
        let idx = self.inner.borrow();
        let alpha = alpha.unwrap_or(0.8);
        let parsed_filter = filter
            .map(|f| parse_metadata_filter(py, f.bind(py)))
            .transpose()?;
        let res = idx
            .query(
                &query,
                top_k,
                Some(&query_embedding),
                alpha,
                parsed_filter.as_ref(),
            )
            .map_err(PyValueError::new_err)?;
        Ok(res.into())
    }

    // ---------- Serialization ----------

    /// Serialize this index to a `SerializedIndex`.
    pub fn serialize(&self) -> PyResult<PySerializedIndex> {
        let idx = self.inner.borrow();
        Ok(idx.serialize().into())
    }

    /// Load serialized metadata/embeddings into this index using full documents.
    pub fn deserialize(
        &self,
        data: PySerializedIndex,
        documents: Vec<PyDocumentInfo>,
    ) -> PyResult<()> {
        let mut idx = self.inner.borrow_mut();
        let core_data: core::SerializedIndex = data.into();
        let core_docs: Vec<core::DocumentInfo> = documents.into_iter().map(Into::into).collect();
        idx.deserialize(&core_data, &core_docs)
            .map_err(PyValueError::new_err)
    }

    // ---------- Utilities ----------

    /// Number of documents in the index.
    #[getter]
    pub fn doc_count(&self) -> PyResult<usize> {
        Ok(self.inner.borrow().doc_count())
    }

    /// Clear all documents and embeddings.
    pub fn clear(&self) {
        self.inner.borrow_mut().clear();
    }
}
