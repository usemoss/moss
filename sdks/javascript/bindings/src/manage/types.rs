use napi_derive::napi;
use ::moss::manage::types as core_manage;

// ---------- Manage Types ----------

/// Job status for async cloud operations.
#[napi(string_enum, js_name = "JobStatus")]
#[derive(Debug, Clone)]
pub enum JsJobStatus {
    #[napi(value = "pending_upload")]
    PendingUpload,
    #[napi(value = "uploading")]
    Uploading,
    #[napi(value = "building")]
    Building,
    #[napi(value = "completed")]
    Completed,
    #[napi(value = "failed")]
    Failed,
}

impl From<core_manage::JobStatus> for JsJobStatus {
    fn from(s: core_manage::JobStatus) -> Self {
        match s {
            core_manage::JobStatus::PendingUpload => JsJobStatus::PendingUpload,
            core_manage::JobStatus::Uploading => JsJobStatus::Uploading,
            core_manage::JobStatus::Building => JsJobStatus::Building,
            core_manage::JobStatus::Completed => JsJobStatus::Completed,
            core_manage::JobStatus::Failed => JsJobStatus::Failed,
        }
    }
}

impl From<JsJobStatus> for core_manage::JobStatus {
    fn from(s: JsJobStatus) -> Self {
        match s {
            JsJobStatus::PendingUpload => core_manage::JobStatus::PendingUpload,
            JsJobStatus::Uploading => core_manage::JobStatus::Uploading,
            JsJobStatus::Building => core_manage::JobStatus::Building,
            JsJobStatus::Completed => core_manage::JobStatus::Completed,
            JsJobStatus::Failed => core_manage::JobStatus::Failed,
        }
    }
}

/// Job phase for async cloud operations.
#[napi(string_enum, js_name = "JobPhase")]
#[derive(Debug, Clone)]
pub enum JsJobPhase {
    #[napi(value = "downloading")]
    Downloading,
    #[napi(value = "deserializing")]
    Deserializing,
    #[napi(value = "generating_embeddings")]
    GeneratingEmbeddings,
    #[napi(value = "building_index")]
    BuildingIndex,
    #[napi(value = "uploading")]
    Uploading,
    #[napi(value = "cleanup")]
    Cleanup,
}

impl From<core_manage::JobPhase> for JsJobPhase {
    fn from(p: core_manage::JobPhase) -> Self {
        match p {
            core_manage::JobPhase::Downloading => JsJobPhase::Downloading,
            core_manage::JobPhase::Deserializing => JsJobPhase::Deserializing,
            core_manage::JobPhase::GeneratingEmbeddings => JsJobPhase::GeneratingEmbeddings,
            core_manage::JobPhase::BuildingIndex => JsJobPhase::BuildingIndex,
            core_manage::JobPhase::Uploading => JsJobPhase::Uploading,
            core_manage::JobPhase::Cleanup => JsJobPhase::Cleanup,
        }
    }
}

impl From<JsJobPhase> for core_manage::JobPhase {
    fn from(p: JsJobPhase) -> Self {
        match p {
            JsJobPhase::Downloading => core_manage::JobPhase::Downloading,
            JsJobPhase::Deserializing => core_manage::JobPhase::Deserializing,
            JsJobPhase::GeneratingEmbeddings => core_manage::JobPhase::GeneratingEmbeddings,
            JsJobPhase::BuildingIndex => core_manage::JobPhase::BuildingIndex,
            JsJobPhase::Uploading => core_manage::JobPhase::Uploading,
            JsJobPhase::Cleanup => core_manage::JobPhase::Cleanup,
        }
    }
}

/// Progress update for async cloud operations.
#[napi(object, js_name = "JobProgress")]
#[derive(Clone, Debug)]
pub struct JsJobProgress {
    pub job_id: String,
    pub status: JsJobStatus,
    pub progress: f64,
    pub current_phase: Option<JsJobPhase>,
}

impl From<core_manage::JobProgress> for JsJobProgress {
    fn from(p: core_manage::JobProgress) -> Self {
        Self {
            job_id: p.job_id,
            status: p.status.into(),
            progress: p.progress,
            current_phase: p.current_phase.map(Into::into),
        }
    }
}

/// Options for async mutation operations.
#[napi(object, js_name = "MutationOptions")]
#[derive(Clone, Debug)]
pub struct JsMutationOptions {
    pub upsert: Option<bool>,
}

impl From<core_manage::MutationOptions> for JsMutationOptions {
    fn from(o: core_manage::MutationOptions) -> Self {
        Self { upsert: o.upsert }
    }
}

impl From<JsMutationOptions> for core_manage::MutationOptions {
    fn from(o: JsMutationOptions) -> Self {
        Self { upsert: o.upsert }
    }
}

/// Completed result from an async mutation operation.
#[napi(object, js_name = "MutationResult")]
#[derive(Clone, Debug)]
pub struct JsMutationResult {
    pub job_id: String,
    pub index_name: String,
    pub doc_count: u32,
}

impl From<core_manage::MutationResult> for JsMutationResult {
    fn from(r: core_manage::MutationResult) -> Self {
        Self {
            job_id: r.job_id,
            index_name: r.index_name,
            doc_count: r.doc_count as u32,
        }
    }
}

/// Status payload for a long-running async job.
#[napi(object, js_name = "JobStatusResponse")]
#[derive(Clone, Debug)]
pub struct JsJobStatusResponse {
    pub job_id: String,
    pub status: JsJobStatus,
    pub progress: f64,
    pub current_phase: Option<JsJobPhase>,
    pub error: Option<String>,
    pub created_at: String,
    pub updated_at: String,
    pub completed_at: Option<String>,
}

impl From<core_manage::JobStatusResponse> for JsJobStatusResponse {
    fn from(r: core_manage::JobStatusResponse) -> Self {
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

// Re-export common types that manage needs from models
pub use crate::models::{JsDocumentInfo, JsGetDocumentsOptions, JsIndexInfo};
