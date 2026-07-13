"""Server startup tasks."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from mcp_server.server import KnowledgeOrchestrator

logger = logging.getLogger(__name__)

_MACOS_TCC_HINT = (
    "On macOS this is usually a privacy restriction (TCC): grant the process "
    "running the server Full Disk Access (System Settings > Privacy & Security "
    "> Full Disk Access), or move the data root out of protected locations such "
    "as ~/Documents, ~/Desktop, or ~/Downloads and update KNOWLEDGE_RAG_DIR / "
    "KRP_DOCUMENTS_DIR."
)


def _probe_readable(path: Path, label: str) -> None:
    """Raise RuntimeError if path is not an existing, listable directory.

    os.walk (used by parse_directory) swallows access errors silently, so a
    TCC-protected folder on macOS would index zero files and report success.
    Probe with os.scandir, which surfaces the error. KRP_DOCUMENTS_DIR is never
    auto-created by the proxy, so a failing probe reflects a real access problem
    rather than an empty folder the process created itself.
    """
    if not path.is_dir():
        raise RuntimeError(
            f"{label} does not exist or is not a directory: {path}. "
            "Set KNOWLEDGE_RAG_DIR / KRP_DOCUMENTS_DIR to a readable folder."
        )
    try:
        with os.scandir(path) as entries:
            for _ in entries:
                break
    except OSError as error:
        raise RuntimeError(
            f"{label} is not readable: {path} ({error.strerror}). {_MACOS_TCC_HINT}"
        ) from error


def index_documents_on_startup(orchestrator: KnowledgeOrchestrator) -> None:
    """Kick off incremental indexing in the background so the server serves immediately.

    The readability probe stays synchronous: it is a fast scandir that surfaces a
    real access problem (e.g. macOS TCC) at boot rather than letting the server
    come up and silently index zero files. The indexing itself runs in a daemon
    thread (via the library's background reindex), so requests are served right
    away; clients monitor progress with GET /get_reindex_status.
    """
    from mcp_server.config import config

    _probe_readable(config.documents_dir, "Documents directory (KRP_DOCUMENTS_DIR)")

    logger.debug("Starting incremental document indexing in background")
    result = orchestrator.start_reindex_background("incremental")
    if result.get("status") == "already_running":
        logger.info("Startup index skipped: indexing already running")
        return
    logger.info(
        "Server ready; background indexing in progress (monitor via GET /get_reindex_status)"
    )
