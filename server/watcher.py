"""Optional document watcher — stub. Paths come from config.yaml."""

from __future__ import annotations

from typing import Any


def start_watchers(_config: dict[str, Any]) -> None:
    """Start watchdog observers for configured directories.

    TODO Phase 1: wire knowledge-rag DocumentWatcher with debounce from config.
    """
    pass


def stop_watchers() -> None:
    """Stop all active observers."""
    pass
