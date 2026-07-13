"""Prepare StoredDoc + StoredChunk records from a file (+ optional markdown)."""

from __future__ import annotations

import binascii
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from server.engine.ingest.chunk_text import build_search_text
from server.engine.ingest.chunker import chunk_markdown
from server.engine.ingest.models import PreparedDocument
from server.engine.protocols import EmbeddingProvider, Parser
from server.engine.store_models import StoredChunk, StoredDoc

logger = logging.getLogger(__name__)

MARKDOWN_SUFFIXES = frozenset({".md", ".markdown"})


def file_checksums(data: bytes) -> tuple[bytes, bytes]:
    crc32 = binascii.crc32(data).to_bytes(4, byteorder="big", signed=False)
    sha256 = hashlib.sha256(data).digest()
    return crc32, sha256


def new_doc_id() -> str:
    return f"doc:{uuid.uuid4()}"


def new_chunk_id() -> str:
    return f"chunk:{uuid.uuid4()}"


def prepare_markdown(
    markdown: str,
    filename: str,
    doc_id: str,
    *,
    embedder: EmbeddingProvider,
) -> list[StoredChunk]:
    logger.debug("Chunking markdown: filename=%s chars=%d", filename, len(markdown))
    domain_chunks = chunk_markdown(markdown, filename)
    if not domain_chunks:
        raise ValueError("markdown produced no chunks")
    logger.info("Chunked document: filename=%s chunks=%d", filename, len(domain_chunks))

    search_texts = [
        build_search_text(
            chunk.breadcrumb,
            chunk.content,
            prefix=chunk.prefix,
            suffix=chunk.suffix,
        )
        for chunk in domain_chunks
    ]
    logger.debug("Embedding chunks: filename=%s count=%d", filename, len(search_texts))
    embeddings = embedder.embed(search_texts)

    return [
        StoredChunk(
            id=new_chunk_id(),
            doc=doc_id,
            chunk_index=domain_chunk.chunk_index,
            breadcrumb=domain_chunk.breadcrumb,
            prefix=domain_chunk.prefix,
            suffix=domain_chunk.suffix,
            content=domain_chunk.content,
            search_text=search_text,
            embedding=embedding,
        )
        for domain_chunk, search_text, embedding in zip(
            domain_chunks, search_texts, embeddings, strict=True
        )
    ]


def resolve_markdown(path: Path, data: bytes, markdown: str | None, parser: Parser) -> str:
    if markdown is not None:
        return markdown
    if path.suffix.lower() in MARKDOWN_SUFFIXES:
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"markdown file is not valid UTF-8: {path.name}") from error
    return parser.convert_bytes(path.name, data).markdown


def prepare_file(
    path: Path,
    root_relative_path: str,
    markdown: str | None = None,
    *,
    parser: Parser,
    embedder: EmbeddingProvider,
    embedding_model: str,
    description: str | None = None,
    doc_id: str | None = None,
) -> PreparedDocument:
    logger.debug("Preparing file: path=%s markdown_supplied=%s", root_relative_path, markdown is not None)
    data = path.read_bytes()
    if not data:
        raise ValueError("empty file")

    resolved = resolve_markdown(path, data, markdown, parser)
    resolved_doc_id = doc_id or new_doc_id()
    stored_chunks = prepare_markdown(resolved, path.name, resolved_doc_id, embedder=embedder)

    now = datetime.now(timezone.utc)
    crc32, sha256 = file_checksums(data)
    document = StoredDoc(
        id=resolved_doc_id,
        path=root_relative_path,
        created_at=now,
        modified_at=now,
        size_bytes=len(data),
        crc32=crc32,
        sha256=sha256,
        embedding_model=embedding_model,
        chunk_count=len(stored_chunks),
        description=description,
    )
    return PreparedDocument(doc=document, chunks=stored_chunks)
