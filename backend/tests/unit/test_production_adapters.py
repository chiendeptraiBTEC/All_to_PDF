from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from all_to_pdf.domain.job import JobStatus, TranslationJob, TranslatorProfile
from all_to_pdf.infrastructure.queues.redis import RedisJobQueue
from all_to_pdf.infrastructure.repositories.in_memory import ConcurrentJobUpdateError
from all_to_pdf.infrastructure.repositories.postgres import PostgresJobRepository
from all_to_pdf.infrastructure.storage.s3 import S3ObjectStorage

_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _job(job_id: str = "job-1", key: str = "idem-1") -> TranslationJob:
    return TranslationJob.create(
        job_id=job_id,
        input_object_key="uploads/input.pdf",
        source_language="en",
        target_language="vi",
        translator_profile=TranslatorProfile.AZURE_NMT,
        idempotency_key=key,
        allow_paid_fallback=False,
        llm_profile_id=None,
        now=datetime(2026, 8, 29, tzinfo=UTC),
    ).queue()


class FakePostgresPool:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.by_key: dict[str, str] = {}
        self.closed = False

    async def execute(self, query: str, *args: Any) -> str:
        if "CREATE TABLE" in query:
            return "CREATE TABLE"
        if "UPDATE translation_jobs" in query:
            job_id = str(args[0])
            row = self.rows.get(job_id)
            expected = int(args[9])
            if row is None or int(row["revision"]) != expected:
                return "UPDATE 0"
            row.update(
                status=args[1],
                updated_at=args[2],
                progress_percent=args[3],
                progress_stage=args[4],
                output_object_key=args[5],
                failure_code=args[6],
                failure_message=args[7],
                revision=args[8],
            )
            return "UPDATE 1"
        raise AssertionError(query)

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        if "INSERT INTO translation_jobs" in query:
            key = str(args[5])
            if key in self.by_key:
                return None
            names = [
                "id",
                "input_object_key",
                "source_language",
                "target_language",
                "translator_profile",
                "idempotency_key",
                "allow_paid_fallback",
                "llm_profile_id",
                "status",
                "created_at",
                "updated_at",
                "progress_percent",
                "progress_stage",
                "output_object_key",
                "failure_code",
                "failure_message",
                "revision",
            ]
            row = dict(zip(names, args, strict=True))
            self.rows[str(row["id"])] = row
            self.by_key[key] = str(row["id"])
            return row
        if "WHERE idempotency_key=$1" in query:
            job_id = self.by_key.get(str(args[0]))
            return None if job_id is None else self.rows[job_id]
        if "WHERE id=$1" in query:
            return self.rows.get(str(args[0]))
        raise AssertionError(query)

    async def fetchval(self, query: str) -> int:
        assert query == "SELECT 1"
        return 1

    async def close(self) -> None:
        self.closed = True


async def test_postgres_repository_idempotency_and_compare_and_set() -> None:
    pool = FakePostgresPool()
    repository = PostgresJobRepository("postgres://unused", pool=pool)
    persisted, inserted = await repository.add_if_absent(_job())
    duplicate, duplicate_inserted = await repository.add_if_absent(_job("job-2"))
    assert inserted is True
    assert duplicate_inserted is False
    assert duplicate.id == persisted.id
    assert await repository.healthcheck() is True

    updated = persisted.transition_to(JobStatus.PREFLIGHT)
    await repository.save(updated)
    assert (await repository.get(updated.id)) == updated
    with pytest.raises(ConcurrentJobUpdateError):
        await repository.save(persisted.transition_to(JobStatus.PREFLIGHT))
    await repository.close()
    assert pool.closed is True


class FakePipeline:
    def __init__(self, redis: FakeRedis) -> None:
        self.redis = redis
        self.operations: list[tuple[str, tuple[Any, ...]]] = []

    def xack(self, *args: Any) -> FakePipeline:
        self.operations.append(("xack", args))
        return self

    def xdel(self, *args: Any) -> FakePipeline:
        self.operations.append(("xdel", args))
        return self

    def xadd(self, *args: Any) -> FakePipeline:
        self.operations.append(("xadd", args))
        return self

    async def execute(self) -> list[Any]:
        return [await getattr(self.redis, name)(*args) for name, args in self.operations]


