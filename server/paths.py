"""Path boundary for the documents root (GRIM_DOCUMENTS_DIR).

The API and everything below it speak in root-relative POSIX paths. This module
is the single sanitizing crossing point: an inbound API path is validated and
canonicalized here (`to_relative_path`) exactly once, then stored in the DB,
submitted to the index queue, and echoed back verbatim. Downstream code never
re-sanitizes because those paths are already root-relative.
"""

from __future__ import annotations

from pathlib import Path

from server import env_config
from server.errors import ServiceError


def documents_root() -> Path:
    return env_config.get_allowed_roots()[0]


def _contains_parent_reference(filepath: str) -> bool:
    return ".." in Path(filepath).parts


def resolve_allowed_path(filepath: str) -> Path:
    if _contains_parent_reference(filepath):
        raise ServiceError(
            400,
            f"Invalid path: {filepath}",
            hint="Use a path relative to the documents root, without '..'.",
        )
    root = documents_root()
    candidate = Path(filepath)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    if not resolved.is_relative_to(root):
        raise ServiceError(
            400,
            f"Path outside the documents directory: {filepath}",
            hint="Paths must stay within the documents root.",
        )
    return resolved


def to_relative_path(filepath: str) -> str:
    """Validate an API-supplied path and return its canonical root-relative form.

    The one place inbound paths are sanitized: the result is safe to store,
    queue, or return without any further normalization.
    """
    resolved = resolve_allowed_path(filepath)
    return resolved.relative_to(documents_root()).as_posix()
