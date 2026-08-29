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
    max_upload_bytes: int = Field(default=50 * 1024 * 1024, ge=1024)

    azure_translator_endpoint: str = "https://api.cognitive.microsofttranslator.com"
    azure_translator_api_key: SecretStr | None = None
    azure_translator_region: str | None = None

    llm_base_url: str | None = None
    llm_api_key: SecretStr | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float = Field(default=60.0, gt=0)
