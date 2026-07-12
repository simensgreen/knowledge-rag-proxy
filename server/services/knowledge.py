"""Knowledge-rag orchestrator business logic."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from mcp_server.config import config
from mcp_server.server import KnowledgeOrchestrator

from server.errors import ServiceError
from server.paths import relativize, to_library_path
from server.responses import success
from server.snippet import make_snippet


def _valid_categories() -> list[str]:
    return list(config.keyword_routes.keys()) + list(set(config.category_mappings.values())) + ["general"]


def search_knowledge(
    orchestrator: KnowledgeOrchestrator,
    query: str,
    max_results: int | None = 5,
    category: str | None = None,
    hybrid_alpha: float | None = 0.3,
    min_score: float | None = 0.0,
    snippet_mode: bool = True,
) -> dict[str, Any]:
    if not query or not query.strip():
        raise ServiceError(
            400,
            "Query cannot be empty",
            hint="Provide a non-empty query string with 1-3 keywords or a short phrase.",
        )

    clamped_max_results = max(1, min(max_results or 5, config.max_results))
    clamped_hybrid_alpha = max(0.0, min(hybrid_alpha if hybrid_alpha is not None else 0.3, 1.0))
    clamped_min_score = max(0.0, min(min_score if min_score is not None else 0.0, 1.0))

    valid_categories = _valid_categories()
    if category and category not in valid_categories:
        raise ServiceError(
            400,
            f"Invalid category '{category}'. Valid: {', '.join(valid_categories)}",
            hint="Call GET /list_categories to see available category names.",
        )

    results = orchestrator.query(
        query.strip(),
        max_results=clamped_max_results,
        category_filter=category,
        hybrid_alpha=clamped_hybrid_alpha,
    )

    total_before_filter = len(results)
    if clamped_min_score > 0.0:
        results = [result for result in results if result.get("score", 0) >= clamped_min_score]

    if snippet_mode:
        for result in results:
            full_length = len(result.get("content", ""))
            result["content"] = make_snippet(result["content"])
            result["content_length"] = full_length

    return success(
        {
            "query": query,
            "hybrid_alpha": clamped_hybrid_alpha,
            "result_count": len(results),
            "filtered_by_score": total_before_filter - len(results),
            "cache_hit_rate": orchestrator.query_cache.stats()["hit_rate"],
            "results": relativize(results),
        }
    )


def get_document(orchestrator: KnowledgeOrchestrator, filepath: str) -> dict[str, Any]:
    document = orchestrator.get_document(to_library_path(filepath))
    if not document:
        raise ServiceError(
            404,
            f"Document not found: {filepath}",
            hint="Call GET /list_documents to see indexed filepaths, or POST /upload to add the file.",
        )
    return success({"document": relativize(document)})


def reindex_documents(
    orchestrator: KnowledgeOrchestrator,
    force: bool = False,
    full_rebuild: bool = False,
) -> dict[str, Any]:
    if full_rebuild:
        mode = "nuclear_rebuild"
    elif force:
        mode = "smart_reindex"
    else:
        mode = "incremental"

    result = orchestrator.start_reindex_background(mode)

    if result["status"] == "already_running":
        progress = result["progress"]
        raise ServiceError(
            400,
            "Reindex already running",
            hint="Call GET /get_reindex_status to monitor progress.",
        )

    return success(
        {
            "operation": mode,
            "message": "Reindex running in background. Use GET /get_reindex_status to monitor progress.",
        }
    )


def get_reindex_status(orchestrator: KnowledgeOrchestrator) -> dict[str, Any]:
    return success({"reindex": orchestrator.get_reindex_status()})


def list_categories(orchestrator: KnowledgeOrchestrator) -> dict[str, Any]:
    categories = orchestrator.list_categories()
    return success(
        {
            "categories": categories,
            "total_documents": sum(categories.values()),
        }
    )


def _source_under_prefix(source: str, prefix: PurePosixPath) -> bool:
    """True when a root-relative source lies at or under the path prefix."""
    if not source:
        return False
    candidate = PurePosixPath(source)
    return candidate == prefix or prefix in candidate.parents


def list_documents(
    orchestrator: KnowledgeOrchestrator,
    category: str | None = None,
    path: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    # Relativize first so the path filter operates on the same root-relative
    # paths the client sees; the library returns absolute paths.
    documents = relativize(orchestrator.list_documents(category=category))

    normalized_path = ""
    if path and path.strip():
        candidate = path.strip().strip("/")
        if ".." in PurePosixPath(candidate).parts:
            raise ServiceError(
                400,
                f"Invalid path filter: {path}",
                hint="Use a path relative to the documents root, without '..'.",
            )
        normalized_path = candidate
        if normalized_path:
            prefix = PurePosixPath(normalized_path)
            documents = [
                document
                for document in documents
                if _source_under_prefix(document.get("source", ""), prefix)
            ]

    total = len(documents)
    page = documents[offset : offset + limit]
    return success(
        {
            "filter": category or "all",
            "path": normalized_path,
            "total": total,
            "count": len(page),
            "offset": offset,
            "limit": limit,
            "documents": page,
        }
    )


def get_index_stats(orchestrator: KnowledgeOrchestrator) -> dict[str, Any]:
    return success({"stats": orchestrator.get_stats()})


def update_document(
    orchestrator: KnowledgeOrchestrator,
    filepath: str,
    content: str,
) -> dict[str, Any]:
    if not filepath:
        raise ServiceError(400, "Filepath required", hint="Provide the path of an existing indexed document.")
    if not content or not content.strip():
        raise ServiceError(400, "Content cannot be empty", hint="Provide the new full document text.")

    result = orchestrator.update_document_content(to_library_path(filepath), content.strip())
    if "error" in result:
        message = result["error"]
        # The library echoes the absolute path in "not found" messages; report
        # the client's own relative path instead so no absolute path leaks.
        if "not found" in message.lower():
            raise ServiceError(
                404,
                f"Document not found: {filepath}",
                hint="Call GET /list_documents to see indexed filepaths.",
            )
        raise ServiceError(400, message)
    return success(relativize(result))


def remove_document(
    orchestrator: KnowledgeOrchestrator,
    filepath: str,
    delete_file: bool = False,
) -> dict[str, Any]:
    if not filepath:
        raise ServiceError(400, "Filepath required", hint="Provide the path of an indexed document.")

    result = orchestrator.remove_document_by_path(to_library_path(filepath), delete_file=delete_file)
    if "error" in result:
        # Report the client's relative path, not the library's absolute one.
        raise ServiceError(
            404,
            f"Document not found in index: {filepath}",
            hint="Call GET /list_documents to see indexed filepaths.",
        )
    return success(relativize(result))


def search_similar(
    orchestrator: KnowledgeOrchestrator,
    filepath: str,
    max_results: int | None = 5,
) -> dict[str, Any]:
    if not filepath:
        raise ServiceError(400, "Filepath required", hint="Provide a path to an indexed reference document.")

    clamped_max_results = max(1, min(max_results or 5, 20))
    results = orchestrator.search_similar(to_library_path(filepath), max_results=clamped_max_results)

    return success(
        {
            "reference": filepath,
            "count": len(results),
            "similar_documents": relativize(results),
        }
    )


def health_payload(orchestrator: KnowledgeOrchestrator) -> dict[str, Any]:
    stats = orchestrator.get_stats()
    return success(
        {
            "ok": True,
            "version": "0.1.0",
            "documents": stats.get("total_documents", 0),
        }
    )
