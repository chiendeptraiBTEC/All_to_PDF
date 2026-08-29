"""Dependency composition root.

Only this module decides which concrete adapters are used. Business logic depends on
protocols, making the in-memory adapters replaceable by PostgreSQL, Redis, and S3.
"""

from __future__ import annotations

from dataclasses import dataclass

from all_to_pdf.application.jobs import (
    CancelTranslationJob,
    GetTranslationJob,
    SubmitTranslationJob,
)
from all_to_pdf.application.ports import ObjectStorage, WorkerQueue
from all_to_pdf.application.uploads import SavePdfUpload
from all_to_pdf.application.worker import ProcessTranslationJob
from all_to_pdf.config import Settings
from all_to_pdf.infrastructure.quality.basic import BasicPdfQualityGate
from all_to_pdf.infrastructure.queues.in_memory import InMemoryJobQueue
from all_to_pdf.infrastructure.repositories.in_memory import InMemoryJobRepository
from all_to_pdf.infrastructure.runners.subprocess import BabelDocSubprocessRunner
from all_to_pdf.infrastructure.storage.local import LocalObjectStorage


@dataclass(frozen=True, slots=True)
class Container:
    settings: Settings
    repository: InMemoryJobRepository
    queue: WorkerQueue
    storage: ObjectStorage
    submit_job: SubmitTranslationJob
    get_job: GetTranslationJob
    cancel_job: CancelTranslationJob
    save_upload: SavePdfUpload


@dataclass(frozen=True, slots=True)
class WorkerContainer:
    app: Container
    process_job: ProcessTranslationJob


def build_container(settings: Settings | None = None) -> Container:
    resolved_settings = settings or Settings()
    repository = InMemoryJobRepository()
    queue = InMemoryJobQueue()
    storage = LocalObjectStorage(
        resolved_settings.local_storage_directory,
        max_upload_bytes=resolved_settings.max_upload_bytes,
    )
    return Container(
        settings=resolved_settings,
        repository=repository,
        queue=queue,
        storage=storage,
        submit_job=SubmitTranslationJob(repository, queue),
        get_job=GetTranslationJob(repository),
        cancel_job=CancelTranslationJob(repository),
        save_upload=SavePdfUpload(storage),
    )


def build_worker(container: Container) -> WorkerContainer:
    runner = BabelDocSubprocessRunner(
        timeout_seconds=container.settings.engine_timeout_seconds,
        environment=container.settings.engine_environment(),
    )
    return WorkerContainer(
        app=container,
        process_job=ProcessTranslationJob(
            container.repository,
            container.storage,
            runner,
            BasicPdfQualityGate(),
            workspace_root=container.settings.working_directory,
        ),
    )
