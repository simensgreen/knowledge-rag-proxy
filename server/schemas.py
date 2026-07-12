"""Pydantic request models for API endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class ReindexDocumentsRequest(BaseModel):
    force: bool = False
    full_rebuild: bool = False


class UpdateDocumentRequest(BaseModel):
    filepath: str
    content: str


class RemoveDocumentRequest(BaseModel):
    filepath: str
    delete_file: bool = False
