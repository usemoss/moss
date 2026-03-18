import math

import pytest

from moss_core import PyEmbeddingService


EMBEDDING_DIMENSION = 384


@pytest.fixture(scope="module")
def loaded_service() -> PyEmbeddingService:
    service = PyEmbeddingService("moss-minilm")
    result = service.load_model()
    assert result is None
    return service


@pytest.fixture(scope="module")
def loaded_service_without_normalization() -> PyEmbeddingService:
    service = PyEmbeddingService("moss-minilm", normalize=False)
    service.load_model()
    return service


def test_constructor_rejects_custom_model() -> None:
    with pytest.raises(RuntimeError, match="custom models are not supported"):
        PyEmbeddingService("custom")


def test_create_embedding_before_load_raises_runtime_error() -> None:
    service = PyEmbeddingService("moss-minilm")

    with pytest.raises(RuntimeError, match="not loaded"):
        service.create_embedding("hello world")


def test_is_loaded_transitions_after_load(loaded_service: PyEmbeddingService) -> None:
    assert loaded_service.is_loaded is True


def test_create_embedding_returns_384_floats(loaded_service: PyEmbeddingService) -> None:
    embedding = loaded_service.create_embedding("hello world")

    assert isinstance(embedding, list)
    assert len(embedding) == EMBEDDING_DIMENSION
    assert all(isinstance(value, float) for value in embedding)
    assert math.isclose(
        math.sqrt(sum(value * value for value in embedding)),
        1.0,
        rel_tol=1e-4,
        abs_tol=1e-4,
    )


def test_create_embeddings_returns_two_vectors(
    loaded_service: PyEmbeddingService,
) -> None:
    embeddings = loaded_service.create_embeddings(["a", "b"])

    assert isinstance(embeddings, list)
    assert len(embeddings) == 2
    assert all(len(embedding) == EMBEDDING_DIMENSION for embedding in embeddings)
    assert all(all(isinstance(value, float) for value in embedding) for embedding in embeddings)


def test_normalize_false_returns_non_unit_norm_embedding(
    loaded_service_without_normalization: PyEmbeddingService,
) -> None:
    embedding = loaded_service_without_normalization.create_embedding(
        "normalization should be optional"
    )
    norm = math.sqrt(sum(value * value for value in embedding))

    assert len(embedding) == EMBEDDING_DIMENSION
    assert not math.isclose(norm, 1.0, rel_tol=1e-4, abs_tol=1e-4)
