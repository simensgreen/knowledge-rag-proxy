"""Startup reconciliation: disk vs SurrealDB index."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from server.engine.doc_store import DocStore
from server.engine.ingest.prepare import file_checksums
from server.engine.protocols import Parser
from server.engine.store_models import StoredDoc
from server.env_config import get_documents_dir
from server.paths import documents_root
from server.services.index_queue import IndexQueue, IndexTask

logger = logging.getLogger(__name__)


def is_stale(path: Path, document: StoredDoc) -> bool:
    try:
        stat = path.stat()
    except OSError:
        return True

    if stat.st_size != document.size_bytes:
        return True

    file_mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    doc_modified = document.modified_at
    if doc_modified.tzinfo is None:
        doc_modified = doc_modified.replace(tzinfo=timezone.utc)
    if abs((file_mtime - doc_modified).total_seconds()) > 1.0:
        return True

    try:
        data = path.read_bytes()
    except OSError:
        return True
    _crc32, sha256 = file_checksums(data)
    return sha256 != document.sha256


def walk_document_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        files.append(path)
    return files


async def reconcile_index(queue: IndexQueue, store: DocStore, parser: Parser) -> None:
    logger.info("Starting index reconciliation")
    root = documents_root()
    docs = {document.path: document for document in store.list_all_docs()}
    seen: set[str] = set()

    retried_failed = 0
    for file_path in walk_document_files(root):
        relative = file_path.relative_to(root).as_posix()
        seen.add(relative)
        document = docs.get(relative)
        supported = parser.is_supported(file_path.suffix)
        if document is None:
            # New file: enqueue index. The worker indexes supported formats and
            # records unsupported ones as unindexable (chunk_count=None), so
            # every disk file ends up in the DB either way.
            await queue.submit(IndexTask(path=relative, kind="index"))
        elif document.chunk_count is None:
            if not supported:
                # Already recorded as unindexable; retrying can never succeed.
                logger.debug("Keeping unsupported file without retry: path=%s", relative)
                continue
            # Supported file that failed for a transient reason: force a rebuild.
            # A plain "index" would be skipped by the sha256 guard because
            # mark_failed stored the current file checksum on failure.
            logger.debug("Retrying previously failed document: path=%s", relative)
            await queue.submit(IndexTask(path=relative, kind="reindex"))
            retried_failed += 1
        elif is_stale(file_path, document):
            await queue.submit(IndexTask(path=relative, kind="index"))

    for path in sorted(docs.keys() - seen):
        await queue.submit(IndexTask(path=path, kind="delete"))

    logger.info(
        "Index reconciliation finished (disk_files=%d, indexed=%d, retried_failed=%d)",
        len(seen),
        len(docs),
        retried_failed,
    )


def probe_documents_dir_path() -> Path:
    return get_documents_dir()
