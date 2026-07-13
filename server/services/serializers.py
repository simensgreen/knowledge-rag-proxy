"""API serialization for StoredDoc / StoredChunk."""

from __future__ import annotations

from typing import Any

from server.engine.store_models import StoredDoc


def doc_to_api(document: StoredDoc) -> dict[str, Any]:
    return {
        "id": document.id,
        "path": document.path,
        "created_at": document.created_at.isoformat(),
        "modified_at": document.modified_at.isoformat(),
        "accessed_at": document.accessed_at.isoformat() if document.accessed_at else None,
        "access_count": document.access_count,
        "size_bytes": document.size_bytes,
        "crc32": document.crc32.hex(),
        "sha256": document.sha256.hex(),
        "embedding_model": document.embedding_model,
        "chunk_count": document.chunk_count,
        "description": document.description,
    }


def doc_to_list_item(document: StoredDoc) -> dict[str, Any]:
    """Slim listing view: omit id, access stats, checksums, embedding model, description."""
    return {
        "path": document.path,
        "created_at": document.created_at.isoformat(),
        "modified_at": document.modified_at.isoformat(),
        "size_bytes": document.size_bytes,
        "chunk_count": document.chunk_count,
    }
