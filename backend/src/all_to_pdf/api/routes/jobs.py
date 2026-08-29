from fastapi import APIRouter, Depends, HTTPException, status

from all_to_pdf.api.dependencies import get_container
from all_to_pdf.api.schemas import JobResponse, SubmitJobRequest
from all_to_pdf.application.jobs import JobNotFoundError, SubmitJobCommand
from all_to_pdf.bootstrap import Container

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
