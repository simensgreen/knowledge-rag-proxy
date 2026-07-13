"""Tests for coalescing index queue."""

from __future__ import annotations

import asyncio

from server.services.index_queue import IndexQueue, IndexTask


def test_submit_always_starts_in_debounced() -> None:
    async def scenario() -> None:
        queue = IndexQueue(debounce_seconds=10.0)
        await queue.submit(IndexTask(path="a.md", kind="index"))
        snapshot = queue.snapshot()
        assert len(snapshot.debounced) == 1
        assert snapshot.debounced[0].path == "a.md"
        assert snapshot.pending == []
        assert snapshot.processing == []
        assert snapshot.to_indexing_or_none() is not None

    asyncio.run(scenario())


def test_coalesce_same_path() -> None:
    async def scenario() -> None:
        queue = IndexQueue(debounce_seconds=10.0)
        await queue.submit(IndexTask(path="a.md", kind="index", description="first"))
        await queue.submit(
            IndexTask(path="a.md", kind="index", markdown="# body", description="second")
        )
        snapshot = queue.snapshot()
        assert len(snapshot.debounced) == 1
        task = queue._debounced["a.md"]
        assert task.markdown == "# body"
        assert task.description == "second"

    asyncio.run(scenario())


def test_promote_to_pending_and_pop() -> None:
    async def scenario() -> None:
        queue = IndexQueue(debounce_seconds=0.01)
        await queue.submit(IndexTask(path="a.md", kind="reindex"))
        await asyncio.sleep(0.05)
        snapshot = queue.snapshot()
        assert snapshot.debounced == []
        assert len(snapshot.pending) == 1

        task = await asyncio.wait_for(queue.pop(), timeout=1.0)
        assert task.path == "a.md"
        assert task.kind == "reindex"
        assert queue.snapshot().processing[0].path == "a.md"
        await queue.done()
        assert queue.snapshot().to_indexing_or_none() is None

    asyncio.run(scenario())
