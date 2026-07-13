"""Tests for the index worker task processing."""

from __future__ import annotations

from pathlib import Path

import pytest

from server.services.index_queue import IndexTask
from server.services.indexing import process_task


class _FakeParser:
    def is_supported(self, suffix: str) -> bool:
        return suffix.lower() in {".md", ".markdown", ".txt", ".pdf"}

    def supported_formats(self) -> list[str]:
        return ["md", "markdown", "txt", "pdf"]

    def convert_bytes(self, filename: str, data: bytes):  # pragma: no cover - unused
        raise NotImplementedError

    def convert_file(self, path: Path):  # pragma: no cover - unused
        raise NotImplementedError


class _UnusedEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover - unused
        raise AssertionError("embedder must not be called for unsupported files")


def test_process_task_records_unsupported_file_as_unindexable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.conftest import FakeDocStore

    documents_dir = tmp_path / "documents"
    documents_dir.mkdir()
    (documents_dir / "archive.bin").write_text("binary junk", encoding="utf-8")

    monkeypatch.setenv("GRIM_DOCUMENTS_DIR", str(documents_dir))
    monkeypatch.setattr("server.paths.documents_root", lambda: documents_dir)
    monkeypatch.setattr("server.env_config.get_allowed_roots", lambda: [documents_dir])

    store = FakeDocStore()
    process_task(
        IndexTask(path="archive.bin", kind="index"),
        store=store,
        parser=_FakeParser(),
        embedder=_UnusedEmbedder(),
        embedding_model="test-model",
    )

    document = store.get_doc_by_path("archive.bin")
    assert document is not None
    assert document.chunk_count is None
