"""Force reindex of matching indexed documents via the index queue."""

from __future__ import annotations

import logging
from typing import Any

from server.engine.doc_store import DocStore
from server.errors import ServiceError
from server.responses import success
from server.services.index_queue import IndexQueue, IndexTask

logger = logging.getLogger(__name__)


async def request_reindex(store: DocStore, queue: IndexQueue, path: str) -> dict[str, Any]:
    if not path or not path.strip():
        raise ServiceError(
            400,
            "Path filter required",
            hint="Provide a regex matching root-relative paths to reindex.",
        )
    normalized = path.strip()

    matched = store.matching_doc_paths(normalized)
    if not matched:
        raise ServiceError(
            404,
            f"No indexed files match: {path}",
            hint="Call GET /api/list_files to see indexed paths.",
        )

    logger.debug("Queueing reindex: pattern=%r matches=%d", normalized, len(matched))
    for relative in matched:
        await queue.submit(IndexTask(path=relative, kind="reindex"))
    logger.info("Queued reindex for %d file(s) matching %r", len(matched), normalized)

    return success({"path": normalized, "count": len(matched), "matched": matched})
