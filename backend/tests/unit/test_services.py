from all_to_pdf.application.jobs import SubmitJobCommand, SubmitTranslationJob
from all_to_pdf.domain.job import JobStatus, TranslatorProfile
from all_to_pdf.infrastructure.queues.in_memory import InMemoryJobQueue
from all_to_pdf.infrastructure.repositories.in_memory import InMemoryJobRepository


async def test_submit_is_idempotent_and_enqueues_once() -> None:
    repository = InMemoryJobRepository()
    queue = InMemoryJobQueue()
    service = SubmitTranslationJob(repository, queue)
    command = SubmitJobCommand(
        input_object_key="uploads/input.pdf",
        source_language="en",
        target_language="vi",
        translator_profile=TranslatorProfile.AZURE_NMT,
        idempotency_key="same-request-key",
    )

    first = await service.execute(command)
    second = await service.execute(command)

    assert first.id == second.id
    assert first.status is JobStatus.QUEUED
    assert queue.size == 1
