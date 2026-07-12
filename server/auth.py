"""Bearer token authentication."""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from server.errors import ServiceError

bearer_scheme = HTTPBearer(auto_error=False)

_VELLUM_TOKEN_HINT = (
    "In Vellum: use credential_store (secure prompt) to ask the user for the API token "
    "and save it in the credential vault (e.g. alias knowledge-rag-proxy/api_token). "
    "Set apiTokenCredentialRef in plugin config.json to that alias; CES injects "
    "Authorization: Bearer on outbound requests. The token must match KRP_BEARER on the server."
)


def verify_bearer_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
) -> None:
    """Validate Authorization: Bearer against KRP_BEARER."""
    expected = os.environ.get("KRP_BEARER")
    if not expected:
        raise ServiceError(
            503,
            "KRP_BEARER is not configured on the server",
            hint="Set KRP_BEARER in the server .env file and restart the service.",
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ServiceError(
            401,
            "Missing Bearer token",
            hint=f"Send Authorization: Bearer <token>. {_VELLUM_TOKEN_HINT}",
        )
    if credentials.credentials != expected:
        raise ServiceError(
            401,
            "Invalid Bearer token",
            hint=f"The token does not match KRP_BEARER on the server. {_VELLUM_TOKEN_HINT}",
        )
