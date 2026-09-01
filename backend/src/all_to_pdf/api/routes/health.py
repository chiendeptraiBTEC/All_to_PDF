import asyncio

from fastapi import APIRouter, Depends, Response, status

from all_to_pdf.api.dependencies import get_container
from all_to_pdf.bootstrap import Container

router = APIRouter(tags=["health"])


@router.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(
    response: Response,
    container: Container = Depends(get_container),
) -> dict[str, object]:
    repository_ready, queue_ready, storage_ready = await asyncio.gather(
        container.repository.healthcheck(),
        container.queue.healthcheck(),
        container.storage.healthcheck(),
    )
    ready = repository_ready and queue_ready and storage_ready
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if ready else "not_ready",
        "components": {
            "job_repository": "ready" if repository_ready else "not_ready",
            "job_queue": "ready" if queue_ready else "not_ready",
            "object_storage": "ready" if storage_ready else "not_ready",
        },
    }
