"""Engine protocol definitions (Phase 2 implementations swap in later)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from server.engine.models import MarkdownResult, ParsedDocument


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""


class OcrProvider(ABC):
    @abstractmethod
    def extract_text(self, image_bytes: bytes, filename: str) -> str:
        """Return OCR text for an image."""


class Store(ABC):
    @abstractmethod
    def upsert_document(self, document: ParsedDocument) -> int:
        """Persist document chunks; return chunks written."""


class Parser(ABC):
    @abstractmethod
    def convert_bytes(self, filename: str, data: bytes) -> MarkdownResult:
        """Convert uploaded bytes to markdown."""

    @abstractmethod
    def convert_file(self, path: Path) -> MarkdownResult:
        """Convert a file on disk to markdown (Phase 2 indexing/watcher)."""

    @abstractmethod
    def is_supported(self, suffix: str) -> bool:
        """True when the suffix can be parsed."""

    @abstractmethod
    def supported_formats(self) -> list[str]:
        """Supported file extensions without leading dot."""


class Engine(ABC):
    @abstractmethod
    def search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        """Search indexed content."""

    @abstractmethod
    def get_file(self, path: str) -> dict[str, Any] | None:
        """Return indexed document payload for a root-relative path."""

    @abstractmethod
    def list_files(
        self,
        path_regex: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """List indexed files; return (page, total)."""

    @abstractmethod
    def stats(self) -> dict[str, Any]:
        """Index statistics for /status."""

    @abstractmethod
    def index_file(self, path: Path) -> dict[str, Any]:
        """Index a file already on disk."""

    @abstractmethod
    def remove_by_path(self, path: str) -> dict[str, Any] | None:
        """Remove from index; return None when not indexed."""

    @abstractmethod
    def is_supported(self, suffix: str) -> bool:
        """True when the suffix can be indexed."""

    @abstractmethod
    def supported_formats(self) -> list[str]:
        """Supported file extensions without leading dot."""
