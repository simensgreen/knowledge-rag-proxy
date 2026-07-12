"""Path translation across the API boundary.

The API speaks only in paths relative to the documents root (KRP_DOCUMENTS_DIR).
knowledge-rag stores and returns absolute filesystem paths. This module is the
single crossing point: inbound API paths get the root prefix added before a
library call, and every path the library hands back has the prefix stripped
before it reaches the client. An absolute filesystem path (and the user's home
layout) must never reach the LLM.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from server import env_config
from server.errors import ServiceError

# Response keys whose string values are filesystem paths to relativize.
_PATH_KEYS = frozenset({"source", "filepath", "top_result"})


def documents_root() -> Path:
    """Absolute documents root; the only folder the API exposes."""
    return env_config.get_allowed_roots()[0]


def _contains_parent_reference(filepath: str) -> bool:
    return ".." in Path(filepath).parts


def resolve_allowed_path(filepath: str) -> Path:
    """Resolve an API path to an absolute Path under the documents root.

    Accepts a path relative to the root (the normal case) or an absolute path
    that already lies inside it. Raises ServiceError(400) for '..' or anything
    resolving outside the root.
    """
    if _contains_parent_reference(filepath):
        raise ServiceError(
            400,
            f"Invalid filepath: {filepath}",
            hint="Use a path relative to the documents root, without '..'.",
        )
    root = documents_root()
    candidate = Path(filepath)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    if not resolved.is_relative_to(root):
        raise ServiceError(
            400,
            f"Filepath outside the documents directory: {filepath}",
            hint="Paths must stay within the documents root.",
        )
    return resolved


def to_library_path(filepath: str) -> str:
    """API path (root-relative) -> absolute path string for knowledge-rag."""
    return str(resolve_allowed_path(filepath))


def to_api_path(path: str) -> str:
    """knowledge-rag path -> path relative to the documents root.

    A path inside the root becomes its root-relative form. Anything already
    relative is returned as-is; anything absolute but outside the root collapses
    to its bare name, so an absolute filesystem path never crosses the boundary.
    """
    if not path:
        return path
    resolved = Path(path)
    if not resolved.is_absolute():
        return resolved.as_posix()
    root = documents_root()
    if resolved.is_relative_to(root):
        return resolved.relative_to(root).as_posix()
    return resolved.name


def relativize(payload: Any) -> Any:
    """Recursively rewrite known path-bearing keys to their root-relative form.

    Walks dicts and lists so nested structures (search results, an embedded
    document block) are covered by a single call.
    """
    if isinstance(payload, dict):
        return {
            key: (to_api_path(value) if key in _PATH_KEYS and isinstance(value, str) else relativize(value))
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [relativize(item) for item in payload]
    return payload
