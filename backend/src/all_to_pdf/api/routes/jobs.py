from fastapi import APIRouter, Depends, HTTPException, status

from all_to_pdf.api.dependencies import get_container
from all_to_pdf.api.schemas import DownloadUrlResponse, JobResponse, SubmitJobRequest
from all_to_pdf.application.jobs import JobNotFoundError, SubmitJobCommand
from all_to_pdf.bootstrap import Container
from all_to_pdf.domain.job import JobStatus

router = APIRouter(prefix="/v1/pdf-translations", tags=["translations"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_job(
    request: SubmitJobRequest,
    container: Container = Depends(get_container),
) -> JobResponse:
    try:
        job = await container.submit_job.execute(
            SubmitJobCommand(
                input_object_key=request.input_object_key,
                source_language=request.source_language,
                target_language=request.target_language,
                translator_profile=request.translator_profile,
                idempotency_key=request.idempotency_key,
                allow_paid_fallback=request.allow_paid_fallback,
                llm_profile_id=request.llm_profile_id,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return JobResponse.from_domain(job)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    container: Container = Depends(get_container),
) -> JobResponse:
    try:
        job = await container.get_job.execute(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Translation job not found") from exc
    return JobResponse.from_domain(job)


@router.get("/{job_id}/download-url", response_model=DownloadUrlResponse)
async def get_download_url(
    job_id: str,
    container: Container = Depends(get_container),
) -> DownloadUrlResponse:
    try:
        job = await container.get_job.execute(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Translation job not found") from exc
    if job.status is not JobStatus.SUCCEEDED or not job.output_object_key:
        raise HTTPException(status_code=409, detail="Translation output is not ready")
    if container.download_urls is None:
        raise HTTPException(status_code=409, detail="Presigned downloads are not configured")
    expires = container.settings.s3_presign_expiry_seconds
    url = await container.download_urls.create_download_url(
        job.output_object_key,
        expires_seconds=expires,
    )
    return DownloadUrlResponse(url=url, expires_in_seconds=expires)


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: str,
    container: Container = Depends(get_container),
) -> JobResponse:
    try:
        job = await container.cancel_job.execute(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Translation job not found") from exc
    return JobResponse.from_domain(job)
