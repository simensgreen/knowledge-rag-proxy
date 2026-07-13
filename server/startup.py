"""Server startup tasks."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from server.engine.doc_store import DocStore
from server.engine.protocols import EmbeddingProvider
from server.env_config import get_documents_dir, get_embedding_dimensions

logger = logging.getLogger(__name__)

_EMBEDDING_PROBE_TEXT = "grimoire embedding healthcheck"

_MACOS_TCC_HINT = (
    "On macOS this is usually a privacy restriction (TCC): grant the process "
    "running the server Full Disk Access, or move the data root out of protected "
    "locations such as ~/Documents, ~/Desktop, or ~/Downloads and update "
    "GRIM_DOCUMENTS_DIR."
)


def _probe_readable(path: Path, label: str) -> None:
    if not path.is_dir():
        raise RuntimeError(
            f"{label} does not exist or is not a directory: {path}. "
            "Set GRIM_DOCUMENTS_DIR to a readable folder."
        )
    try:
        with os.scandir(path) as entries:
            for _ in entries:
                break
    except OSError as error:
        raise RuntimeError(
            f"{label} is not readable: {path} ({error.strerror}). {_MACOS_TCC_HINT}"
        ) from error


def probe_documents_dir() -> None:
    """Fail fast when the documents directory is missing or unreadable."""
    documents_dir = get_documents_dir()
    _probe_readable(documents_dir, "Documents directory (GRIM_DOCUMENTS_DIR)")
    logger.info("Documents directory probe succeeded: %s", documents_dir)


def probe_embedding_provider(embedder: EmbeddingProvider) -> None:
    """Fail fast when embeddings are unreachable or return an unexpected size."""
    expected_dimensions = get_embedding_dimensions()
    logger.debug("Probing embedding provider with a test phrase")
    try:
        vectors = embedder.embed([_EMBEDDING_PROBE_TEXT])
    except RuntimeError:
        # embed() already validates the returned size; surface that message as-is.
        raise
    except Exception as error:
        raise RuntimeError(
            "Embedding provider is not reachable. Check GRIM_EMBEDDING_BASE_URL, "
            "GRIM_EMBEDDING_TOKEN, and that the embedding model is loaded. "
            f"Cause: {error}"
        ) from error

    if not vectors or not vectors[0]:
        raise RuntimeError("Embedding provider returned no vector for the probe text.")

    dimension = len(vectors[0])
    if dimension != expected_dimensions:
        raise RuntimeError(
            f"Embedding size mismatch: provider returned {dimension}, "
            f"GRIM_EMBEDDING_DIMENSIONS is {expected_dimensions}. "
            "Set GRIM_EMBEDDING_DIMENSIONS to the embedding model's native size."
        )
    logger.info("Embedding provider probe succeeded (dimensions=%d)", dimension)


def verify_stored_embedding_dimensions(store: DocStore) -> None:
    """Fail fast when stored embeddings do not match GRIM_EMBEDDING_DIMENSIONS."""
    expected_dimensions = get_embedding_dimensions()
    logger.debug("Checking stored embedding dimensions against GRIM_EMBEDDING_DIMENSIONS")
    stored_dimensions = store.embedding_dimensions_in_use()
    mismatched = [dimension for dimension in stored_dimensions if dimension != expected_dimensions]
    if mismatched:
        raise RuntimeError(
            f"Stored embeddings have dimensions {mismatched} that differ from "
            f"GRIM_EMBEDDING_DIMENSIONS ({expected_dimensions}). The embedding model "
            "changed. Re-create the SurrealDB store (delete the surreal data dir) or "
            "restore the previous GRIM_EMBEDDING_DIMENSIONS value."
        )
    if stored_dimensions:
        logger.info(
            "Stored embedding dimensions verified (dimensions=%d)", expected_dimensions
        )
    else:
        logger.debug("No stored embeddings to verify")
