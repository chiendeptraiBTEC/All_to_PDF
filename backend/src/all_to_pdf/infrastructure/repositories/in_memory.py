"""Thread-safe in-memory repository for local development and tests."""

from __future__ import annotations

import asyncio

from all_to_pdf.domain.job import TranslationJob


class InMemoryJobRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, TranslationJob] = {}
        self._job_id_by_idempotency_key: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def add_if_absent(self, job: TranslationJob) -> tuple[TranslationJob, bool]:
        async with self._lock:
            existing_id = self._job_id_by_idempotency_key.get(job.idempotency_key)
            if existing_id is not None:
                return self._jobs[existing_id], False
            self._jobs[job.id] = job
            self._job_id_by_idempotency_key[job.idempotency_key] = job.id
            return job, True

    async def get(self, job_id: str) -> TranslationJob | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def save(self, job: TranslationJob) -> None:
        async with self._lock:
            if job.id not in self._jobs:
                raise KeyError(f"job does not exist: {job.id}")
            self._jobs[job.id] = job
