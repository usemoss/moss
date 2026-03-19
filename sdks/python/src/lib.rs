//! Python module initializer for the `moss` package.
//!
//! Exposes Python-facing data models and the `Index` class via pyo3.
mod embedding;
mod index;
mod indexmanager;
mod localindexmanager;
mod manage;
mod models;
mod sessionindex;
mod utils;

use pyo3::prelude::*;

use moss::constants;

use crate::embedding::PyEmbeddingService;
use crate::index::PyIndex;
use crate::indexmanager::PyIndexManager;
use crate::localindexmanager::PyLocalIndexManager;
use crate::manage::{register_manage_types, PyManageClient};
use crate::models::register_models;
use crate::sessionindex::{PyPushIndexResult, PySessionIndex};
use crate::utils::register_utils;

#[pymodule]
fn moss_core(py: Python<'_>, m: &Bound<PyModule>) -> PyResult<()> {
    register_models(py, m)?;
    register_utils(py, m)?;
    register_manage_types(py, m)?;

    m.add_class::<PyEmbeddingService>()?;
    m.add_class::<PyIndex>()?;
    m.add_class::<PyIndexManager>()?;
    m.add_class::<PyLocalIndexManager>()?;
    m.add_class::<PyManageClient>()?;
    m.add_class::<PySessionIndex>()?;
    m.add_class::<PyPushIndexResult>()?;

    m.add("MODEL_DOWNLOAD_URL", constants::MODEL_DOWNLOAD_URL)?;
    m.add("SDK_VERSION_NUMBER", constants::SDK_VERSION_NUMBER)?;
    m.add("CLOUD_API_MANAGE_URL", constants::CLOUD_API_MANAGE_URL)?;

    Ok(())
}
