from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from all_to_pdf.api.dependencies import get_container
from all_to_pdf.api.schemas import UploadResponse
from all_to_pdf.bootstrap import Container
from all_to_pdf.infrastructure.storage.local import InvalidPdfUpload, UploadTooLarge

router = APIRouter(prefix="/v1/uploads", tags=["uploads"])
_CHUNK_SIZE = 1024 * 1024


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_pdf(
    file: UploadFile = File(...),
    container: Container = Depends(get_container),
) -> UploadResponse:
    filename = file.filename or "document.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only .pdf files are accepted")

    async def chunks() -> AsyncIterator[bytes]:
        while chunk := await file.read(_CHUNK_SIZE):
            yield chunk

    try:
        stored = await container.save_upload.execute(
            chunks=chunks(),
            original_filename=filename,
            content_type=file.content_type or "application/pdf",
        )
    except UploadTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except InvalidPdfUpload as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    finally:
        await file.close()

    return UploadResponse(
        object_key=stored.key,
        original_filename=stored.original_filename,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
    )
