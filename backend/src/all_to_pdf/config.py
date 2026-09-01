"""Application configuration loaded from environment variables."""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ATP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"
    service_name: str = "all-to-pdf"
    web_directory: Path = Path("frontend")
    local_storage_directory: Path = Path("var/storage")
    working_directory: Path = Path("var/work")
    max_upload_bytes: int = Field(default=50 * 1024 * 1024, ge=1024)
    embedded_worker_enabled: bool = False

    persistence_backend: str = "memory"
    database_url: str | None = None
    database_pool_min_size: int = Field(default=1, ge=1)
    database_pool_max_size: int = Field(default=10, ge=1)
    redis_url: str | None = None
    redis_stream: str = "all-to-pdf:jobs"
    redis_consumer_group: str = "all-to-pdf-workers"
    redis_dead_letter_stream: str = "all-to-pdf:jobs:dead"
    queue_visibility_timeout_seconds: float = Field(default=120.0, gt=1)
    queue_heartbeat_seconds: float = Field(default=30.0, gt=0)
    queue_max_retries: int = Field(default=3, ge=0)

    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_region: str = "us-east-1"
    s3_access_key_id: SecretStr | None = None
    s3_secret_access_key: SecretStr | None = None
    s3_presign_expiry_seconds: int = Field(default=900, ge=60, le=86400)

    quality_mode: str = "basic"
    min_readable_scale: float = Field(default=0.62, gt=0.1, le=1.0)
    third_party_license_acknowledged: bool = False

    engine_timeout_seconds: float = Field(default=30 * 60, gt=0)
    translation_qps: int = Field(default=4, ge=1)
    translation_pool_max_workers: int = Field(default=4, ge=1)
    azure_translator_endpoint: str = "https://api.cognitive.microsofttranslator.com"
    azure_translator_api_key: SecretStr | None = None
    azure_translator_region: str | None = None
    llm_base_url: str | None = None
    llm_api_key: SecretStr | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float = Field(default=60.0, gt=0)

    def require_production_persistence(self) -> tuple[str, str, str]:
        if self.persistence_backend != "production":
            raise ValueError("production persistence is not enabled")
        missing = [
            name
            for name, value in (
                ("ATP_DATABASE_URL", self.database_url),
                ("ATP_REDIS_URL", self.redis_url),
                ("ATP_S3_BUCKET", self.s3_bucket),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"missing production settings: {', '.join(missing)}")
        assert self.database_url is not None
        assert self.redis_url is not None
        assert self.s3_bucket is not None
        return self.database_url, self.redis_url, self.s3_bucket

    def require_engine_license_acknowledgement(self) -> None:
        if self.persistence_backend == "production" and not self.third_party_license_acknowledged:
            raise ValueError(
                "production worker requires ATP_THIRD_PARTY_LICENSE_ACKNOWLEDGED=true "
                "after reviewing the AGPL-3.0 dependencies"
            )

    def engine_environment(self) -> dict[str, str]:
        values = {
            "ATP_ENVIRONMENT": self.environment,
            "ATP_ENGINE_TIMEOUT_SECONDS": str(self.engine_timeout_seconds),
            "ATP_TRANSLATION_QPS": str(self.translation_qps),
            "ATP_TRANSLATION_POOL_MAX_WORKERS": str(self.translation_pool_max_workers),
            "ATP_AZURE_TRANSLATOR_ENDPOINT": self.azure_translator_endpoint,
            "ATP_AZURE_TRANSLATOR_REGION": self.azure_translator_region or "",
            "ATP_LLM_BASE_URL": self.llm_base_url or "",
            "ATP_LLM_MODEL": self.llm_model or "",
            "ATP_LLM_TIMEOUT_SECONDS": str(self.llm_timeout_seconds),
        }
        if self.azure_translator_api_key:
            values["ATP_AZURE_TRANSLATOR_API_KEY"] = (
                self.azure_translator_api_key.get_secret_value()
            )
        if self.llm_api_key:
            values["ATP_LLM_API_KEY"] = self.llm_api_key.get_secret_value()
        return values
