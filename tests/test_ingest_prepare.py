"""Tests for prepare_markdown / prepare_file."""

from __future__ import annotations

from pathlib import Path

import pytest

from server.engine.ingest.prepare import prepare_file, prepare_markdown
from server.engine.models import MarkdownResult


class MockEmbedder:
    def __init__(self, dimensions: int = 4) -> None:
        self.dimensions = dimensions
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[0.1] * self.dimensions for _ in texts]


class SpyParser:
    """Records how many times markitdown conversion was invoked."""

    def __init__(self) -> None:
        self.convert_calls = 0

    def convert_bytes(self, filename: str, data: bytes) -> MarkdownResult:
        self.convert_calls += 1
        return MarkdownResult(
            filename=filename,
            format="bin",
            markdown="# Parsed\n\nBody from parser.",
            metadata={},
        )


def test_prepare_markdown_single_batch_embed() -> None:
    embedder = MockEmbedder(dimensions=4)
    chunks = prepare_markdown(
        "# Hello\n\nBody text.",
        "note.md",
        "doc:test",
        embedder=embedder,
    )
    assert len(embedder.calls) == 1
    assert len(embedder.calls[0]) == len(chunks)
    assert all(chunk.doc == "doc:test" for chunk in chunks)
    assert all(chunk.search_text for chunk in chunks)
    assert all(len(chunk.embedding) == 4 for chunk in chunks)


def test_prepare_markdown_empty_raises() -> None:
    embedder = MockEmbedder()
    with pytest.raises(ValueError, match="no chunks"):
        prepare_markdown("", "empty.md", "doc:test", embedder=embedder)


def test_prepare_file_markdown_file_skips_parser(tmp_path: Path) -> None:
    source = tmp_path / "readme.md"
    source.write_text("# Title\n\nParagraph.", encoding="utf-8")
    parser = SpyParser()
    embedder = MockEmbedder(dimensions=4)

    prepared = prepare_file(
        source,
        "readme.md",
        parser=parser,
        embedder=embedder,
        embedding_model="test-model",
    )

    assert parser.convert_calls == 0
    assert prepared.doc.path == "readme.md"
    assert prepared.doc.size_bytes == source.stat().st_size
    assert prepared.doc.chunk_count == len(prepared.chunks)
    assert all(chunk.doc == prepared.doc.id for chunk in prepared.chunks)


def test_prepare_file_provided_markdown_skips_parser(tmp_path: Path) -> None:
    source = tmp_path / "report.bin"
    source.write_bytes(b"\x00\x01binary payload")
    parser = SpyParser()
    embedder = MockEmbedder(dimensions=4)

    prepared = prepare_file(
        source,
        "report.bin",
        "# Report\n\nSupplied markdown body.",
        parser=parser,
        embedder=embedder,
        embedding_model="test-model",
    )

    assert parser.convert_calls == 0
    assert any("Supplied markdown body." in chunk.content for chunk in prepared.chunks)


def test_prepare_file_non_markdown_uses_parser(tmp_path: Path) -> None:
    source = tmp_path / "sheet.csv"
    source.write_text("a,b\n1,2\n", encoding="utf-8")
    parser = SpyParser()
    embedder = MockEmbedder(dimensions=4)

    prepared = prepare_file(
        source,
        "sheet.csv",
        parser=parser,
        embedder=embedder,
        embedding_model="test-model",
    )

    assert parser.convert_calls == 1
    assert len(prepared.chunks) >= 1


def test_prepare_file_empty_raises(tmp_path: Path) -> None:
    source = tmp_path / "empty.md"
    source.write_bytes(b"")
    parser = SpyParser()
    embedder = MockEmbedder()

    with pytest.raises(ValueError, match="empty file"):
        prepare_file(
            source,
            "empty.md",
            parser=parser,
            embedder=embedder,
            embedding_model="test-model",
        )
