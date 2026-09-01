"""S3-compatible object storage with checksums and gated output publication."""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import os
import tempfile
from collections.abc import AsyncIterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiofiles

from all_to_pdf.application.ports import StoredObject
from all_to_pdf.infrastructure.storage.local import InvalidPdfUpload, UploadTooLarge


class S3ObjectStorage:
    def __init__(
        self,
        bucket: str,
        *,
        max_upload_bytes: int,
        endpoint_url: str | None = None,
        region: str = "us-east-1",
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        self._bucket = bucket
        self._max_upload_bytes = max_upload_bytes
        self._endpoint_url = endpoint_url
        self._region = region
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._client = client

    def _client_instance(self) -> Any:
        if self._client is None:
            boto3 = importlib.import_module("boto3")
            self._client = boto3.client(
                "s3",
                endpoint_url=self._endpoint_url,
                region_name=self._region,
                aws_access_key_id=self._access_key_id,
                aws_secret_access_key=self._secret_access_key,
            )
        return self._client

    async def save_pdf(
        self,
        *,
        chunks: AsyncIterable[bytes],
        original_filename: str,
        content_type: str,
    ) -> StoredObject:
        now = datetime.now(UTC)
        key = f"uploads/{now:%Y}/{now:%m}/{uuid4().hex}.pdf"
        with tempfile.TemporaryDirectory(prefix="all-to-pdf-upload-") as directory:
            path = Path(directory) / "upload.pdf"
            size, digest = await self._write_upload(chunks, path)
            client = self._client_instance()
            await asyncio.to_thread(
                client.upload_file,
                str(path),
                self._bucket,
                key,
                ExtraArgs={
                    "ContentType": content_type or "application/pdf",
                    "Metadata": {
                        "sha256": digest,
                        "original-filename": self._safe_filename(original_filename),
                    },
                },
            )
        return StoredObject(
            key=key,
            size_bytes=size,
            content_type=content_type or "application/pdf",
            original_filename=self._safe_filename(original_filename),
        )

    async def materialize_pdf(self, key: str, destination: Path) -> Path:
        self._validate_key(key)
        await asyncio.to_thread(destination.parent.mkdir, parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".part")
        client = self._client_instance()
        try:
            await asyncio.to_thread(client.download_file, self._bucket, key, str(temporary))
            await asyncio.to_thread(self._validate_pdf_file, temporary)
            await asyncio.to_thread(os.replace, temporary, destination)
        except Exception:
            await asyncio.to_thread(temporary.unlink, missing_ok=True)
            raise
        return destination

    async def publish_pdf(
        self,
        source_path: Path,
        *,
        original_filename: str,
    ) -> StoredObject:
        if not await asyncio.to_thread(source_path.is_file):
            raise FileNotFoundError(source_path)
        await asyncio.to_thread(self._validate_pdf_file, source_path)
        size = await asyncio.to_thread(lambda: source_path.stat().st_size)
        digest = await asyncio.to_thread(self._sha256_file, source_path)
        now = datetime.now(UTC)
        key = f"outputs/{now:%Y}/{now:%m}/{uuid4().hex}.pdf"
        client = self._client_instance()
        await asyncio.to_thread(
            client.upload_file,
            str(source_path),
            self._bucket,
            key,
            ExtraArgs={
                "ContentType": "application/pdf",
                "Metadata": {
                    "sha256": digest,
                    "original-filename": self._safe_filename(original_filename),
                    "publication": "quality-gate-passed",
                },
            },
        )
        return StoredObject(
            key=key,
            size_bytes=size,
            content_type="application/pdf",
            original_filename=self._safe_filename(original_filename),
        )

    async def create_download_url(self, key: str, *, expires_seconds: int) -> str:
        self._validate_key(key)
        client = self._client_instance()
        return str(
            await asyncio.to_thread(
                client.generate_presigned_url,
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_seconds,
            )
        )

    async def healthcheck(self) -> bool:
        try:
            client = self._client_instance()
            await asyncio.to_thread(client.head_bucket, Bucket=self._bucket)
            return True
        except Exception:
            return False

    async def _write_upload(
        self,
        chunks: AsyncIterable[bytes],
        path: Path,
    ) -> tuple[int, str]:
        size = 0
        header = bytearray()
        digest = hashlib.sha256()
        async with aiofiles.open(path, "xb") as destination:
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
                digest.update(chunk)
                await destination.write(chunk)
            await destination.flush()
            await asyncio.to_thread(os.fsync, destination.fileno())
        if size == 0 or bytes(header) != b"%PDF-":
            raise InvalidPdfUpload("uploaded file does not start with a PDF signature")
        return size, digest.hexdigest()

    @staticmethod
    def _validate_pdf_file(path: Path) -> None:
        if path.stat().st_size < 12:
            raise InvalidPdfUpload("PDF object is unexpectedly small")
        with path.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise InvalidPdfUpload("PDF object has an invalid signature")

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _safe_filename(filename: str) -> str:
        return (Path(filename).name or "document.pdf")[:200]

    @staticmethod
    def _validate_key(key: str) -> None:
        path = Path(key)
        if not key or path.is_absolute() or ".." in path.parts:
            raise ValueError("invalid object key")
