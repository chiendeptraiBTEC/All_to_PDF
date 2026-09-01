"""Build translation providers from validated application settings."""

from __future__ import annotations

from all_to_pdf.config import Settings
from all_to_pdf.domain.job import TranslatorProfile
from all_to_pdf.domain.provider import TextTranslationProvider
from all_to_pdf.infrastructure.providers.azure import AzureTextTranslationProvider
from all_to_pdf.infrastructure.providers.openai_compatible import (
    OpenAICompatibleTranslationProvider,
)


class ProviderConfigurationError(ValueError):
    pass


class TranslationProviderFactory:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(
        self,
        profile: TranslatorProfile,
        *,
        llm_profile_id: str | None,
    ) -> TextTranslationProvider:
        if profile is TranslatorProfile.AZURE_NMT:
            if self._settings.azure_translator_api_key is None:
                raise ProviderConfigurationError("Azure Translator API key is not configured")
            return AzureTextTranslationProvider(
                endpoint=self._settings.azure_translator_endpoint,
                api_key=self._settings.azure_translator_api_key.get_secret_value(),
                region=self._settings.azure_translator_region,
            )

        if llm_profile_id != "default":
            raise ProviderConfigurationError(
                "M1 supports only the administrator-managed LLM profile 'default'"
            )
        if not self._settings.llm_base_url or not self._settings.llm_model:
            raise ProviderConfigurationError("OpenAI-compatible LLM is not configured")
        if self._settings.llm_api_key is None:
            raise ProviderConfigurationError("OpenAI-compatible LLM API key is not configured")
        return OpenAICompatibleTranslationProvider(
            base_url=self._settings.llm_base_url,
            api_key=self._settings.llm_api_key.get_secret_value(),
            model=self._settings.llm_model,
            timeout_seconds=self._settings.llm_timeout_seconds,
        )
