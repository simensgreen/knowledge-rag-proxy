"""Search business logic."""

from __future__ import annotations

from typing import Any

from server.engine.doc_store import DocStore
from server.engine.protocols import EmbeddingProvider
from server.errors import ServiceError
from server.responses import success

DEFAULT_MAX_RESULTS = 5


def search(
    store: DocStore,
    embedder: EmbeddingProvider,
    query: str,
    max_results: int | None = None,
) -> dict[str, Any]:
    if not query or not query.strip():
        raise ServiceError(
            400,
            "Query cannot be empty",
            hint="Provide a non-empty query string with 1-3 keywords or a short phrase.",
        )

    normalized_query = query.strip()
    effective_max_results = max(1, max_results or DEFAULT_MAX_RESULTS)

    vectors = embedder.embed([normalized_query])
    query_embedding = vectors[0] if vectors else []
    results = store.search(normalized_query, query_embedding, effective_max_results)

    return success(
        {
            "query": query,
            "result_count": len(results),
            "results": results,
        }
    )
