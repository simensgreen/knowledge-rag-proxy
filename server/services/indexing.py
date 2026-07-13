"""Index task processing (worker-only)."""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

from starlette.concurrency import run_in_threadpool

from server.engine.doc_store import DocStore
from server.engine.ingest.prepare import file_checksums, prepare_file, prepare_markdown
from server.engine.protocols import EmbeddingProvider, Parser
from server.paths import resolve_allowed_path
from server.services.index_queue import IndexQueue, IndexTask

logger = logging.getLogger(__name__)


def process_task(
    task: IndexTask,
    *,
    store: DocStore,
    parser: Parser,
    embedder: EmbeddingProvider,
    embedding_model: str,
) -> None:
    if task.kind == "delete":
        removed = store.remove_by_path(task.path)
        if removed:
            logger.info("Removed indexed document: %s", task.path)
        else:
            logger.debug("Delete task skipped; document not indexed: %s", task.path)
        return

    if task.kind == "move":
        if not task.dest_path:
            raise ValueError("move task requires dest_path")
        renamed = store.rename_path(task.path, task.dest_path)
        if renamed is None:
            logger.debug("Move task skipped; source not indexed: %s", task.path)
        else:
            logger.info("Renamed indexed document: %s -> %s", task.path, task.dest_path)
        return

    if task.kind == "reindex_markdown":
        if task.markdown is None:
            raise ValueError("reindex_markdown task requires markdown")
        document = store.get_doc_by_path(task.path)
        if document is None:
            abs_path = resolve_allowed_path(task.path)
            prepared = prepare_file(
                abs_path,
                task.path,
                task.markdown,
                parser=parser,
                embedder=embedder,
                embedding_model=embedding_model,
                description=task.description,
            )
            store.upsert_prepared(prepared, preserve_description=True)
            logger.info("Indexed document from markdown replace: %s", task.path)
            return
        chunks = prepare_markdown(
            task.markdown,
            Path(task.path).name,
            document.id,
            embedder=embedder,
        )
        store.replace_chunks(document.id, chunks)
        logger.info("Replaced markdown chunks for: %s (%d chunks)", task.path, len(chunks))
        return

    abs_path = resolve_allowed_path(task.path)
    data = abs_path.read_bytes()
    crc32, sha256 = file_checksums(data)
    existing = store.get_doc_by_path(task.path)

    if (
        task.kind == "index"
        and existing is not None
        and existing.sha256 == sha256
        and task.markdown is None
    ):
        logger.debug("Index skipped; checksum unchanged: %s", task.path)
        return

    if task.markdown is None and not parser.is_supported(abs_path.suffix):
        # Unsupported formats cannot be parsed; record them as unindexable
        # (chunk_count=None) instead of raising, so they still appear in the DB.
        store.mark_failed(
            task.path,
            size_bytes=len(data),
            crc32=crc32,
            sha256=sha256,
            embedding_model=embedding_model,
        )
        logger.warning("Recorded unsupported file as unindexable (chunk_count=None): %s", task.path)
        return

    prepared = prepare_file(
        abs_path,
        task.path,
        task.markdown,
        parser=parser,
        embedder=embedder,
        embedding_model=embedding_model,
        description=task.description,
        doc_id=existing.id if existing is not None else None,
    )
    prepared = replace(
        prepared,
        doc=prepared.doc.model_copy(
            update={
                "crc32": crc32,
                "sha256": sha256,
                "size_bytes": len(data),
            }
        ),
    )
    store.upsert_prepared(prepared, preserve_description=True)
    logger.info(
        "Indexed document: %s (kind=%s, chunks=%d)",
        task.path,
        task.kind,
        len(prepared.chunks),
    )


def mark_task_failed(
    task: IndexTask,
    *,
    store: DocStore,
    embedding_model: str,
) -> None:
    try:
        abs_path = resolve_allowed_path(task.path)
        data = abs_path.read_bytes() if abs_path.is_file() else b""
        crc32, sha256 = file_checksums(data) if data else (b"\x00" * 4, b"\x00" * 32)
        store.mark_failed(
            task.path,
            size_bytes=len(data),
            crc32=crc32,
            sha256=sha256,
            embedding_model=embedding_model,
        )
    except Exception:
        logger.exception("Failed to mark document as failed: %s", task.path)


async def run_index_worker(
    queue: IndexQueue,
    *,
    store: DocStore,
    parser: Parser,
    embedder: EmbeddingProvider,
    embedding_model: str,
) -> None:
    logger.info("Index worker started")
    while True:
        task = await queue.pop()
        logger.debug("Index worker processing: path=%s kind=%s", task.path, task.kind)
        try:
            await run_in_threadpool(
                process_task,
                task,
                store=store,
                parser=parser,
                embedder=embedder,
                embedding_model=embedding_model,
            )
        except Exception:
            logger.exception("Index task failed: path=%s kind=%s", task.path, task.kind)
            await run_in_threadpool(
                mark_task_failed,
                task,
                store=store,
                embedding_model=embedding_model,
            )
        finally:
            await queue.done()
