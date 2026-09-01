from __future__ import annotations

import pytest

from all_to_pdf.config import Settings
from all_to_pdf.domain.job import TranslatorProfile
from all_to_pdf.infrastructure.providers.azure import AzureTextTranslationProvider
from all_to_pdf.infrastructure.providers.factory import (
    ProviderConfigurationError,
    TranslationProviderFactory,
)
from all_to_pdf.infrastructure.providers.openai_compatible import (
    OpenAICompatibleTranslationProvider,
)


def test_factory_builds_configured_azure_provider() -> None:
    settings = Settings(
        _env_file=None,
        azure_translator_api_key="secret",
        azure_translator_region="southeastasia",
    )

    provider = TranslationProviderFactory(settings).build(
        TranslatorProfile.AZURE_NMT,
        llm_profile_id=None,
    )

    assert isinstance(provider, AzureTextTranslationProvider)
    provider.close()


def test_factory_builds_default_llm_profile() -> None:
    settings = Settings(
        _env_file=None,
        llm_base_url="https://llm.example/v1",
        llm_api_key="secret",
        llm_model="translation-model",
    )

    provider = TranslationProviderFactory(settings).build(
        TranslatorProfile.OPENAI_COMPATIBLE_LLM,
        llm_profile_id="default",
    )

    assert isinstance(provider, OpenAICompatibleTranslationProvider)
    assert provider.model_id == "translation-model"
    provider.close()


@pytest.mark.parametrize(
    ("settings", "profile", "profile_id", "message"),
    [
        (
            Settings(_env_file=None),
            TranslatorProfile.AZURE_NMT,
            None,
            "Azure Translator API key",
        ),
        (
            Settings(_env_file=None),
            TranslatorProfile.OPENAI_COMPATIBLE_LLM,
            "tenant",
            "administrator-managed",
        ),
        (
            Settings(_env_file=None),
            TranslatorProfile.OPENAI_COMPATIBLE_LLM,
            "default",
            "not configured",
        ),
        (
            Settings(
                _env_file=None,
                llm_base_url="https://llm.example/v1",
                llm_model="model",
            ),
            TranslatorProfile.OPENAI_COMPATIBLE_LLM,
            "default",
            "API key",
        ),
    ],
)
def test_factory_rejects_incomplete_profiles(
    settings: Settings,
    profile: TranslatorProfile,
    profile_id: str | None,
    message: str,
) -> None:
    with pytest.raises(ProviderConfigurationError, match=message):
        TranslationProviderFactory(settings).build(profile, llm_profile_id=profile_id)


def test_engine_environment_contains_only_engine_configuration() -> None:
    settings = Settings(
        _env_file=None,
        environment="test",
        azure_translator_api_key="azure-secret",
        azure_translator_region="southeastasia",
        llm_base_url="https://llm.example/v1",
        llm_api_key="llm-secret",
        llm_model="model",
        translation_qps=3,
        translation_pool_max_workers=2,
    )

    environment = settings.engine_environment()

    assert environment["ATP_AZURE_TRANSLATOR_API_KEY"] == "azure-secret"
    assert environment["ATP_LLM_API_KEY"] == "llm-secret"
    assert environment["ATP_TRANSLATION_QPS"] == "3"
    assert environment["ATP_TRANSLATION_POOL_MAX_WORKERS"] == "2"
    assert "ATP_LOCAL_STORAGE_DIRECTORY" not in environment
