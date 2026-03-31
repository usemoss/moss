use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;

use moss::manager::{IndexManager, LoadIndexOptions};

use crate::models::{parse_metadata_filter, PyIndexInfo, PySearchResult};

// ---------- PyIndexManager ----------

#[pyclass(name = "IndexManager")]
pub struct PyIndexManager {
    inner: IndexManager,
    runtime: tokio::runtime::Runtime,
}

#[pymethods]
impl PyIndexManager {
    #[new]
    #[pyo3(signature = (project_id, project_key, base_url=None, client_id=None))]
    pub fn new(
        project_id: String,
        project_key: String,
        base_url: Option<String>,
        client_id: Option<String>,
    ) -> PyResult<Self> {
        let runtime = tokio::runtime::Runtime::new()
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to create runtime: {}", e)))?;

        let inner = match base_url {
            Some(url) => IndexManager::with_base_url(project_id, project_key, url, runtime.handle().clone(), client_id),
            None => IndexManager::new(project_id, project_key, runtime.handle().clone(), client_id),
        };

        Ok(Self {
            inner,
            runtime,
        })
    }

    /// Loads an index from the cloud into memory.
    /// If the index is already loaded, it will be reloaded (stops any existing polling).
    /// Optionally enables auto-refresh polling via options.
    #[pyo3(signature = (index_name, auto_refresh=false, polling_interval_in_seconds=600))]
    pub fn load_index(
        &self,
        index_name: String,
        auto_refresh: bool,
        polling_interval_in_seconds: u64,
    ) -> PyResult<PyIndexInfo> {
        let options = if auto_refresh {
            Some(LoadIndexOptions {
                auto_refresh: true,
                polling_interval_in_seconds,
            })
        } else {
            None
        };

        self.runtime
            .block_on(self.inner.load_index(&index_name, options))
            .map(|info| info.into())
            .map_err(|e| PyRuntimeError::new_err(format!("{}", e)))
    }

    pub fn unload_index(&self, index_name: String) -> PyResult<()> {
        self.runtime
            .block_on(self.inner.unload_index(&index_name))
            .map_err(|e| PyRuntimeError::new_err(format!("{}", e)))
    }

    pub fn has_index(&self, index_name: String) -> PyResult<bool> {
        Ok(self.runtime.block_on(self.inner.has_index(&index_name)))
    }

    #[pyo3(signature = (index_name, query, query_embedding, top_k=5, alpha=0.8, filter=None))]
    pub fn query(
        &self,
        py: Python<'_>,
        index_name: String,
        query: String,
        query_embedding: Vec<f32>,
        top_k: usize,
        alpha: f32,
        filter: Option<Py<PyAny>>,
    ) -> PyResult<PySearchResult> {
        let parsed_filter = filter
            .map(|f| parse_metadata_filter(py, f.bind(py)))
            .transpose()?;
        let result = self.runtime
            .block_on(self.inner.query(
                &index_name,
                &query,
                &query_embedding,
                top_k,
                alpha,
                parsed_filter.as_ref(),
            ))
            .map(|result| result.into())
            .map_err(|e| PyRuntimeError::new_err(format!("{}", e)))?;

        Ok(result)
    }

    #[pyo3(signature = (index_name, query, top_k=5, alpha=0.8, filter=None))]
    pub fn query_text(
        &self,
        py: Python<'_>,
        index_name: String,
        query: String,
        top_k: usize,
        alpha: f32,
        filter: Option<Py<PyAny>>,
    ) -> PyResult<PySearchResult> {
        let parsed_filter = filter
            .map(|f| parse_metadata_filter(py, f.bind(py)))
            .transpose()?;
        let result = self
            .runtime
            .block_on(
                self.inner
                    .query_text(&index_name, &query, top_k, alpha, parsed_filter.as_ref()),
            )
            .map(|result| result.into())
            .map_err(|e| PyRuntimeError::new_err(format!("{}", e)))?;

        Ok(result)
    }

    pub fn load_query_model(&self, index_name: String) -> PyResult<()> {
        self.runtime
            .block_on(self.inner.load_query_model(&index_name))
            .map_err(|e| PyRuntimeError::new_err(format!("{}", e)))
    }

}
