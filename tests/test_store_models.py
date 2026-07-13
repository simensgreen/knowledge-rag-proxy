"""Pydantic model tests for SurrealDB records."""

from __future__ import annotations

from datetime import datetime, timezone

from surrealdb.data.types.record_id import RecordID

from server.engine.store_models import StoredChunk, StoredDoc


def test_stored_doc_from_surreal_row() -> None:
    now = datetime.now(timezone.utc)
    row = {
        "id": RecordID("doc", "11111111-1111-1111-1111-111111111111"),
        "path": "notes/a.md",
        "created_at": now,
        "modified_at": now,
        "accessed_at": None,
        "access_count": 0,
        "size_bytes": 12,
        "crc32": b"\x00\x00\x00\x01",
        "sha256": b"x" * 32,
        "embedding_model": "text-embedding-3-small",
        "chunk_count": 3,
        "description": "A note",
    }

    document = StoredDoc.model_validate(row)
    assert document.id == str(RecordID("doc", "11111111-1111-1111-1111-111111111111"))
    assert document.path == "notes/a.md"
    assert document.chunk_count == 3
    assert document.description == "A note"


def test_stored_chunk_maps_index_field() -> None:
    row = {
        "id": RecordID("chunk", "22222222-2222-2222-2222-222222222222"),
        "doc": RecordID("doc", "11111111-1111-1111-1111-111111111111"),
        "index": 0,
        "breadcrumb": "note.md",
        "prefix": "intro",
        "suffix": None,
        "content": "hello",
        "search_text": "note.md\nintrohello",
        "embedding": [0.1, 0.2],
    }

    chunk = StoredChunk.model_validate(row)
    assert chunk.chunk_index == 0
    assert chunk.breadcrumb == "note.md"
    assert chunk.prefix == "intro"
    assert chunk.suffix is None
    assert chunk.search_text == "note.md\nintrohello"
    assert chunk.doc.startswith("doc:")
