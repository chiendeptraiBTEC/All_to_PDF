from datetime import UTC, datetime

import pytest

from all_to_pdf.domain.job import (
    InvalidJobTransition,
    JobStatus,
    TranslationJob,
    TranslatorProfile,
)


def make_job() -> TranslationJob:
    return TranslationJob.create(
        job_id="job-1",
        input_object_key="uploads/input.pdf",
        source_language="en",
        target_language="vi",
        translator_profile=TranslatorProfile.AZURE_NMT,
        idempotency_key="idempotency-1",
        allow_paid_fallback=False,
        llm_profile_id=None,
        now=datetime(2026, 8, 29, tzinfo=UTC),
    )


def test_job_follows_valid_lifecycle() -> None:
    job = make_job().queue()
    job = job.transition_to(JobStatus.PREFLIGHT)
    job = job.transition_to(JobStatus.PARSING)
    job = job.record_progress(22.0, stage="Parse paragraphs")
    job = job.transition_to(JobStatus.TRANSLATING)
    job = job.transition_to(JobStatus.TYPESETTING)
    job = job.transition_to(JobStatus.GENERATING_PDF)
    job = job.transition_to(JobStatus.QUALITY_CHECK)
    job = job.transition_to(JobStatus.SUCCEEDED, output_object_key="outputs/job-1.pdf")

    assert job.status is JobStatus.SUCCEEDED
    assert job.output_object_key == "outputs/job-1.pdf"
    assert job.progress_percent == 100.0
    assert job.status.is_terminal


def test_job_rejects_invalid_transition() -> None:
    with pytest.raises(InvalidJobTransition):
        make_job().transition_to(JobStatus.TRANSLATING)


def test_succeeded_job_requires_output() -> None:
    job = make_job().queue()
    job = job.transition_to(JobStatus.PREFLIGHT)
    job = job.transition_to(JobStatus.PARSING)
    job = job.transition_to(JobStatus.TRANSLATING)
    job = job.transition_to(JobStatus.TYPESETTING)
    job = job.transition_to(JobStatus.GENERATING_PDF)
    job = job.transition_to(JobStatus.QUALITY_CHECK)

    with pytest.raises(InvalidJobTransition):
        job.transition_to(JobStatus.SUCCEEDED)


def test_progress_must_be_monotonic() -> None:
    job = make_job().queue().transition_to(JobStatus.PREFLIGHT)
    job = job.record_progress(20, stage="preflight")
    with pytest.raises(ValueError, match="monotonic"):
        job.record_progress(19, stage="preflight")


def test_llm_profile_requires_profile_id() -> None:
    with pytest.raises(ValueError, match="llm_profile_id"):
        TranslationJob.create(
            job_id="job-1",
            input_object_key="uploads/input.pdf",
            source_language="en",
            target_language="vi",
            translator_profile=TranslatorProfile.OPENAI_COMPATIBLE_LLM,
            idempotency_key="idempotency-1",
            allow_paid_fallback=False,
            llm_profile_id=None,
        )
