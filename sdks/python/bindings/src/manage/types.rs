use pyo3::prelude::*;

use moss::manage::types as core;

#[pyclass(name = "JobStatus")]
#[derive(Clone, Debug)]
pub struct PyJobStatus {
    #[pyo3(get)]
    pub value: String,
}

#[pymethods]
impl PyJobStatus {
    #[classattr]
    const PENDING_UPLOAD: &'static str = "pending_upload";
    #[classattr]
    const UPLOADING: &'static str = "uploading";
    #[classattr]
    const BUILDING: &'static str = "building";
    #[classattr]
    const COMPLETED: &'static str = "completed";
    #[classattr]
    const FAILED: &'static str = "failed";
}

impl From<core::JobStatus> for PyJobStatus {
    fn from(s: core::JobStatus) -> Self {
        let value = match s {
            core::JobStatus::PendingUpload => "pending_upload",
            core::JobStatus::Uploading => "uploading",
            core::JobStatus::Building => "building",
            core::JobStatus::Completed => "completed",
            core::JobStatus::Failed => "failed",
        };
        Self {
            value: value.into(),
        }
    }
}

#[pyclass(name = "JobPhase")]
#[derive(Clone, Debug)]
pub struct PyJobPhase {
    #[pyo3(get)]
    pub value: String,
}

#[pymethods]
impl PyJobPhase {
    #[classattr]
    const DOWNLOADING: &'static str = "downloading";
    #[classattr]
    const DESERIALIZING: &'static str = "deserializing";
    #[classattr]
    const GENERATING_EMBEDDINGS: &'static str = "generating_embeddings";
    #[classattr]
    const BUILDING_INDEX: &'static str = "building_index";
    #[classattr]
    const UPLOADING: &'static str = "uploading";
    #[classattr]
    const CLEANUP: &'static str = "cleanup";
}

impl From<core::JobPhase> for PyJobPhase {
    fn from(p: core::JobPhase) -> Self {
        let value = match p {
            core::JobPhase::Downloading => "downloading",
            core::JobPhase::Deserializing => "deserializing",
            core::JobPhase::GeneratingEmbeddings => "generating_embeddings",
            core::JobPhase::BuildingIndex => "building_index",
            core::JobPhase::Uploading => "uploading",
            core::JobPhase::Cleanup => "cleanup",
        };
        Self {
            value: value.into(),
        }
    }
}

#[pyclass(name = "JobProgress")]
#[derive(Clone, Debug)]
pub struct PyJobProgress {
    #[pyo3(get)]
    pub job_id: String,
    #[pyo3(get)]
    pub status: PyJobStatus,
    #[pyo3(get)]
    pub progress: f64,
    #[pyo3(get)]
    pub current_phase: Option<PyJobPhase>,
}

impl From<core::JobProgress> for PyJobProgress {
    fn from(p: core::JobProgress) -> Self {
        Self {
            job_id: p.job_id,
            status: p.status.into(),
            progress: p.progress,
            current_phase: p.current_phase.map(Into::into),
        }
    }
}

#[pyclass(name = "MutationResult")]
#[derive(Clone, Debug)]
pub struct PyMutationResult {
    #[pyo3(get)]
    pub job_id: String,
    #[pyo3(get)]
    pub index_name: String,
    #[pyo3(get)]
    pub doc_count: usize,
}

impl From<core::MutationResult> for PyMutationResult {
    fn from(r: core::MutationResult) -> Self {
        Self {
            job_id: r.job_id,
            index_name: r.index_name,
            doc_count: r.doc_count,
        }
    }
}

#[pyclass(name = "MutationOptions")]
#[derive(Clone, Debug)]
pub struct PyMutationOptions {
    #[pyo3(get, set)]
    pub upsert: Option<bool>,
}

#[pymethods]
impl PyMutationOptions {
    #[new]
    #[pyo3(signature = (upsert=None))]
    fn new(upsert: Option<bool>) -> Self {
        Self { upsert }
    }
}

impl From<PyMutationOptions> for core::MutationOptions {
    fn from(p: PyMutationOptions) -> Self {
        Self { upsert: p.upsert }
    }
}

#[pyclass(name = "JobStatusResponse")]
#[derive(Clone, Debug)]
pub struct PyJobStatusResponse {
    #[pyo3(get)]
    pub job_id: String,
    #[pyo3(get)]
    pub status: PyJobStatus,
    #[pyo3(get)]
    pub progress: f64,
    #[pyo3(get)]
    pub current_phase: Option<PyJobPhase>,
    #[pyo3(get)]
    pub error: Option<String>,
    #[pyo3(get)]
    pub created_at: String,
    #[pyo3(get)]
    pub updated_at: String,
    #[pyo3(get)]
    pub completed_at: Option<String>,
}

impl From<core::JobStatusResponse> for PyJobStatusResponse {
    fn from(r: core::JobStatusResponse) -> Self {
        Self {
            job_id: r.job_id,
            status: r.status.into(),
            progress: r.progress,
            current_phase: r.current_phase.map(Into::into),
            error: r.error,
            created_at: r.created_at,
            updated_at: r.updated_at,
            completed_at: r.completed_at,
        }
    }
}

pub fn register_manage_types(_py: Python<'_>, m: &Bound<PyModule>) -> PyResult<()> {
    m.add_class::<PyJobStatus>()?;
    m.add_class::<PyJobPhase>()?;
    m.add_class::<PyJobProgress>()?;
    m.add_class::<PyMutationResult>()?;
    m.add_class::<PyMutationOptions>()?;
    m.add_class::<PyJobStatusResponse>()?;
    Ok(())
}
