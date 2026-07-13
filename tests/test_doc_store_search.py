"""Integration tests for DocStore hybrid search and listing against embedded SurrealDB."""

from __future__ import annotations

import tempfile

import pytest

from server.engine.doc_store import DocStore
from server.engine.store import ensure_store_schema

_CRC32 = b"\x00\x00\x00\x01"
_SHA256 = b"x" * 32


def _seed_document(store, path: str, content: str, embedding: list[float]) -> None:
    document = store.query(
        "CREATE doc SET "
        "id = rand::uuid(), path = $path, created_at = time::now(), "
        "modified_at = time::now(), access_count = 0, size_bytes = 5, "
        "crc32 = $crc32, sha256 = $sha256, embedding_model = 'test', chunk_count = 1",
        {"path": path, "crc32": _CRC32, "sha256": _SHA256},
    )[0]
    store.query(
        "CREATE chunk SET "
        "id = rand::uuid(), doc = $doc, `index` = 0, breadcrumb = $breadcrumb, "
        "content = $content, search_text = $search_text, embedding = $embedding",
        {
            "doc": document["id"],
            "breadcrumb": path.rsplit("/", 1)[-1],
            "content": content,
            "search_text": f"{path}\n{content}",
            "embedding": embedding,
        },
    )


@pytest.fixture
def seeded_doc_store(monkeypatch: pytest.MonkeyPatch) -> DocStore:
    temp_root = tempfile.mkdtemp()
    monkeypatch.setenv("GRIM_SURREAL_URL", f"surrealkv://{temp_root}/search-test")
    monkeypatch.setenv("GRIM_EMBEDDING_DIMENSIONS", "4")

    store = ensure_store_schema()
    _seed_document(store, "docs/foxes.md", "quick brown foxes jump high", [0.9, 0.1, 0.0, 0.0])
    _seed_document(store, "notes/oceans.md", "deep blue oceans and waves", [0.0, 0.0, 0.9, 0.1])
    doc_store = DocStore(store)
    try:
        yield doc_store
    finally:
        store.close()


def test_list_documents_orders_and_filters(seeded_doc_store: DocStore) -> None:
    documents, total = seeded_doc_store.list_documents(None, 50, 0)
    assert total == 2
    assert [document.path for document in documents] == ["docs/foxes.md", "notes/oceans.md"]

    filtered, filtered_total = seeded_doc_store.list_documents("notes", 50, 0)
    assert filtered_total == 1
    assert filtered[0].path == "notes/oceans.md"


def test_matching_doc_paths_filters_by_regex(seeded_doc_store: DocStore) -> None:
    assert seeded_doc_store.matching_doc_paths(r"^docs/") == ["docs/foxes.md"]
    assert seeded_doc_store.matching_doc_paths(r"\.md$") == ["docs/foxes.md", "notes/oceans.md"]
    assert seeded_doc_store.matching_doc_paths("missing") == []


def test_list_documents_paginates(seeded_doc_store: DocStore) -> None:
    first_page, total = seeded_doc_store.list_documents(None, 1, 0)
    second_page, _ = seeded_doc_store.list_documents(None, 1, 1)
    assert total == 2
    assert first_page[0].path == "docs/foxes.md"
    assert second_page[0].path == "notes/oceans.md"


def test_fulltext_search_matches_keyword(seeded_doc_store: DocStore) -> None:
    results = seeded_doc_store.search("foxes", [0.9, 0.1, 0.0, 0.0], 5)
    assert results
    assert results[0]["path"] == "docs/foxes.md"
    assert results[0]["filename"] == "foxes.md"


def test_vector_search_ranks_nearest_embedding(seeded_doc_store: DocStore) -> None:
    # Empty query text disables fulltext, isolating the HNSW vector ranking.
    results = seeded_doc_store.search("", [0.0, 0.0, 0.9, 0.1], 1)
    assert results
    assert results[0]["path"] == "notes/oceans.md"