class FakeRedis:
    def __init__(self) -> None:
        self.streams: dict[str, list[tuple[str, dict[str, str]]]] = {}
        self.counter = 0
        self.heartbeats = 0
        self.closed = False

    async def xgroup_create(self, *args: Any, **kwargs: Any) -> bool:
        del args, kwargs
        return True

    async def xadd(self, stream: str, fields: dict[str, str]) -> str:
        self.counter += 1
        receipt = f"{self.counter}-0"
        self.streams.setdefault(stream, []).append((receipt, dict(fields)))
        return receipt

    async def xautoclaim(self, *args: Any, **kwargs: Any) -> tuple[str, list[Any], list[Any]]:
        del args, kwargs
        return "0-0", [], []

    async def xreadgroup(
        self,
        group: str,
        consumer: str,
        streams: dict[str, str],
        *,
        count: int,
        block: int,
    ) -> list[Any]:
        del group, consumer, count, block
        stream = next(iter(streams))
        messages = self.streams.get(stream, [])
        return [] if not messages else [(stream, [messages.pop(0)])]

    async def xack(self, *args: Any) -> int:
        del args
        return 1

    async def xdel(self, *args: Any) -> int:
        del args
        return 1

    async def xclaim(self, *args: Any, **kwargs: Any) -> list[str]:
        del args, kwargs
        self.heartbeats += 1
        return ["ok"]

    def pipeline(self, *, transaction: bool) -> FakePipeline:
        assert transaction is True
        return FakePipeline(self)

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        self.closed = True


async def test_redis_queue_retry_dead_letter_and_heartbeat() -> None:
    client = FakeRedis()
    queue = RedisJobQueue(
        "redis://unused",
        max_retries=1,
        client=client,
        block_seconds=0.001,
    )
    await queue.enqueue("job-1")
    message = await queue.dequeue()
    assert message.job_id == "job-1"
    await queue.heartbeat(message)
    assert client.heartbeats == 1
    assert await queue.retry(message) is True
    retry = await queue.dequeue()
    assert retry.attempt == 1
    assert await queue.retry(retry) is False
    assert len(client.streams["all-to-pdf:jobs:dead"]) == 1
    assert await queue.healthcheck() is True
    await queue.close()
    assert client.closed is True


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.extra: dict[tuple[str, str], dict[str, Any]] = {}

    def upload_file(
        self,
        filename: str,
        bucket: str,
        key: str,
        *,
        ExtraArgs: dict[str, Any],
    ) -> None:
        self.objects[(bucket, key)] = Path(filename).read_bytes()
        self.extra[(bucket, key)] = ExtraArgs

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        Path(filename).write_bytes(self.objects[(bucket, key)])

    def generate_presigned_url(
        self,
        operation: str,
        *,
        Params: dict[str, str],
        ExpiresIn: int,
    ) -> str:
        return f"https://example.invalid/{operation}/{Params['Key']}?expires={ExpiresIn}"

    def head_bucket(self, *, Bucket: str) -> dict[str, str]:
        return {"bucket": Bucket}


async def _chunks() -> AsyncIterator[bytes]:
    yield _PDF[:8]
    yield _PDF[8:]


async def test_s3_storage_validates_publishes_and_presigns(tmp_path: Path) -> None:
    client = FakeS3()
    storage = S3ObjectStorage("documents", max_upload_bytes=1024, client=client)
    stored = await storage.save_pdf(
        chunks=_chunks(),
        original_filename="../source.pdf",
        content_type="application/pdf",
    )
    assert stored.original_filename == "source.pdf"
    materialized = tmp_path / "source.pdf"
    await storage.materialize_pdf(stored.key, materialized)
    assert materialized.read_bytes() == _PDF
    published = await storage.publish_pdf(materialized, original_filename="translated.pdf")
    metadata = client.extra[("documents", published.key)]["Metadata"]
    assert metadata["publication"] == "quality-gate-passed"
    assert len(metadata["sha256"]) == 64
    url = await storage.create_download_url(published.key, expires_seconds=600)
    assert "expires=600" in url
    assert await storage.healthcheck() is True
    with pytest.raises(ValueError):
        await storage.materialize_pdf("../escape.pdf", tmp_path / "bad.pdf")
