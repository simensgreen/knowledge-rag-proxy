"""Markitdown conversion business logic."""

from __future__ import annotations

from typing import Any, BinaryIO

from server.engine.protocols import Parser
from server.errors import ServiceError
from server.responses import success


def convert_upload(parser: Parser, filename: str | None, data: bytes) -> dict[str, Any]:
    if not filename:
        raise ServiceError(400, "Filename required", hint="Attach a file with a filename in the multipart form.")
    if len(data) == 0:
        raise ServiceError(400, "Uploaded file is empty", hint="Attach a non-empty file.")

    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix and not parser.is_supported(f".{suffix}"):
        supported = ", ".join(parser.supported_formats())
        raise ServiceError(
            400,
            f"Unsupported format: {suffix}",
            hint=f"Supported formats: {supported}.",
        )

    try:
        result = parser.convert_bytes(filename, data)
    except ValueError as error:
        raise ServiceError(400, str(error), hint="Attach a non-empty file.") from error

    return success(
        {
            "filename": result.filename,
            "format": result.format,
            "markdown": result.markdown,
            "metadata": result.metadata,
        }
    )


def read_upload_stream(source: BinaryIO) -> bytes:
    return source.read()
