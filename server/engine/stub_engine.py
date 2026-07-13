"""Stub engine returning canned data for Phase 1 scaffold."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from server.engine.protocols import Engine

_STUB_FORMATS = [".md", ".txt", ".pdf", ".docx", ".pptx", ".xlsx"]

_STUB_FILES = [
    {"id": "0", "path": "docs/a.md", "format": "md", "chunks": 1},
    {"id": "1", "path": "docs/b.md", "format": "md", "chunks": 1},
    {"id": "2", "path": "notes/c.md", "format": "md", "chunks": 1},
    {"id": "3", "path": "notes/sub/d.md", "format": "md", "chunks": 1},
]


class StubEngine(Engine):
    def search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        del query
        return [
            {
                "content": "sample content",
                "score": 0.9,
                "path": "docs/a.md",
                "filename": "a.md",
            }
        ][:max_results]

    def get_file(self, path: str) -> dict[str, Any] | None:
        if Path(path).name == "missing.md":
            return None
        return {
            "content": "full text",
            "path": path,
            "filename": Path(path).name,
            "format": Path(path).suffix.lstrip(".") or "md",
            "metadata": {},
            "keywords": [],
            "chunk_count": 1,
        }

    def list_files(
        self,
        path_regex: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        documents = list(_STUB_FILES)
        if path_regex:
            pattern = re.compile(path_regex)
            documents = [document for document in documents if pattern.search(document["path"])]
        total = len(documents)
        page = documents[offset : offset + limit]
        return page, total

    def stats(self) -> dict[str, Any]:
        return {
            "documents": 1,
            "chunks": 3,
            "indexing": {"active": False},
        }

    def index_file(self, path: Path) -> dict[str, Any]:
        return {
            "path": str(path),
            "format": path.suffix.lstrip("."),
            "chunks_added": 2,
        }

    def remove_by_path(self, path: str) -> dict[str, Any] | None:
        if Path(path).name == "missing.md":
            return None
        return {"path": path, "chunks_removed": 1}

    def is_supported(self, suffix: str) -> bool:
        normalized = suffix if suffix.startswith(".") else f".{suffix}"
        return normalized.lower() in _STUB_FORMATS

    def supported_formats(self) -> list[str]:
        return [extension.lstrip(".") for extension in _STUB_FORMATS]
