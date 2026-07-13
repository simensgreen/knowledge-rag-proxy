"""File list/status business logic."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any

from server.engine.doc_store import DocStore
from server.engine.protocols import Parser
from server.errors import ServiceError
from server.responses import success
from server.services.index_queue import IndexQueue
from server.services.serializers import doc_to_list_item


def list_files(
    store: DocStore,
    path_regex: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    normalized_regex = ""
    if path_regex and path_regex.strip():
        normalized_regex = path_regex.strip()
        try:
            re.compile(normalized_regex)
        except re.error as error:
            raise ServiceError(
                400,
                f"Invalid path regex: {path_regex}",
                hint=f"Fix the regex pattern: {error}",
            ) from error

    documents, total = store.list_documents(normalized_regex or None, limit, offset)
    files = [doc_to_list_item(document) for document in documents]
    return success(
        {
            "path": normalized_regex,
            "total": total,
            "count": len(files),
            "offset": offset,
            "limit": limit,
            "files": files,
        }
    )


def status(store: DocStore, queue: IndexQueue, parser: Parser) -> dict[str, Any]:
    stats = store.count_stats()
    indexing = queue.snapshot().to_indexing_or_none()

    # Docs with chunk_count=None are either supported files that failed a
    # transient step (retryable) or unsupported formats recorded as-is; the
    # split is derived from the parser, never persisted, to avoid a stale field.
    failed = 0
    unsupported = 0
    for path in store.failed_doc_paths():
        if parser.is_supported(PurePosixPath(path).suffix):
            failed += 1
        else:
            unsupported += 1

    return success(
        {
            "documents": stats["documents"],
            "chunks": stats["chunks"],
            "failed": failed,
            "unsupported": unsupported,
            "indexing": indexing,
        }
    )
