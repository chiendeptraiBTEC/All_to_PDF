"""Redis Streams queue with visibility recovery, retries, and dead letters."""

from __future__ import annotations

import asyncio
import importlib
import socket
from typing import Any
from uuid import uuid4

from all_to_pdf.application.ports import QueueMessage


class RedisJobQueue:
    def __init__(
        self,
        url: str,
        *,
        stream: str = "all-to-pdf:jobs",
        group: str = "all-to-pdf-workers",
        consumer: str | None = None,
        dead_letter_stream: str = "all-to-pdf:jobs:dead",
        visibility_timeout_seconds: float = 120.0,
        block_seconds: float = 5.0,
        max_retries: int = 3,
        client: Any | None = None,
    ) -> None:
        self._url = url
        self._stream = stream
        self._group = group
        self._consumer = consumer or f"{socket.gethostname()}-{uuid4().hex[:8]}"
        self._dead_letter_stream = dead_letter_stream
        self._visibility_ms = max(1000, int(visibility_timeout_seconds * 1000))
        self._block_ms = max(1, int(block_seconds * 1000))
        self._max_retries = max_retries
        self._client = client
        self._group_ready = False
        self._init_lock = asyncio.Lock()

    async def _client_instance(self) -> Any:
        if self._client is None:
            async with self._init_lock:
                if self._client is None:
                    redis_async = importlib.import_module("redis.asyncio")
                    self._client = redis_async.from_url(self._url, decode_responses=True)
        return self._client

    async def _ensure_group(self) -> Any:
        client = await self._client_instance()
        if self._group_ready:
            return client
        async with self._init_lock:
            if not self._group_ready:
                try:
                    await client.xgroup_create(self._stream, self._group, id="0-0", mkstream=True)
                except Exception as exc:
                    if "BUSYGROUP" not in str(exc):
                        raise
                self._group_ready = True
        return client

    async def enqueue(self, job_id: str) -> None:
        client = await self._ensure_group()
        await client.xadd(self._stream, {"job_id": job_id, "attempt": "0"})

    async def dequeue(self) -> QueueMessage:
        client = await self._ensure_group()
        while True:
            claimed = await client.xautoclaim(
                self._stream,
                self._group,
                self._consumer,
                min_idle_time=self._visibility_ms,
                start_id="0-0",
                count=1,
            )
            messages = claimed[1] if len(claimed) > 1 else []
            if messages:
                return self._decode(messages[0])
            response = await client.xreadgroup(
                self._group,
                self._consumer,
                {self._stream: ">"},
                count=1,
                block=self._block_ms,
            )
            if response and response[0][1]:
                return self._decode(response[0][1][0])

    async def acknowledge(self, message: QueueMessage) -> None:
        client = await self._ensure_group()
        pipe = client.pipeline(transaction=True)
        pipe.xack(self._stream, self._group, message.receipt)
        pipe.xdel(self._stream, message.receipt)
        await pipe.execute()

    async def retry(self, message: QueueMessage) -> bool:
        client = await self._ensure_group()
        next_attempt = message.attempt + 1
        pipe = client.pipeline(transaction=True)
        pipe.xack(self._stream, self._group, message.receipt)
        pipe.xdel(self._stream, message.receipt)
        fields = {"job_id": message.job_id, "attempt": str(next_attempt)}
        if next_attempt > self._max_retries:
            pipe.xadd(self._dead_letter_stream, fields)
            await pipe.execute()
            return False
        pipe.xadd(self._stream, fields)
        await pipe.execute()
        return True

    async def heartbeat(self, message: QueueMessage) -> None:
        client = await self._ensure_group()
        await client.xclaim(
            self._stream,
            self._group,
            self._consumer,
            min_idle_time=0,
            message_ids=[message.receipt],
            justid=True,
        )

    async def healthcheck(self) -> bool:
        try:
            client = await self._client_instance()
            return bool(await client.ping())
        except Exception:
            return False

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            self._group_ready = False

    @staticmethod
    def _decode(raw: Any) -> QueueMessage:
        receipt, fields = raw
        return QueueMessage(
            job_id=str(fields["job_id"]),
            receipt=str(receipt),
            attempt=int(fields.get("attempt", 0)),
        )
