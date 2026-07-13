"""File read/list/status business logic."""

from __future__ import annotations

import re
from typing import Any

from server.engine.protocols import Engine
from server.errors import ServiceError
from server.paths import relativize
from server.responses import success


def get_file(engine: Engine, path: str) -> dict[str, Any]:
    if not path or not path.strip():
        raise ServiceError(400, "Path required", hint="Provide the path of an indexed file.")
    document = engine.get_file(path.strip())
    if document is None:
        raise ServiceError(
            404,
            f"File not found: {path}",
            hint="Call GET /list_files to see indexed paths, or POST /upload to add the file.",
        )
    return success({"file": relativize(document)})


def list_files(
    engine: Engine,
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

    page, total = engine.list_files(normalized_regex or None, limit, offset)
    return success(
        {
            "path": normalized_regex,
            "total": total,
            "count": len(page),
            "offset": offset,
            "limit": limit,
            "files": relativize(page),
        }
    )


def status(engine: Engine) -> dict[str, Any]:
    stats = engine.stats()
    return success(stats)
