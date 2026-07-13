"""File upload, download, move, and remove (filesystem only)."""

from __future__ import annotations

import errno
import mimetypes
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO

from fastapi.responses import FileResponse

from server.env_config import get_temp_dir
from server.errors import ServiceError
from server.paths import documents_root, resolve_allowed_path
from server.responses import success
from server.services.index_queue import IndexQueue, IndexTask

_UPLOAD_CHUNK_SIZE = 1024 * 1024

_SUPPORTED_UPLOAD_SUFFIXES = frozenset(
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


def _assert_supported_format(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix not in _SUPPORTED_UPLOAD_SUFFIXES and suffix != "":
        supported = ", ".join(sorted(extension.lstrip(".") for extension in _SUPPORTED_UPLOAD_SUFFIXES))
        raise ServiceError(
            400,
            f"Unsupported format: {suffix}",
            hint=f"Supported formats: {supported}. Convert the file or upload a supported type.",
        )


def _stream_to_system_temp(source: BinaryIO) -> Path:
    handle, temp_name = tempfile.mkstemp(
        dir=get_temp_dir(), prefix="grimoire.", suffix=".download"
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(handle, "wb") as destination:
            shutil.copyfileobj(source, destination, _UPLOAD_CHUNK_SIZE)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    return temp_path


def _finalize_upload(temp_path: Path, final_path: Path) -> None:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.replace(temp_path, final_path)
        return
    except OSError as error:
        if error.errno != errno.EXDEV:
            temp_path.unlink(missing_ok=True)
            raise

    handle, staged_name = tempfile.mkstemp(
        dir=final_path.parent, prefix=f"{final_path.name}.", suffix=".download"
    )
    staged_path = Path(staged_name)
    try:
        with os.fdopen(handle, "wb") as destination, open(temp_path, "rb") as source:
            shutil.copyfileobj(source, destination, _UPLOAD_CHUNK_SIZE)
        os.replace(staged_path, final_path)
    except BaseException:
        staged_path.unlink(missing_ok=True)
        raise
    finally:
        temp_path.unlink(missing_ok=True)


def resolve_download_path(path: str) -> Path:
    resolved = resolve_allowed_path(path)
    if not resolved.is_file():
        raise ServiceError(
            404,
            f"File not found: {path}",
            hint="Call GET /api/list_files to see available paths.",
        )
    return resolved


def save_uploaded_file(
    source: BinaryIO,
    original_filename: str | None,
    filedir: str | None = None,
) -> Path:
    filename = Path(original_filename).name if original_filename else ""
    if not filename:
        filename = f"{datetime.now():%Y%m%d-%H%M%S}.bin"

    relative_path = str(Path(filedir) / filename) if filedir else filename
    full_path = resolve_allowed_path(relative_path)

    if full_path.exists():
        raise ServiceError(
            400,
            f"File already exists: {relative_path}",
            hint="Remove the existing file or upload under a different filedir.",
        )
    _assert_supported_format(full_path)

    temp_path = _stream_to_system_temp(source)
    try:
        if temp_path.stat().st_size == 0:
            raise ServiceError(
                400, "Uploaded file is empty", hint="Attach a non-empty file in the multipart form."
            )
        _finalize_upload(temp_path, full_path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise

    return full_path


def upload_payload(full_path: Path) -> dict[str, Any]:
    return success(
        {
            "path": full_path.relative_to(documents_root()).as_posix(),
            "format": full_path.suffix.lstrip("."),
        }
    )


def build_download_response(path: str) -> FileResponse:
    resolved = resolve_download_path(path)
    media_type, _encoding = mimetypes.guess_type(str(resolved))
    return FileResponse(
        path=resolved,
        filename=resolved.name,
        media_type=media_type or "application/octet-stream",
    )


def remove_file(path: str) -> dict[str, Any]:
    if not path:
        raise ServiceError(400, "Path required", hint="Provide the path of a file to remove.")

    resolved = resolve_allowed_path(path)
    if not resolved.is_file():
        raise ServiceError(
            404,
            f"File not found: {path}",
            hint="Call GET /api/list_files to see available paths.",
        )

    relative = resolved.relative_to(documents_root()).as_posix()
    resolved.unlink()
    return success({"path": relative})


async def move_file(queue: IndexQueue, source_path: str, dest_path: str) -> dict[str, Any]:
    if not source_path:
        raise ServiceError(
            400,
            "Source path required",
            hint="Provide the root-relative path of the file to move, including the filename.",
        )
    if not dest_path:
        raise ServiceError(
            400,
            "Destination path required",
            hint="Provide the root-relative destination path, including the filename.",
        )

    source_resolved = resolve_allowed_path(source_path)
    dest_resolved = resolve_allowed_path(dest_path)

    if not source_resolved.is_file():
        raise ServiceError(
            404,
            f"File not found: {source_path}",
            hint="Call GET /api/list_files to see available paths.",
        )
    if dest_resolved.exists():
        raise ServiceError(
            400,
            f"Destination already exists: {dest_path}",
            hint="Choose another dest_path or remove the existing file first with POST /api/remove.",
        )

    root = documents_root()
    source_relative = source_resolved.relative_to(root).as_posix()
    dest_relative = dest_resolved.relative_to(root).as_posix()

    dest_resolved.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source_resolved, dest_resolved)

    await queue.submit(
        IndexTask(path=source_relative, kind="move", dest_path=dest_relative)
    )

    return success(
        {
            "source_path": source_relative,
            "dest_path": dest_relative,
        }
    )
