from fastapi import APIRouter, Depends

from all_to_pdf.api.dependencies import get_container
from all_to_pdf.api.schemas import ProviderSummary
from all_to_pdf.bootstrap import Container
from all_to_pdf.domain.job import TranslatorProfile

router = APIRouter(prefix="/v1/providers", tags=["providers"])


@router.get("", response_model=list[ProviderSummary])
def list_providers(
    container: Container = Depends(get_container),
) -> list[ProviderSummary]:
    settings = container.settings
    return [
        ProviderSummary(
            id=TranslatorProfile.AZURE_NMT,
            configured=settings.azure_translator_api_key is not None,
            label="Azure AI Translator",
            description="Default NMT provider. Supports the Azure F0 free tier.",
        ),
        ProviderSummary(
            id=TranslatorProfile.OPENAI_COMPATIBLE_LLM,
            configured=bool(settings.llm_base_url and settings.llm_api_key and settings.llm_model),
            label="OpenAI-compatible LLM",
            description="Optional provider configured by base URL, API key, and model.",
        ),
    ]
