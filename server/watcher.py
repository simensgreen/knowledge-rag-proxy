"""Document watcher lifecycle (stubbed in Phase 1)."""

from __future__ import annotations

import logging

from server.env_config import is_watcher_disabled

logger = logging.getLogger(__name__)


def start_watchers() -> None:
    """Phase 2: start debounced filesystem watcher on GRIM_DOCUMENTS_DIR."""
    if is_watcher_disabled():
        logger.debug("Watcher disabled via GRIM_WATCH_DISABLED")
        return
    logger.debug("Watcher not implemented in Phase 1 scaffold")


def stop_watchers() -> None:
    """Phase 2: stop active filesystem watchers."""
    logger.debug("Watcher stop noop in Phase 1 scaffold")
