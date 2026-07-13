"""Engine domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Chunk:
    chunk_index: int
    content: str


@dataclass(frozen=True)
class ParsedDocument:
    path: str
    filename: str
    format: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    keywords: list[str] = field(default_factory=list)
    chunks: list[Chunk] = field(default_factory=list)


@dataclass(frozen=True)
class SearchResult:
    content: str
    score: float
    path: str
    filename: str


@dataclass(frozen=True)
class MarkdownResult:
    filename: str
    format: str
    markdown: str
    metadata: dict[str, Any] = field(default_factory=dict)
