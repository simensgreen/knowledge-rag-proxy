"""Abstract provider protocols (embedding, parser)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from server.engine.models import MarkdownResult


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""


class Parser(ABC):
    @abstractmethod
    def convert_bytes(self, filename: str, data: bytes) -> MarkdownResult:
        """Convert uploaded bytes to markdown."""

    @abstractmethod
    def convert_file(self, path: Path) -> MarkdownResult:
        """Convert a file on disk to markdown."""

    @abstractmethod
    def is_supported(self, suffix: str) -> bool:
        """True when the suffix can be parsed."""

    @abstractmethod
    def supported_formats(self) -> list[str]:
        """Supported file extensions without leading dot."""
