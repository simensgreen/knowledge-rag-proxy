"""Tests for startup reconciliation helpers."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from server.engine.ingest.prepare import file_checksums
from server.engine.store_models import StoredDoc
from server.services.index_queue import IndexQueue
from server.services.reconcile import is_stale, reconcile_index, walk_document_files

_SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt", ".pdf"}


class _FakeParser:
    def is_supported(self, suffix: str) -> bool:
        return suffix.lower() in _SUPPORTED_SUFFIXES

    def supported_formats(self) -> list[str]:
        return sorted(suffix.lstrip(".") for suffix in _SUPPORTED_SUFFIXES)

    def convert_bytes(self, filename: str, data: bytes):  # pragma: no cover - unused
        raise NotImplementedError

    def convert_file(self, path: Path):  # pragma: no cover - unused
        raise NotImplementedError


def _doc_for(path: Path, *, size: int | None = None, sha: bytes | None = None) -> StoredDoc:
    data = path.read_bytes()
    crc32, sha256 = file_checksums(data)
    now = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return StoredDoc(
        id="doc:1",
        path=path.name,
        created_at=now,
        modified_at=now,
        size_bytes=size if size is not None else len(data),
        crc32=crc32,
        sha256=sha if sha is not None else sha256,
        embedding_model="test",
        chunk_count=1,
    )


def test_is_stale_when_size_differs(tmp_path: Path) -> None:
    file_path = tmp_path / "a.md"
    file_path.write_text("hello", encoding="utf-8")
    document = _doc_for(file_path, size=1)
    assert is_stale(file_path, document) is True


def test_is_stale_false_when_matching(tmp_path: Path) -> None:
    file_path = tmp_path / "a.md"
    file_path.write_text("hello", encoding="utf-8")
    document = _doc_for(file_path)
    assert is_stale(file_path, document) is False


def test_is_stale_when_hash_differs(tmp_path: Path) -> None:
    file_path = tmp_path / "a.md"
    file_path.write_text("hello", encoding="utf-8")
    document = _doc_for(file_path, sha=b"y" * 32)
    document = document.model_copy(
        update={"modified_at": datetime.now(timezone.utc) + timedelta(hours=1)}
    )
    # Force mtime/size check to pass by matching size and bumping stored mtime ahead
    document = document.model_copy(
        update={
            "size_bytes": file_path.stat().st_size,
            "modified_at": datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc),
            "sha256": b"y" * 32,
        }
    )
    assert is_stale(file_path, document) is True


def test_walk_skips_dotfiles(tmp_path: Path) -> None:
    (tmp_path / "keep.md").write_text("x", encoding="utf-8")
    (tmp_path / ".hidden").write_text("y", encoding="utf-8")
    files = walk_document_files(tmp_path)
    names = {path.name for path in files}
    assert "keep.md" in names
    assert ".hidden" not in names


def test_reconcile_enqueues_new_and_orphan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.conftest import FakeDocStore

    documents_dir = tmp_path / "documents"
    documents_dir.mkdir()
    (documents_dir / "new.md").write_text("# new", encoding="utf-8")

    store = FakeDocStore()
    now = datetime.now(timezone.utc)
    store.docs["gone.md"] = StoredDoc(
        id="doc:gone",
        path="gone.md",
        created_at=now,
        modified_at=now,
        size_bytes=1,
        crc32=b"\x00\x00\x00\x01",
        sha256=b"x" * 32,
        embedding_model="test",
        chunk_count=1,
    )

    monkeypatch.setattr("server.services.reconcile.documents_root", lambda: documents_dir)
    queue = IndexQueue(debounce_seconds=10.0)

    async def scenario() -> None:
        await reconcile_index(queue, store, _FakeParser())

    asyncio.run(scenario())
    snapshot = queue.snapshot()
    kinds = {item.path: item.kind for item in snapshot.debounced}
    assert kinds["new.md"] == "index"
    assert kinds["gone.md"] == "delete"


def test_reconcile_retries_failed_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.conftest import FakeDocStore

    documents_dir = tmp_path / "documents"
    documents_dir.mkdir()
    failed_file = documents_dir / "failed.md"
    failed_file.write_text("# failed", encoding="utf-8")

    # A failed doc stores the current file checksum + mtime, so it is NOT stale;
    # only the chunk_count=None flag marks it for a forced reindex.
    crc32, sha256 = file_checksums(failed_file.read_bytes())
    mtime = datetime.fromtimestamp(failed_file.stat().st_mtime, tz=timezone.utc)
    store = FakeDocStore()
    store.docs["failed.md"] = StoredDoc(
        id="doc:failed",
        path="failed.md",
        created_at=mtime,
        modified_at=mtime,
        size_bytes=failed_file.stat().st_size,
        crc32=crc32,
        sha256=sha256,
        embedding_model="test",
        chunk_count=None,
    )

    monkeypatch.setattr("server.services.reconcile.documents_root", lambda: documents_dir)
    queue = IndexQueue(debounce_seconds=10.0)

    asyncio.run(reconcile_index(queue, store, _FakeParser()))

    snapshot = queue.snapshot()
    kinds = {item.path: item.kind for item in snapshot.debounced}
    assert kinds["failed.md"] == "reindex"


def test_reconcile_indexes_new_unsupported_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.conftest import FakeDocStore

    documents_dir = tmp_path / "documents"
    documents_dir.mkdir()
    (documents_dir / "archive.bin").write_text("binary junk", encoding="utf-8")

    # New unsupported file has no doc yet: it is enqueued so the worker can
    # record it as unindexable (chunk_count=None) and it appears in the DB.
    store = FakeDocStore()
    monkeypatch.setattr("server.services.reconcile.documents_root", lambda: documents_dir)
    queue = IndexQueue(debounce_seconds=10.0)

    asyncio.run(reconcile_index(queue, store, _FakeParser()))

    kinds = {item.path: item.kind for item in queue.snapshot().debounced}
    assert kinds["archive.bin"] == "index"


def test_reconcile_does_not_retry_recorded_unsupported_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.conftest import FakeDocStore

    documents_dir = tmp_path / "documents"
    documents_dir.mkdir()
    unsupported = documents_dir / "archive.bin"
    unsupported.write_text("binary junk", encoding="utf-8")

    # An unsupported file already recorded with chunk_count=None must not be retried.
    crc32, sha256 = file_checksums(unsupported.read_bytes())
    mtime = datetime.fromtimestamp(unsupported.stat().st_mtime, tz=timezone.utc)
    store = FakeDocStore()
    store.docs["archive.bin"] = StoredDoc(
        id="doc:bin",
        path="archive.bin",
        created_at=mtime,
        modified_at=mtime,
        size_bytes=unsupported.stat().st_size,
        crc32=crc32,
        sha256=sha256,
        embedding_model="test",
        chunk_count=None,
    )

    monkeypatch.setattr("server.services.reconcile.documents_root", lambda: documents_dir)
    queue = IndexQueue(debounce_seconds=10.0)

    asyncio.run(reconcile_index(queue, store, _FakeParser()))

    paths = {item.path for item in queue.snapshot().debounced}
    assert "archive.bin" not in paths
