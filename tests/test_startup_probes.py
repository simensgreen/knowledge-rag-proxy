"""Tests for startup embedding probes and stored-dimension verification."""

from __future__ import annotations

import tempfile
import uuid

import pytest

from server.engine.doc_store import DocStore
from server.engine.store import ensure_store_schema
from server.startup import probe_embedding_provider, verify_stored_embedding_dimensions

_EMBEDDING = [0.1, 0.2, 0.3, 0.4]


class _Embedder:
    def __init__(self, dimension: int = 4, error: Exception | None = None) -> None:
        self._dimension = dimension
        self._error = error

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._error is not None:
            raise self._error
        return [[0.0] * self._dimension for _ in texts]


@pytest.fixture(autouse=True)
def _expected_dimensions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRIM_EMBEDDING_DIMENSIONS", "4")


def test_probe_embedding_provider_accepts_matching_dimension() -> None:
    probe_embedding_provider(_Embedder(dimension=4))


def test_probe_embedding_provider_rejects_wrong_dimension() -> None:
    with pytest.raises(RuntimeError, match="Embedding size mismatch"):
        probe_embedding_provider(_Embedder(dimension=8))


def test_probe_embedding_provider_fails_when_unreachable() -> None:
    with pytest.raises(RuntimeError, match="not reachable"):
        probe_embedding_provider(_Embedder(error=ConnectionError("refused")))


def _doc_store_with_embedding(monkeypatch: pytest.MonkeyPatch) -> DocStore:
    temp_root = tempfile.mkdtemp()
    monkeypatch.setenv("GRIM_SURREAL_URL", f"surrealkv://{temp_root}/probe-test")
    store = ensure_store_schema()
    doc_store = DocStore(store)
    from surrealdb.data.types.record_id import RecordID

    doc_id = RecordID("doc", uuid.uuid4())
    store.query(
        "CREATE $doc_id SET path='a.md', created_at=time::now(), modified_at=time::now(), "
        "access_count=0, size_bytes=1, crc32=<bytes>'', sha256=<bytes>'', embedding_model='m', "
        "chunk_count=1",
        {"doc_id": doc_id},
    )
    store.query(
        "CREATE $chunk_id SET doc=$doc_id, `index`=0, breadcrumb='b', content='c', "
        "search_text='s', embedding=$embedding",
        {"chunk_id": RecordID("chunk", uuid.uuid4()), "doc_id": doc_id, "embedding": _EMBEDDING},
    )
    return doc_store


def test_verify_stored_dimensions_passes_on_match(monkeypatch: pytest.MonkeyPatch) -> None:
    doc_store = _doc_store_with_embedding(monkeypatch)
    try:
        verify_stored_embedding_dimensions(doc_store)
    finally:
        doc_store.store.close()


def test_verify_stored_dimensions_fails_on_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    doc_store = _doc_store_with_embedding(monkeypatch)
    monkeypatch.setenv("GRIM_EMBEDDING_DIMENSIONS", "8")
    try:
        with pytest.raises(RuntimeError, match="Stored embeddings have dimensions"):
            verify_stored_embedding_dimensions(doc_store)
    finally:
        doc_store.store.close()


def test_verify_stored_dimensions_noop_on_empty_store(monkeypatch: pytest.MonkeyPatch) -> None:
    temp_root = tempfile.mkdtemp()
    monkeypatch.setenv("GRIM_SURREAL_URL", f"surrealkv://{temp_root}/empty-test")
    store = ensure_store_schema()
    doc_store = DocStore(store)
    try:
        verify_stored_embedding_dimensions(doc_store)
        assert doc_store.embedding_dimensions_in_use() == []
    finally:
        store.close()
