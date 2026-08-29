"""FastAPI dependencies that expose the application container."""

from fastapi import Request

from all_to_pdf.bootstrap import Container


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container
