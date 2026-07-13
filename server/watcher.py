"""Filesystem watcher that submits index/delete tasks to the coalescing queue."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from server.env_config import get_documents_dir
from server.paths import documents_root
from server.services.index_queue import IndexQueue, IndexTask

logger = logging.getLogger(__name__)

_observer: Observer | None = None


def _relative_path(path: str | bytes) -> str | None:
    if isinstance(path, bytes):
        path = path.decode("utf-8", errors="replace")
    absolute = Path(path)
    root = documents_root()
    try:
        resolved = absolute.resolve()
    except OSError:
        return None
    if not resolved.is_relative_to(root):
        return None
    if resolved.name.startswith("."):
        return None
    return resolved.relative_to(root).as_posix()


class IndexEventHandler(FileSystemEventHandler):
    def __init__(self, queue: IndexQueue, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__()
        self.queue = queue
        self.loop = loop

    def _submit(self, task: IndexTask) -> None:
        future = asyncio.run_coroutine_threadsafe(self.queue.submit(task), self.loop)
        future.add_done_callback(self._log_submit_error)

    @staticmethod
    def _log_submit_error(future: Any) -> None:
        error = future.exception()
        if error is not None:
            logger.exception("Failed to submit watcher task: %s", error)

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        relative = _relative_path(event.src_path)
        if relative is None:
            return
        logger.debug("Watcher created: %s", relative)
        self._submit(IndexTask(path=relative, kind="index"))

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        relative = _relative_path(event.src_path)
        if relative is None:
            return
        logger.debug("Watcher modified: %s", relative)
        self._submit(IndexTask(path=relative, kind="index"))

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        relative = _relative_path(event.src_path)
        if relative is None:
            return
        logger.debug("Watcher deleted: %s", relative)
        self._submit(IndexTask(path=relative, kind="delete"))

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        source = _relative_path(event.src_path)
        dest = _relative_path(getattr(event, "dest_path", ""))
        if source is not None:
            self._submit(IndexTask(path=source, kind="delete"))
        if dest is not None:
            self._submit(IndexTask(path=dest, kind="index"))


def start_watchers(queue: IndexQueue, loop: asyncio.AbstractEventLoop | None = None) -> None:
    global _observer
    if _observer is not None:
        return

    documents_dir = get_documents_dir()
    event_loop = loop or asyncio.get_running_loop()
    handler = IndexEventHandler(queue, event_loop)
    observer = Observer()
    observer.schedule(handler, str(documents_dir), recursive=True)
    observer.daemon = True
    observer.start()
    _observer = observer
    logger.info("Filesystem watcher started on %s", documents_dir)


def stop_watchers() -> None:
    global _observer
    if _observer is None:
        return
    logger.info("Stopping filesystem watcher")
    _observer.stop()
    _observer.join(timeout=5.0)
    _observer = None
