"""Integration tests for DocStore write paths against embedded SurrealDB.

Guards the record-id binding: stored ids are `table:<uuid>` strings and must be
converted back to RecordID objects, since SurrealDB rejects bare strings where a
record link (`id TYPE uuid`, `doc TYPE record<doc>`) is expected.
"""

from __future__ import annotations

import tempfile
import uuid

import pytest

from server.engine.doc_store import DocStore
from server.engine.ingest.models import PreparedDocument
from server.engine.store import ensure_store_schema
from server.engine.store_models import StoredChunk, StoredDoc

_CRC32 = b"\x00\x00\x00\x01"
_SHA256 = b"x" * 32
_EMBEDDING = [0.1, 0.2, 0.3, 0.4]


def _prepared(path: str, contents: list[str], *, description: str | None = None) -> PreparedDocument:
    doc_id = f"doc:{uuid.uuid4()}"
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    document = StoredDoc(
        id=doc_id,
        path=path,
        created_at=now,
        modified_at=now,
        size_bytes=sum(len(chunk) for chunk in contents),
        crc32=_CRC32,
        sha256=_SHA256,
        embedding_model="test-model",
        chunk_count=len(contents),
        description=description,
    )
    chunks = [
        StoredChunk(
            id=f"chunk:{uuid.uuid4()}",
            doc=doc_id,
            chunk_index=index,
            breadcrumb=path.rsplit("/", 1)[-1],
            content=content,
            search_text=f"{path}\n{content}",
            embedding=_EMBEDDING,
        )
        for index, content in enumerate(contents)
    ]
    return PreparedDocument(doc=document, chunks=chunks)


@pytest.fixture
def doc_store(monkeypatch: pytest.MonkeyPatch) -> DocStore:
    temp_root = tempfile.mkdtemp()
    monkeypatch.setenv("GRIM_SURREAL_URL", f"surrealkv://{temp_root}/crud-test")
    monkeypatch.setenv("GRIM_EMBEDDING_DIMENSIONS", "4")
    store = ensure_store_schema()
    try:
        yield DocStore(store)
    finally:
        store.close()


def test_upsert_creates_then_updates_same_path(doc_store: DocStore) -> None:
    created = doc_store.upsert_prepared(_prepared("docs/a.md", ["# One\n", "Two\n"]))
    assert created.chunk_count == 2
    assert doc_store.get_markdown_content("docs/a.md") == "# One\nTwo\n"

    updated = doc_store.upsert_prepared(_prepared("docs/a.md", ["# Rewritten\n"]))
    assert updated.chunk_count == 1
    assert updated.id == created.id
    assert doc_store.get_markdown_content("docs/a.md") == "# Rewritten\n"

    stats = doc_store.count_stats()
    assert stats["documents"] == 1
    assert stats["chunks"] == 1


def test_upsert_preserves_description_on_reindex(doc_store: DocStore) -> None:
    doc_store.upsert_prepared(_prepared("docs/b.md", ["body\n"], description="keep me"))
    doc_store.upsert_prepared(_prepared("docs/b.md", ["new body\n"], description=None))
    document = doc_store.get_doc_by_path("docs/b.md")
    assert document is not None
    assert document.description == "keep me"


def test_replace_chunks_updates_content(doc_store: DocStore) -> None:
    created = doc_store.upsert_prepared(_prepared("docs/c.md", ["old\n"]))
    replacement = _prepared("docs/c.md", ["fresh one\n", "fresh two\n"]).chunks
    updated = doc_store.replace_chunks(created.id, replacement)
    assert updated is not None
    assert updated.chunk_count == 2
    assert doc_store.get_markdown_content("docs/c.md") == "fresh one\nfresh two\n"


def test_rename_path_moves_document(doc_store: DocStore) -> None:
    doc_store.upsert_prepared(_prepared("docs/old.md", ["x\n"]))
    renamed = doc_store.rename_path("docs/old.md", "docs/new.md")
    assert renamed is not None
    assert renamed.path == "docs/new.md"
    assert doc_store.get_doc_by_path("docs/old.md") is None
    assert doc_store.get_doc_by_path("docs/new.md") is not None


def test_remove_deletes_document_and_chunks(doc_store: DocStore) -> None:
    doc_store.upsert_prepared(_prepared("docs/d.md", ["gone\n"]))
    assert doc_store.remove_by_path("docs/d.md") is True
    assert doc_store.get_doc_by_path("docs/d.md") is None
    assert doc_store.count_stats()["chunks"] == 0


def test_mark_failed_then_reindex_recovers(doc_store: DocStore) -> None:
    failed = doc_store.mark_failed(
        "docs/e.md",
        size_bytes=5,
        crc32=_CRC32,
        sha256=_SHA256,
        embedding_model="test-model",
    )
    assert failed.chunk_count is None
    assert doc_store.failed_doc_paths() == ["docs/e.md"]

    doc_store.mark_failed(
        "docs/e.md",
        size_bytes=6,
        crc32=_CRC32,
        sha256=_SHA256,
        embedding_model="test-model",
    )
    recovered = doc_store.upsert_prepared(_prepared("docs/e.md", ["recovered\n"]))
    assert recovered.chunk_count == 1
    assert doc_store.failed_doc_paths() == []
