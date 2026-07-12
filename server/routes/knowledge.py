"""MCP tool routes and health."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from mcp_server.server import KnowledgeOrchestrator

from server.deps import get_orchestrator_dep
from server.responses import cache_read_only, no_store
from server.schemas import (
    ReindexDocumentsRequest,
    RemoveDocumentRequest,
    UpdateDocumentRequest,
)
from server.services import knowledge as knowledge_service

router = APIRouter()

OrchestratorDep = Annotated[KnowledgeOrchestrator, Depends(get_orchestrator_dep)]


@router.get("/health", dependencies=[Depends(no_store)])
def health(orchestrator: OrchestratorDep) -> dict:
    return knowledge_service.health_payload(orchestrator)


@router.get("/search_knowledge", dependencies=[Depends(cache_read_only)])
def search_knowledge(
    orchestrator: OrchestratorDep,
    query: Annotated[str, Query()],
    max_results: Annotated[int | None, Query()] = 5,
    category: Annotated[str | None, Query()] = None,
    hybrid_alpha: Annotated[float | None, Query()] = 0.3,
    min_score: Annotated[float | None, Query()] = 0.0,
    snippet_mode: Annotated[bool, Query()] = True,
) -> dict:
    return knowledge_service.search_knowledge(
        orchestrator,
        query=query,
        max_results=max_results,
        category=category,
        hybrid_alpha=hybrid_alpha,
        min_score=min_score,
        snippet_mode=snippet_mode,
    )


@router.get("/get_document", dependencies=[Depends(cache_read_only)])
def get_document(
    orchestrator: OrchestratorDep,
    filepath: Annotated[str, Query()],
) -> dict:
    return knowledge_service.get_document(orchestrator, filepath)


@router.get("/list_categories", dependencies=[Depends(cache_read_only)])
def list_categories(orchestrator: OrchestratorDep) -> dict:
    return knowledge_service.list_categories(orchestrator)


@router.get("/list_documents", dependencies=[Depends(cache_read_only)])
def list_documents(
    orchestrator: OrchestratorDep,
    category: Annotated[str | None, Query()] = None,
    path: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    return knowledge_service.list_documents(
        orchestrator,
        category=category,
        path=path,
        limit=limit,
        offset=offset,
    )


@router.get("/get_index_stats", dependencies=[Depends(cache_read_only)])
def get_index_stats(orchestrator: OrchestratorDep) -> dict:
    return knowledge_service.get_index_stats(orchestrator)


@router.get("/search_similar", dependencies=[Depends(cache_read_only)])
def search_similar(
    orchestrator: OrchestratorDep,
    filepath: Annotated[str, Query()],
    max_results: Annotated[int | None, Query()] = 5,
) -> dict:
    return knowledge_service.search_similar(
        orchestrator,
        filepath=filepath,
        max_results=max_results,
    )


@router.get("/get_reindex_status", dependencies=[Depends(no_store)])
def get_reindex_status(orchestrator: OrchestratorDep) -> dict:
    return knowledge_service.get_reindex_status(orchestrator)


@router.post("/reindex_documents")
def reindex_documents(
    body: ReindexDocumentsRequest,
    orchestrator: OrchestratorDep,
) -> dict:
    return knowledge_service.reindex_documents(
        orchestrator,
        force=body.force,
        full_rebuild=body.full_rebuild,
    )


@router.post("/update_document")
def update_document(
    body: UpdateDocumentRequest,
    orchestrator: OrchestratorDep,
) -> dict:
    return knowledge_service.update_document(
        orchestrator,
        filepath=body.filepath,
        content=body.content,
    )


@router.post("/remove_document")
def remove_document(
    body: RemoveDocumentRequest,
    orchestrator: OrchestratorDep,
) -> dict:
    return knowledge_service.remove_document(
        orchestrator,
        filepath=body.filepath,
        delete_file=body.delete_file,
    )
