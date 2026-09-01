"""Small typed provider clients used by the legacy engine-driver test harness."""

from __future__ import annotations

import os
from typing import ClassVar, Protocol

import httpx

from all_to_pdf.engine.errors import EngineProcessError


class ProviderClient(Protocol):
    provider_name: str
    model_name: str

    def translate(self, text: str) -> str: ...

    def close(self) -> None: ...


class DeterministicProviderClient:
    provider_name = "deterministic_test"
    model_name = "deterministic-en-vi-v1"

    _REPLACEMENTS: ClassVar[dict[str, str]] = {
        "Hello world.": "Xin chào thế giới.",
        "Hello": "Xin chào",
    }

    def __init__(self, *, target_language: str) -> None:
        self._target_language = target_language

    def translate(self, text: str) -> str:
        translated = self._REPLACEMENTS.get(text)
        if translated is not None:
            return translated
        prefix = "VI" if self._target_language.casefold() == "vi" else self._target_language.upper()
        return f"[{prefix}] {text}"

    def close(self) -> None:
        return None


class AzureProviderClient:
    provider_name = "azure_nmt"
    model_name = "azure-translator-v3"

    def __init__(self, *, source_language: str, target_language: str) -> None:
        endpoint = os.getenv("ATP_AZURE_TRANSLATOR_ENDPOINT", "").rstrip("/")
        api_key = os.getenv("ATP_AZURE_TRANSLATOR_API_KEY", "")
        if not endpoint or not api_key:
            raise EngineProcessError(
                "Azure Translator endpoint/API key is not configured",
                code="PROVIDER_NOT_CONFIGURED",
            )
        self._endpoint = endpoint
        self._api_key = api_key
        self._region = os.getenv("ATP_AZURE_TRANSLATOR_REGION", "")
        self._source_language = source_language
        self._target_language = target_language
        self._client = httpx.Client(timeout=30.0)

    def translate(self, text: str) -> str:
        headers = {
            "Ocp-Apim-Subscription-Key": self._api_key,
            "Content-Type": "application/json",
        }
        if self._region:
            headers["Ocp-Apim-Subscription-Region"] = self._region
        response = self._client.post(
            f"{self._endpoint}/translate",
            params={
                "api-version": "3.0",
                "from": self._source_language,
                "to": self._target_language,
            },
            headers=headers,
            json=[{"Text": text}],
        )
        if response.is_error:
            raise EngineProcessError(
                f"Azure Translator returned HTTP {response.status_code}",
                code=_provider_http_error_code(response.status_code),
            )
        payload = response.json()
        try:
            value = payload[0]["translations"][0]["text"]
        except (IndexError, KeyError, TypeError) as exc:
            raise EngineProcessError(
                "Azure Translator returned an invalid response",
                code="PROVIDER_INVALID_RESPONSE",
            ) from exc
        if not isinstance(value, str):
            raise EngineProcessError(
                "Azure Translator returned a non-text response",
                code="PROVIDER_INVALID_RESPONSE",
            )
        return value

    def close(self) -> None:
        self._client.close()


class OpenAICompatibleProviderClient:
    provider_name = "openai_compatible_llm"

    def __init__(self, *, source_language: str, target_language: str) -> None:
        base_url = os.getenv("ATP_LLM_BASE_URL", "").rstrip("/")
        api_key = os.getenv("ATP_LLM_API_KEY", "")
        model = os.getenv("ATP_LLM_MODEL", "")
        if not base_url or not api_key or not model:
            raise EngineProcessError(
                "OpenAI-compatible provider is not configured",
                code="PROVIDER_NOT_CONFIGURED",
            )
        self._base_url = base_url
        self._api_key = api_key
        self.model_name = model
        self._source_language = source_language
        self._target_language = target_language
        timeout = float(os.getenv("ATP_LLM_TIMEOUT_SECONDS", "60"))
        self._client = httpx.Client(timeout=timeout)

    def translate(self, text: str) -> str:
        response = self._client.post(
            f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model_name,
                "temperature": 0,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Translate faithfully from "
                            f"{self._source_language} to {self._target_language}. "
                            "Return only the translated text and preserve placeholders exactly."
                        ),
                    },
                    {"role": "user", "content": text},
                ],
            },
        )
        if response.is_error:
            raise EngineProcessError(
                f"LLM provider returned HTTP {response.status_code}",
                code=_provider_http_error_code(response.status_code),
            )
        payload = response.json()
        try:
            value = payload["choices"][0]["message"]["content"]
        except (IndexError, KeyError, TypeError) as exc:
            raise EngineProcessError(
                "LLM provider returned an invalid response",
                code="PROVIDER_INVALID_RESPONSE",
            ) from exc
        if not isinstance(value, str):
            raise EngineProcessError(
                "LLM provider returned a non-text response",
                code="PROVIDER_INVALID_RESPONSE",
            )
        return value

    def close(self) -> None:
        self._client.close()


def build_provider_client(
    profile: str,
    *,
    source_language: str,
    target_language: str,
) -> ProviderClient:
    if profile == "deterministic_test":
        return DeterministicProviderClient(target_language=target_language)
    if profile == "azure_nmt":
        return AzureProviderClient(
            source_language=source_language,
            target_language=target_language,
        )
    if profile == "openai_compatible_llm":
        return OpenAICompatibleProviderClient(
            source_language=source_language,
            target_language=target_language,
        )
    raise EngineProcessError(
        f"unsupported translator profile: {profile}",
        code="PROVIDER_NOT_CONFIGURED",
    )


def _provider_http_error_code(status_code: int) -> str:
    if status_code in {401, 403}:
        return "PROVIDER_AUTH_FAILED"
    if status_code == 429:
        return "PROVIDER_RATE_LIMITED"
    if status_code >= 500:
        return "PROVIDER_SERVER_ERROR"
    return "PROVIDER_INVALID_REQUEST"
