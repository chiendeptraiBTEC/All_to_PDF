"""PostgreSQL job repository with idempotency and optimistic concurrency."""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Mapping
from typing import Any

from all_to_pdf.domain.job import JobStatus, TranslationJob, TranslatorProfile
from all_to_pdf.infrastructure.repositories.in_memory import ConcurrentJobUpdateError

_SCHEMA = """
CREATE TABLE IF NOT EXISTS translation_jobs (
    id TEXT PRIMARY KEY,
    input_object_key TEXT NOT NULL,
    source_language TEXT NOT NULL,
    target_language TEXT NOT NULL,
    translator_profile TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    allow_paid_fallback BOOLEAN NOT NULL,
    llm_profile_id TEXT,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    progress_percent DOUBLE PRECISION NOT NULL,
    progress_stage TEXT,
    output_object_key TEXT,
    failure_code TEXT,
    failure_message TEXT,
    revision BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_translation_jobs_status_updated
ON translation_jobs(status, updated_at);
"""

_COLUMNS = """
id, input_object_key, source_language, target_language, translator_profile,
idempotency_key, allow_paid_fallback, llm_profile_id, status, created_at, updated_at,
progress_percent, progress_stage, output_object_key, failure_code, failure_message, revision
"""


class PostgresJobRepository:
    def __init__(
        self,
        dsn: str,
        *,
        min_pool_size: int = 1,
        max_pool_size: int = 10,
        pool: Any | None = None,
    ) -> None:
        self._dsn = dsn
        self._min_pool_size = min_pool_size
        self._max_pool_size = max_pool_size
        self._pool = pool
        self._schema_ready = False
        self._init_lock = asyncio.Lock()

    async def _pool_instance(self) -> Any:
        if self._pool is not None:
            return self._pool
        async with self._init_lock:
            if self._pool is None:
                asyncpg = importlib.import_module("asyncpg")
                self._pool = await asyncpg.create_pool(
                    self._dsn,
                    min_size=self._min_pool_size,
                    max_size=self._max_pool_size,
                )
        return self._pool

    async def _ensure_schema(self) -> Any:
        pool = await self._pool_instance()
        if self._schema_ready:
            return pool
        async with self._init_lock:
            if not self._schema_ready:
                await pool.execute(_SCHEMA)
                self._schema_ready = True
        return pool

    async def add_if_absent(self, job: TranslationJob) -> tuple[TranslationJob, bool]:
        pool = await self._ensure_schema()
        row = await pool.fetchrow(
            f"""
            INSERT INTO translation_jobs ({_COLUMNS})
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING {_COLUMNS}
            """,
            *self._values(job),
        )
        if row is not None:
            return self._from_row(row), True
        row = await pool.fetchrow(
            f"SELECT {_COLUMNS} FROM translation_jobs WHERE idempotency_key=$1",
            job.idempotency_key,
        )
        if row is None:
            raise RuntimeError("idempotent insert lost without a visible conflicting row")
        return self._from_row(row), False

    async def get(self, job_id: str) -> TranslationJob | None:
        pool = await self._ensure_schema()
        row = await pool.fetchrow(
            f"SELECT {_COLUMNS} FROM translation_jobs WHERE id=$1",
            job_id,
        )
        return None if row is None else self._from_row(row)

    async def save(self, job: TranslationJob) -> None:
        if job.revision <= 0:
            raise ConcurrentJobUpdateError("saved jobs must advance revision")
        pool = await self._ensure_schema()
        result = await pool.execute(
            """
            UPDATE translation_jobs SET
                status=$2, updated_at=$3, progress_percent=$4, progress_stage=$5,
                output_object_key=$6, failure_code=$7, failure_message=$8, revision=$9
            WHERE id=$1 AND revision=$10
            """,
            job.id,
            job.status.value,
            job.updated_at,
            job.progress_percent,
            job.progress_stage,
            job.output_object_key,
            job.failure_code,
            job.failure_message,
            job.revision,
            job.revision - 1,
        )
        if result == "UPDATE 1":
            return
        current = await self.get(job.id)
        if current is not None and current.status is JobStatus.CANCELLED:
            return
        raise ConcurrentJobUpdateError(
            f"compare-and-set failed for job {job.id} at revision {job.revision}"
        )

    async def healthcheck(self) -> bool:
        try:
            pool = await self._ensure_schema()
            result = await pool.fetchval("SELECT 1")
            return bool(result == 1)
        except Exception:
            return False

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            self._schema_ready = False

    @staticmethod
    def _values(job: TranslationJob) -> tuple[object, ...]:
        return (
            job.id,
            job.input_object_key,
            job.source_language,
            job.target_language,
            job.translator_profile.value,
            job.idempotency_key,
            job.allow_paid_fallback,
            job.llm_profile_id,
            job.status.value,
            job.created_at,
            job.updated_at,
            job.progress_percent,
            job.progress_stage,
            job.output_object_key,
            job.failure_code,
            job.failure_message,
            job.revision,
        )

    @staticmethod
    def _from_row(row: Mapping[str, Any]) -> TranslationJob:
        return TranslationJob(
            id=str(row["id"]),
            input_object_key=str(row["input_object_key"]),
            source_language=str(row["source_language"]),
            target_language=str(row["target_language"]),
            translator_profile=TranslatorProfile(str(row["translator_profile"])),
            idempotency_key=str(row["idempotency_key"]),
            allow_paid_fallback=bool(row["allow_paid_fallback"]),
            llm_profile_id=None if row["llm_profile_id"] is None else str(row["llm_profile_id"]),
            status=JobStatus(str(row["status"])),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            progress_percent=float(row["progress_percent"]),
            progress_stage=None if row["progress_stage"] is None else str(row["progress_stage"]),
            output_object_key=(
                None if row["output_object_key"] is None else str(row["output_object_key"])
            ),
            failure_code=None if row["failure_code"] is None else str(row["failure_code"]),
            failure_message=(
                None if row["failure_message"] is None else str(row["failure_message"])
            ),
            revision=int(row["revision"]),
        )
