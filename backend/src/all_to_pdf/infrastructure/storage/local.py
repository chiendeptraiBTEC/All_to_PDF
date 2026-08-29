"""Local filesystem object storage adapter.

Production will replace this adapter with S3-compatible storage while preserving the
same application port. Writes are streamed and published atomically.
"""

from __future__ import annotations

import asyncio
import os
import shutil
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

    async def materialize_pdf(self, key: str, destination: Path) -> Path:
        source = self._resolve_key(key)
        if not source.is_file():
            raise FileNotFoundError(f"object does not exist: {key}")
        await asyncio.to_thread(destination.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copyfile, source, destination)
        return destination

    async def publish_pdf(
        self,
        source_path: Path,
        *,
        original_filename: str,
    ) -> StoredObject:
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        now = datetime.now(UTC)
        relative_path = (
            Path("outputs") / f"{now:%Y}" / f"{now:%m}" / f"{uuid4().hex}.pdf"
        )
        target = self._root / relative_path
        temporary = target.with_suffix(".pdf.part")
        await asyncio.to_thread(target.parent.mkdir, parents=True, exist_ok=True)
        try:
            await asyncio.to_thread(shutil.copyfile, source_path, temporary)
            await asyncio.to_thread(self._fsync_file, temporary)
            await asyncio.to_thread(temporary.replace, target)
        except Exception:
            await asyncio.to_thread(temporary.unlink, missing_ok=True)
            raise
        return StoredObject(
            key=relative_path.as_posix(),
            size_bytes=target.stat().st_size,
            content_type="application/pdf",
            original_filename=Path(original_filename).name or "translated.pdf",
        )

    async def healthcheck(self) -> bool:
        return await asyncio.to_thread(self._healthcheck_sync)

    def _resolve_key(self, key: str) -> Path:
        root = self._root.resolve()
        candidate = (root / Path(key)).resolve()
        if not candidate.is_relative_to(root):
            raise ValueError("object key escapes the configured storage root")
        return candidate

    @staticmethod
    def _fsync_file(path: Path) -> None:
        with path.open("rb") as stream:
            os.fsync(stream.fileno())

    def _healthcheck_sync(self) -> bool:
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            probe = self._root / ".healthcheck"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True
        except OSError:
            return False
