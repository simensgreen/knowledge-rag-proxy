"""Bearer token authentication."""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from server.errors import ServiceError

bearer_scheme = HTTPBearer(auto_error=False)

_MISSING_BEARER_HINT = (
    "Missing Bearer token. To fix: trigger the Vellum secure credential prompt so the user "
    "can enter the token in a popup (never ask for the token in chat). Use the assistant CLI "
    "command 'assistant credentials prompt' (resolve its current path yourself; it lives under "
    "the Vellum app CLI dir and may move between versions) with these flags: "
    '--service "knowledge-rag-proxy" --field "api_token" '
    '--allowed-domains "<host from baseUrl, e.g. localhost>" '
    '--allowed-tools "krp_search_knowledge,krp_list_documents,krp_get_document,krp_download_document,krp_upload_content,krp_upload_workspace,krp_move_document,krp_remove_document" '
    "--injection-templates "
    '\'[{"hostPattern":"<same host>","injectionType":"header","headerName":"Authorization","valuePrefix":"Bearer "}]\'. '
    "Give the prompt a generous timeout so the user has time to respond. "
    "If the CLI flags differ in this Vellum version, run its --help to adapt them."
)

_INVALID_BEARER_HINT = (
    "Invalid Bearer token: the stored value does not match KRP_BEARER on the server. "
    "Re-run the secure credential prompt with the correct token, "
    "or update KRP_BEARER in the server .env to match."
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
            hint=_MISSING_BEARER_HINT,
        )
    if credentials.credentials != expected:
        raise ServiceError(
            401,
            "Invalid Bearer token",
            hint=_INVALID_BEARER_HINT,
        )
