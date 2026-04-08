//! Rustler NIF bindings for ManageClient.
//!
//! Mirrors bindings/python/src/manage/client.rs with Rustler idioms.

use rustler::ResourceArc;

use moss::manage::client::ManageClient;
use moss::manage::types::MutationOptions;
use moss::models::GetDocumentsOptions;

use crate::models::{
    ManageResource, NifCredentialsInfo, NifDocumentInfo, NifIndexInfo,
    NifJobStatusResponse, NifMutationResult,
};
use crate::RUNTIME;

rustler::atoms! { ok }

#[rustler::nif]
pub fn manage_new(
    project_id: String,
    project_key: String,
    base_url: Option<String>,
    client_id: Option<String>,
) -> Result<ResourceArc<ManageResource>, String> {
    let inner = match base_url {
        Some(url) => ManageClient::with_base_url(project_id, project_key, url, client_id),
        None => ManageClient::new(project_id, project_key, client_id),
    };
    Ok(ResourceArc::new(ManageResource {
        inner: std::sync::Mutex::new(inner),
    }))
}

#[rustler::nif(schedule = "DirtyIo")]
pub fn manage_create_index(
    resource: ResourceArc<ManageResource>,
    name: String,
    docs: Vec<NifDocumentInfo>,
    model_id: String,
) -> Result<NifMutationResult, String> {
    let core_docs: Vec<_> = docs.into_iter().map(Into::into).collect();
    RUNTIME
        .block_on(
            resource
                .inner
                .lock()
                .unwrap()
                .create_index(&name, &core_docs, &model_id, None::<fn(_)>),
        )
        .map(NifMutationResult::from)
        .map_err(|e| e.to_string())
}

#[rustler::nif(schedule = "DirtyIo")]
pub fn manage_add_docs(
    resource: ResourceArc<ManageResource>,
    name: String,
    docs: Vec<NifDocumentInfo>,
    upsert: Option<bool>,
) -> Result<NifMutationResult, String> {
    let core_docs: Vec<_> = docs.into_iter().map(Into::into).collect();
    let core_opts = upsert.map(|u| MutationOptions { upsert: Some(u) });
    RUNTIME
        .block_on(
            resource
                .inner
                .lock()
                .unwrap()
                .add_docs(&name, &core_docs, core_opts, None::<fn(_)>),
        )
        .map(NifMutationResult::from)
        .map_err(|e| e.to_string())
}

#[rustler::nif(schedule = "DirtyIo")]
pub fn manage_delete_docs(
    resource: ResourceArc<ManageResource>,
    name: String,
    doc_ids: Vec<String>,
) -> Result<NifMutationResult, String> {
    RUNTIME
        .block_on(
            resource
                .inner
                .lock()
                .unwrap()
                .delete_docs(&name, &doc_ids, None::<fn(_)>),
        )
        .map(NifMutationResult::from)
        .map_err(|e| e.to_string())
}

#[rustler::nif(schedule = "DirtyIo")]
pub fn manage_get_job_status(
    resource: ResourceArc<ManageResource>,
    job_id: String,
) -> Result<NifJobStatusResponse, String> {
    RUNTIME
        .block_on(resource.inner.lock().unwrap().get_job_status(&job_id))
        .map(NifJobStatusResponse::from)
        .map_err(|e| e.to_string())
}

#[rustler::nif(schedule = "DirtyIo")]
pub fn manage_get_index(
    resource: ResourceArc<ManageResource>,
    name: String,
) -> Result<NifIndexInfo, String> {
    RUNTIME
        .block_on(resource.inner.lock().unwrap().get_index(&name))
        .map(NifIndexInfo::from)
        .map_err(|e| e.to_string())
}

#[rustler::nif(schedule = "DirtyIo")]
pub fn manage_list_indexes(
    resource: ResourceArc<ManageResource>,
) -> Result<Vec<NifIndexInfo>, String> {
    RUNTIME
        .block_on(resource.inner.lock().unwrap().list_indexes())
        .map(|v| v.into_iter().map(NifIndexInfo::from).collect())
        .map_err(|e| e.to_string())
}

#[rustler::nif(schedule = "DirtyIo")]
pub fn manage_delete_index(
    resource: ResourceArc<ManageResource>,
    name: String,
) -> Result<bool, String> {
    RUNTIME
        .block_on(resource.inner.lock().unwrap().delete_index(&name))
        .map_err(|e| e.to_string())
}

#[rustler::nif(schedule = "DirtyIo")]
pub fn manage_get_docs(
    resource: ResourceArc<ManageResource>,
    name: String,
    doc_ids: Option<Vec<String>>,
) -> Result<Vec<NifDocumentInfo>, String> {
    let opts = doc_ids.map(|ids| GetDocumentsOptions { doc_ids: Some(ids) });
    RUNTIME
        .block_on(resource.inner.lock().unwrap().get_docs(&name, opts))
        .map(|v| v.into_iter().map(NifDocumentInfo::from).collect())
        .map_err(|e| e.to_string())
}

#[rustler::nif(schedule = "DirtyIo")]
pub fn manage_validate_credentials(
    resource: ResourceArc<ManageResource>,
) -> Result<NifCredentialsInfo, String> {
    let resp = RUNTIME
        .block_on(resource.inner.lock().unwrap().validate_credentials())
        .map_err(|e| e.to_string())?;

    if !resp.valid {
        return Err(
            "Invalid project credentials: project key does not match the project".to_string(),
        );
    }
    Ok(NifCredentialsInfo::from(resp))
}
