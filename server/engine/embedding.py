"""OpenAI-compatible HTTP embedding provider."""

from __future__ import annotations

import logging
import time

from openai import APIError, OpenAI

from server.engine.protocols import EmbeddingProvider
from server.env_config import ProviderConfig, get_embedding_dimensions

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

# Large single requests crash some local backends (e.g. LM Studio returns
# connection_send_failed, then "No models loaded"); send at most this many
# texts per HTTP call.
EMBEDDING_BATCH_SIZE = 256

# Local backends intermittently drop the model connection under repeated load;
# the failure is transient, so retry each batch with exponential backoff.
EMBEDDING_MAX_ATTEMPTS = 5
EMBEDDING_RETRY_INITIAL_DELAY = 0.5
EMBEDDING_RETRY_MAX_DELAY = 8.0


def openai_client_from_provider(config: ProviderConfig) -> OpenAI:
    return OpenAI(base_url=config.base_url, api_key=config.token)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self.client = openai_client_from_provider(config)
        self.model = config.model or DEFAULT_EMBEDDING_MODEL
        self.dimensions = get_embedding_dimensions()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        batch_count = (len(texts) + EMBEDDING_BATCH_SIZE - 1) // EMBEDDING_BATCH_SIZE
        logger.debug(
            "Requesting embeddings: count=%d model=%s dimensions=%d batches=%d",
            len(texts),
            self.model,
            self.dimensions,
            batch_count,
        )
        vectors: list[list[float]] = []
        for batch_start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            batch = texts[batch_start : batch_start + EMBEDDING_BATCH_SIZE]
            vectors.extend(self._embed_batch(batch))

        if len(vectors) != len(texts):
            raise RuntimeError(
                f"embedding provider returned {len(vectors)} vectors for {len(texts)} texts"
            )
        logger.info("Received embeddings: count=%d", len(vectors))
        return vectors

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        logger.debug("Embedding batch: count=%d", len(texts))
        response = self._create_with_retry(texts)
        vectors = [item.embedding for item in response.data]
        if len(vectors) != len(texts):
            raise RuntimeError(
                f"embedding provider returned {len(vectors)} vectors for {len(texts)} texts"
            )
        for vector in vectors:
            if len(vector) != self.dimensions:
                raise RuntimeError(
                    f"embedding vector size {len(vector)} != GRIM_EMBEDDING_DIMENSIONS {self.dimensions}"
                )
        return vectors

    def _create_with_retry(self, texts: list[str]):
        delay = EMBEDDING_RETRY_INITIAL_DELAY
        for attempt in range(1, EMBEDDING_MAX_ATTEMPTS + 1):
            try:
                return self.client.embeddings.create(
                    input=texts,
                    model=self.model,
                    dimensions=self.dimensions,
                )
            except APIError as error:
                if attempt == EMBEDDING_MAX_ATTEMPTS:
                    raise
                logger.warning(
                    "Embedding request failed (attempt %d/%d), retrying in %.1fs: %s",
                    attempt,
                    EMBEDDING_MAX_ATTEMPTS,
                    delay,
                    error,
                )
                time.sleep(delay)
                delay = min(delay * 2, EMBEDDING_RETRY_MAX_DELAY)
        raise RuntimeError("unreachable: embedding retry loop exited without returning")
