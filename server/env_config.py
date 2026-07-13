"""Server configuration from environment variables (.env). No YAML."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_dir

_APP_NAME = "grimoire"
_DEFAULT_SEARCH_RESULTS = 5
_DEFAULT_SEARCH_MAX_RESULTS = 20


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _optional_int(env_name: str) -> int | None:
    raw = os.environ.get(env_name)
    if raw is None or not raw.strip():
        return None
    return int(raw.strip())


def _app_data_dir() -> Path:
    return Path(user_data_dir(_APP_NAME))


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
    return f"surrealkv://{_app_data_dir() / 'surreal'}"


def get_allowed_roots() -> list[Path]:
    return [get_documents_dir()]


def is_watcher_disabled() -> bool:
    return os.environ.get("GRIM_WATCH_DISABLED", "").strip() == "1"


def get_watcher_debounce_seconds() -> float:
    debounce = _optional_int("GRIM_WATCH_DEBOUNCE")
    if debounce is not None and debounce > 0:
        return float(debounce)
    return 10.0


def get_search_default_results() -> int:
    configured = _optional_int("GRIM_SEARCH_DEFAULT_RESULTS")
    if configured is not None and configured >= 1:
        return configured
    return _DEFAULT_SEARCH_RESULTS


def get_search_max_results() -> int:
    configured = _optional_int("GRIM_SEARCH_MAX_RESULTS")
    if configured is not None and configured >= 1:
        return configured
    return _DEFAULT_SEARCH_MAX_RESULTS


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    base_url: str
    token: str
    model: str | None = None


def _read_provider(prefix: str) -> ProviderConfig | None:
    provider = os.environ.get(f"GRIM_{prefix}_PROVIDER", "").strip()
    base_url = os.environ.get(f"GRIM_{prefix}_BASE_URL", "").strip()
    token = os.environ.get(f"GRIM_{prefix}_TOKEN", "").strip()
    if not provider and not base_url and not token:
        return None
    model = os.environ.get(f"GRIM_{prefix}_MODEL", "").strip() or None
    return ProviderConfig(provider=provider, base_url=base_url, token=token, model=model)


def get_embedding_provider_config() -> ProviderConfig | None:
    return _read_provider("EMBEDDING")


def get_ocr_provider_config() -> ProviderConfig | None:
    return _read_provider("OCR")


def get_embedding_dimensions() -> int | None:
    return _optional_int("GRIM_EMBEDDING_DIMENSIONS")


def is_docs_enabled() -> bool:
    return _truthy(os.environ.get("GRIM_DOCS"))


def get_log_level() -> str:
    return os.environ.get("GRIM_LOG_LEVEL", "INFO").upper()
