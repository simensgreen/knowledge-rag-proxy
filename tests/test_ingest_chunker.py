"""Tests for markdown chunker."""

from __future__ import annotations

from server.engine.ingest.chunk_text import reconstruct_document
from server.engine.ingest.chunker import chunk_markdown


def test_chunk_markdown_simple_paragraph() -> None:
    markdown = "# Title\n\nHello world."
    chunks = chunk_markdown(markdown, "note.md")
    assert reconstruct_document(chunks) == markdown
    assert chunks[0].breadcrumb.startswith("note.md\n# Title")


def test_chunk_markdown_fenced_code() -> None:
    markdown = "```python\nprint('hi')\nprint('there')\n```"
    chunks = chunk_markdown(markdown, "code.md")
    assert reconstruct_document(chunks) == markdown


def test_chunk_markdown_table() -> None:
    markdown = "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |"
    chunks = chunk_markdown(markdown, "table.md")
    assert reconstruct_document(chunks) == markdown


def test_chunk_markdown_list() -> None:
    markdown = "- one\n- two\n- three"
    chunks = chunk_markdown(markdown, "list.md")
    assert reconstruct_document(chunks) == markdown


def test_chunk_markdown_long_paragraph_splits() -> None:
    sentence = "This is a long sentence with enough words. "
    markdown = sentence * 80
    chunks = chunk_markdown(markdown, "long.md")
    assert len(chunks) > 1
    assert reconstruct_document(chunks) == markdown


def test_chunk_markdown_nested_list_reconstructs() -> None:
    markdown = "- parent\n  - child one\n  - child two\n- sibling"
    chunks = chunk_markdown(markdown, "nested.md")
    assert reconstruct_document(chunks) == markdown


def test_chunk_markdown_blockquote_reconstructs() -> None:
    markdown = "> quoted line one\n> quoted line two\n\nAfter the quote."
    chunks = chunk_markdown(markdown, "quote.md")
    assert reconstruct_document(chunks) == markdown


def test_chunk_markdown_setext_heading_breadcrumb() -> None:
    markdown = "Chapter One\n===========\n\nBody text."
    chunks = chunk_markdown(markdown, "setext.md")
    assert reconstruct_document(chunks) == markdown
    assert any("# Chapter One" in chunk.breadcrumb for chunk in chunks)


def test_chunk_markdown_heading_with_inline_markup() -> None:
    markdown = "## The **bold** term\n\nExplanation."
    chunks = chunk_markdown(markdown, "inline.md")
    assert reconstruct_document(chunks) == markdown
    assert any("The **bold** term" in chunk.breadcrumb for chunk in chunks)


def test_chunk_markdown_oversized_nested_list_reconstructs() -> None:
    parent_items = [f"- item number {index} with some descriptive text" for index in range(60)]
    parent_items.insert(3, "  - nested child that belongs to item two")
    markdown = "\n".join(parent_items)
    chunks = chunk_markdown(markdown, "big_list.md")
    assert len(chunks) > 1
    assert reconstruct_document(chunks) == markdown
