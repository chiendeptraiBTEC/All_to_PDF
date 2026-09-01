"""Domain model for PDF translation jobs.

This module contains no framework or database code. The revision field provides the
compare-and-set token used by production repositories.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum


class JobStatus(StrEnum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PREFLIGHT = "preflight"
    PARSING = "parsing"
    TRANSLATING = "translating"
    TYPESETTING = "typesetting"
    GENERATING_PDF = "generating_pdf"
    QUALITY_CHECK = "quality_check"
    SUCCEEDED = "succeeded"
    OCR_REQUIRED = "ocr_required"
    NEEDS_REVIEW = "needs_review"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_PERMANENT = "failed_permanent"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {
            self.SUCCEEDED,
            self.OCR_REQUIRED,
            self.NEEDS_REVIEW,
            self.FAILED_PERMANENT,
            self.CANCELLED,
        }


class TranslatorProfile(StrEnum):
    AZURE_NMT = "azure_nmt"
    OPENAI_COMPATIBLE_LLM = "openai_compatible_llm"


class InvalidJobTransition(ValueError):
    """Raised when a job is moved to a state that violates the lifecycle."""


_ALLOWED_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.UPLOADED: frozenset({JobStatus.QUEUED, JobStatus.CANCELLED}),
    JobStatus.QUEUED: frozenset(
        {JobStatus.PREFLIGHT, JobStatus.CANCELLED, JobStatus.FAILED_RETRYABLE}
    ),
    JobStatus.PREFLIGHT: frozenset(
        {
            JobStatus.PARSING,
            JobStatus.OCR_REQUIRED,
            JobStatus.FAILED_RETRYABLE,
            JobStatus.FAILED_PERMANENT,
            JobStatus.CANCELLED,
        }
    ),
    JobStatus.PARSING: frozenset(
        {
            JobStatus.TRANSLATING,
            JobStatus.OCR_REQUIRED,
            JobStatus.FAILED_RETRYABLE,
            JobStatus.FAILED_PERMANENT,
            JobStatus.CANCELLED,
        }
    ),
    JobStatus.TRANSLATING: frozenset(
        {
            JobStatus.TYPESETTING,
            JobStatus.FAILED_RETRYABLE,
            JobStatus.FAILED_PERMANENT,
            JobStatus.CANCELLED,
        }
    ),
    JobStatus.TYPESETTING: frozenset(
        {
            JobStatus.GENERATING_PDF,
            JobStatus.NEEDS_REVIEW,
            JobStatus.FAILED_RETRYABLE,
            JobStatus.FAILED_PERMANENT,
            JobStatus.CANCELLED,
        }
    ),
    JobStatus.GENERATING_PDF: frozenset(
        {
            JobStatus.QUALITY_CHECK,
            JobStatus.FAILED_RETRYABLE,
            JobStatus.FAILED_PERMANENT,
            JobStatus.CANCELLED,
        }
    ),
    JobStatus.QUALITY_CHECK: frozenset(
        {
            JobStatus.SUCCEEDED,
            JobStatus.NEEDS_REVIEW,
            JobStatus.FAILED_RETRYABLE,
            JobStatus.FAILED_PERMANENT,
            JobStatus.CANCELLED,
        }
    ),
    JobStatus.FAILED_RETRYABLE: frozenset(
        {JobStatus.QUEUED, JobStatus.FAILED_PERMANENT, JobStatus.CANCELLED}
    ),
}

_PROGRESS_FLOOR: dict[JobStatus, float] = {
    JobStatus.UPLOADED: 0.0,
    JobStatus.QUEUED: 1.0,
    JobStatus.PREFLIGHT: 3.0,
    JobStatus.PARSING: 10.0,
    JobStatus.TRANSLATING: 35.0,
    JobStatus.TYPESETTING: 75.0,
    JobStatus.GENERATING_PDF: 88.0,
    JobStatus.QUALITY_CHECK: 95.0,
    JobStatus.SUCCEEDED: 100.0,
}


@dataclass(frozen=True, slots=True)
class TranslationJob:
    id: str
    input_object_key: str
    source_language: str
    target_language: str
    translator_profile: TranslatorProfile
    idempotency_key: str
    allow_paid_fallback: bool
    llm_profile_id: str | None
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    progress_percent: float = 0.0
    progress_stage: str | None = None
    output_object_key: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    revision: int = 0

    @classmethod
    def create(
        cls,
        *,
        job_id: str,
        input_object_key: str,
        source_language: str,
        target_language: str,
        translator_profile: TranslatorProfile,
        idempotency_key: str,
        allow_paid_fallback: bool,
        llm_profile_id: str | None,
        now: datetime | None = None,
    ) -> TranslationJob:
        timestamp = now or datetime.now(UTC)
        if translator_profile is TranslatorProfile.OPENAI_COMPATIBLE_LLM and not llm_profile_id:
            raise ValueError("llm_profile_id is required for the OpenAI-compatible profile")
        if source_language.lower() == target_language.lower():
            raise ValueError("source_language and target_language must be different")
        return cls(
            id=job_id,
            input_object_key=input_object_key,
            source_language=source_language.lower(),
            target_language=target_language.lower(),
            translator_profile=translator_profile,
            idempotency_key=idempotency_key,
            allow_paid_fallback=allow_paid_fallback,
            llm_profile_id=llm_profile_id,
            status=JobStatus.UPLOADED,
            created_at=timestamp,
            updated_at=timestamp,
            progress_stage=JobStatus.UPLOADED.value,
        )

    def transition_to(
        self,
        status: JobStatus,
        *,
        now: datetime | None = None,
        output_object_key: str | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
    ) -> TranslationJob:
        if self.status.is_terminal:
            raise InvalidJobTransition(f"terminal job {self.id} cannot leave {self.status}")
        allowed = _ALLOWED_TRANSITIONS.get(self.status, frozenset())
        if status not in allowed:
            raise InvalidJobTransition(
                f"cannot transition job {self.id}: {self.status} -> {status}"
            )
        if status is JobStatus.SUCCEEDED and not output_object_key:
            raise InvalidJobTransition("a succeeded job must have output_object_key")
        if status in {JobStatus.FAILED_RETRYABLE, JobStatus.FAILED_PERMANENT} and not failure_code:
            raise InvalidJobTransition("a failed job must have failure_code")
        progress = max(self.progress_percent, _PROGRESS_FLOOR.get(status, self.progress_percent))
        return replace(
            self,
            status=status,
            updated_at=now or datetime.now(UTC),
            progress_percent=progress,
            progress_stage=status.value,
            output_object_key=output_object_key or self.output_object_key,
            failure_code=failure_code,
            failure_message=failure_message,
            revision=self.revision + 1,
        )

    def record_progress(
        self,
        percent: float,
        *,
        stage: str,
        now: datetime | None = None,
    ) -> TranslationJob:
        if self.status.is_terminal:
            raise InvalidJobTransition("cannot update progress for a terminal job")
        if not 0.0 <= percent <= 100.0:
            raise ValueError("progress percent must be between 0 and 100")
        if percent < self.progress_percent:
            raise ValueError("progress percent must be monotonic")
        if not stage.strip():
            raise ValueError("progress stage must not be blank")
        return replace(
            self,
            progress_percent=percent,
            progress_stage=stage.strip()[:200],
            updated_at=now or datetime.now(UTC),
            revision=self.revision + 1,
        )

    def queue(self, *, now: datetime | None = None) -> TranslationJob:
        return self.transition_to(JobStatus.QUEUED, now=now)

    def retry(self, *, now: datetime | None = None) -> TranslationJob:
        if self.status is not JobStatus.FAILED_RETRYABLE:
            raise InvalidJobTransition("only retryable failures can be queued again")
        return self.transition_to(JobStatus.QUEUED, now=now)

    def cancel(self, *, now: datetime | None = None) -> TranslationJob:
        return self.transition_to(JobStatus.CANCELLED, now=now)
