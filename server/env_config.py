"""Server configuration from environment variables (.env). No YAML."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_dir

APP_NAME = "grimoire"


def truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def optional_int(env_name: str) -> int | None:
    raw = os.environ.get(env_name)
    if raw is None or not raw.strip():
        return None
    return int(raw.strip())


def app_data_dir() -> Path:
    return Path(user_data_dir(APP_NAME))


def get_temp_dir() -> Path:
    """Base temp dir for in-progress uploads."""
    raw = os.environ.get("GRIM_TMP_DIR")
    if raw and raw.strip():
        override = Path(raw).expanduser().resolve()
        override.mkdir(parents=True, exist_ok=True)
        return override
    return Path(tempfile.gettempdir())


def get_documents_dir() -> Path:
    raw = os.environ.get("GRIM_DOCUMENTS_DIR")
    if not raw or not raw.strip():
        raise RuntimeError(
            "GRIM_DOCUMENTS_DIR is not set. Point it at the folder to index and "
            "watch (set it in .env)."
        )
    return Path(raw).expanduser().resolve()


def get_surreal_url() -> str:
    raw = os.environ.get("GRIM_SURREAL_URL")
    if raw and raw.strip():
        return raw.strip()
    return f"surrealkv://{app_data_dir() / 'surreal'}"


def get_surreal_namespace() -> str:
    raw = os.environ.get("GRIM_SURREAL_NAMESPACE")
    if raw and raw.strip():
        return raw.strip()
    return APP_NAME


def get_surreal_database() -> str:
    raw = os.environ.get("GRIM_SURREAL_DATABASE")
    if raw and raw.strip():
        return raw.strip()
    return "main"


def get_fulltext_languages_raw() -> str | None:
    return os.environ.get("GRIM_FULLTEXT_LANGUAGES")


def get_allowed_roots() -> list[Path]:
    return [get_documents_dir()]


def get_watcher_debounce_seconds() -> float:
    debounce = optional_int("GRIM_WATCH_DEBOUNCE")
    if debounce is not None and debounce > 0:
        return float(debounce)
    return 10.0


@dataclass(frozen=True)
class ProviderConfig:
    base_url: str
    token: str
    model: str | None = None


def read_provider(prefix: str) -> ProviderConfig | None:
    base_url = os.environ.get(f"GRIM_{prefix}_BASE_URL", "").strip()
    token = os.environ.get(f"GRIM_{prefix}_TOKEN", "").strip()
    if not base_url and not token:
        return None
    model = os.environ.get(f"GRIM_{prefix}_MODEL", "").strip() or None
    return ProviderConfig(base_url=base_url, token=token, model=model)


def get_embedding_provider_config() -> ProviderConfig | None:
    return read_provider("EMBEDDING")


def require_embedding_provider_config() -> ProviderConfig:
    config = get_embedding_provider_config()
    if config is None or not config.base_url or not config.token:
        raise RuntimeError(
            "GRIM_EMBEDDING_BASE_URL and GRIM_EMBEDDING_TOKEN are required. "
            "Set both in .env for embedding at startup."
        )
    return config


def get_ocr_provider_config() -> ProviderConfig | None:
    return read_provider("OCR")


def get_embedding_dimensions() -> int:
    dimensions = optional_int("GRIM_EMBEDDING_DIMENSIONS")
    if dimensions is None or dimensions < 1:
        raise RuntimeError(
            "GRIM_EMBEDDING_DIMENSIONS is not set. Set it to the embedding vector size "
            "(for example 1536) in .env."
        )
    return dimensions


def is_docs_enabled() -> bool:
    return truthy(os.environ.get("GRIM_DOCS"))


def get_log_level() -> str:
    return os.environ.get("GRIM_LOG_LEVEL", "INFO").upper()
