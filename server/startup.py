"""Server startup tasks."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from server.env_config import get_documents_dir

logger = logging.getLogger(__name__)

_MACOS_TCC_HINT = (
    "On macOS this is usually a privacy restriction (TCC): grant the process "
    "running the server Full Disk Access, or move the data root out of protected "
    "locations such as ~/Documents, ~/Desktop, or ~/Downloads and update "
    "GRIM_DOCUMENTS_DIR."
)


def _probe_readable(path: Path, label: str) -> None:
    if not path.is_dir():
        raise RuntimeError(
            f"{label} does not exist or is not a directory: {path}. "
            "Set GRIM_DOCUMENTS_DIR to a readable folder."
        )
    try:
        with os.scandir(path) as entries:
            for _ in entries:
                break
    except OSError as error:
        raise RuntimeError(
            f"{label} is not readable: {path} ({error.strerror}). {_MACOS_TCC_HINT}"
        ) from error


def probe_documents_dir() -> None:
    """Fail fast when the documents directory is missing or unreadable."""
    documents_dir = get_documents_dir()
    _probe_readable(documents_dir, "Documents directory (GRIM_DOCUMENTS_DIR)")
    logger.info("Documents directory probe succeeded: %s", documents_dir)
