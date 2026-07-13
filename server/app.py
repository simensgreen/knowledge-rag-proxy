"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
import traceback
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from server.env_config import get_log_level

logging.basicConfig(
    level=get_log_level(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

from fastapi import Depends, FastAPI, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402

from server.auth import verify_bearer_token  # noqa: E402
from server.env_config import is_docs_enabled  # noqa: E402
from server.errors import ServiceError  # noqa: E402
from server.responses import error_response  # noqa: E402
from server.routes import api  # noqa: E402
from server.startup import probe_documents_dir  # noqa: E402
from server.watcher import start_watchers, stop_watchers  # noqa: E402


@asynccontextmanager
async def lifespan(_app: FastAPI):
    probe_documents_dir()
    start_watchers()
    yield
    stop_watchers()


app = FastAPI(
    title="grimoire",
    version="0.1.0",
    lifespan=lifespan,
    dependencies=[Depends(verify_bearer_token)],
    docs_url="/docs" if is_docs_enabled() else None,
    redoc_url="/redoc" if is_docs_enabled() else None,
    openapi_url="/openapi.json" if is_docs_enabled() else None,
)

app.include_router(api.router)


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
