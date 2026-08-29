"""Interfaces used by application services.

Infrastructure code implements these protocols. The application layer never imports
FastAPI, a database driver, Redis, or a cloud SDK.
"""

from __future__ import annotations

from collections.abc import AsyncIterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from all_to_pdf.domain.job import TranslationJob


class JobRepository(Protocol):
    async def add_if_absent(self, job: TranslationJob) -> tuple[TranslationJob, bool]: ...

    async def get(self, job_id: str) -> TranslationJob | None: ...

    async def save(self, job: TranslationJob) -> None: ...


class JobQueue(Protocol):
    async def enqueue(self, job_id: str) -> None: ...


class JobQueueConsumer(Protocol):
    async def dequeue(self) -> str: ...

    async def acknowledge(self, job_id: str) -> None: ...


class WorkerQueue(JobQueue, JobQueueConsumer, Protocol):
    """Combined local interface; production may split producer and consumer clients."""


@dataclass(frozen=True, slots=True)
class StoredObject:
    key: str
    size_bytes: int
    content_type: str
    original_filename: str


class ObjectStorage(Protocol):
    async def save_pdf(
        self,
        *,
        chunks: AsyncIterable[bytes],
        original_filename: str,
        content_type: str,
    ) -> StoredObject: ...

    async def materialize_pdf(self, key: str, destination: Path) -> Path: ...

    async def publish_pdf(
        self,
        source_path: Path,
        *,
        original_filename: str,
    ) -> StoredObject: ...

    async def healthcheck(self) -> bool: ...
