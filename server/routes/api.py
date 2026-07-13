"""Grimoire API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from starlette.concurrency import run_in_threadpool

from server.deps import get_engine_dep, get_parser_dep
from server.engine.protocols import Engine, Parser
from server.env_config import is_watcher_disabled
from server.errors import ServiceError
from server.responses import cache_read_only, error_response, no_store
from server.schemas import MoveRequest, RemoveRequest
from server.services import documents as documents_service
from server.services import files as files_service
from server.services import markitdown as markitdown_service
from server.services import search as search_service

router = APIRouter()

EngineDep = Annotated[Engine, Depends(get_engine_dep)]
ParserDep = Annotated[Parser, Depends(get_parser_dep)]


@router.get("/health", dependencies=[Depends(no_store)])
def health(engine: EngineDep) -> dict:
    stats = engine.stats()
    return {
        "status": "success",
        "ok": True,
        "version": "0.1.0",
        "documents": stats.get("documents", 0),
    }


@router.get("/search", dependencies=[Depends(cache_read_only)])
def search_route(
    engine: EngineDep,
    query: Annotated[str, Query()],
    max_results: Annotated[int | None, Query()] = None,
) -> dict:
    return search_service.search(engine, query=query, max_results=max_results)


@router.get("/file", dependencies=[Depends(cache_read_only)])
def file_route(
    engine: EngineDep,
    path: Annotated[str, Query()],
) -> dict:
    return files_service.get_file(engine, path)


@router.get("/list_files", dependencies=[Depends(cache_read_only)])
def list_files_route(
    engine: EngineDep,
    path: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    return files_service.list_files(engine, path_regex=path, limit=limit, offset=offset)


@router.get("/status", dependencies=[Depends(no_store)])
def status_route(engine: EngineDep) -> dict:
    return files_service.status(engine)


@router.post("/upload")
async def upload_route(
    background_tasks: BackgroundTasks,
    engine: EngineDep,
    file: Annotated[UploadFile, File()],
    filedir: Annotated[str | None, Form()] = None,
) -> dict:
    full_path = await run_in_threadpool(
        documents_service.save_uploaded_file,
        engine,
        file.file,
        file.filename,
        filedir,
    )

    indexing = "background" if is_watcher_disabled() else "watcher"
    if is_watcher_disabled():
        background_tasks.add_task(engine.index_file, full_path)

    return documents_service.upload_payload(full_path, indexing)


@router.get("/download")
def download_route(path: Annotated[str, Query()]) -> object:
    try:
        return documents_service.build_download_response(path)
    except ServiceError as service_error:
        if service_error.status_code == 404:
            return error_response(
                service_error.status_code,
                service_error.message,
                service_error.hint,
            )
        raise


@router.post("/remove")
def remove_route(body: RemoveRequest, engine: EngineDep) -> dict:
    return documents_service.remove_file(engine, body.path)


@router.post("/move")
async def move_route(body: MoveRequest, engine: EngineDep) -> dict:
    return await run_in_threadpool(
        documents_service.move_file,
        engine,
        body.source_path,
        body.dest_path,
    )


@router.post("/markitdown")
async def markitdown_route(
    parser: ParserDep,
    file: Annotated[UploadFile, File()],
) -> dict:
    data = await run_in_threadpool(markitdown_service.read_upload_stream, file.file)
    return markitdown_service.convert_upload(parser, file.filename, data)
