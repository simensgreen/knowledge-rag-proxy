"""Pytest fixtures for server tests."""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("GRIM_DOCUMENTS_DIR", str(_REPO_ROOT / "documents"))
os.environ.setdefault("GRIM_EMBEDDING_BASE_URL", "http://localhost:9999")
os.environ.setdefault("GRIM_EMBEDDING_TOKEN", "test-embedding-token")
os.environ.setdefault("GRIM_EMBEDDING_DIMENSIONS", "4")

from server.app import app  # noqa: E402
from server.deps import (  # noqa: E402
    get_embedder_dep,
    get_parser_dep,
    get_queue_dep,
    get_store_dep,
)
from server.engine.markitdown_parser import MarkitdownParser  # noqa: E402
from server.engine.store_models import StoredChunk, StoredDoc  # noqa: E402
from server.services.index_queue import IndexQueue  # noqa: E402


@dataclass
class FakeDocStore:
    docs: dict[str, StoredDoc] = field(default_factory=dict)
    chunks: dict[str, list[StoredChunk]] = field(default_factory=dict)

    def get_doc_by_path(self, path: str) -> StoredDoc | None:
        return self.docs.get(path)

    def list_all_docs(self) -> list[StoredDoc]:
        return list(self.docs.values())

    def list_documents(
        self,
        path_regex: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[StoredDoc], int]:
        documents = sorted(self.docs.values(), key=lambda document: document.path)
        if path_regex:
            pattern = re.compile(path_regex)
            documents = [document for document in documents if pattern.search(document.path)]
        total = len(documents)
        return documents[offset : offset + limit], total

    def matching_doc_paths(self, path_regex: str) -> list[str]:
        pattern = re.compile(path_regex)
        return sorted(
            document.path
            for document in self.docs.values()
            if pattern.search(document.path)
        )

    def search(
        self,
        query_text: str,
        query_embedding: list[float],
        limit: int,
    ) -> list[dict[str, Any]]:
        del query_text, query_embedding
        results: list[dict[str, Any]] = []
        for document in sorted(self.docs.values(), key=lambda document: document.path):
            chunks = sorted(self.chunks.get(document.id, []), key=lambda chunk: chunk.chunk_index)
            for chunk in chunks:
                results.append(
                    {
                        "path": document.path,
                        "filename": document.path.rsplit("/", 1)[-1],
                        "content": chunk.content,
                        "breadcrumb": chunk.breadcrumb,
                        "chunk_index": chunk.chunk_index,
                        "score": 1.0,
                    }
                )
        return results[:limit]

    def count_stats(self) -> dict[str, int]:
        chunk_total = sum(len(items) for items in self.chunks.values())
        return {
            "documents": len(self.docs),
            "chunks": chunk_total,
        }

    def failed_doc_paths(self) -> list[str]:
        return [
            document.path
            for document in self.docs.values()
            if document.chunk_count is None
        ]

    def update_description(self, path: str, description: str | None) -> StoredDoc | None:
        document = self.docs.get(path)
        if document is None:
            return None
        updated = document.model_copy(update={"description": description})
        self.docs[path] = updated
        return updated

    def get_markdown_content(self, path: str) -> str | None:
        document = self.docs.get(path)
        if document is None:
            return None
        chunks = self.chunks.get(document.id, [])
        ordered = sorted(chunks, key=lambda chunk: chunk.chunk_index)
        return "".join(chunk.content for chunk in ordered)

    def upsert_prepared(self, prepared: Any, *, preserve_description: bool = True) -> StoredDoc:
        existing = self.docs.get(prepared.doc.path)
        description = prepared.doc.description
        if preserve_description and existing is not None and prepared.doc.description is None:
            description = existing.description
        document = prepared.doc.model_copy(update={"description": description})
        self.docs[document.path] = document
        self.chunks[document.id] = list(prepared.chunks)
        return document

    def replace_chunks(self, doc_id: str, chunks: list[StoredChunk]) -> StoredDoc | None:
        for path, document in self.docs.items():
            if document.id == doc_id:
                updated = document.model_copy(update={"chunk_count": len(chunks)})
                self.docs[path] = updated
                self.chunks[doc_id] = list(chunks)
                return updated
        return None

    def rename_path(self, source_path: str, dest_path: str) -> StoredDoc | None:
        document = self.docs.pop(source_path, None)
        if document is None:
            return None
        updated = document.model_copy(update={"path": dest_path})
        self.docs[dest_path] = updated
        return updated

    def remove_by_path(self, path: str) -> bool:
        document = self.docs.pop(path, None)
        if document is None:
            return False
        self.chunks.pop(document.id, None)
        return True

    def mark_failed(
        self,
        path: str,
        *,
        size_bytes: int,
        crc32: bytes,
        sha256: bytes,
        embedding_model: str,
    ) -> StoredDoc:
        now = datetime.now(timezone.utc)
        existing = self.docs.get(path)
        if existing is None:
            document = StoredDoc(
                id=f"doc:failed-{path}",
                path=path,
                created_at=now,
                modified_at=now,
                size_bytes=size_bytes,
                crc32=crc32,
                sha256=sha256,
                embedding_model=embedding_model,
                chunk_count=None,
            )
        else:
            document = existing.model_copy(
                update={
                    "modified_at": now,
                    "size_bytes": size_bytes,
                    "crc32": crc32,
                    "sha256": sha256,
                    "embedding_model": embedding_model,
                    "chunk_count": None,
                }
            )
        self.docs[path] = document
        return document


