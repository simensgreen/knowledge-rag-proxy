"""Server endpoint tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from server.engine.stub_engine import StubEngine


def test_health_requires_bearer(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 401


def test_health_ok(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/health", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["ok"] is True


def test_old_routes_removed(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert client.get("/search_knowledge", params={"query": "x"}, headers=auth_headers).status_code == 404
    assert client.get("/get_document", params={"filepath": "a.md"}, headers=auth_headers).status_code == 404
    assert client.post("/reindex", json={}, headers=auth_headers).status_code == 404


def test_search_success(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/search", params={"query": "example"}, headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["result_count"] == 1
    assert payload["results"][0]["path"] == "docs/a.md"


def test_search_empty_query(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/search", params={"query": "   "}, headers=auth_headers)
    assert response.status_code == 400


def test_file_missing(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/file", params={"path": "missing.md"}, headers=auth_headers)
    assert response.status_code == 404


def test_file_success(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/file", params={"path": "docs/a.md"}, headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["file"]["path"] == "docs/a.md"
    assert not Path(payload["file"]["path"]).is_absolute()


def test_list_files_regex(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/list_files", params={"path": "notes"}, headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2


def test_list_files_invalid_regex(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/list_files", params={"path": "[invalid"}, headers=auth_headers)
    assert response.status_code == 400


def test_status(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/status", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["documents"] == 1


def test_upload_success(
    client: TestClient,
    auth_headers: dict[str, str],
    stub_engine: StubEngine,
    temp_dirs: dict[str, Path],
) -> None:
    response = client.post(
        "/upload",
        headers=auth_headers,
        files={"file": ("note.md", b"# hello", "text/markdown")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["path"] == "note.md"
    assert "document" not in payload
    assert (temp_dirs["documents_dir"] / "note.md").is_file()


def test_upload_background_indexes_when_watcher_disabled(
    client: TestClient,
    auth_headers: dict[str, str],
    stub_engine: StubEngine,
) -> None:
    stub_engine.index_file = MagicMock(return_value={"chunks_added": 1})  # type: ignore[method-assign]
    response = client.post(
        "/upload",
        headers=auth_headers,
        files={"file": ("bg.md", b"# hello", "text/markdown")},
    )
    assert response.status_code == 200
    assert response.json()["indexing"] == "background"


def test_markitdown_post(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/markitdown",
        headers=auth_headers,
        files={"file": ("note.md", b"# hello", "text/markdown")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["markdown"].startswith("# stub markdown")


def test_download_success(client: TestClient, auth_headers: dict[str, str], temp_dirs: dict[str, Path]) -> None:
    target = temp_dirs["documents_dir"] / "readme.md"
    target.write_text("hello file", encoding="utf-8")
    response = client.get("/download", params={"path": "readme.md"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.content == b"hello file"


def test_remove_success(
    client: TestClient,
    auth_headers: dict[str, str],
    temp_dirs: dict[str, Path],
) -> None:
    target = temp_dirs["documents_dir"] / "docs"
    target.mkdir(parents=True)
    file_path = target / "a.md"
    file_path.write_text("content", encoding="utf-8")
    response = client.post("/remove", json={"path": "docs/a.md"}, headers=auth_headers)
    assert response.status_code == 200
    assert not file_path.exists()


def test_move_success(
    client: TestClient,
    auth_headers: dict[str, str],
    temp_dirs: dict[str, Path],
) -> None:
    source = temp_dirs["documents_dir"] / "notes" / "draft.md"
    source.parent.mkdir(parents=True)
    source.write_text("# draft", encoding="utf-8")
    response = client.post(
        "/move",
        json={"source_path": "notes/draft.md", "dest_path": "archive/draft.md"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert not source.exists()
    assert (temp_dirs["documents_dir"] / "archive" / "draft.md").is_file()


def test_temp_dir_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from server.env_config import get_temp_dir

    override = tmp_path / "custom-tmp"
    monkeypatch.setenv("GRIM_TMP_DIR", str(override))
    resolved = get_temp_dir()
    assert resolved == override.resolve()
    assert resolved.is_dir()
