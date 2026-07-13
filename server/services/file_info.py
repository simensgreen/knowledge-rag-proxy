"""File info API: read/update StoredDoc metadata."""

from __future__ import annotations

from typing import Any

from server.engine.doc_store import DocStore
from server.errors import ServiceError
from server.paths import to_relative_path
from server.responses import success
from server.services.serializers import doc_to_api


def get_info(store: DocStore, path: str) -> dict[str, Any]:
    if not path or not path.strip():
        raise ServiceError(400, "Path required", hint="Provide the root-relative path of an indexed file.")
    document = store.get_doc_by_path(to_relative_path(path))
    if document is None:
        raise ServiceError(
            404,
            f"File not found: {path}",
            hint="Wait for indexing to finish, or call GET /api/status / GET /api/list_files.",
        )
    return success({"file": doc_to_api(document)})


def update_description(store: DocStore, path: str, description: str | None) -> dict[str, Any]:
    if not path or not path.strip():
        raise ServiceError(400, "Path required", hint="Provide the root-relative path of an indexed file.")
    document = store.update_description(to_relative_path(path), description)
    if document is None:
        raise ServiceError(
            404,
            f"File not found: {path}",
            hint="Wait for indexing to finish, then retry updating description.",
        )
    return success({"file": doc_to_api(document)})
