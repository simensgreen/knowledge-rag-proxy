"""Grimoire API routes under /api."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from starlette.concurrency import run_in_threadpool

from server.deps import get_embedder_dep, get_parser_dep, get_queue_dep, get_store_dep
from server.engine.doc_store import DocStore
from server.engine.protocols import EmbeddingProvider, Parser
from server.errors import ServiceError
from server.paths import documents_root
from server.responses import cache_read_only, error_response, no_store
from server.schemas import FileContentReplaceRequest
from server.services import documents as documents_service
from server.services import file_content as file_content_service
from server.services import file_info as file_info_service
from server.services import files as files_service
from server.services import markitdown as markitdown_service
from server.services import reindex as reindex_service
from server.services import search as search_service
from server.services.index_queue import IndexQueue, IndexTask

router = APIRouter()

ParserDep = Annotated[Parser, Depends(get_parser_dep)]
StoreDep = Annotated[DocStore, Depends(get_store_dep)]
QueueDep = Annotated[IndexQueue, Depends(get_queue_dep)]
EmbedderDep = Annotated[EmbeddingProvider, Depends(get_embedder_dep)]


@router.get("/health", dependencies=[Depends(no_store)])
def health() -> dict:
    return {"ok": True}


@router.get("/search", dependencies=[Depends(cache_read_only)])
async def search_route(
    store: StoreDep,
    embedder: EmbedderDep,
    query: Annotated[str, Query()],
    max_results: Annotated[int | None, Query()] = None,
) -> dict:
    return await run_in_threadpool(
        search_service.search,
        store,
        embedder,
        query,
        max_results,
    )


@router.get("/list_files", dependencies=[Depends(cache_read_only)])
def list_files_route(
    store: StoreDep,
    path: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    return files_service.list_files(store, path_regex=path, limit=limit, offset=offset)


@router.get("/status", dependencies=[Depends(no_store)])
def status_route(store: StoreDep, queue: QueueDep, parser: ParserDep) -> dict:
    return files_service.status(store, queue, parser)


@router.get("/file_info", dependencies=[Depends(cache_read_only)])
def file_info_get(store: StoreDep, path: Annotated[str, Query()]) -> dict:
    return file_info_service.get_info(store, path)


@router.post("/file_info")
def file_info_post(
    store: StoreDep,
    path: Annotated[str, Query()],
    description: Annotated[str | None, Query()] = None,
) -> dict:
    return file_info_service.update_description(store, path, description)


@router.get("/file_content", dependencies=[Depends(cache_read_only)])
def file_content_get(store: StoreDep, path: Annotated[str, Query()]) -> dict:
    return file_content_service.get_content(store, path)


@router.post("/file_content")
async def file_content_post(
    queue: QueueDep,
    body: FileContentReplaceRequest,
    path: Annotated[str, Query()],
) -> dict:
    return await file_content_service.replace_content(queue, path, body.markdown)


@router.post("/reindex")
async def reindex_route(store: StoreDep, queue: QueueDep, path: Annotated[str, Query()]) -> dict:
    return await reindex_service.request_reindex(store, queue, path)


@router.post("/upload")
async def upload_route(
    queue: QueueDep,
    file: Annotated[UploadFile, File()],
    filedir: Annotated[str | None, Form()] = None,
    markdown: Annotated[UploadFile | None, File()] = None,
    description: Annotated[str | None, Form()] = None,
) -> dict:
    full_path = await run_in_threadpool(
        documents_service.save_uploaded_file,
        file.file,
        file.filename,
        filedir,
    )
    relative = full_path.relative_to(documents_root()).as_posix()
    markdown_text: str | None = None
    if markdown is not None:
        data = await markdown.read()
        markdown_text = data.decode("utf-8")
    if markdown_text is not None or description is not None:
        await queue.submit(
            IndexTask(
                path=relative,
                kind="index",
                markdown=markdown_text,
                description=description,
            )
        )
    return documents_service.upload_payload(full_path)


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
def remove_route(path: Annotated[str, Query()]) -> dict:
    return documents_service.remove_file(path)


@router.post("/move")
async def move_route(
    queue: QueueDep,
    source_path: Annotated[str, Query()],
    dest_path: Annotated[str, Query()],
) -> dict:
    return await documents_service.move_file(queue, source_path, dest_path)


@router.post("/markitdown")
async def markitdown_route(
    parser: ParserDep,
    file: Annotated[UploadFile, File()],
) -> dict:
    data = await file.read()
    return await run_in_threadpool(
        markitdown_service.convert_upload,
        parser,
        file.filename,
        data,
    )
