"""Public HTTP request and response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from all_to_pdf.domain.job import JobStatus, TranslationJob, TranslatorProfile


class UploadResponse(BaseModel):
    object_key: str
    original_filename: str
    content_type: str
    size_bytes: int


class SubmitJobRequest(BaseModel):
    input_object_key: str = Field(min_length=1, max_length=1024)
    source_language: str = Field(default="en", min_length=2, max_length=16)
    target_language: str = Field(default="vi", min_length=2, max_length=16)
    translator_profile: TranslatorProfile = TranslatorProfile.AZURE_NMT
    idempotency_key: str = Field(min_length=8, max_length=200)
    allow_paid_fallback: bool = False
    llm_profile_id: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("input_object_key", "source_language", "target_language", "idempotency_key")
    @classmethod
    def strip_required_values(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped

    @model_validator(mode="after")
    def validate_provider_configuration(self) -> "SubmitJobRequest":
        if (
            self.translator_profile is TranslatorProfile.OPENAI_COMPATIBLE_LLM
            and not self.llm_profile_id
        ):
            raise ValueError("llm_profile_id is required for openai_compatible_llm")
        return self


class JobResponse(BaseModel):
    id: str
    input_object_key: str
    output_object_key: str | None
    source_language: str
    target_language: str
    translator_profile: TranslatorProfile
    allow_paid_fallback: bool
    llm_profile_id: str | None
    status: JobStatus
    failure_code: str | None
    failure_message: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, job: TranslationJob) -> "JobResponse":
        return cls(
            id=job.id,
            input_object_key=job.input_object_key,
            output_object_key=job.output_object_key,
            source_language=job.source_language,
            target_language=job.target_language,
            translator_profile=job.translator_profile,
            allow_paid_fallback=job.allow_paid_fallback,
            llm_profile_id=job.llm_profile_id,
            status=job.status,
            failure_code=job.failure_code,
            failure_message=job.failure_message,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


class ProviderSummary(BaseModel):
    id: TranslatorProfile
    configured: bool
    label: str
    description: str
