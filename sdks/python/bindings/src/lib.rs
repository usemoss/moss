//! Python module initializer for the `moss_core` package.
//!
//! Exposes the IndexManager, ManageClient, and data models used by the
//! `moss` Python SDK.
mod indexmanager;
mod manage;
mod models;

use pyo3::prelude::*;

use moss::constants;

use crate::indexmanager::PyIndexManager;
use crate::manage::{register_manage_types, PyManageClient};
use crate::models::register_models;

#[pymodule]
fn moss_core(py: Python<'_>, m: &Bound<PyModule>) -> PyResult<()> {
    register_models(py, m)?;
    register_manage_types(py, m)?;

    m.add_class::<PyIndexManager>()?;
    m.add_class::<PyManageClient>()?;

    m.add("CLOUD_API_MANAGE_URL", constants::CLOUD_API_MANAGE_URL)?;

    Ok(())
}
