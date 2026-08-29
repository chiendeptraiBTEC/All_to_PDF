"""Use case for streaming a PDF into object storage."""

from __future__ import annotations

from collections.abc import AsyncIterable

from all_to_pdf.application.ports import ObjectStorage, StoredObject


class SavePdfUpload:
    def __init__(self, storage: ObjectStorage) -> None:
        self._storage = storage

    async def execute(
        self,
        *,
        chunks: AsyncIterable[bytes],
        original_filename: str,
        content_type: str,
    ) -> StoredObject:
        return await self._storage.save_pdf(
            chunks=chunks,
            original_filename=original_filename,
            content_type=content_type,
        )
