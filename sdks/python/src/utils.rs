use pyo3::prelude::*;
use pyo3::types::PyBytes;

use crate::models::PySerializedIndex;
use moss::models::SerializedIndex;
use moss::utils::binary::{deserialize_from_binary, serialize_to_binary};

/// Serialize a SerializedIndex into binary (.moss file format).
#[pyfunction(name = "serializeToBinary")]
pub fn py_serialize_to_binary(
    py: Python<'_>,
    index: Bound<'_, PySerializedIndex>,
) -> PyResult<Py<PyBytes>> {
    // Convert PySerializedIndex -> core::SerializedIndex
    let py_index: PySerializedIndex = index.extract()?; // Bound -> owned py struct
    let core_index: SerializedIndex = py_index.into(); // uses your `impl From<PySerializedIndex>`

    let data: Vec<u8> = serialize_to_binary(&core_index);
    Ok(PyBytes::new(py, &data).into())
}

/// Deserialize a binary blob into a SerializedIndex (Python object).
#[pyfunction(name = "deserializeFromBinary")]
pub fn py_deserialize_from_binary(
    py: Python<'_>,
    blob: &Bound<PyAny>,
) -> PyResult<Py<PySerializedIndex>> {
    let data: &[u8] = blob.extract()?;

    let core_index: SerializedIndex = deserialize_from_binary(data)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    let py_index = PySerializedIndex::from(core_index); // uses your `impl From<core::SerializedIndex>`
    Py::new(py, py_index)
}

/// Register utils into the Python module.
pub fn register_utils(_py: Python<'_>, m: &Bound<PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(py_serialize_to_binary, m)?)?;
    m.add_function(wrap_pyfunction!(py_deserialize_from_binary, m)?)?;
    Ok(())
}
