"""Use cases for creating, reading, and cancelling translation jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from all_to_pdf.application.ports import JobQueue, JobRepository
from all_to_pdf.domain.job import JobStatus, TranslationJob, TranslatorProfile


class JobNotFoundError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class SubmitJobCommand:
    input_object_key: str
    source_language: str
    target_language: str
    translator_profile: TranslatorProfile
    idempotency_key: str
    allow_paid_fallback: bool = False
    llm_profile_id: str | None = None


class SubmitTranslationJob:
    def __init__(self, repository: JobRepository, queue: JobQueue) -> None:
        self._repository = repository
        self._queue = queue

    async def execute(self, command: SubmitJobCommand) -> TranslationJob:
        now = datetime.now(UTC)
        job = TranslationJob.create(
            job_id=str(uuid4()),
            input_object_key=command.input_object_key,
            source_language=command.source_language,
            target_language=command.target_language,
            translator_profile=command.translator_profile,
            idempotency_key=command.idempotency_key,
            allow_paid_fallback=command.allow_paid_fallback,
            llm_profile_id=command.llm_profile_id,
            now=now,
        ).queue(now=now)

        persisted, inserted = await self._repository.add_if_absent(job)
        if inserted:
            await self._queue.enqueue(persisted.id)
        return persisted


class GetTranslationJob:
    def __init__(self, repository: JobRepository) -> None:
        self._repository = repository

    async def execute(self, job_id: str) -> TranslationJob:
        job = await self._repository.get(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        return job


class CancelTranslationJob:
    def __init__(self, repository: JobRepository) -> None:
        self._repository = repository

    async def execute(self, job_id: str) -> TranslationJob:
        job = await self._repository.get(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        if job.status.is_terminal:
            return job
        cancelled = job.cancel()
        await self._repository.save(cancelled)
        return cancelled


class AdvanceTranslationJob:
    """Small worker-facing service that enforces domain transitions."""

    def __init__(self, repository: JobRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        job_id: str,
        status: JobStatus,
        *,
        output_object_key: str | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
    ) -> TranslationJob:
        job = await self._repository.get(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        updated = job.transition_to(
            status,
            output_object_key=output_object_key,
            failure_code=failure_code,
            failure_message=failure_message,
        )
        await self._repository.save(updated)
        return updated
