"""In-memory queue used only for local development and application tests."""

from __future__ import annotations

import asyncio


class InMemoryJobQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()

    async def enqueue(self, job_id: str) -> None:
        await self._queue.put(job_id)

    async def dequeue(self) -> str:
        return await self._queue.get()

    @property
    def size(self) -> int:
        return self._queue.qsize()
