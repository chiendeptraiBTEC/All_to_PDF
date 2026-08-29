"""Local filesystem object storage adapter.

Production will replace this adapter with S3-compatible storage while preserving the
same application port. Writes are streamed and published atomically.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import aiofiles

from all_to_pdf.application.ports import StoredObject


class InvalidPdfUpload(ValueError):
    pass


class UploadTooLarge(ValueError):
    pass


class LocalObjectStorage:
    def __init__(self, root: Path, *, max_upload_bytes: int) -> None:
        self._root = root
        self._max_upload_bytes = max_upload_bytes

    async def save_pdf(
        self,
        *,
        chunks: AsyncIterable[bytes],
        original_filename: str,
        content_type: str,
    ) -> StoredObject:
        now = datetime.now(UTC)
        relative_directory = Path("uploads") / f"{now:%Y}" / f"{now:%m}"
        object_id = uuid4().hex
        relative_path = relative_directory / f"{object_id}.pdf"
        target = self._root / relative_path
        temporary = target.with_suffix(".pdf.part")
        await asyncio.to_thread(target.parent.mkdir, parents=True, exist_ok=True)

        size = 0
        header = bytearray()
        try:
            async with aiofiles.open(temporary, "xb") as destination:
                async for chunk in chunks:
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > self._max_upload_bytes:
                        raise UploadTooLarge(
                            f"PDF exceeds maximum upload size of {self._max_upload_bytes} bytes"
                        )
                    if len(header) < 5:
                        header.extend(chunk[: 5 - len(header)])
                    await destination.write(chunk)
                await destination.flush()
                await asyncio.to_thread(os.fsync, destination.fileno())

            if size == 0 or bytes(header) != b"%PDF-":
                raise InvalidPdfUpload("uploaded file does not start with a PDF signature")
            await asyncio.to_thread(temporary.replace, target)
        except Exception:
            await asyncio.to_thread(temporary.unlink, missing_ok=True)
            raise

        return StoredObject(
            key=relative_path.as_posix(),
            size_bytes=size,
            content_type=content_type or "application/pdf",
            original_filename=Path(original_filename).name or "document.pdf",
        )

    async def healthcheck(self) -> bool:
        return await asyncio.to_thread(self._healthcheck_sync)

    def _healthcheck_sync(self) -> bool:
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            probe = self._root / ".healthcheck"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True
        except OSError:
            return False
