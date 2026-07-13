"""Pydantic request models for API endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class RemoveRequest(BaseModel):
    path: str


class MoveRequest(BaseModel):
    source_path: str
    dest_path: str
