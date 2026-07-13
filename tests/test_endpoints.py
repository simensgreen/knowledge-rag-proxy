"""Server endpoint tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def test_health_requires_bearer(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 401


def test_no_bearer_required_when_unset(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GRIM_BEARER", raising=False)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_health_invalid_bearer(client: TestClient) -> None:
    response = client.get("/api/health", headers={"Authorization": "Bearer wrong-token"})
    assert response.status_code == 401


def test_health_ok(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/health", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload == {"ok": True}


def test_legacy_routes_without_api_prefix_return_404(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    assert client.get("/health", headers=auth_headers).status_code == 404
    assert client.get("/search", params={"query": "x"}, headers=auth_headers).status_code == 404
    assert client.get("/file", params={"path": "a.md"}, headers=auth_headers).status_code == 404


def test_old_routes_removed(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert client.get("/search_knowledge", params={"query": "x"}, headers=auth_headers).status_code == 404
    assert client.get("/get_document", params={"filepath": "a.md"}, headers=auth_headers).status_code == 404


def test_search_success(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/search", params={"query": "example"}, headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["result_count"] == 1
    assert payload["results"][0]["path"] == "docs/a.md"


def test_search_empty_query(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/search", params={"query": "   "}, headers=auth_headers)
    assert response.status_code == 400


def test_file_info_missing(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/file_info", params={"path": "missing.md"}, headers=auth_headers)
    assert response.status_code == 404


def test_file_info_success(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/file_info", params={"path": "docs/a.md"}, headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["file"]["path"] == "docs/a.md"
    assert payload["file"]["description"] == "sample"
    assert not Path(payload["file"]["path"]).is_absolute()


def test_file_info_post_updates_description(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.post(
        "/api/file_info",
        params={"path": "docs/a.md", "description": "updated"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["file"]["description"] == "updated"


def test_file_content_get(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/file_content", params={"path": "docs/a.md"}, headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["path"] == "docs/a.md"
    assert "Hello" in payload["markdown"]


def test_file_content_post_queues(
    client: TestClient,
    auth_headers: dict[str, str],
    index_queue,
) -> None:
    response = client.post(
        "/api/file_content",
        params={"path": "docs/a.md"},
        json={"markdown": "# Replaced\n"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["path"] == "docs/a.md"
    snapshot = index_queue.snapshot()
    assert any(item.path == "docs/a.md" for item in snapshot.debounced + snapshot.pending)


def test_reindex_queues(
    client: TestClient,
    auth_headers: dict[str, str],
    index_queue,
) -> None:
    response = client.post(
        "/api/reindex",
        params={"path": r"docs/a\.md"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["matched"] == ["docs/a.md"]
    snapshot = index_queue.snapshot()
    assert any(
        item.path == "docs/a.md" and item.kind == "reindex"
        for item in snapshot.debounced + snapshot.pending
    )


def test_reindex_regex_matches_multiple(
    client: TestClient,
    auth_headers: dict[str, str],
    fake_store,
    index_queue,
) -> None:
    from datetime import datetime, timezone

    from server.engine.store_models import StoredDoc

    now = datetime.now(timezone.utc)
    for path in ("notes/first.md", "notes/second.md"):
        fake_store.docs[path] = StoredDoc(
            id=f"doc:{path}",
            path=path,
            created_at=now,
            modified_at=now,
            size_bytes=5,
            crc32=b"\x00\x00\x00\x01",
            sha256=b"y" * 32,
            embedding_model="test-model",
            chunk_count=1,
        )

    response = client.post("/api/reindex", params={"path": r"^notes/"}, headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert payload["matched"] == ["notes/first.md", "notes/second.md"]

    queued = {
        item.path
        for item in index_queue.snapshot().debounced + index_queue.snapshot().pending
        if item.kind == "reindex"
    }
    assert queued == {"notes/first.md", "notes/second.md"}


def test_reindex_no_match(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post("/api/reindex", params={"path": r"nothing/here\.md"}, headers=auth_headers)
    assert response.status_code == 404


def test_list_files_regex(client: TestClient, auth_headers: dict[str, str]) -> None:
    matched = client.get("/api/list_files", params={"path": "docs"}, headers=auth_headers)
    assert matched.status_code == 200
    matched_payload = matched.json()
    assert matched_payload["total"] == 1
    listed = matched_payload["files"][0]
    assert listed["path"] == "docs/a.md"
    hidden_fields = ("id", "accessed_at", "access_count", "embedding_model", "description", "crc32", "sha256")
    for hidden_field in hidden_fields:
        assert hidden_field not in listed

    missed = client.get("/api/list_files", params={"path": "notes"}, headers=auth_headers)
    assert missed.status_code == 200
    assert missed.json()["total"] == 0


def test_list_files_invalid_regex(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/list_files", params={"path": "[invalid"}, headers=auth_headers)
    assert response.status_code == 400


def test_status(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/status", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["documents"] == 1
    assert payload["chunks"] == 1
    assert payload["failed"] == 0
    assert payload["unsupported"] == 0
    assert payload["indexing"] is None or isinstance(payload["indexing"], dict)


def test_upload_success(
    client: TestClient,
    auth_headers: dict[str, str],
    temp_dirs: dict[str, Path],
) -> None:
    response = client.post(
        "/api/upload",
        headers=auth_headers,
        files={"file": ("note.md", b"# hello", "text/markdown")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["path"] == "note.md"
    assert (temp_dirs["documents_dir"] / "note.md").is_file()


def test_upload_with_markdown_queues(
    client: TestClient,
    auth_headers: dict[str, str],
    index_queue,
) -> None:
    response = client.post(
        "/api/upload",
        headers=auth_headers,
        files={
            "file": ("report.pdf", b"%PDF-1.4 binary", "application/pdf"),
            "markdown": ("report.md", b"# Report\n\nBody", "text/markdown"),
        },
        data={"description": "Quarterly report"},
    )
    assert response.status_code == 200
    snapshot = index_queue.snapshot()
    assert any(item.path == "report.pdf" for item in snapshot.debounced + snapshot.pending)


def test_markitdown_post(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/markitdown",
        headers=auth_headers,
        files={"file": ("note.md", b"# hello", "text/markdown")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "# hello" in payload["markdown"].lower()
    assert payload["metadata"]["title"] == "hello"


def test_download_success(
    client: TestClient,
    auth_headers: dict[str, str],
    temp_dirs: dict[str, Path],
) -> None:
    target = temp_dirs["documents_dir"] / "readme.md"
    target.write_text("hello file", encoding="utf-8")
    response = client.get("/api/download", params={"path": "readme.md"}, headers=auth_headers)
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
    response = client.post("/api/remove", params={"path": "docs/a.md"}, headers=auth_headers)
    assert response.status_code == 200
    assert not file_path.exists()


def test_move_success(
    client: TestClient,
    auth_headers: dict[str, str],
    temp_dirs: dict[str, Path],
    index_queue,
) -> None:
    source = temp_dirs["documents_dir"] / "notes" / "draft.md"
    source.parent.mkdir(parents=True)
    source.write_text("# draft", encoding="utf-8")
    response = client.post(
        "/api/move",
        params={"source_path": "notes/draft.md", "dest_path": "archive/draft.md"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert not source.exists()
    assert (temp_dirs["documents_dir"] / "archive" / "draft.md").is_file()
    snapshot = index_queue.snapshot()
    assert any(
        item.kind == "move" and item.path == "notes/draft.md"
        for item in snapshot.debounced + snapshot.pending
    )


def test_temp_dir_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from server.env_config import get_temp_dir

    override = tmp_path / "custom-tmp"
    monkeypatch.setenv("GRIM_TMP_DIR", str(override))
    resolved = get_temp_dir()
    assert resolved == override.resolve()
    assert resolved.is_dir()


def test_embedding_dimensions_required(monkeypatch: pytest.MonkeyPatch) -> None:
    from server.env_config import get_embedding_dimensions

    monkeypatch.delenv("GRIM_EMBEDDING_DIMENSIONS", raising=False)
    with pytest.raises(RuntimeError, match="GRIM_EMBEDDING_DIMENSIONS"):
        get_embedding_dimensions()


def test_embedding_provider_required(monkeypatch: pytest.MonkeyPatch) -> None:
    from server.env_config import require_embedding_provider_config

    monkeypatch.delenv("GRIM_EMBEDDING_BASE_URL", raising=False)
    monkeypatch.delenv("GRIM_EMBEDDING_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="GRIM_EMBEDDING_BASE_URL"):
        require_embedding_provider_config()
