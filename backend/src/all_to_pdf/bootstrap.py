"""Dependency composition root for local and production adapters."""

from __future__ import annotations

from dataclasses import dataclass

from all_to_pdf.application.jobs import (
    CancelTranslationJob,
    GetTranslationJob,
    SubmitTranslationJob,
)
from all_to_pdf.application.ports import (
    DownloadUrlProvider,
    JobRepository,
    ObjectStorage,
    WorkerQueue,
)
from all_to_pdf.application.uploads import SavePdfUpload
from all_to_pdf.application.worker import ProcessTranslationJob
from all_to_pdf.config import Settings
from all_to_pdf.infrastructure.quality.basic import BasicPdfQualityGate
from all_to_pdf.infrastructure.quality.structural import StructuralPdfQualityGate
from all_to_pdf.infrastructure.queues.in_memory import InMemoryJobQueue
from all_to_pdf.infrastructure.queues.redis import RedisJobQueue
from all_to_pdf.infrastructure.repositories.in_memory import InMemoryJobRepository
from all_to_pdf.infrastructure.repositories.postgres import PostgresJobRepository
from all_to_pdf.infrastructure.runners.subprocess import BabelDocSubprocessRunner
from all_to_pdf.infrastructure.storage.local import LocalObjectStorage
from all_to_pdf.infrastructure.storage.s3 import S3ObjectStorage


@dataclass(frozen=True, slots=True)
class Container:
    settings: Settings
    repository: JobRepository
    queue: WorkerQueue
    storage: ObjectStorage
    download_urls: DownloadUrlProvider | None
    submit_job: SubmitTranslationJob
    get_job: GetTranslationJob
    cancel_job: CancelTranslationJob
    save_upload: SavePdfUpload

    async def close(self) -> None:
        await self.queue.close()
        await self.repository.close()


@dataclass(frozen=True, slots=True)
class WorkerContainer:
    app: Container
    process_job: ProcessTranslationJob


def build_container(settings: Settings | None = None) -> Container:
    resolved = settings or Settings()
    if resolved.persistence_backend == "memory":
        repository: JobRepository = InMemoryJobRepository()
        queue: WorkerQueue = InMemoryJobQueue(max_retries=resolved.queue_max_retries)
        storage: ObjectStorage = LocalObjectStorage(
            resolved.local_storage_directory,
            max_upload_bytes=resolved.max_upload_bytes,
        )
        download_urls: DownloadUrlProvider | None = None
    elif resolved.persistence_backend == "production":
        database_url, redis_url, bucket = resolved.require_production_persistence()
        repository = PostgresJobRepository(
            database_url,
            min_pool_size=resolved.database_pool_min_size,
            max_pool_size=resolved.database_pool_max_size,
        )
        queue = RedisJobQueue(
            redis_url,
            stream=resolved.redis_stream,
            group=resolved.redis_consumer_group,
            dead_letter_stream=resolved.redis_dead_letter_stream,
            visibility_timeout_seconds=resolved.queue_visibility_timeout_seconds,
            max_retries=resolved.queue_max_retries,
        )
        s3 = S3ObjectStorage(
            bucket,
            max_upload_bytes=resolved.max_upload_bytes,
            endpoint_url=resolved.s3_endpoint_url,
            region=resolved.s3_region,
            access_key_id=(
                None
                if resolved.s3_access_key_id is None
                else resolved.s3_access_key_id.get_secret_value()
            ),
            secret_access_key=(
                None
                if resolved.s3_secret_access_key is None
                else resolved.s3_secret_access_key.get_secret_value()
            ),
        )
        storage = s3
        download_urls = s3
    else:
        raise ValueError("ATP_PERSISTENCE_BACKEND must be 'memory' or 'production'")

    return Container(
        settings=resolved,
        repository=repository,
        queue=queue,
        storage=storage,
        download_urls=download_urls,
        submit_job=SubmitTranslationJob(repository, queue),
        get_job=GetTranslationJob(repository),
        cancel_job=CancelTranslationJob(repository),
        save_upload=SavePdfUpload(storage),
    )


def build_worker(container: Container) -> WorkerContainer:
    container.settings.require_engine_license_acknowledgement()
    runner = BabelDocSubprocessRunner(
        timeout_seconds=container.settings.engine_timeout_seconds,
        environment=container.settings.engine_environment(),
    )
    if container.settings.quality_mode == "structural":
        quality_gate = StructuralPdfQualityGate(
            minimum_readable_scale=container.settings.min_readable_scale
        )
    elif container.settings.quality_mode == "basic":
        quality_gate = BasicPdfQualityGate()
    else:
        raise ValueError("ATP_QUALITY_MODE must be 'basic' or 'structural'")
    return WorkerContainer(
        app=container,
        process_job=ProcessTranslationJob(
            container.repository,
            container.storage,
            runner,
            quality_gate,
            workspace_root=container.settings.working_directory,
            queue_heartbeat_seconds=container.settings.queue_heartbeat_seconds,
        ),
    )
