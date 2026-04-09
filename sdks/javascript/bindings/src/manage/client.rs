use napi::bindgen_prelude::*;
use napi::threadsafe_function::{ThreadsafeFunction, ThreadsafeFunctionCallMode};
use napi_derive::napi;

use ::moss::manage::client::ManageClient as CoreManageClient;
use ::moss::manage::types as core_manage;
use ::moss::models as core_models;

use crate::manage::types::{
    JsDocumentInfo, JsGetDocumentsOptions, JsIndexInfo, JsJobProgress, JsJobStatusResponse,
    JsMutationOptions, JsMutationResult,
};

#[napi(js_name = "ManageClient")]
/// Rust-backed cloud orchestration client for index mutations and metadata operations.
pub struct JsManageClient {
    inner: CoreManageClient,
}

#[napi]
impl JsManageClient {
    #[napi(constructor, ts_args_type = "projectId: string, projectKey: string, baseUrl?: string | null")]
    pub fn new(project_id: String, project_key: String, base_url: Option<String>) -> Self {
        let inner = match base_url {
            Some(url) => CoreManageClient::with_base_url(project_id, project_key, url, None),
            None => CoreManageClient::new(project_id, project_key, None),
        };
        Self { inner }
    }

    #[napi(ts_args_type = "name: string, docs: Array<DocumentInfo>, modelId: string, onProgress?: (progress: JobProgress) => void", ts_return_type = "Promise<MutationResult>")]
    pub async fn create_index(
        &self,
        name: String,
        docs: Vec<JsDocumentInfo>,
        model_id: String,
        on_progress: Option<ThreadsafeFunction<JsJobProgress>>,
    ) -> Result<JsMutationResult> {
        let core_docs: Vec<core_models::DocumentInfo> = docs.into_iter().map(Into::into).collect();
        let callback = on_progress.map(|tsfn| {
            move |p: core_manage::JobProgress| {
                tsfn.call(Ok(JsJobProgress::from(p)), ThreadsafeFunctionCallMode::NonBlocking);
            }
        });
        let result = self
            .inner
            .create_index(&name, &core_docs, &model_id, callback)
            .await
            .map_err(|e| Error::new(Status::GenericFailure, e.to_string()))?;
        Ok(result.into())
    }

    #[napi(ts_args_type = "name: string, docs: Array<DocumentInfo>, options?: MutationOptions | null, onProgress?: (progress: JobProgress) => void", ts_return_type = "Promise<MutationResult>")]
    pub async fn add_docs(
        &self,
        name: String,
        docs: Vec<JsDocumentInfo>,
        options: Option<JsMutationOptions>,
        on_progress: Option<ThreadsafeFunction<JsJobProgress>>,
    ) -> Result<JsMutationResult> {
        let core_docs: Vec<core_models::DocumentInfo> = docs.into_iter().map(Into::into).collect();
        let core_opts = options.map(Into::into);
        let callback = on_progress.map(|tsfn| {
            move |p: core_manage::JobProgress| {
                tsfn.call(Ok(JsJobProgress::from(p)), ThreadsafeFunctionCallMode::NonBlocking);
            }
        });
        let result = self
            .inner
            .add_docs(&name, &core_docs, core_opts, callback)
            .await
            .map_err(|e| Error::new(Status::GenericFailure, e.to_string()))?;
        Ok(result.into())
    }

    #[napi(ts_args_type = "name: string, docIds: Array<string>, onProgress?: (progress: JobProgress) => void", ts_return_type = "Promise<MutationResult>")]
    pub async fn delete_docs(
        &self,
        name: String,
        doc_ids: Vec<String>,
        on_progress: Option<ThreadsafeFunction<JsJobProgress>>,
    ) -> Result<JsMutationResult> {
        let callback = on_progress.map(|tsfn| {
            move |p: core_manage::JobProgress| {
                tsfn.call(Ok(JsJobProgress::from(p)), ThreadsafeFunctionCallMode::NonBlocking);
            }
        });
        let result = self
            .inner
            .delete_docs(&name, &doc_ids, callback)
            .await
            .map_err(|e| Error::new(Status::GenericFailure, e.to_string()))?;
        Ok(result.into())
    }

    #[napi(ts_return_type = "Promise<JobStatusResponse>")]
    pub async fn get_job_status(&self, job_id: String) -> Result<JsJobStatusResponse> {
        let result = self
            .inner
            .get_job_status(&job_id)
            .await
            .map_err(|e| Error::new(Status::GenericFailure, e.to_string()))?;
        Ok(result.into())
    }

    #[napi(ts_return_type = "Promise<IndexInfo>")]
    pub async fn get_index(&self, name: String) -> Result<JsIndexInfo> {
        let result = self
            .inner
            .get_index(&name)
            .await
            .map_err(|e| Error::new(Status::GenericFailure, e.to_string()))?;
        Ok(result.into())
    }

    #[napi(ts_return_type = "Promise<Array<IndexInfo>>")]
    pub async fn list_indexes(&self) -> Result<Vec<JsIndexInfo>> {
        let result = self
            .inner
            .list_indexes()
            .await
            .map_err(|e| Error::new(Status::GenericFailure, e.to_string()))?;
        Ok(result.into_iter().map(Into::into).collect())
    }

    #[napi(ts_return_type = "Promise<boolean>")]
    pub async fn delete_index(&self, name: String) -> Result<bool> {
        self.inner
            .delete_index(&name)
            .await
            .map_err(|e| Error::new(Status::GenericFailure, e.to_string()))
    }

    #[napi(ts_args_type = "name: string, options?: GetDocumentsOptions | null", ts_return_type = "Promise<Array<DocumentInfo>>")]
    pub async fn get_docs(
        &self,
        name: String,
        options: Option<JsGetDocumentsOptions>,
    ) -> Result<Vec<JsDocumentInfo>> {
        let core_opts = options.map(Into::into);
        let result = self
            .inner
            .get_docs(&name, core_opts)
            .await
            .map_err(|e| Error::new(Status::GenericFailure, e.to_string()))?;
        Ok(result.into_iter().map(Into::into).collect())
    }
}
