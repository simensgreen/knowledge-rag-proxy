"""MarkItDown parser unit tests (no OCR network calls)."""

from __future__ import annotations

from pathlib import Path

import pytest

from server.engine.markitdown_parser import MarkitdownParser


@pytest.fixture
def parser() -> MarkitdownParser:
    return MarkitdownParser(ocr_config=None)


def test_convert_bytes_markdown(parser: MarkitdownParser) -> None:
    result = parser.convert_bytes("note.md", b"# Hello\n\n**bold** text.\n")
    assert result.markdown.startswith("# Hello")
    assert result.format == "md"
    assert result.metadata["title"] == "Hello"
    assert result.metadata["heading_count"] == 1


def test_convert_bytes_empty_raises(parser: MarkitdownParser) -> None:
    with pytest.raises(ValueError, match="empty file"):
        parser.convert_bytes("note.md", b"")


def test_convert_file_round_trip(parser: MarkitdownParser, tmp_path: Path) -> None:
    source = tmp_path / "readme.txt"
    source.write_text("Plain text document.", encoding="utf-8")
    result = parser.convert_file(source)
    assert "Plain text document" in result.markdown
    assert result.filename == "readme.txt"


def test_is_supported_common_formats(parser: MarkitdownParser) -> None:
    assert parser.is_supported(".pdf")
    assert parser.is_supported("docx")
    assert not parser.is_supported(".exe")
