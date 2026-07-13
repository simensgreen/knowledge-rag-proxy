"""Domain models for document ingest (chunking and preparation)."""

from __future__ import annotations

from dataclasses import dataclass

from server.engine.store_models import StoredChunk, StoredDoc


@dataclass(frozen=True)
class Chunk:
    chunk_index: int
    content: str
    breadcrumb: str
    prefix: str | None = None
    suffix: str | None = None


@dataclass(frozen=True)
class PreparedDocument:
    doc: StoredDoc
    chunks: list[StoredChunk]
