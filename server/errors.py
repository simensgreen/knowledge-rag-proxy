"""Application errors mapped to HTTP status codes."""

from __future__ import annotations


class ServiceError(Exception):
    """Raised by services; converted to JSON error envelope by the app handler."""

    def __init__(
        self,
        status_code: int,
        message: str,
        hint: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.hint = hint
        super().__init__(message)
