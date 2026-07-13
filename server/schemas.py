"""Pydantic request models for API endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class FileContentReplaceRequest(BaseModel):
    markdown: str
