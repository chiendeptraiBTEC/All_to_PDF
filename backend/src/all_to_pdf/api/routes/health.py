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
    storage_ready = await container.storage.healthcheck()
    ready = storage_ready
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if ready else "not_ready",
        "components": {
            "job_repository": "ready",
            "job_queue": "ready",
            "object_storage": "ready" if storage_ready else "not_ready",
        },
    }
