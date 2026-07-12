"""FastAPI dependencies."""

from __future__ import annotations

from mcp_server.server import KnowledgeOrchestrator, get_orchestrator


def get_orchestrator_dep() -> KnowledgeOrchestrator:
    return get_orchestrator()
