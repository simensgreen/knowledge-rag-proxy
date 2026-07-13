"""File content API: reconstruct/replace markdown in the index."""

from __future__ import annotations

from typing import Any

from server.engine.doc_store import DocStore
from server.errors import ServiceError
from server.paths import to_relative_path
from server.responses import success
from server.services.index_queue import IndexQueue, IndexTask


def get_content(store: DocStore, path: str) -> dict[str, Any]:
    if not path or not path.strip():
        raise ServiceError(400, "Path required", hint="Provide the root-relative path of an indexed file.")
    normalized = to_relative_path(path)
    markdown = store.get_markdown_content(normalized)
    if markdown is None:
        raise ServiceError(
            404,
            f"File not found: {path}",
            hint="Wait for indexing to finish, or call GET /api/status.",
        )
    return success({"path": normalized, "markdown": markdown})


async def replace_content(queue: IndexQueue, path: str, markdown: str) -> dict[str, Any]:
    if not path or not path.strip():
        raise ServiceError(400, "Path required", hint="Provide the root-relative path of an indexed file.")
    if markdown is None:
        raise ServiceError(400, "Markdown required", hint="Provide non-empty markdown content.")
    normalized = to_relative_path(path)
    await queue.submit(
        IndexTask(path=normalized, kind="reindex_markdown", markdown=markdown)
    )
    return success({"path": normalized})
