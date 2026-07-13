"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
import traceback
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from server.logging_config import configure_logging

configure_logging()

from fastapi import Depends, FastAPI, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402

from server.auth import verify_bearer_token  # noqa: E402
from server.deps import (  # noqa: E402
    build_embedder,
    build_parser,
    embedding_model_name,
)
from server.engine.doc_store import DocStore  # noqa: E402
from server.engine.store import ensure_store_schema  # noqa: E402
from server.env_config import is_docs_enabled, require_embedding_provider_config  # noqa: E402
from server.errors import ServiceError  # noqa: E402
from server.responses import error_response  # noqa: E402
from server.routes import api  # noqa: E402
from server.services.index_queue import IndexQueue  # noqa: E402
from server.services.indexing import run_index_worker  # noqa: E402
from server.services.reconcile import reconcile_index  # noqa: E402
from server.startup import (  # noqa: E402
    probe_documents_dir,
    probe_embedding_provider,
    verify_stored_embedding_dimensions,
)
from server.watcher import start_watchers, stop_watchers  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    require_embedding_provider_config()
    app.state.parser = build_parser()
    app.state.embedder = build_embedder()
    surreal = ensure_store_schema()
    app.state.store = surreal
    app.state.doc_store = DocStore(surreal)
    app.state.queue = IndexQueue()
    embedding_model = embedding_model_name(app.state.embedder)

    probe_documents_dir()
    probe_embedding_provider(app.state.embedder)
    verify_stored_embedding_dimensions(app.state.doc_store)

    app.state.worker = asyncio.create_task(
        run_index_worker(
            app.state.queue,
            store=app.state.doc_store,
            parser=app.state.parser,
            embedder=app.state.embedder,
            embedding_model=embedding_model,
        )
    )
    start_watchers(app.state.queue, loop=asyncio.get_running_loop())
    app.state.reconcile_task = asyncio.create_task(
        reconcile_index(app.state.queue, app.state.doc_store, app.state.parser)
    )

    yield

    for task_name in ("worker", "reconcile_task"):
        task = getattr(app.state, task_name, None)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    stop_watchers()
    store = app.state.store
    if store is not None:
        store.close()


app = FastAPI(
    title="grimoire",
    version="0.1.0",
    lifespan=lifespan,
    dependencies=[Depends(verify_bearer_token)],
    docs_url="/docs" if is_docs_enabled() else None,
    redoc_url="/redoc" if is_docs_enabled() else None,
    openapi_url="/openapi.json" if is_docs_enabled() else None,
)

app.include_router(api.router, prefix="/api")


@app.exception_handler(ServiceError)
async def service_error_handler(_request: Request, exc: ServiceError):
    return error_response(exc.status_code, exc.message, exc.hint)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    del exc
    return error_response(
        422,
        "Invalid request body",
        hint="Check required fields and JSON schema for this endpoint.",
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(_request: Request, exc: Exception):
    traceback.print_exc()
    return error_response(
        500,
        "Internal server error",
        hint="Check server logs for details.",
    )


def main() -> None:
    import uvicorn

    uvicorn.run("server.app:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
