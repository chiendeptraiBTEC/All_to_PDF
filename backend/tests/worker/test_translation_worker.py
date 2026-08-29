from __future__ import annotations

from pathlib import Path

from all_to_pdf.engine.errors import EngineProcessError
from all_to_pdf.engine.models import EngineProgress, EngineRequest, EngineResult, EngineStage
from all_to_pdf.worker.translation_worker import TranslationWorker


class FakeRunner:
    def __init__(
        self,
        result: EngineResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error

    def run(self, request, on_progress, is_cancelled):
        assert not is_cancelled()
        on_progress(EngineProgress(EngineStage.PARSING, 10, "parse"))
        on_progress(EngineProgress(EngineStage.COMPLETED, 100, "done"))
        if self.error:
            raise self.error
        assert self.result is not None
        return self.result


class RecordingSink:
    def __init__(self) -> None:
        self.progress: list[EngineProgress] = []
        self.success: EngineResult | None = None
        self.failure: tuple[str, str, bool] | None = None
        self.cancelled = False

    def is_cancel_requested(self, job_id: str) -> bool:
        assert job_id == "job-1"
        return self.cancelled

    def record_progress(self, job_id: str, progress: EngineProgress) -> None:
        assert job_id == "job-1"
        self.progress.append(progress)

    def record_success(self, job_id: str, result: EngineResult) -> None:
        assert job_id == "job-1"
        self.success = result

    def record_failure(
        self,
        job_id: str,
        *,
        code: str,
        message: str,
        retryable: bool,
    ) -> None:
        assert job_id == "job-1"
        self.failure = (code, message, retryable)


def _request(tmp_path: Path) -> EngineRequest:
    return EngineRequest(
        "job-1",
        tmp_path / "input.pdf",
        tmp_path / "output",
        "en",
        "vi",
        "deterministic_test",
    )


def test_worker_records_success(tmp_path: Path) -> None:
    output = tmp_path / "translated.pdf"
    result = EngineResult(output, 1.0, "fake", "1")
    sink = RecordingSink()

    returned = TranslationWorker(FakeRunner(result=result), sink).process(_request(tmp_path))

    assert returned == result
    assert sink.success == result
    assert sink.failure is None
    assert len(sink.progress) == 2


def test_worker_records_engine_failure(tmp_path: Path) -> None:
    sink = RecordingSink()
    error = EngineProcessError("provider down", code="PROVIDER_SERVER_ERROR")

    returned = TranslationWorker(FakeRunner(error=error), sink).process(_request(tmp_path))

    assert returned is None
    assert sink.failure == ("PROVIDER_SERVER_ERROR", "provider down", True)


def test_worker_rejects_regressing_progress(tmp_path: Path) -> None:
    class RegressingRunner:
        def run(self, request, on_progress, is_cancelled):
            on_progress(EngineProgress(EngineStage.PARSING, 50, "first"))
            on_progress(EngineProgress(EngineStage.PARSING, 40, "regressed"))
            raise AssertionError("unreachable")

    sink = RecordingSink()

    assert TranslationWorker(RegressingRunner(), sink).process(_request(tmp_path)) is None
    assert sink.failure is not None
    assert sink.failure[0] == "WORKER_UNEXPECTED_ERROR"
