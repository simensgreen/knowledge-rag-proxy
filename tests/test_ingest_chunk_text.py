"""Tests for ingest chunk_text helpers."""

from __future__ import annotations

from server.engine.ingest.chunk_text import (
    build_breadcrumb,
    build_search_text,
    greedy_take,
    reconstruct_document,
)
from server.engine.ingest.models import Chunk


def test_build_breadcrumb_filename_only() -> None:
    assert build_breadcrumb("notes/report.md", []) == "report.md"


def test_build_breadcrumb_with_headings() -> None:
    breadcrumb = build_breadcrumb("report.md", [(1, "Income Tax"), (2, "Marginal Relief")])
    assert breadcrumb == "report.md\n# Income Tax\n## Marginal Relief"


def test_build_search_text_optional_prefix_suffix() -> None:
    assert build_search_text("report.md", "body") == "report.md\nbody"
    assert (
        build_search_text("report.md", "row1", prefix="header", suffix="row2")
        == "report.md\n\nheaderrow1\nrow2"
    )


def test_reconstruct_document_joins_content() -> None:
    chunks = [
        Chunk(chunk_index=1, content=" world", breadcrumb="a.md"),
        Chunk(chunk_index=0, content="hello", breadcrumb="a.md"),
    ]
    assert reconstruct_document(chunks) == "hello world"


def test_greedy_take_prose_from_start_and_end() -> None:
    text = "First sentence. Second sentence. Third sentence."
    assert greedy_take(text, 20, block_kind="prose", from_end=False).startswith("First")
    assert greedy_take(text, 20, block_kind="prose", from_end=True).endswith("Third sentence.")
