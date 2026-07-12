"""FastAPI application — stub endpoints. See AGENTS.md for API schema."""

from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer(auto_error=False)

app = FastAPI(title="knowledge-rag-proxy", version="0.1.0")


def verify_bearer_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
) -> None:
    """Validate Authorization: Bearer against KB_PROXY_API_KEY."""
    expected = os.environ.get("KB_PROXY_API_KEY")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="KB_PROXY_API_KEY is not configured on the server",
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
        )
    if credentials.credentials != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Bearer token",
        )


Authenticated = Annotated[None, Depends(verify_bearer_token)]


def not_implemented() -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Endpoint not implemented yet — see Phase 1 in AGENTS.md",
    )


@app.get("/health")
def health() -> dict[str, Any]:
    """Liveness check. Unauthenticated for load balancers (Phase 1 may gate this)."""
    return {
        "ok": True,
        "version": "0.1.0",
        "documents": 0,
    }


@app.post("/search")
def search(_body: dict[str, Any], _auth: Authenticated) -> dict[str, Any]:
    """Hybrid search. Request: {query, max_results?, category?}."""
    not_implemented()
    return {"hits": []}


@app.post("/upload")
def upload(_auth: Authenticated) -> dict[str, Any]:
    """Multipart upload. Form: file, optional category."""
    not_implemented()
    return {"status": "ok", "filepath": ""}


@app.get("/list")
def list_documents(_auth: Authenticated) -> dict[str, Any]:
    """List indexed documents. Query: category?, limit?."""
    not_implemented()
    return {"documents": [], "total": 0}


@app.get("/stats")
def stats(_auth: Authenticated) -> dict[str, Any]:
    """Index statistics."""
    not_implemented()
    return {
        "total_documents": 0,
        "total_chunks": 0,
        "categories": [],
        "bm25_ready": False,
    }


@app.post("/reindex")
def reindex(_body: dict[str, Any], _auth: Authenticated) -> dict[str, Any]:
    """Trigger incremental or force reindex. Request: {force?: bool}."""
    not_implemented()
    return {"indexed": 0, "chunks_added": 0, "skipped": 0}


def main() -> None:
    import uvicorn

    uvicorn.run("server.app:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
