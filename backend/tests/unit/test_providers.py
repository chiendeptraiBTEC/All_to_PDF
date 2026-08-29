import httpx
import pytest

from all_to_pdf.domain.provider import PlaceholderValidationError, ProviderRateLimitError
from all_to_pdf.infrastructure.providers.azure import AzureTextTranslationProvider
from all_to_pdf.infrastructure.providers.openai_compatible import (
    OpenAICompatibleTranslationProvider,
)


def test_azure_provider_uses_official_v3_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/translate"
        assert request.url.params["api-version"] == "3.0"
        assert request.url.params["from"] == "en"
        assert request.url.params["to"] == "vi"
        assert request.headers["Ocp-Apim-Subscription-Key"] == "secret"
        assert request.headers["Ocp-Apim-Subscription-Region"] == "southeastasia"
        return httpx.Response(
            200,
            json=[{"translations": [{"text": "Năng lượng {v1}"}]}],
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = AzureTextTranslationProvider(
        endpoint="https://api.cognitive.microsofttranslator.com",
        api_key="secret",
        region="southeastasia",
        client=client,
    )

    result = provider.translate("Energy {v1}", source_language="en", target_language="vi")

    assert result.translated_text == "Năng lượng {v1}"
    assert result.provider_id == "azure_nmt"


def test_azure_provider_classifies_rate_limit() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(429, json={}))
    )
    provider = AzureTextTranslationProvider(
        endpoint="https://api.cognitive.microsofttranslator.com",
        api_key="secret",
        region=None,
        client=client,
    )

    with pytest.raises(ProviderRateLimitError):
        provider.translate("Energy", source_language="en", target_language="vi")


def test_openai_compatible_provider_preserves_placeholders() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer secret"
        payload = __import__("json").loads(request.content)
        assert payload["model"] == "translation-model"
        assert payload["temperature"] == 0
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Năng lượng {v1}"}}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleTranslationProvider(
        base_url="https://llm.example/v1",
        api_key="secret",
        model="translation-model",
        client=client,
    )

    result = provider.translate("Energy {v1}", source_language="en", target_language="vi")

    assert result.translated_text == "Năng lượng {v1}"
    assert result.model_id == "translation-model"


def test_openai_compatible_provider_rejects_lost_placeholder() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={"choices": [{"message": {"content": "Năng lượng"}}]},
            )
        )
    )
    provider = OpenAICompatibleTranslationProvider(
        base_url="https://llm.example/v1",
        api_key="secret",
        model="translation-model",
        client=client,
    )

    with pytest.raises(PlaceholderValidationError):
        provider.translate("Energy {v1}", source_language="en", target_language="vi")


def test_provider_empty_text_avoids_network() -> None:
    def unexpected(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("network should not be called for empty text")

    client = httpx.Client(transport=httpx.MockTransport(unexpected))
    azure = AzureTextTranslationProvider(
        endpoint="https://api.cognitive.microsofttranslator.com",
        api_key="secret",
        region=None,
        client=client,
    )
    llm = OpenAICompatibleTranslationProvider(
        base_url="https://llm.example/v1",
        api_key="secret",
        model="translation-model",
        client=client,
    )

    assert azure.translate("", source_language="en", target_language="vi").translated_text == ""
    assert llm.translate("", source_language="en", target_language="vi").translated_text == ""


def test_azure_provider_rejects_invalid_response_shape() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={}))
    )
    provider = AzureTextTranslationProvider(
        endpoint="https://api.cognitive.microsofttranslator.com",
        api_key="secret",
        region=None,
        client=client,
    )

    from all_to_pdf.domain.provider import ProviderInvalidResponseError

    with pytest.raises(ProviderInvalidResponseError):
        provider.translate("Energy", source_language="en", target_language="vi")


def test_openai_provider_classifies_authentication_error() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(401, json={}))
    )
    provider = OpenAICompatibleTranslationProvider(
        base_url="https://llm.example/v1",
        api_key="secret",
        model="translation-model",
        client=client,
    )

    from all_to_pdf.domain.provider import ProviderAuthenticationError

    with pytest.raises(ProviderAuthenticationError):
        provider.translate("Energy", source_language="en", target_language="vi")


def test_azure_provider_maps_network_failure() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = AzureTextTranslationProvider(
        endpoint="https://api.cognitive.microsofttranslator.com",
        api_key="secret",
        region=None,
        client=client,
    )

    from all_to_pdf.domain.provider import ProviderTransientError

    with pytest.raises(ProviderTransientError):
        provider.translate("Energy", source_language="en", target_language="vi")


def test_openai_provider_maps_network_failure() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleTranslationProvider(
        base_url="https://llm.example/v1",
        api_key="secret",
        model="translation-model",
        client=client,
    )

    from all_to_pdf.domain.provider import ProviderTransientError

    with pytest.raises(ProviderTransientError):
        provider.translate("Energy", source_language="en", target_language="vi")
