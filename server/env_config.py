"""Server configuration from environment variables (.env). No YAML."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from platformdirs import user_data_dir

_APP_NAME = "knowledge-rag-proxy"

# Proxy defaults override knowledge-rag's built-in bge-small-en-v1.5 (English-only).
_DEFAULT_EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
_DEFAULT_EMBEDDING_DIMENSIONS = 1024


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _app_data_dir() -> Path:
    """Cross-platform per-user data dir for chroma/db and model cache.

    macOS: ~/Library/Application Support/knowledge-rag-proxy
    Linux: ~/.local/share/knowledge-rag-proxy
    Windows: %LOCALAPPDATA%\\knowledge-rag-proxy
    """
    return Path(user_data_dir(_APP_NAME))


def get_temp_dir() -> Path:
    """Base temp dir for throwaway scaffolding and in-progress uploads.

    KRP_TMP_DIR overrides it (created if missing); unset falls back to the
    cross-platform system temp (tempfile.gettempdir(): macOS/Linux $TMPDIR or
    /tmp, Windows %TEMP%). Kept separate from the watched documents dir so
    half-written uploads never reach the watcher or external sync.
    """
    raw = os.environ.get("KRP_TMP_DIR")
    if raw and raw.strip():
        override = Path(raw).expanduser().resolve()
        override.mkdir(parents=True, exist_ok=True)
        return override
    return Path(tempfile.gettempdir())


def _library_base_dir() -> Path:
    """Throwaway base for the knowledge-rag library's import-time scaffolding.

    The library eagerly creates {BASE_DIR}/{documents,data,models_cache} on
    import; the proxy overrides every real path afterwards, so this base holds
    nothing persistent. Put it under the temp dir (KRP_TMP_DIR or system temp).
    """
    return get_temp_dir() / _APP_NAME / "base"


def _path_or_default(env_name: str, default: Path) -> Path:
    raw = os.environ.get(env_name)
    if raw and raw.strip():
        return Path(raw).expanduser().resolve()
    return default.resolve()


def _optional_int(env_name: str) -> int | None:
    raw = os.environ.get(env_name)
    if raw is None or not raw.strip():
        return None
    return int(raw.strip())


def _optional_json_object(env_name: str) -> dict[str, Any] | None:
    raw = os.environ.get(env_name)
    if raw is None or not raw.strip():
        return None
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError(f"{env_name} must be a JSON object")
    return parsed


def get_documents_dir() -> Path:
    """The single folder that is watched, uploaded to, and downloaded from.

    Required (KRP_DOCUMENTS_DIR). Independent of the library's internal BASE_DIR;
    relative paths resolve against the current working directory.
    """
    raw = os.environ.get("KRP_DOCUMENTS_DIR")
    if not raw or not raw.strip():
        raise RuntimeError(
            "KRP_DOCUMENTS_DIR is not set. Point it at the folder to index and "
            "watch (set it in .env)."
        )
    return Path(raw).expanduser().resolve()


def bootstrap_library_base() -> None:
    """Prepare the environment before the knowledge-rag library is imported.

    knowledge-rag resolves BASE_DIR from KNOWLEDGE_RAG_DIR at import time and
    eagerly creates {BASE_DIR}/{documents,data,models_cache}. If unset, steer
    that internal base to {KRP_TMP_DIR or system temp}/knowledge-rag-proxy/base
    so the library's throwaway scaffolding never lands in the indexed folder or
    a TCC-protected directory. The folder actually indexed and watched is
    KRP_DOCUMENTS_DIR.

    Must run after load_dotenv() and before importing anything that pulls in
    mcp_server.config.
    """
    if not os.environ.get("KRP_DOCUMENTS_DIR", "").strip():
        raise RuntimeError(
            "KRP_DOCUMENTS_DIR is not set. Point it at the folder to index and "
            "watch (set it in .env)."
        )
    if not os.environ.get("KNOWLEDGE_RAG_DIR", "").strip():
        os.environ["KNOWLEDGE_RAG_DIR"] = str(_library_base_dir())


def apply_env_config() -> None:
    """Apply KRP_* env vars to the knowledge-rag config singleton.

    Call once after load_dotenv() and before get_orchestrator().
    """
    from mcp_server.config import config

    app_data = _app_data_dir()

    config.documents_dir = get_documents_dir()
    config.data_dir = _path_or_default("KRP_DATA_DIR", app_data / "db")
    config.chroma_dir = config.data_dir / "chroma_db"
    config.models_cache_dir = _path_or_default("KRP_MODELS_CACHE_DIR", app_data / "models_cache")

    embedding_model = os.environ.get("KRP_EMBEDDING_MODEL", _DEFAULT_EMBEDDING_MODEL).strip()
    config.embedding_model = embedding_model

    embedding_dimensions = _optional_int("KRP_EMBEDDING_DIMENSIONS")
    config.embedding_dim = (
        embedding_dimensions if embedding_dimensions is not None else _DEFAULT_EMBEDDING_DIMENSIONS
    )

    chunk_size = _optional_int("KRP_CHUNK_SIZE")
    if chunk_size is not None:
        config.chunk_size = chunk_size

    chunk_overlap = _optional_int("KRP_CHUNK_OVERLAP")
    if chunk_overlap is not None:
        config.chunk_overlap = chunk_overlap

    reranker_enabled = os.environ.get("KRP_RERANKER_ENABLED")
    if reranker_enabled is not None:
        config.reranker_enabled = _truthy(reranker_enabled)

    reranker_model = os.environ.get("KRP_RERANKER_MODEL")
    if reranker_model:
        config.reranker_model = reranker_model.strip()

    reranker_top_k = _optional_int("KRP_RERANKER_TOP_K_MULTIPLIER")
    if reranker_top_k is not None:
        config.reranker_top_k_multiplier = reranker_top_k

    default_results = _optional_int("KRP_SEARCH_DEFAULT_RESULTS")
    if default_results is not None:
        config.default_results = default_results

    max_results = _optional_int("KRP_SEARCH_MAX_RESULTS")
    if max_results is not None:
        config.max_results = max_results

    collection_name = os.environ.get("KRP_COLLECTION_NAME")
    if collection_name:
        config.collection_name = collection_name.strip()

    category_mappings = _optional_json_object("KRP_CATEGORY_MAPPINGS")
    if category_mappings is not None:
        config.category_mappings = {str(key): str(value) for key, value in category_mappings.items()}

    keyword_routes = _optional_json_object("KRP_KEYWORD_ROUTES")
    if keyword_routes is not None:
        config.keyword_routes = {
            str(key): [str(item) for item in value]
            for key, value in keyword_routes.items()
            if isinstance(value, list)
        }

    # Create only app-managed storage. The indexed folder (documents_dir /
    # KRP_DOCUMENTS_DIR) is the user's own directory and must already exist;
    # startup probing fails fast if it does not, instead of silently creating
    # an empty folder that indexes nothing.
    for directory in (config.data_dir, config.chroma_dir, config.models_cache_dir):
        directory.mkdir(parents=True, exist_ok=True)


def get_watcher_debounce_seconds() -> float:
    debounce = _optional_int("KRP_WATCH_DEBOUNCE")
    if debounce is not None and debounce > 0:
        return float(debounce)
    return 10.0


def get_allowed_roots() -> list[Path]:
    """Single root for upload/download path resolution: the documents folder."""
    from mcp_server.config import config

    return [config.documents_dir.resolve()]
