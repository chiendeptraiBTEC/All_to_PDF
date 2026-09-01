from dataclasses import replace
from pathlib import Path

import pytest
from fastapi import HTTPException

from all_to_pdf.api.routes.jobs import get_download_url
from all_to_pdf.application.jobs import SubmitJobCommand
from all_to_pdf.bootstrap import Container, build_container
from all_to_pdf.config import Settings
from all_to_pdf.domain.job import JobStatus, TranslatorProfile


class FakeDownloadUrls:
    async def create_download_url(self, key: str, *, expires_seconds: int) -> str:
        return f"https://download.invalid/{key}?expires={expires_seconds}"


def _container(tmp_path: Path) -> Container:
    settings = Settings(
        web_directory=tmp_path / "missing-web",
        local_storage_directory=tmp_path / "storage",
        s3_presign_expiry_seconds=600,
    )
    return replace(build_container(settings), download_urls=FakeDownloadUrls())


async def _submit(container: Container) -> str:
    job = await container.submit_job.execute(
        SubmitJobCommand(
            input_object_key="uploads/input.pdf",
            source_language="en",
            target_language="vi",
            translator_profile=TranslatorProfile.AZURE_NMT,
            idempotency_key="download-test-key",
        )
    )
    return job.id


async def test_download_url_requires_succeeded_job(tmp_path: Path) -> None:
    container = _container(tmp_path)
    job_id = await _submit(container)
    with pytest.raises(HTTPException) as captured:
        await get_download_url(job_id, container)
    assert captured.value.status_code == 409


async def test_succeeded_job_gets_short_lived_download_url(tmp_path: Path) -> None:
    container = _container(tmp_path)
    job_id = await _submit(container)
    job = await container.repository.get(job_id)
    assert job is not None
    for state in (
        JobStatus.PREFLIGHT,
        JobStatus.PARSING,
        JobStatus.TRANSLATING,
        JobStatus.TYPESETTING,
        JobStatus.GENERATING_PDF,
        JobStatus.QUALITY_CHECK,
    ):
        job = job.transition_to(state)
        await container.repository.save(job)
    job = job.transition_to(JobStatus.SUCCEEDED, output_object_key="outputs/result.pdf")
    await container.repository.save(job)
    result = await get_download_url(job_id, container)
    assert result.expires_in_seconds == 600
    assert "outputs/result.pdf" in result.url
