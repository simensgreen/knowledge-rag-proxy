"""FastAPI application entrypoint."""

from __future__ import annotations

import os
import traceback
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# knowledge-rag creates {KNOWLEDGE_RAG_DIR}/{documents,data,models_cache} as a
# side effect of importing mcp_server.config, so KNOWLEDGE_RAG_DIR must be steered
# to a safe internal location before importing anything that pulls in mcp_server
# (server.deps, server.routes, server.watcher). The indexed folder is
# KRP_DOCUMENTS_DIR, applied to the config singleton afterwards.
load_dotenv()

from server.env_config import apply_env_config, bootstrap_library_base  # noqa: E402

bootstrap_library_base()
apply_env_config()

# knowledge-rag's BM25 tokenizer is ASCII-only; patch it to index/query Cyrillic
# and other non-Latin scripts before the orchestrator builds the keyword index.
from server.patches import apply_unicode_tokenizer_patch  # noqa: E402

apply_unicode_tokenizer_patch()

from fastapi import Depends, FastAPI, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402

from server.auth import verify_bearer_token  # noqa: E402
from server.deps import get_orchestrator_dep  # noqa: E402
from server.errors import ServiceError  # noqa: E402
from server.responses import error_response  # noqa: E402
from server.routes import documents, knowledge  # noqa: E402
from server.startup import index_documents_on_startup  # noqa: E402
from server.watcher import start_watchers, stop_watchers  # noqa: E402


def _docs_enabled() -> bool:
    return os.environ.get("KRP_DOCS", "").strip().lower() in {"1", "true", "yes", "on"}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    orchestrator = get_orchestrator_dep()
    index_documents_on_startup(orchestrator)
    start_watchers()
    yield
    stop_watchers()


_docs_enabled = _docs_enabled()

app = FastAPI(
    title="knowledge-rag-proxy",
    version="0.1.0",
    lifespan=lifespan,
    dependencies=[Depends(verify_bearer_token)],
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

app.include_router(knowledge.router)
app.include_router(documents.router)


@app.exception_handler(ServiceError)
async def service_error_handler(_request: Request, exc: ServiceError):
    return error_response(exc.status_code, exc.message, exc.hint)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
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
