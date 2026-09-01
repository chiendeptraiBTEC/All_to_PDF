"""FastAPI application entry point."""

from __future__ import annotations

import argparse
import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from all_to_pdf.api.router import api_router
from all_to_pdf.bootstrap import Container, build_container, build_worker
from all_to_pdf.config import Settings

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    resolved_container = container or build_container(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        worker_task: asyncio.Task[None] | None = None
        if resolved_container.settings.embedded_worker_enabled:
            worker = build_worker(resolved_container)
            worker_task = asyncio.create_task(
                worker.process_job.run_forever(resolved_container.queue),
                name="embedded-pdf-worker",
            )
        try:
            yield
        finally:
            if worker_task is not None:
                worker_task.cancel()
                await asyncio.gather(worker_task, return_exceptions=True)
            await resolved_container.close()

    app = FastAPI(
        title="All_to_PDF API",
        version="0.3.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.container = resolved_container

    @app.middleware("http")
    async def request_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; "
            "base-uri 'self'; form-action 'self'"
        )
        return response

    @app.exception_handler(Exception)
    def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        logger.exception("Unhandled request error", extra={"request_id": request_id})
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected error occurred", "request_id": request_id},
        )

    app.include_router(api_router)
    web_directory = Path(resolved_container.settings.web_directory)
    if web_directory.is_dir():
        app.mount("/", StaticFiles(directory=web_directory, html=True), name="web")
    return app


app = create_app()


def run() -> None:
    parser = argparse.ArgumentParser(description="Run the All_to_PDF API server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    uvicorn.run(
        "all_to_pdf.main:app",
        app_dir="backend/src",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    run()
