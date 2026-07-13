"""Document watcher lifecycle."""

from __future__ import annotations

from typing import Any

from mcp_server.server import DocumentWatcher, get_orchestrator
from watchdog.observers import Observer

from server.env_config import get_allowed_roots, get_watcher_debounce_seconds, is_watcher_disabled

_observers: list[Observer] = []


def start_watchers() -> None:
    """Start DocumentWatcher on the documents directory."""
    if is_watcher_disabled():
        return

    debounce_seconds = get_watcher_debounce_seconds()
    watcher = DocumentWatcher(get_orchestrator, debounce_seconds=debounce_seconds)

    for root in get_allowed_roots():
        root.mkdir(parents=True, exist_ok=True)
        observer = Observer()
        observer.schedule(watcher, str(root), recursive=True)
        observer.daemon = True
        observer.start()
        _observers.append(observer)


def stop_watchers() -> None:
    """Stop all active observers."""
    for observer in _observers:
        try:
            observer.stop()
            observer.join(timeout=5)
        except Exception:
            pass
    _observers.clear()
