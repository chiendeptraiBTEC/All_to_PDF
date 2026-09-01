import pytest

from all_to_pdf.bootstrap import build_container, build_worker
from all_to_pdf.config import Settings
from all_to_pdf.infrastructure.queues.redis import RedisJobQueue
from all_to_pdf.infrastructure.repositories.postgres import PostgresJobRepository
from all_to_pdf.infrastructure.storage.s3 import S3ObjectStorage


def test_production_container_uses_external_adapters() -> None:
    settings = Settings(
        persistence_backend="production",
        database_url="postgresql://db/app",
        redis_url="redis://queue/0",
        s3_bucket="documents",
    )
    container = build_container(settings)
    assert isinstance(container.repository, PostgresJobRepository)
    assert isinstance(container.queue, RedisJobQueue)
    assert isinstance(container.storage, S3ObjectStorage)


def test_production_worker_requires_agpl_acknowledgement() -> None:
    settings = Settings(
        persistence_backend="production",
        database_url="postgresql://db/app",
        redis_url="redis://queue/0",
        s3_bucket="documents",
    )
    container = build_container(settings)
    with pytest.raises(ValueError, match="AGPL"):
        build_worker(container)


def test_production_settings_require_all_dependencies() -> None:
    settings = Settings(persistence_backend="production")
    with pytest.raises(ValueError, match="ATP_DATABASE_URL"):
        settings.require_production_persistence()
