"""Server startup tasks."""

from __future__ import annotations

import os
from pathlib import Path

from mcp_server.server import KnowledgeOrchestrator

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
    """Index documents_dir before serving requests or starting the watcher."""
    from mcp_server.config import config

    _probe_readable(config.documents_dir, "Documents directory (KRP_DOCUMENTS_DIR)")

    print("[STARTUP] Beginning incremental document indexing...")
    stats = orchestrator.index_all(force=False)
    errors = stats.get("errors", 0)
    print(
        "[STARTUP] Indexing complete: "
        f"{stats.get('indexed', 0)} new, "
        f"{stats.get('updated', 0)} updated, "
        f"{stats.get('deleted', 0)} deleted, "
        f"{stats.get('skipped', 0)} skipped, "
        f"{errors} errors"
    )
    if errors:
        print(
            f"[STARTUP] WARNING: {errors} file(s) failed to index; "
            "check permissions on the documents directory and its contents."
        )
