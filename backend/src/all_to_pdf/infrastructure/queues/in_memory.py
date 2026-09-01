"""Reliable in-memory queue used for local development and tests."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from all_to_pdf.application.ports import QueueMessage


class InMemoryJobQueue:
    def __init__(self, *, max_retries: int = 3) -> None:
        self._queue: asyncio.Queue[QueueMessage] = asyncio.Queue()
        self._max_retries = max_retries
        self._dead_letters: list[QueueMessage] = []

    async def enqueue(self, job_id: str) -> None:
        await self._queue.put(QueueMessage(job_id=job_id, receipt=uuid4().hex))

    async def dequeue(self) -> QueueMessage:
        return await self._queue.get()

    async def acknowledge(self, message: QueueMessage) -> None:
        del message
        self._queue.task_done()

    async def retry(self, message: QueueMessage) -> bool:
        self._queue.task_done()
        next_message = QueueMessage(
            job_id=message.job_id,
            receipt=uuid4().hex,
            attempt=message.attempt + 1,
        )
        if next_message.attempt > self._max_retries:
            self._dead_letters.append(next_message)
            return False
        await self._queue.put(next_message)
        return True

    async def heartbeat(self, message: QueueMessage) -> None:
        del message

    @property
    def size(self) -> int:
        return self._queue.qsize()

    @property
    def dead_letter_size(self) -> int:
        return len(self._dead_letters)

    async def healthcheck(self) -> bool:
        return True

    async def close(self) -> None:
        return None
