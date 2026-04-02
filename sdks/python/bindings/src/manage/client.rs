use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;

use moss::cloud::CloudError;
use moss::manage::client::ManageClient;
use moss::manage::types::MutationOptions;
use moss::models::GetDocumentsOptions;

use super::types::{PyJobStatusResponse, PyMutationOptions, PyMutationResult};
use crate::models::{PyDocumentInfo, PyGetDocumentsOptions, PyIndexInfo};

fn to_py_err(e: CloudError) -> PyErr {
    PyRuntimeError::new_err(e.to_string())
}

#[pyclass(name = "ManageClient")]
pub struct PyManageClient {
    inner: ManageClient,
    runtime: tokio::runtime::Runtime,
}

#[pymethods]
impl PyManageClient {
    #[new]
    #[pyo3(signature = (project_id, project_key, base_url=None, client_id=None))]
    fn new(project_id: String, project_key: String, base_url: Option<String>, client_id: Option<String>) -> PyResult<Self> {
        let runtime = tokio::runtime::Runtime::new()
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to create runtime: {}", e)))?;

        let inner = match base_url {
            Some(url) => ManageClient::with_base_url(project_id, project_key, url, client_id),
            None => ManageClient::new(project_id, project_key, client_id),
        };

        Ok(Self { inner, runtime })
    }

    #[pyo3(signature = (name, docs, model_id))]
    fn create_index(
        &self,
        name: String,
        docs: Vec<PyDocumentInfo>,
        model_id: String,
    ) -> PyResult<PyMutationResult> {
        let core_docs: Vec<_> = docs.into_iter().map(Into::into).collect();
        self.runtime
            .block_on(
                self.inner
                    .create_index(&name, &core_docs, &model_id, None::<fn(_)>),
            )
            .map(PyMutationResult::from)
            .map_err(to_py_err)
    }

    #[pyo3(signature = (name, docs, options=None))]
    fn add_docs(
        &self,
        name: String,
        docs: Vec<PyDocumentInfo>,
        options: Option<PyMutationOptions>,
    ) -> PyResult<PyMutationResult> {
        let core_docs: Vec<_> = docs.into_iter().map(Into::into).collect();
        let core_opts = options.map(MutationOptions::from);
        self.runtime
            .block_on(
                self.inner
                    .add_docs(&name, &core_docs, core_opts, None::<fn(_)>),
            )
            .map(PyMutationResult::from)
            .map_err(to_py_err)
    }

    fn delete_docs(&self, name: String, doc_ids: Vec<String>) -> PyResult<PyMutationResult> {
        self.runtime
            .block_on(self.inner.delete_docs(&name, &doc_ids, None::<fn(_)>))
            .map(PyMutationResult::from)
            .map_err(to_py_err)
    }

    fn get_job_status(&self, job_id: String) -> PyResult<PyJobStatusResponse> {
        self.runtime
            .block_on(self.inner.get_job_status(&job_id))
            .map(PyJobStatusResponse::from)
            .map_err(to_py_err)
    }

    fn get_index(&self, name: String) -> PyResult<PyIndexInfo> {
        self.runtime
            .block_on(self.inner.get_index(&name))
            .map(PyIndexInfo::from)
            .map_err(to_py_err)
    }

    fn list_indexes(&self) -> PyResult<Vec<PyIndexInfo>> {
        self.runtime
            .block_on(self.inner.list_indexes())
            .map(|v| v.into_iter().map(PyIndexInfo::from).collect())
            .map_err(to_py_err)
    }

    fn delete_index(&self, name: String) -> PyResult<bool> {
        self.runtime
            .block_on(self.inner.delete_index(&name))
            .map_err(to_py_err)
    }

    #[pyo3(signature = (name, options=None))]
    fn get_docs(
        &self,
        name: String,
        options: Option<PyGetDocumentsOptions>,
    ) -> PyResult<Vec<PyDocumentInfo>> {
        let core_opts = options.map(GetDocumentsOptions::from);
        self.runtime
            .block_on(self.inner.get_docs(&name, core_opts))
            .map(|v| v.into_iter().map(PyDocumentInfo::from).collect())
            .map_err(to_py_err)
    }
}
