"""Coalescing in-memory index task queue with debounce."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field, replace
from typing import Literal

from server.env_config import get_watcher_debounce_seconds

TaskKind = Literal["index", "delete", "reindex", "reindex_markdown", "move"]


@dataclass
class IndexTask:
    path: str
    kind: TaskKind
    markdown: str | None = None
    description: str | None = None
    dest_path: str | None = None
    enqueued_at: float = field(default_factory=time.time)
    debounced_at: float | None = None
    started_at: float | None = None


@dataclass(frozen=True)
class QueueTaskView:
    path: str
    kind: str
    dest_path: str | None = None
    debounced_at: float | None = None
    enqueued_at: float | None = None
    started_at: float | None = None


@dataclass(frozen=True)
class QueueSnapshot:
    debounced: list[QueueTaskView]
    processing: list[QueueTaskView]
    pending: list[QueueTaskView]

    def to_indexing_or_none(self) -> dict[str, list[dict[str, object]]] | None:
        if not self.debounced and not self.processing and not self.pending:
            return None
        return {
            "debounced": [_task_view_to_dict(item) for item in self.debounced],
            "processing": [_task_view_to_dict(item) for item in self.processing],
            "pending": [_task_view_to_dict(item) for item in self.pending],
        }


def _task_view_to_dict(view: QueueTaskView) -> dict[str, object]:
    payload: dict[str, object] = {"path": view.path, "kind": view.kind}
    if view.dest_path is not None:
        payload["dest_path"] = view.dest_path
    if view.debounced_at is not None:
        payload["debounced_at"] = view.debounced_at
    if view.enqueued_at is not None:
        payload["enqueued_at"] = view.enqueued_at
    if view.started_at is not None:
        payload["started_at"] = view.started_at
    return payload


def _merge_tasks(existing: IndexTask, incoming: IndexTask) -> IndexTask:
    if incoming.kind == "delete" and existing.kind != "move":
        kind: TaskKind = "delete"
    elif incoming.kind == "move" or existing.kind == "move":
        kind = "move"
    elif incoming.kind == "reindex" or existing.kind == "reindex":
        kind = "reindex"
    elif incoming.kind == "reindex_markdown" or existing.kind == "reindex_markdown":
        kind = "reindex_markdown"
    else:
        kind = incoming.kind

    return IndexTask(
        path=incoming.path,
        kind=kind,
        markdown=incoming.markdown if incoming.markdown is not None else existing.markdown,
        description=(
            incoming.description if incoming.description is not None else existing.description
        ),
        dest_path=incoming.dest_path if incoming.dest_path is not None else existing.dest_path,
        enqueued_at=existing.enqueued_at,
        debounced_at=incoming.debounced_at or existing.debounced_at,
        started_at=None,
    )


def _to_view(task: IndexTask, *, stage: str) -> QueueTaskView:
    return QueueTaskView(
        path=task.path,
        kind=task.kind,
        dest_path=task.dest_path,
        debounced_at=task.debounced_at if stage == "debounced" else None,
        enqueued_at=task.enqueued_at if stage == "pending" else None,
        started_at=task.started_at if stage == "processing" else None,
    )


class IndexQueue:
    def __init__(self, debounce_seconds: float | None = None) -> None:
        self._debounce_seconds = (
            debounce_seconds if debounce_seconds is not None else get_watcher_debounce_seconds()
        )
        self._debounced: dict[str, IndexTask] = {}
        self._debounce_handles: dict[str, asyncio.TimerHandle] = {}
        self._pending: dict[str, IndexTask] = {}
        self._order: deque[str] = deque()
        self._processing: IndexTask | None = None
        self._event = asyncio.Event()
        self._lock = asyncio.Lock()

    async def submit(self, task: IndexTask) -> None:
        now = time.time()
        stamped = replace(task, debounced_at=now)
        async with self._lock:
            existing = self._debounced.get(stamped.path) or self._pending.get(stamped.path)
            merged = _merge_tasks(existing, stamped) if existing else stamped

            self._debounced[stamped.path] = merged
            if stamped.path in self._pending:
                del self._pending[stamped.path]
                try:
                    self._order.remove(stamped.path)
                except ValueError:
                    pass

            handle = self._debounce_handles.pop(stamped.path, None)
            if handle is not None:
                handle.cancel()

            loop = asyncio.get_running_loop()
            self._debounce_handles[stamped.path] = loop.call_later(
                self._debounce_seconds,
                lambda path=stamped.path: asyncio.create_task(self._promote_debounced(path)),
            )

    async def _promote_debounced(self, path: str) -> None:
        async with self._lock:
            task = self._debounced.pop(path, None)
            self._debounce_handles.pop(path, None)
            if task is None:
                return
            existing_pending = self._pending.get(path)
            merged = _merge_tasks(existing_pending, task) if existing_pending else task
            merged = replace(merged, enqueued_at=time.time(), debounced_at=None)
            self._pending[path] = merged
            if path not in self._order:
                self._order.append(path)
            self._event.set()

    async def pop(self) -> IndexTask:
        while True:
            async with self._lock:
                if self._order:
                    path = self._order.popleft()
                    task = self._pending.pop(path)
                    started = replace(task, started_at=time.time())
                    self._processing = started
                    if not self._order:
                        self._event.clear()
                    return started
                self._event.clear()
            await self._event.wait()

    async def done(self) -> None:
        async with self._lock:
            self._processing = None

    def snapshot(self) -> QueueSnapshot:
        processing = (
            [_to_view(self._processing, stage="processing")] if self._processing is not None else []
        )
        pending = [
            _to_view(self._pending[path], stage="pending")
            for path in list(self._order)
            if path in self._pending
        ]
        debounced = [_to_view(task, stage="debounced") for task in list(self._debounced.values())]
        return QueueSnapshot(debounced=debounced, processing=processing, pending=pending)
