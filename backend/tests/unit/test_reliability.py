from datetime import UTC, datetime

import pytest

from all_to_pdf.domain.job import JobStatus, TranslationJob, TranslatorProfile
from all_to_pdf.infrastructure.queues.in_memory import InMemoryJobQueue
from all_to_pdf.infrastructure.repositories.in_memory import (
    ConcurrentJobUpdateError,
    InMemoryJobRepository,
)


def _job() -> TranslationJob:
    return TranslationJob.create(
        job_id="job-1",
        input_object_key="uploads/input.pdf",
        source_language="en",
        target_language="vi",
        translator_profile=TranslatorProfile.AZURE_NMT,
        idempotency_key="reliability-key",
        allow_paid_fallback=False,
        llm_profile_id=None,
        now=datetime(2026, 8, 29, tzinfo=UTC),
    ).queue()


async def test_repository_rejects_stale_writer_and_cancel_wins() -> None:
    repository = InMemoryJobRepository()
    original = _job()
    await repository.add_if_absent(original)
    first = original.transition_to(JobStatus.PREFLIGHT)
    await repository.save(first)
    with pytest.raises(ConcurrentJobUpdateError):
        await repository.save(original.transition_to(JobStatus.PREFLIGHT))
    cancelled = first.cancel()
    await repository.save(cancelled)
    await repository.save(first.transition_to(JobStatus.PARSING))
    assert (await repository.get(first.id)) == cancelled


async def test_retryable_job_reenters_queue_and_queue_dead_letters() -> None:
    job = _job().transition_to(JobStatus.FAILED_RETRYABLE, failure_code="TEMP")
    assert job.status.is_terminal is False
    retried = job.retry()
    assert retried.status is JobStatus.QUEUED
    queue = InMemoryJobQueue(max_retries=0)
    await queue.enqueue(job.id)
    message = await queue.dequeue()
    assert await queue.retry(message) is False
    assert queue.size == 0
    assert queue.dead_letter_size == 1
    assert await queue.healthcheck() is True
