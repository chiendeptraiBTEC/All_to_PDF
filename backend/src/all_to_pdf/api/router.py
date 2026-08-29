from fastapi import APIRouter

from all_to_pdf.api.routes import health, jobs, providers, uploads

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(uploads.router)
api_router.include_router(jobs.router)
api_router.include_router(providers.router)
