"""Pytest fixtures for server tests."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parent.parent
# KRP_DOCUMENTS_DIR is required at import; point it at the repo's documents dir.
os.environ.setdefault("KRP_DOCUMENTS_DIR", str(_REPO_ROOT / "documents"))
# Keep the library's internal base and db/model-cache out of real app-data dirs.
_TEST_APP_DATA = _REPO_ROOT / ".pytest_appdata"
os.environ.setdefault("KNOWLEDGE_RAG_DIR", str(_TEST_APP_DATA / "base"))
os.environ.setdefault("KRP_DATA_DIR", str(_TEST_APP_DATA / "db"))
os.environ.setdefault("KRP_MODELS_CACHE_DIR", str(_TEST_APP_DATA / "models_cache"))

from server.app import app  # noqa: E402
from server.deps import get_orchestrator_dep  # noqa: E402


class MockOrchestrator:
    """Lightweight stand-in for KnowledgeOrchestrator."""

    def __init__(self, documents_dir: Path, uploads_dir: Path) -> None:
        self.documents_dir = documents_dir
        self.uploads_dir = uploads_dir
        self.query_cache = MagicMock()
        self.query_cache.stats.return_value = {"hit_rate": 0.0}
        self.bm25_index = MagicMock()
        self._indexed_docs: dict[str, dict[str, Any]] = {}
        self._source_to_docid: dict[str, str] = {}
        self.parser = MagicMock()
        self._index_document = MagicMock(return_value=(2, 0))

    def query(self, *_args, **_kwargs) -> list[dict[str, Any]]:
        return [{"content": "sample content", "score": 0.9, "source": "docs/a.md"}]

    def get_document(self, filepath: str) -> dict[str, Any] | None:
        if Path(filepath).name == "missing.md":
            return None
        return {
            "content": "full text",
            "source": str(filepath),
            "filename": Path(filepath).name,
            "category": "general",
            "format": ".md",
            "metadata": {},
            "keywords": [],
            "chunk_count": 1,
        }

    def start_reindex_background(self, mode: str) -> dict[str, Any]:
        if mode == "already_running":
            return {"status": "already_running", "progress": {"processed": 1, "total_files": 10}}
        return {"status": "started", "operation": mode}

    def get_reindex_status(self) -> dict[str, Any]:
        return {"active": False}

    def index_all(self, force: bool = False) -> dict[str, Any]:
        del force
        return {"indexed": 0, "updated": 0, "deleted": 0, "skipped": 0, "chunks_added": 0}

    def list_categories(self) -> dict[str, int]:
        return {"general": 1}

    def list_documents(self, category: str | None = None) -> list[dict[str, Any]]:
        del category
        relative_sources = ["docs/a.md", "docs/b.md", "notes/c.md", "notes/sub/d.md"]
        return [
            {
                "id": str(index),
                "source": str(self.documents_dir / source),
                "category": "general",
                "format": ".md",
                "chunks": 1,
                "keywords": [],
            }
            for index, source in enumerate(relative_sources)
        ]

    def get_stats(self) -> dict[str, Any]:
        return {"total_documents": 1, "total_chunks": 3}

    def add_document_from_content(self, content: str, filepath: str, category: str) -> dict[str, Any]:
        del content
        return {"filepath": str(self.documents_dir / filepath), "chunks_added": 2, "category": category}

    def update_document_content(self, filepath: str, content: str) -> dict[str, Any]:
        del content
        if Path(filepath).name == "missing.md":
            return {"error": f"File not found: {filepath}"}
        return {"old_chunks_removed": 1, "new_chunks_added": 2, "filepath": filepath}

    def remove_document_by_path(self, filepath: str, delete_file: bool = False) -> dict[str, Any]:
        if Path(filepath).name == "missing.md":
            return {"error": f"Document not found in index: {filepath}"}
        resolved = str(Path(filepath).resolve())
        chunks_removed = 0
        doc_id = self._source_to_docid.pop(resolved, None)
        if doc_id is not None:
            self._indexed_docs.pop(doc_id, None)
            chunks_removed = 1
        if delete_file and Path(filepath).exists():
            Path(filepath).unlink()
        return {"chunks_removed": chunks_removed, "filepath": filepath, "file_deleted": delete_file}

    def search_similar(self, filepath: str, max_results: int = 5) -> list[dict[str, Any]]:
        del filepath, max_results
        return [{"source": "docs/b.md", "score": 0.8}]

    def _save_metadata(self) -> None:
        pass


@pytest.fixture
def temp_dirs(tmp_path: Path) -> dict[str, Path]:
    documents_dir = tmp_path / "documents"
    documents_dir.mkdir()
    return {"documents_dir": documents_dir}


@pytest.fixture
def mock_orchestrator(temp_dirs: dict[str, Path]) -> MockOrchestrator:
    return MockOrchestrator(temp_dirs["documents_dir"], temp_dirs["documents_dir"])


@pytest.fixture
def api_key(monkeypatch: pytest.MonkeyPatch) -> str:
    token = "test-token-for-pytest"
    monkeypatch.setenv("KRP_BEARER", token)
    return token


@pytest.fixture
def client(
    api_key: str,
    mock_orchestrator: MockOrchestrator,
    temp_dirs: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    del api_key
    monkeypatch.setenv("KRP_WATCH_DISABLED", "1")

    def fake_get_orchestrator() -> MockOrchestrator:
        return mock_orchestrator

    monkeypatch.setattr("server.deps.get_orchestrator_dep", fake_get_orchestrator)
    monkeypatch.setattr("server.app.get_orchestrator_dep", fake_get_orchestrator)
    monkeypatch.setattr("mcp_server.server.get_orchestrator", fake_get_orchestrator)
    app.dependency_overrides[get_orchestrator_dep] = fake_get_orchestrator
    allowed_roots = lambda: [temp_dirs["documents_dir"]]
    monkeypatch.setattr("server.env_config.get_allowed_roots", allowed_roots)
    monkeypatch.setattr("server.app.start_watchers", lambda: None)
    monkeypatch.setattr("server.app.stop_watchers", lambda: None)

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}
