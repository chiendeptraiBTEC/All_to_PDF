"""Application-level orchestration for one translation job."""

from __future__ import annotations

from typing import Protocol

from all_to_pdf.engine.errors import EngineError
from all_to_pdf.engine.models import EngineProgress, EngineRequest, EngineResult
from all_to_pdf.engine.ports import TranslationRunner


class WorkerJobSink(Protocol):
    """Persistence boundary used by the worker.

    A PostgreSQL implementation can enforce compare-and-set transitions later;
    tests use an in-memory recorder without changing worker logic.
    """

    def is_cancel_requested(self, job_id: str) -> bool: ...

    def record_progress(self, job_id: str, progress: EngineProgress) -> None: ...

    def record_success(self, job_id: str, result: EngineResult) -> None: ...

    def record_failure(
        self,
        job_id: str,
        *,
        code: str,
        message: str,
        retryable: bool,
    ) -> None: ...


class TranslationWorker:
    """Coordinates progress and terminal outcome without knowing BabelDOC."""

    def __init__(self, runner: TranslationRunner, sink: WorkerJobSink) -> None:
        self._runner = runner
        self._sink = sink

    def process(self, request: EngineRequest) -> EngineResult | None:
        last_percent = -1.0

        def on_progress(progress: EngineProgress) -> None:
            nonlocal last_percent
            if progress.percent < last_percent:
                raise ValueError(
                    f"engine progress regressed from {last_percent} to {progress.percent}"
                )
            last_percent = progress.percent
            self._sink.record_progress(request.job_id, progress)

        try:
            result = self._runner.run(
                request,
                on_progress=on_progress,
                is_cancelled=lambda: self._sink.is_cancel_requested(request.job_id),
            )
        except EngineError as exc:
            self._sink.record_failure(
                request.job_id,
                code=exc.code,
                message=str(exc),
                retryable=exc.retryable,
            )
            return None
        except Exception as exc:
            self._sink.record_failure(
                request.job_id,
                code="WORKER_UNEXPECTED_ERROR",
                message=str(exc),
                retryable=False,
            )
            return None

        self._sink.record_success(request.job_id, result)
        return result
