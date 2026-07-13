"""File upload, download, and path safety."""

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
from mcp_server.config import config
from mcp_server.server import KnowledgeOrchestrator

from server.env_config import get_temp_dir
from server.errors import ServiceError
from server.paths import relativize, resolve_allowed_path, to_library_path
from server.responses import success

# Copy uploads to disk in fixed-size chunks so large files never sit in RAM.
_UPLOAD_CHUNK_SIZE = 1024 * 1024


def _assert_supported_format(orchestrator: KnowledgeOrchestrator, path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix not in orchestrator.parser._parsers:
        supported = ", ".join(sorted(config.supported_formats))
        raise ServiceError(
            400,
            f"Unsupported format: {suffix}",
            hint=f"Supported formats: {supported}. Convert the file or upload a supported type.",
        )


def _stream_to_system_temp(source: BinaryIO) -> Path:
    """Stream source into the temp dir in chunks (never whole in RAM).

    Writes to the temp dir (KRP_TMP_DIR or the system default) so the
    in-progress upload stays out of the watched documents dir — neither the
    file watcher nor external sync (iCloud/Dropbox) sees a half-written file.
    Returns the temp path.
    """
    handle, temp_name = tempfile.mkstemp(
        dir=get_temp_dir(), prefix="knowledge-rag-proxy.", suffix=".download"
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
    """Move the completed temp file onto final_path atomically.

    os.replace is an atomic rename when temp and destination share a filesystem
    (common case: one volume). If they differ (EXDEV, e.g. Linux tmpfs /tmp),
    fall back to staging a copy inside the destination dir, then atomically
    rename that — so the watched folder only ever sees the finished file appear.
    """
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


def resolve_download_path(filepath: str) -> Path:
    """Resolve an existing file for download."""
    resolved = resolve_allowed_path(filepath)
    if not resolved.is_file():
        raise ServiceError(
            404,
            f"File not found: {filepath}",
            hint="Call GET /list_documents to see available filepaths.",
        )
    return resolved


def index_saved_file(
    orchestrator: KnowledgeOrchestrator,
    full_path: Path,
    category: str | None = None,
) -> dict[str, Any]:
    """Parse and index a file already written to disk."""
    _assert_supported_format(orchestrator, full_path)

    document = orchestrator.parser.parse_file(full_path)
    if not document:
        raise ServiceError(
            400,
            f"Failed to parse document: {full_path.name}",
            hint="Ensure the file is not empty and matches a supported format.",
        )

    resolved_category = category or document.category
    document.category = resolved_category
    for chunk in document.chunks:
        chunk.metadata["category"] = resolved_category

    chunks_added, dedup_skipped = orchestrator._index_document(document)

    try:
        file_stat = full_path.stat()
        file_mtime = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
        file_size = file_stat.st_size
    except OSError:
        file_mtime = datetime.now().isoformat()
        file_size = 0

    orchestrator._indexed_docs[document.id] = {
        "source": str(full_path),
        "category": resolved_category,
        "format": document.format,
        "chunks": chunks_added,
        "keywords": document.keywords,
        "indexed_at": datetime.now().isoformat(),
        "file_mtime": file_mtime,
        "file_size": file_size,
    }
    orchestrator._source_to_docid[str(full_path.resolve())] = document.id
    orchestrator._save_metadata()
    orchestrator.query_cache.invalidate()
    orchestrator.bm25_index.build_index()

    return {
        "filepath": str(full_path),
        "format": document.format,
        "chunks_added": chunks_added,
        "dedup_skipped": dedup_skipped,
        "category": resolved_category,
        "document": {
            "content": document.content,
            "source": str(document.source),
            "filename": document.filename,
            "category": document.category,
            "format": document.format,
            "metadata": document.metadata,
            "keywords": document.keywords,
            "chunk_count": len(document.chunks),
        },
    }


def upload_file(
    orchestrator: KnowledgeOrchestrator,
    source: BinaryIO,
    original_filename: str | None,
    filedir: str | None = None,
    category: str | None = None,
    return_document: bool = False,
) -> dict[str, Any]:
    # filedir is a directory under KRP_DOCUMENTS_DIR (omitted -> the root). The
    # file keeps its own uploaded name; only the bare name is used so a filename
    # containing path separators can't escape the chosen directory.
    filename = Path(original_filename).name if original_filename else ""
    if not filename:
        filename = f"{datetime.now():%Y%m%d-%H%M%S}.bin"

    relative_path = str(Path(filedir) / filename) if filedir else filename
    full_path = resolve_allowed_path(relative_path)

    # Validate before touching disk so a rejected upload writes nothing.
    if full_path.exists():
        raise ServiceError(
            400,
            f"File already exists: {full_path}",
            hint="Remove the existing file or upload under a different filedir.",
        )
    _assert_supported_format(orchestrator, full_path)

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

    index_result = index_saved_file(orchestrator, full_path, category=category)

    payload: dict[str, Any] = {
        "filepath": index_result["filepath"],
        "format": index_result["format"],
        "chunks_added": index_result["chunks_added"],
        "dedup_skipped": index_result["dedup_skipped"],
        "category": index_result["category"],
    }
    if return_document:
        payload["document"] = index_result["document"]
    return success(relativize(payload))


def build_download_response(filepath: str) -> FileResponse:
    resolved = resolve_download_path(filepath)
    media_type, _encoding = mimetypes.guess_type(str(resolved))
    return FileResponse(
        path=resolved,
        filename=resolved.name,
        media_type=media_type or "application/octet-stream",
    )


def move_document(
    orchestrator: KnowledgeOrchestrator,
    source_filepath: str,
    dest_filepath: str,
) -> dict[str, Any]:
    if not source_filepath:
        raise ServiceError(
            400,
            "Source filepath required",
            hint="Provide the root-relative path of the file to move, including the filename.",
        )
    if not dest_filepath:
        raise ServiceError(
            400,
            "Destination filepath required",
            hint="Provide the root-relative destination path, including the filename.",
        )

    source_path = resolve_allowed_path(source_filepath)
    dest_path = resolve_allowed_path(dest_filepath)

    if not source_path.is_file():
        raise ServiceError(
            404,
            f"File not found: {source_filepath}",
            hint="Call GET /list_documents to see available filepaths.",
        )
    if dest_path.exists():
        raise ServiceError(
            400,
            f"Destination already exists: {dest_filepath}",
            hint="Choose another dest_filepath or remove the existing file first with POST /remove_document.",
        )

    chunks_removed = 0
    source_key = str(source_path.resolve())
    if source_key in orchestrator._source_to_docid:
        remove_result = orchestrator.remove_document_by_path(
            to_library_path(source_filepath),
            delete_file=False,
        )
        if "error" not in remove_result:
            chunks_removed = int(remove_result.get("chunks_removed", 0))

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source_path, dest_path)

    payload: dict[str, Any] = {
        "source_filepath": source_filepath,
        "dest_filepath": dest_filepath,
        "chunks_removed": chunks_removed,
    }

    suffix = dest_path.suffix.lower()
    if suffix in orchestrator.parser._parsers:
        index_result = index_saved_file(orchestrator, dest_path)
        payload["chunks_added"] = index_result["chunks_added"]
        payload["format"] = index_result["format"]
        payload["category"] = index_result["category"]

    return success(relativize(payload))
