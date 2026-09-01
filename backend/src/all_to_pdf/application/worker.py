"""Worker use case that owns the translation-job lifecycle."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from contextlib import suppress
from pathlib import Path

from all_to_pdf.application.engine import (
    EngineProgress,
    OcrRequiredError,
    PdfQualityGate,
    ReviewRequiredError,
    TranslationEngineError,
    TranslationRunner,
    TranslationRunRequest,
)
from all_to_pdf.application.ports import (
    JobQueueConsumer,
    JobRepository,
    ObjectStorage,
    QueueMessage,
)
from all_to_pdf.domain.job import JobStatus, TranslationJob

logger = logging.getLogger(__name__)

_PIPELINE = (
    JobStatus.QUEUED,
    JobStatus.PREFLIGHT,
    JobStatus.PARSING,
    JobStatus.TRANSLATING,
    JobStatus.TYPESETTING,
    JobStatus.GENERATING_PDF,
    JobStatus.QUALITY_CHECK,
)
_ENGINE_STATUSES = frozenset(
    {
        JobStatus.PARSING,
        JobStatus.TRANSLATING,
        JobStatus.TYPESETTING,
        JobStatus.GENERATING_PDF,
    }
)


class WorkerCancelled(RuntimeError):
    pass


class ProcessTranslationJob:
    def __init__(
        self,
        repository: JobRepository,
        storage: ObjectStorage,
        runner: TranslationRunner,
        quality_gate: PdfQualityGate,
        *,
        workspace_root: Path,
        queue_heartbeat_seconds: float = 30.0,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._runner = runner
        self._quality_gate = quality_gate
        self._workspace_root = workspace_root
        self._queue_heartbeat_seconds = max(1.0, queue_heartbeat_seconds)

    async def execute(self, job_id: str) -> TranslationJob:
        job = await self._require_job(job_id)
        if job.status.is_terminal:
            return job
        try:
            if job.status is JobStatus.FAILED_RETRYABLE:
                job = job.retry()
                await self._repository.save(job)
            if job.status is JobStatus.UPLOADED:
                job = job.queue()
                await self._repository.save(job)
            job = await self._advance_to(job, JobStatus.PREFLIGHT)
            await asyncio.to_thread(
                self._workspace_root.mkdir,
                parents=True,
                exist_ok=True,
            )
            with tempfile.TemporaryDirectory(
                prefix=f"job-{job.id}-",
                dir=self._workspace_root,
            ) as temporary_directory:
                workspace = Path(temporary_directory)
                input_path = await self._storage.materialize_pdf(
                    job.input_object_key,
                    workspace / "source.pdf",
                )
                request = TranslationRunRequest(
                    input_path=input_path,
                    output_path=workspace / "translated.pdf",
                    workspace=workspace,
                    source_language=job.source_language,
                    target_language=job.target_language,
                    translator_profile=job.translator_profile,
                    llm_profile_id=job.llm_profile_id,
                )
                result = await self._runner.run(
                    request,
                    lambda progress: self._record_engine_progress(job.id, progress),
                )
                job = await self._require_active_job(job.id)
                job = await self._advance_to(job, JobStatus.GENERATING_PDF)
                job = await self._advance_to(job, JobStatus.QUALITY_CHECK)
                await self._quality_gate.validate(input_path, result.output_path)
                published = await self._storage.publish_pdf(
                    result.output_path,
                    original_filename=f"{job.id}.pdf",
                )
            job = await self._require_active_job(job.id)
            completed = job.transition_to(
                JobStatus.SUCCEEDED,
                output_object_key=published.key,
            )
            await self._repository.save(completed)
            return completed
        except WorkerCancelled:
            return await self._require_job(job_id)
        except OcrRequiredError as exc:
            return await self._mark_special_terminal(
                job_id,
                JobStatus.OCR_REQUIRED,
                exc,
            )
        except ReviewRequiredError as exc:
            return await self._mark_special_terminal(
                job_id,
                JobStatus.NEEDS_REVIEW,
                exc,
            )
        except TranslationEngineError as exc:
            status = (
                JobStatus.FAILED_RETRYABLE
                if exc.retryable
                else JobStatus.FAILED_PERMANENT
            )
            return await self._mark_failure(job_id, status, exc.code, str(exc))
        except Exception as exc:
            logger.exception("Unexpected worker failure", extra={"job_id": job_id})
            return await self._mark_failure(
                job_id,
                JobStatus.FAILED_RETRYABLE,
                "WORKER_UNEXPECTED_ERROR",
                type(exc).__name__,
            )

    async def run_once(self, queue: JobQueueConsumer) -> TranslationJob:
        message = await queue.dequeue()
        heartbeat = asyncio.create_task(
            self._heartbeat(queue, message),
            name=f"queue-heartbeat-{message.job_id}",
        )
        try:
            result = await self.execute(message.job_id)
            if result.status is JobStatus.FAILED_RETRYABLE:
                requeued = await queue.retry(message)
                if not requeued:
                    return await self._mark_failure(
                        result.id,
                        JobStatus.FAILED_PERMANENT,
                        "RETRY_BUDGET_EXHAUSTED",
                        f"retry budget exhausted after attempt {message.attempt + 1}",
                    )
                return result
            await queue.acknowledge(message)
            return result
        finally:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat

    async def run_forever(self, queue: JobQueueConsumer) -> None:
        while True:
            try:
                await self.run_once(queue)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Worker iteration failed")
                await asyncio.sleep(1)

    async def _heartbeat(
        self,
        queue: JobQueueConsumer,
        message: QueueMessage,
    ) -> None:
        while True:
            await asyncio.sleep(self._queue_heartbeat_seconds)
            await queue.heartbeat(message)

    async def _record_engine_progress(
        self,
        job_id: str,
        progress: EngineProgress,
    ) -> None:
        if progress.status not in _ENGINE_STATUSES:
            raise TranslationEngineError(
                f"engine emitted unsupported worker status: {progress.status}",
                code="ENGINE_INVALID_STAGE",
            )
        job = await self._require_active_job(job_id)
        job = await self._advance_to(job, progress.status)
        updated = job.record_progress(
            max(job.progress_percent, progress.percent),
            stage=progress.stage,
        )
        await self._repository.save(updated)

    async def _advance_to(
        self,
        job: TranslationJob,
        target: JobStatus,
    ) -> TranslationJob:
        if job.status is target:
            return job
        try:
            current_index = _PIPELINE.index(job.status)
            target_index = _PIPELINE.index(target)
        except ValueError as exc:
            raise TranslationEngineError(
                f"cannot advance active pipeline from {job.status} to {target}",
                code="WORKER_INVALID_PIPELINE_STATE",
            ) from exc
        if target_index < current_index:
            return job
        for status in _PIPELINE[current_index + 1 : target_index + 1]:
            job = job.transition_to(status)
            await self._repository.save(job)
        return job

    async def _require_job(self, job_id: str) -> TranslationJob:
        job = await self._repository.get(job_id)
        if job is None:
            raise KeyError(f"job does not exist: {job_id}")
        return job

    async def _require_active_job(self, job_id: str) -> TranslationJob:
        job = await self._require_job(job_id)
        if job.status is JobStatus.CANCELLED:
            raise WorkerCancelled(job_id)
        if job.status.is_terminal:
            raise TranslationEngineError(
                f"job became terminal while engine was running: {job.status}",
                code="WORKER_JOB_ALREADY_TERMINAL",
            )
        return job

    async def _mark_failure(
        self,
        job_id: str,
        status: JobStatus,
        code: str,
        message: str,
    ) -> TranslationJob:
        job = await self._require_job(job_id)
        if job.status.is_terminal:
            return job
        failed = job.transition_to(
            status,
            failure_code=code,
            failure_message=message[:500],
        )
        await self._repository.save(failed)
        return failed

    async def _mark_special_terminal(
        self,
        job_id: str,
        status: JobStatus,
        error: TranslationEngineError,
    ) -> TranslationJob:
        job = await self._require_job(job_id)
        if job.status.is_terminal:
            return job
        if status is JobStatus.NEEDS_REVIEW and job.status not in {
            JobStatus.TYPESETTING,
            JobStatus.QUALITY_CHECK,
        }:
            job = await self._advance_to(job, JobStatus.TYPESETTING)
        terminal = job.transition_to(
            status,
            failure_code=error.code,
            failure_message=str(error)[:500],
        )
        await self._repository.save(terminal)
        return terminal
