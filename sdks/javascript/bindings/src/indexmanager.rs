use napi::bindgen_prelude::*;
use napi_derive::napi;

use ::moss::manager::IndexManager as CoreIndexManager;

use crate::models::{parse_metadata_filter, JsIndexInfo, JsLoadIndexOptions, JsRefreshResult, JsSearchResult};

#[napi(js_name = "IndexManager")]
/// Rust-backed local index manager with optional auto-refresh polling.
pub struct JsIndexManager {
    inner: CoreIndexManager,
    _runtime: tokio::runtime::Runtime,
}

#[napi]
impl JsIndexManager {
    #[napi(constructor, ts_args_type = "projectId: string, projectKey: string, baseUrl?: string | null")]
    pub fn new(project_id: String, project_key: String, base_url: Option<String>) -> Result<Self> {
        let runtime = tokio::runtime::Runtime::new()
            .map_err(|e| Error::new(Status::GenericFailure, format!("Failed to create Tokio runtime: {}", e)))?;
        let handle = runtime.handle().clone();
        let inner = match base_url {
            Some(url) => CoreIndexManager::with_base_url(project_id, project_key, url, handle, None),
            None => CoreIndexManager::new(project_id, project_key, handle, None),
        };
        Ok(Self { inner, _runtime: runtime })
    }

    #[napi(
        js_name = "loadIndex",
        ts_args_type = "indexName: string, options?: LoadIndexOptions | null",
        ts_return_type = "Promise<IndexInfo>"
    )]
    pub async fn load_index(
        &self,
        index_name: String,
        options: Option<JsLoadIndexOptions>,
    ) -> Result<JsIndexInfo> {
        let core_options = options.map(|opts| opts.into());
        let result = self
            .inner
            .load_index(&index_name, core_options)
            .await
            .map_err(|e| Error::new(Status::GenericFailure, e.to_string()))?;
        Ok(result.into())
    }

    #[napi(js_name = "unloadIndex", ts_return_type = "Promise<void>")]
    pub async fn unload_index(&self, index_name: String) -> Result<()> {
        self.inner
            .unload_index(&index_name)
            .await
            .map_err(|e| Error::new(Status::GenericFailure, e.to_string()))
    }

    #[napi(js_name = "hasIndex", ts_return_type = "Promise<boolean>")]
    pub async fn has_index(&self, index_name: String) -> Result<bool> {
        Ok(self.inner.has_index(&index_name).await)
    }

    #[napi(
        js_name = "query",
        ts_args_type = "indexName: string, query: string, queryEmbedding: Array<number>, topK?: number, alpha?: number, filter?: object",
        ts_return_type = "Promise<SearchResult>"
    )]
    pub async fn query(
        &self,
        index_name: String,
        query: String,
        query_embedding: Vec<f64>,
        top_k: Option<u32>,
        alpha: Option<f64>,
        filter: Option<serde_json::Value>,
    ) -> Result<JsSearchResult> {
        let query_embedding_f32: Vec<f32> = query_embedding.into_iter().map(|x| x as f32).collect();
        let top_k_val = top_k.unwrap_or(5) as usize;
        let alpha_val = alpha.unwrap_or(0.8) as f32;
        let parsed_filter = filter.as_ref().map(parse_metadata_filter).transpose()?;
        let result = self
            .inner
            .query(&index_name, &query, &query_embedding_f32, top_k_val, alpha_val, parsed_filter.as_ref())
            .await
            .map_err(|e| Error::new(Status::GenericFailure, e.to_string()))?;
        Ok(result.into())
    }

    #[napi(
        js_name = "queryText",
        ts_args_type = "indexName: string, query: string, topK?: number, alpha?: number, filter?: object",
        ts_return_type = "Promise<SearchResult>"
    )]
    pub async fn query_text(
        &self,
        index_name: String,
        query: String,
        top_k: Option<u32>,
        alpha: Option<f64>,
        filter: Option<serde_json::Value>,
    ) -> Result<JsSearchResult> {
        let top_k_val = top_k.unwrap_or(5) as usize;
        let alpha_val = alpha.unwrap_or(0.8) as f32;
        let parsed_filter = filter.as_ref().map(parse_metadata_filter).transpose()?;
        let result = self
            .inner
            .query_text(&index_name, &query, top_k_val, alpha_val, parsed_filter.as_ref())
            .await
            .map_err(|e| Error::new(Status::GenericFailure, e.to_string()))?;
        Ok(result.into())
    }

    #[napi(js_name = "loadQueryModel", ts_return_type = "Promise<void>")]
    pub async fn load_query_model(&self, index_name: String) -> Result<()> {
        self.inner
            .load_query_model(&index_name)
            .await
            .map_err(|e| Error::new(Status::GenericFailure, e.to_string()))
    }

    #[napi(js_name = "refreshIndex", ts_return_type = "Promise<RefreshResult>")]
    pub async fn refresh_index(&self, index_name: String) -> Result<JsRefreshResult> {
        let result = self
            .inner
            .refresh_index(&index_name)
            .await
            .map_err(|e| Error::new(Status::GenericFailure, e.to_string()))?;
        Ok(result.into())
    }

    #[napi(js_name = "getIndexInfo", ts_return_type = "Promise<IndexInfo>")]
    pub async fn get_index_info(&self, index_name: String) -> Result<JsIndexInfo> {
        let result = self
            .inner
            .get_index_info(&index_name)
            .await
            .map_err(|e| Error::new(Status::GenericFailure, e.to_string()))?;
        Ok(result.into())
    }
}
