"""HTTP response helpers with a consistent JSON envelope."""

from __future__ import annotations

from typing import Any

from fastapi import Response
from fastapi.responses import JSONResponse

# Read-only GET results may be cached briefly by the client. Responses are
# behind Bearer auth, so the cache must be private (never a shared proxy).
_CACHEABLE_MAX_AGE_SECONDS = 300


def cache_read_only(response: Response) -> None:
    """FastAPI dependency: mark a read-only GET response cacheable for 5 minutes."""
    response.headers["Cache-Control"] = f"private, max-age={_CACHEABLE_MAX_AGE_SECONDS}"


def no_store(response: Response) -> None:
    """FastAPI dependency: forbid caching for volatile GET responses."""
    response.headers["Cache-Control"] = "no-store"


def success(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a success envelope dict (HTTP 200 via route return)."""
    return {"status": "success", **payload}


def error_response(
    http_status: int,
    message: str,
    hint: str | None = None,
) -> JSONResponse:
    """Return an error envelope with the given HTTP status."""
    body: dict[str, Any] = {"status": "error", "message": message}
    if hint is not None:
        body["hint"] = hint
    return JSONResponse(status_code=http_status, content=body)
