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

    def engine_environment(self) -> dict[str, str]:
        """Return only variables required by the isolated engine process."""

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
