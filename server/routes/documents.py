"""Upload and download routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from starlette.concurrency import run_in_threadpool

from mcp_server.server import KnowledgeOrchestrator

from server.deps import get_orchestrator_dep
from server.errors import ServiceError
from server.responses import error_response
from server.services import documents as documents_service

router = APIRouter()


@router.post("/upload")
async def upload(
    orchestrator: Annotated[KnowledgeOrchestrator, Depends(get_orchestrator_dep)],
    file: Annotated[UploadFile, File()],
    filedir: Annotated[str | None, Form()] = None,
    category: Annotated[str | None, Form()] = None,
    return_document: Annotated[bool, Form(alias="return")] = False,
) -> dict:
    # Stream the spooled upload straight to disk in a worker thread; never
    # materialize the whole file in memory.
    return await run_in_threadpool(
        documents_service.upload_file,
        orchestrator,
        file.file,
        file.filename,
        filedir,
        category,
        return_document,
    )


@router.get("/download")
def download(filepath: Annotated[str, Query()]) -> object:
    try:
        return documents_service.build_download_response(filepath)
    except ServiceError as service_error:
        if service_error.status_code == 404:
            return error_response(
                service_error.status_code,
                service_error.message,
                service_error.hint,
            )
        raise
