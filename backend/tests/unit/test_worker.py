from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from all_to_pdf.application.engine import (
    EngineProgress,
    OcrRequiredError,
    ProgressCallback,
    ReviewRequiredError,
    TranslationEngineError,
    TranslationRunRequest,
    TranslationRunResult,
)
from all_to_pdf.application.jobs import SubmitJobCommand, SubmitTranslationJob
from all_to_pdf.application.worker import ProcessTranslationJob
from all_to_pdf.domain.job import JobStatus, TranslatorProfile
from all_to_pdf.infrastructure.quality.basic import BasicPdfQualityGate
from all_to_pdf.infrastructure.queues.in_memory import InMemoryJobQueue
from all_to_pdf.infrastructure.repositories.in_memory import InMemoryJobRepository
from all_to_pdf.infrastructure.storage.local import LocalObjectStorage

_MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


async def _chunks() -> AsyncIterator[bytes]:
    yield _MINIMAL_PDF


class CopyingRunner:
    async def run(
        self,
        request: TranslationRunRequest,
        on_progress: ProgressCallback,
    ) -> TranslationRunResult:
        for status, percent in (
            (JobStatus.PARSING, 20.0),
            (JobStatus.TRANSLATING, 30.0),
            (JobStatus.TYPESETTING, 70.0),
            (JobStatus.GENERATING_PDF, 92.0),
        ):
            await on_progress(EngineProgress(status, percent, status.value))
        await asyncio.to_thread(request.output_path.write_bytes, _MINIMAL_PDF)
        return TranslationRunResult(request.output_path, "fake", "1")


class OcrRunner:
    async def run(
        self,
        request: TranslationRunRequest,
        on_progress: ProgressCallback,
    ) -> TranslationRunResult:
        del request
        await on_progress(EngineProgress(JobStatus.PARSING, 15.0, "detect scanned PDF"))
        raise OcrRequiredError("fixture has no text layer")


class ErrorRunner:
    def __init__(self, error: Exception) -> None:
        self._error = error

    async def run(
        self,
        request: TranslationRunRequest,
        on_progress: ProgressCallback,
    ) -> TranslationRunResult:
        del request, on_progress
        raise self._error


class ReviewRunner:
    async def run(
        self,
        request: TranslationRunRequest,
        on_progress: ProgressCallback,
    ) -> TranslationRunResult:
        del request
        await on_progress(EngineProgress(JobStatus.TYPESETTING, 80, "typesetting"))
        raise ReviewRequiredError("manual review")


class RejectingQualityGate:
    async def validate(self, source_path: Path, output_path: Path) -> None:
        del source_path, output_path
        raise ReviewRequiredError("quality review")


async def _submitted_job(
    tmp_path: Path,
) -> tuple[
    InMemoryJobRepository,
    InMemoryJobQueue,
    LocalObjectStorage,
    str,
]:
    storage = LocalObjectStorage(tmp_path / "storage", max_upload_bytes=1024 * 1024)
    stored = await storage.save_pdf(
        chunks=_chunks(),
        original_filename="fixture.pdf",
        content_type="application/pdf",
    )
    repository = InMemoryJobRepository()
    queue = InMemoryJobQueue()
    service = SubmitTranslationJob(repository, queue)
    job = await service.execute(
        SubmitJobCommand(
            input_object_key=stored.key,
            source_language="en",
            target_language="vi",
            translator_profile=TranslatorProfile.AZURE_NMT,
            idempotency_key="worker-test-key",
        )
    )
    return repository, queue, storage, job.id


async def test_worker_completes_job_and_publishes_output(tmp_path: Path) -> None:
    repository, queue, storage, job_id = await _submitted_job(tmp_path)
    worker = ProcessTranslationJob(
        repository,
        storage,
        CopyingRunner(),
        BasicPdfQualityGate(),
        workspace_root=tmp_path / "work",
    )

    completed = await worker.run_once(queue)

    assert completed.id == job_id
    assert completed.status is JobStatus.SUCCEEDED
    assert completed.progress_percent == 100.0
    assert completed.output_object_key is not None
    destination = tmp_path / "download.pdf"
    await storage.materialize_pdf(completed.output_object_key, destination)
    assert await asyncio.to_thread(destination.read_bytes) == _MINIMAL_PDF
    assert queue.size == 0


async def test_worker_maps_scanned_pdf_to_ocr_required(tmp_path: Path) -> None:
    repository, queue, storage, _ = await _submitted_job(tmp_path)
    worker = ProcessTranslationJob(
        repository,
        storage,
        OcrRunner(),
        BasicPdfQualityGate(),
        workspace_root=tmp_path / "work",
    )

    completed = await worker.run_once(queue)

    assert completed.status is JobStatus.OCR_REQUIRED
    assert completed.failure_code == "OCR_REQUIRED"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            TranslationEngineError("retry", code="TEMP", retryable=True),
            JobStatus.FAILED_RETRYABLE,
        ),
        (
            TranslationEngineError("bad", code="BAD", retryable=False),
            JobStatus.FAILED_PERMANENT,
        ),
        (RuntimeError("unexpected"), JobStatus.FAILED_RETRYABLE),
    ],
)
async def test_worker_maps_engine_and_unexpected_failures(
    tmp_path: Path,
    error: Exception,
    expected: JobStatus,
) -> None:
    repository, queue, storage, _ = await _submitted_job(tmp_path)
    worker = ProcessTranslationJob(
        repository,
        storage,
        ErrorRunner(error),
        BasicPdfQualityGate(),
        workspace_root=tmp_path / "work",
    )

    completed = await worker.run_once(queue)

    assert completed.status is expected
    assert completed.failure_code is not None


async def test_worker_maps_engine_and_quality_review(tmp_path: Path) -> None:
    repository, queue, storage, _ = await _submitted_job(tmp_path)
    worker = ProcessTranslationJob(
        repository,
        storage,
        ReviewRunner(),
        BasicPdfQualityGate(),
        workspace_root=tmp_path / "work",
    )
    reviewed = await worker.run_once(queue)
    assert reviewed.status is JobStatus.NEEDS_REVIEW

    repository, queue, storage, _ = await _submitted_job(tmp_path / "quality")
    worker = ProcessTranslationJob(
        repository,
        storage,
        CopyingRunner(),
        RejectingQualityGate(),
        workspace_root=tmp_path / "quality-work",
    )
    rejected = await worker.run_once(queue)
    assert rejected.status is JobStatus.NEEDS_REVIEW


async def test_worker_returns_terminal_job_and_rejects_unknown_id(tmp_path: Path) -> None:
    repository, queue, storage, job_id = await _submitted_job(tmp_path)
    job = await repository.get(job_id)
    assert job is not None
    cancelled = job.cancel()
    await repository.save(cancelled)
    worker = ProcessTranslationJob(
        repository,
        storage,
        CopyingRunner(),
        BasicPdfQualityGate(),
        workspace_root=tmp_path / "work",
    )

    assert await worker.execute(job_id) == cancelled
    with pytest.raises(KeyError):
        await worker.execute("missing")
    assert queue.size == 1
