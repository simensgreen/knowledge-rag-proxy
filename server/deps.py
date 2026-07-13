"""FastAPI dependencies.

Singletons live on `app.state` (created in the lifespan); dependencies read
them from the incoming request, so there is no module-level mutable state.
"""

from __future__ import annotations

from fastapi import Request

from server.engine.doc_store import DocStore
from server.engine.embedding import DEFAULT_EMBEDDING_MODEL, OpenAIEmbeddingProvider
from server.engine.markitdown_parser import MarkitdownParser
from server.engine.protocols import EmbeddingProvider, Parser
from server.env_config import get_ocr_provider_config, require_embedding_provider_config
from server.services.index_queue import IndexQueue


def build_parser() -> Parser:
    return MarkitdownParser(ocr_config=get_ocr_provider_config())


def build_embedder() -> EmbeddingProvider:
    return OpenAIEmbeddingProvider(require_embedding_provider_config())


def embedding_model_name(embedder: EmbeddingProvider) -> str:
    model = getattr(embedder, "model", None)
    if isinstance(model, str) and model:
        return model
    return DEFAULT_EMBEDDING_MODEL


def get_parser_dep(request: Request) -> Parser:
    return request.app.state.parser


def get_store_dep(request: Request) -> DocStore:
    return request.app.state.doc_store


def get_embedder_dep(request: Request) -> EmbeddingProvider:
    return request.app.state.embedder


def get_queue_dep(request: Request) -> IndexQueue:
    return request.app.state.queue
