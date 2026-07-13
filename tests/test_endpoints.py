"""Server endpoint tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from tests.conftest import MockOrchestrator


def test_health_requires_bearer(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 401
    payload = response.json()
    assert payload["status"] == "error"
    assert "hint" in payload


def test_health_ok(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/health", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["ok"] is True
    assert payload["documents"] == 1


def test_add_document_endpoint_removed(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/add_document",
        json={"content": "x", "filepath": "a.md"},
        headers=auth_headers,
    )
    assert response.status_code in (404, 405)


def test_add_from_url_endpoint_removed(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/add_from_url",
        json={"url": "https://example.com", "category": "general"},
        headers=auth_headers,
    )
    assert response.status_code in (404, 405)


def test_evaluate_retrieval_endpoint_removed(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/evaluate_retrieval",
        json={"test_cases": [{"query": "test", "expected_filepath": "a.md"}]},
        headers=auth_headers,
    )
    assert response.status_code in (404, 405)


def test_search_knowledge_requires_bearer(client: TestClient) -> None:
    response = client.get("/search_knowledge", params={"query": "example"})
    assert response.status_code == 401


def test_search_knowledge_empty_query(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/search_knowledge", params={"query": "   "}, headers=auth_headers)
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert "hint" in payload


def test_search_knowledge_success(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get(
        "/search_knowledge",
        params={"query": "example"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, max-age=300"
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["result_count"] == 1


def test_get_document_missing(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get(
        "/get_document",
        params={"filepath": "missing.md"},
        headers=auth_headers,
    )
    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == "error"
    assert "hint" in payload


def test_get_document_success(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get(
        "/get_document",
        params={"filepath": "docs/a.md"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, max-age=300"
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["document"]["content"] == "full text"
    # Absolute paths must never cross the API boundary.
    source = payload["document"]["source"]
    assert source == "docs/a.md"
    assert not Path(source).is_absolute()


def test_update_document_relative_path(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/update_document",
        json={"filepath": "docs/a.md", "content": "new body"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["filepath"] == "docs/a.md"
    assert not Path(payload["filepath"]).is_absolute()


def test_update_document_missing(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/update_document",
        json={"filepath": "missing.md", "content": "x"},
        headers=auth_headers,
    )
    assert response.status_code == 404
    message = response.json()["message"]
    assert message == "Document not found: missing.md"
    assert "/" != message[0]


def test_reindex_already_running(client: TestClient, auth_headers: dict[str, str], mock_orchestrator: MockOrchestrator) -> None:
    def already_running(_mode: str) -> dict:
        return {"status": "already_running", "progress": {"processed": 1, "total_files": 10, "operation": "incremental"}}

    mock_orchestrator.start_reindex_background = already_running  # type: ignore[method-assign]
    response = client.post("/reindex_documents", json={}, headers=auth_headers)
    assert response.status_code == 400
    assert response.json()["status"] == "error"


def test_list_documents(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/list_documents", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, max-age=300"
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["total"] == 4
    assert payload["count"] == 4
    assert all(not Path(doc["source"]).is_absolute() for doc in payload["documents"])


def test_list_documents_path_filter(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/list_documents", params={"path": "notes"}, headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["path"] == "notes"
    assert payload["total"] == 2
    sources = {doc["source"] for doc in payload["documents"]}
    assert sources == {"notes/c.md", "notes/sub/d.md"}


def test_list_documents_path_filter_nested(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/list_documents", params={"path": "notes/sub"}, headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["documents"][0]["source"] == "notes/sub/d.md"


def test_list_documents_pagination(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get(
        "/list_documents",
        params={"limit": 2, "offset": 1},
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 4
    assert payload["count"] == 2
    assert payload["offset"] == 1
    assert payload["limit"] == 2


def test_list_documents_rejects_bad_pagination(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/list_documents", params={"limit": 0}, headers=auth_headers)
    assert response.status_code == 422


def test_list_documents_rejects_parent_path(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/list_documents", params={"path": "../etc"}, headers=auth_headers)
    assert response.status_code == 400


def test_get_reindex_status_no_store(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/get_reindex_status", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"


def test_temp_dir_defaults_to_system(monkeypatch: pytest.MonkeyPatch) -> None:
    import tempfile

    from server.env_config import get_temp_dir

    monkeypatch.delenv("KRP_TMP_DIR", raising=False)
    assert get_temp_dir() == Path(tempfile.gettempdir())


def test_temp_dir_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from server.env_config import get_temp_dir

    override = tmp_path / "custom-tmp"
    monkeypatch.setenv("KRP_TMP_DIR", str(override))
    resolved = get_temp_dir()
    assert resolved == override.resolve()
    assert resolved.is_dir()


def test_upload_outside_scope(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/upload",
        headers=auth_headers,
        data={"filedir": "../.."},
        files={"file": ("secret.txt", b"data", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["status"] == "error"


def test_upload_success_without_document(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_orchestrator: MockOrchestrator,
    temp_dirs: dict[str, Path],
) -> None:
    mock_document = MagicMock()
    mock_document.content = "parsed"
    mock_document.source = temp_dirs["documents_dir"] / "note.md"
    mock_document.filename = "note.md"
    mock_document.category = "general"
    mock_document.format = ".md"
    mock_document.metadata = {}
    mock_document.keywords = []
    mock_document.chunks = [MagicMock()]
    mock_document.id = "doc-1"
    mock_orchestrator.parser.parse_file.return_value = mock_document
    mock_orchestrator.parser._parsers = {".md": lambda _path: ("", {})}

    response = client.post(
        "/upload",
        headers=auth_headers,
        files={"file": ("note.md", b"# hello", "text/markdown")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert "document" not in payload
    assert payload["chunks_added"] == 2
    # Upload echoes a root-relative path, never the absolute disk path.
    assert payload["filepath"] == "note.md"
    assert not Path(payload["filepath"]).is_absolute()


def test_upload_return_document(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_orchestrator: MockOrchestrator,
    temp_dirs: dict[str, Path],
) -> None:
    mock_document = MagicMock()
    mock_document.content = "parsed"
    mock_document.source = temp_dirs["documents_dir"] / "note.md"
    mock_document.filename = "note.md"
    mock_document.category = "general"
    mock_document.format = ".md"
    mock_document.metadata = {}
    mock_document.keywords = []
    mock_document.chunks = [MagicMock()]
    mock_document.id = "doc-1"
    mock_orchestrator.parser.parse_file.return_value = mock_document
    mock_orchestrator.parser._parsers = {".md": lambda _path: ("", {})}

    response = client.post(
        "/upload",
        headers=auth_headers,
        data={"return": "true"},
        files={"file": ("note.md", b"# hello", "text/markdown")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["content"] == "parsed"


def test_upload_into_filedir(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_orchestrator: MockOrchestrator,
    temp_dirs: dict[str, Path],
) -> None:
    mock_document = MagicMock()
    mock_document.category = "general"
    mock_document.chunks = [MagicMock()]
    mock_document.id = "doc-1"
    mock_orchestrator.parser.parse_file.return_value = mock_document
    mock_orchestrator.parser._parsers = {".md": lambda _path: ("", {})}

    response = client.post(
        "/upload",
        headers=auth_headers,
        data={"filedir": "notes"},
        files={"file": ("plan.md", b"# hello", "text/markdown")},
    )
    assert response.status_code == 200
    assert (temp_dirs["documents_dir"] / "notes" / "plan.md").is_file()


def test_upload_existing_file(
    client: TestClient,
    auth_headers: dict[str, str],
    temp_dirs: dict[str, Path],
) -> None:
    existing = temp_dirs["documents_dir"] / "dup.md"
    existing.write_text("already here", encoding="utf-8")
    response = client.post(
        "/upload",
        headers=auth_headers,
        files={"file": ("dup.md", b"new", "text/markdown")},
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["message"]


def test_download_missing(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/download", params={"filepath": "missing.md"}, headers=auth_headers)
    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == "error"
    assert "hint" in payload


def test_download_outside_scope(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/download", params={"filepath": "/etc/passwd"}, headers=auth_headers)
    assert response.status_code == 400
    assert response.json()["status"] == "error"


def test_download_success(
    client: TestClient,
    auth_headers: dict[str, str],
    temp_dirs: dict[str, Path],
) -> None:
    target = temp_dirs["documents_dir"] / "readme.md"
    target.write_text("hello file", encoding="utf-8")
    response = client.get("/download", params={"filepath": "readme.md"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.content == b"hello file"


def test_remove_document_success(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_orchestrator: MockOrchestrator,
    temp_dirs: dict[str, Path],
) -> None:
    target = temp_dirs["documents_dir"] / "docs" / "a.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("content", encoding="utf-8")
    mock_orchestrator._source_to_docid[str(target.resolve())] = "doc-1"

    response = client.post(
        "/remove_document",
        json={"filepath": "docs/a.md", "delete_file": True},
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["filepath"] == "docs/a.md"
    assert not target.exists()


def test_remove_document_missing(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/remove_document",
        json={"filepath": "missing.md"},
        headers=auth_headers,
    )
    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == "error"
    assert "hint" in payload


def test_move_document_success(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_orchestrator: MockOrchestrator,
    temp_dirs: dict[str, Path],
) -> None:
    source = temp_dirs["documents_dir"] / "notes" / "draft.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("# draft", encoding="utf-8")
    mock_orchestrator._source_to_docid[str(source.resolve())] = "doc-move"
    mock_orchestrator.parser._parsers = {".md": lambda _path: ("", {})}

    mock_document = MagicMock()
    mock_document.content = "parsed"
    mock_document.source = temp_dirs["documents_dir"] / "archive" / "draft.md"
    mock_document.filename = "draft.md"
    mock_document.category = "general"
    mock_document.format = ".md"
    mock_document.metadata = {}
    mock_document.keywords = []
    mock_document.chunks = [MagicMock()]
    mock_document.id = "doc-move-new"
    mock_orchestrator.parser.parse_file.return_value = mock_document

    response = client.post(
        "/move_document",
        json={"source_filepath": "notes/draft.md", "dest_filepath": "archive/draft.md"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["source_filepath"] == "notes/draft.md"
    assert payload["dest_filepath"] == "archive/draft.md"
    assert not source.exists()
    assert (temp_dirs["documents_dir"] / "archive" / "draft.md").is_file()


def test_move_document_dest_exists(
    client: TestClient,
    auth_headers: dict[str, str],
    temp_dirs: dict[str, Path],
) -> None:
    source = temp_dirs["documents_dir"] / "a.md"
    dest = temp_dirs["documents_dir"] / "b.md"
    source.write_text("a", encoding="utf-8")
    dest.write_text("b", encoding="utf-8")

    response = client.post(
        "/move_document",
        json={"source_filepath": "a.md", "dest_filepath": "b.md"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert "hint" in payload
    assert source.is_file()


def test_move_document_source_missing(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/move_document",
        json={"source_filepath": "missing.md", "dest_filepath": "new.md"},
        headers=auth_headers,
    )
    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == "error"
    assert "hint" in payload


def test_move_document_path_escape(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/move_document",
        json={"source_filepath": "../etc/passwd", "dest_filepath": "safe.md"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert response.json()["status"] == "error"
