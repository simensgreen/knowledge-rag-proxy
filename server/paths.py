"""Path translation across the API boundary.

The API speaks only in paths relative to the documents root (GRIM_DOCUMENTS_DIR).
This module is the single crossing point: inbound API paths get the root prefix
added before an engine call, and every path handed back has the prefix stripped
before it reaches the client.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from server import env_config
from server.errors import ServiceError

_PATH_KEYS = frozenset({"path", "source_path", "dest_path", "top_result"})


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


def to_root_path(filepath: str) -> str:
    return str(resolve_allowed_path(filepath))


def to_api_path(path: str) -> str:
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
    if isinstance(payload, dict):
        return {
            key: (to_api_path(value) if key in _PATH_KEYS and isinstance(value, str) else relativize(value))
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [relativize(item) for item in payload]
    return payload
