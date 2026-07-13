"""Bearer token authentication."""

from __future__ import annotations

import os
import secrets
from typing import Annotated

from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from server.errors import ServiceError

bearer_scheme = HTTPBearer(auto_error=False)

MISSING_BEARER_HINT = (
    "Missing Bearer token. Set apiToken in the installed plugin config.json to match "
    "GRIM_BEARER on the server."
)

INVALID_BEARER_HINT = (
    "Invalid Bearer token: the stored value does not match GRIM_BEARER on the server. "
    "Update apiToken in plugin config.json or GRIM_BEARER in the server .env."
)


def verify_bearer_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
) -> None:
    expected = os.environ.get("GRIM_BEARER")
    if not expected:
        return
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ServiceError(401, "Missing Bearer token", hint=MISSING_BEARER_HINT)
    if not secrets.compare_digest(credentials.credentials, expected):
        raise ServiceError(401, "Invalid Bearer token", hint=INVALID_BEARER_HINT)