class MockEmbedder:
    def __init__(self, dimensions: int = 4) -> None:
        self.dimensions = dimensions
        self.model = "test-model"
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[0.1] * self.dimensions for _ in texts]


@pytest.fixture
def temp_dirs(tmp_path: Path) -> dict[str, Path]:
    documents_dir = tmp_path / "documents"
    documents_dir.mkdir()
    return {"documents_dir": documents_dir}


@pytest.fixture
def markitdown_parser() -> MarkitdownParser:
    return MarkitdownParser(ocr_config=None)


@pytest.fixture
def fake_store() -> FakeDocStore:
    now = datetime.now(timezone.utc)
    store = FakeDocStore()
    document = StoredDoc(
        id="doc:1",
        path="docs/a.md",
        created_at=now,
        modified_at=now,
        size_bytes=10,
        crc32=b"\x00\x00\x00\x01",
        sha256=b"x" * 32,
        embedding_model="test-model",
        chunk_count=1,
        description="sample",
    )
    store.docs[document.path] = document
    store.chunks[document.id] = [
        StoredChunk(
            id="chunk:1",
            doc=document.id,
            chunk_index=0,
            breadcrumb="a.md",
            content="# Title\n\nHello",
            search_text="a.md\n# Title\n\nHello",
            embedding=[0.1, 0.2, 0.3, 0.4],
        )
    ]
    return store


@pytest.fixture
def index_queue() -> IndexQueue:
    return IndexQueue(debounce_seconds=0.01)


@pytest.fixture
def mock_embedder() -> MockEmbedder:
    return MockEmbedder()


@pytest.fixture
def api_key(monkeypatch: pytest.MonkeyPatch) -> str:
    token = "test-token-for-pytest"
    monkeypatch.setenv("GRIM_BEARER", token)
    return token


async def _idle_forever(*_args: Any, **_kwargs: Any) -> None:
    while True:
        await asyncio.sleep(3600)


async def _noop_reconcile(*_args: Any, **_kwargs: Any) -> None:
    return None


@pytest.fixture
def client(
    api_key: str,
    markitdown_parser: MarkitdownParser,
    fake_store: FakeDocStore,
    index_queue: IndexQueue,
    mock_embedder: MockEmbedder,
    temp_dirs: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    del api_key
    monkeypatch.setenv("GRIM_DOCUMENTS_DIR", str(temp_dirs["documents_dir"]))

    app.dependency_overrides[get_parser_dep] = lambda: markitdown_parser
    app.dependency_overrides[get_store_dep] = lambda: fake_store
    app.dependency_overrides[get_queue_dep] = lambda: index_queue
    app.dependency_overrides[get_embedder_dep] = lambda: mock_embedder

    monkeypatch.setattr("server.env_config.get_allowed_roots", lambda: [temp_dirs["documents_dir"]])
    monkeypatch.setattr("server.paths.documents_root", lambda: temp_dirs["documents_dir"])
    monkeypatch.setattr("server.app.probe_documents_dir", lambda: None)
    monkeypatch.setattr("server.app.probe_embedding_provider", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "server.app.verify_stored_embedding_dimensions", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        "server.app.ensure_store_schema",
        lambda: MagicMock(close=lambda: None),
    )
    monkeypatch.setattr("server.app.start_watchers", lambda *args, **kwargs: None)
    monkeypatch.setattr("server.app.stop_watchers", lambda: None)
    monkeypatch.setattr("server.app.run_index_worker", _idle_forever)
    monkeypatch.setattr("server.app.reconcile_index", _noop_reconcile)

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}
