"""Stub parser returning canned markdown for Phase 1 scaffold."""

from __future__ import annotations

from pathlib import Path

from server.engine.models import MarkdownResult
from server.engine.protocols import Parser

_STUB_MARKDOWN = "# stub markdown\n"


class StubParser(Parser):
    def convert_bytes(self, filename: str, data: bytes) -> MarkdownResult:
        if len(data) == 0:
            raise ValueError("empty file")
        suffix = Path(filename).suffix.lower()
        return MarkdownResult(
            filename=Path(filename).name,
            format=suffix.lstrip(".") or "bin",
            markdown=_STUB_MARKDOWN,
            metadata={},
        )

    def convert_file(self, path: Path) -> MarkdownResult:
        return MarkdownResult(
            filename=path.name,
            format=path.suffix.lstrip(".") or "bin",
            markdown=_STUB_MARKDOWN,
            metadata={},
        )

    def is_supported(self, suffix: str) -> bool:
        normalized = suffix if suffix.startswith(".") else f".{suffix}"
        return normalized.lower() in {".md", ".txt", ".pdf", ".docx", ".pptx", ".xlsx"}

    def supported_formats(self) -> list[str]:
        return ["md", "txt", "pdf", "docx", "pptx", "xlsx"]
