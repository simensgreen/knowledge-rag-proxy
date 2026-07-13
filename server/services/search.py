"""Search business logic."""

from __future__ import annotations

from typing import Any

from server.engine.protocols import Engine
from server.env_config import get_search_default_results, get_search_max_results
from server.errors import ServiceError
from server.paths import relativize
from server.responses import success


def search(engine: Engine, query: str, max_results: int | None = None) -> dict[str, Any]:
    if not query or not query.strip():
        raise ServiceError(
            400,
            "Query cannot be empty",
            hint="Provide a non-empty query string with 1-3 keywords or a short phrase.",
        )

    default_results = get_search_default_results()
    clamped_max_results = max(1, min(max_results or default_results, get_search_max_results()))
    results = engine.search(query.strip(), clamped_max_results)

    return success(
        {
            "query": query,
            "result_count": len(results),
            "results": relativize(results),
        }
    )
