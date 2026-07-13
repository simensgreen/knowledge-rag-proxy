"""Pydantic models for SurrealDB records (store boundary)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from surrealdb.data.types.record_id import RecordID


def record_id_to_str(value: Any) -> str:
    if isinstance(value, RecordID):
        return str(value)
    return str(value)


def to_record_id(value: Any) -> RecordID:
    """Convert a stored `table:<uuid>` id string back into a bindable RecordID.

    SurrealDB rejects a bare string where a record link is expected, and the
    `id`/`doc` fields are declared `TYPE uuid`/`record<doc>`, so the ident must
    be a real UUID rather than a string. Binding a RecordID object is the only
    form the driver serializes correctly for CREATE/UPDATE/DELETE/WHERE.
    """
    if isinstance(value, RecordID):
        return value
    text = str(value)
    table, separator, ident = text.partition(":")
    if not separator:
        raise ValueError(f"record id missing table prefix: {text!r}")
    ident = ident.strip("\u27e8\u27e9")
    try:
        return RecordID(table, uuid.UUID(ident))
    except ValueError:
        return RecordID(table, ident)


class StoredDoc(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    id: str
    path: str
    created_at: datetime
    modified_at: datetime
    accessed_at: datetime | None = None
    access_count: int = 0
    size_bytes: int
    crc32: bytes
    sha256: bytes
    embedding_model: str
    chunk_count: int | None = None
    description: str | None = None

    @field_validator("id", mode="before")
    @classmethod
    def normalize_id(cls, value: Any) -> str:
        return record_id_to_str(value)


class StoredChunk(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    id: str
    doc: str
    chunk_index: int = Field(validation_alias="index", serialization_alias="index")
    breadcrumb: str
    prefix: str | None = None
    suffix: str | None = None
    content: str
    search_text: str
    embedding: list[float]

    @field_validator("id", "doc", mode="before")
    @classmethod
    def normalize_record_ids(cls, value: Any) -> str:
        return record_id_to_str(value)
