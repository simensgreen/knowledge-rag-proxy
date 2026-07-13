"""MarkItDown-backed document parser with optional markitdown-ocr plugin."""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt
from markitdown import MarkItDown, StreamInfo
from markitdown._exceptions import FileConversionException, UnsupportedFormatException
from openai import OpenAI

from server.engine.models import MarkdownResult
from server.engine.protocols import Parser
from server.env_config import ProviderConfig

logger = logging.getLogger(__name__)

DEFAULT_OCR_MODEL = "google/gemini-2.5-flash"

_markdown = MarkdownIt("commonmark")

SUPPORTED_SUFFIXES = frozenset(
    {
        ".md",
        ".markdown",
        ".txt",
        ".text",
        ".html",
        ".htm",
        ".pdf",
        ".docx",
        ".pptx",
        ".xlsx",
        ".xls",
        ".csv",
        ".json",
        ".xml",
        ".epub",
        ".ipynb",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".bmp",
        ".tiff",
        ".zip",
        ".msg",
        ".wav",
        ".mp3",
    }
)


def normalize_suffix(suffix: str) -> str:
    normalized = suffix.lower()
    return normalized if normalized.startswith(".") else f".{normalized}"


def openai_client_from_provider(config: ProviderConfig) -> OpenAI:
    return OpenAI(base_url=config.base_url, api_key=config.token)


def heading_texts(markdown: str) -> list[str]:
    tokens = _markdown.parse(markdown)
    headings: list[str] = []
    for position, token in enumerate(tokens):
        if token.type != "heading_open":
            continue
        inline = tokens[position + 1] if position + 1 < len(tokens) else None
        if inline is None or inline.type != "inline":
            continue
        heading_text = inline.content.strip()
        if heading_text:
            headings.append(heading_text)
    return headings


def build_metadata(markdown: str, title: str | None) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if title:
        metadata["title"] = title
    headings = heading_texts(markdown)
    if headings and "title" not in metadata:
        metadata["title"] = headings[0]
    metadata["heading_count"] = len(headings)
    return metadata


def build_markitdown(ocr_config: ProviderConfig | None = None) -> MarkItDown:
    kwargs: dict[str, Any] = {}
    if ocr_config is not None and ocr_config.token and ocr_config.base_url:
        model = ocr_config.model or DEFAULT_OCR_MODEL
        kwargs["llm_client"] = openai_client_from_provider(ocr_config)
        kwargs["llm_model"] = model
        logger.info("MarkItDown OCR enabled (model=%s)", model)
    elif ocr_config is not None:
        logger.warning(
            "GRIM_OCR_* is partially set; OCR disabled until BASE_URL and TOKEN are configured"
        )
    else:
        logger.info("MarkItDown OCR plugin loaded without LLM client (text-only conversion)")

    return MarkItDown(enable_plugins=True, **kwargs)


class MarkitdownParser(Parser):
    def __init__(self, ocr_config: ProviderConfig | None = None) -> None:
        self.markitdown = build_markitdown(ocr_config)

    def convert_bytes(self, filename: str, data: bytes) -> MarkdownResult:
        if len(data) == 0:
            raise ValueError("empty file")

        extension = Path(filename).suffix.lower()
        stream_info = StreamInfo(filename=Path(filename).name, extension=extension)
        stream = io.BytesIO(data)

        logger.debug(
            "Converting document via MarkItDown: filename=%s bytes=%d",
            Path(filename).name,
            len(data),
        )
        try:
            result = self.markitdown.convert(stream, stream_info=stream_info)
        except UnsupportedFormatException as error:
            raise ValueError(f"Unsupported format: {extension or 'unknown'}") from error
        except FileConversionException as error:
            raise ValueError(str(error)) from error

        markdown = (result.markdown or "").strip()
        if not markdown:
            raise ValueError("conversion produced empty markdown")

        logger.info(
            "Converted document to markdown: filename=%s chars=%d",
            Path(filename).name,
            len(markdown),
        )
        return MarkdownResult(
            filename=Path(filename).name,
            format=extension.lstrip(".") or "bin",
            markdown=markdown,
            metadata=build_metadata(markdown, result.title),
        )

    def convert_file(self, path: Path) -> MarkdownResult:
        if not path.is_file():
            raise ValueError(f"file not found: {path.name}")
        data = path.read_bytes()
        return self.convert_bytes(path.name, data)

    def is_supported(self, suffix: str) -> bool:
        normalized = normalize_suffix(suffix)
        if normalized == ".":
            return True
        return normalized in SUPPORTED_SUFFIXES

    def supported_formats(self) -> list[str]:
        return sorted(suffix.lstrip(".") for suffix in SUPPORTED_SUFFIXES)
