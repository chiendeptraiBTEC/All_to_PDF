"""PDF-engine contracts shared by the worker and infrastructure adapters."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from all_to_pdf.domain.job import JobStatus, TranslatorProfile


@dataclass(frozen=True, slots=True)
class EngineProgress:
    """Normalized progress emitted by any PDF engine implementation."""

    status: JobStatus
    percent: float
    stage: str


@dataclass(frozen=True, slots=True)
class TranslationRunRequest:
    """All non-secret inputs required by the isolated PDF engine."""

    input_path: Path
    output_path: Path
    workspace: Path
    source_language: str
    target_language: str
    translator_profile: TranslatorProfile
    llm_profile_id: str | None


@dataclass(frozen=True, slots=True)
class TranslationRunResult:
    output_path: Path
    engine_name: str
    engine_version: str


ProgressCallback = Callable[[EngineProgress], Awaitable[None]]


class TranslationRunner(Protocol):
    async def run(
        self,
        request: TranslationRunRequest,
        on_progress: ProgressCallback,
    ) -> TranslationRunResult: ...


class PdfQualityGate(Protocol):
    async def validate(self, source_path: Path, output_path: Path) -> None: ...


class TranslationEngineError(RuntimeError):
    default_code = "ENGINE_ERROR"
    default_retryable = False

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code or self.default_code
        self.retryable = self.default_retryable if retryable is None else retryable


class EngineUnavailableError(TranslationEngineError):
    default_code = "ENGINE_DEPENDENCY_MISSING"


class EngineProtocolError(TranslationEngineError):
    default_code = "ENGINE_PROTOCOL_ERROR"


class EngineProcessError(TranslationEngineError):
    default_code = "ENGINE_PROCESS_FAILED"
    default_retryable = True


class EngineTimeoutError(TranslationEngineError):
    default_code = "ENGINE_TIMEOUT"
    default_retryable = True


class OcrRequiredError(TranslationEngineError):
    default_code = "OCR_REQUIRED"


class ReviewRequiredError(TranslationEngineError):
    default_code = "NEEDS_REVIEW"
