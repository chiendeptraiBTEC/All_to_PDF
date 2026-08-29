"""Official Azure AI Translator Text Translation adapter."""

from __future__ import annotations

from typing import Any

import httpx

from all_to_pdf.domain.provider import (
    PlaceholderValidationError,
    ProtectedTokenValidator,
    ProviderAuthenticationError,
    ProviderInvalidResponseError,
    ProviderRateLimitError,
    ProviderTransientError,
    TranslationResult,
)


class AzureTextTranslationProvider:
    provider_id = "azure_nmt"
    model_id = "azure-translator-v3"

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        region: str | None,
        client: httpx.Client | None = None,
        validator: ProtectedTokenValidator | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Azure Translator API key is required")
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._region = region.strip() if region else None
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=15.0)
        self._validator = validator or ProtectedTokenValidator()

    def translate(
        self,
        text: str,
        *,
        source_language: str,
        target_language: str,
    ) -> TranslationResult:
        if not text:
            return TranslationResult("", self.provider_id, self.model_id, 0)

        headers = {
            "Content-Type": "application/json",
            "Ocp-Apim-Subscription-Key": self._api_key,
        }
        if self._region:
            headers["Ocp-Apim-Subscription-Region"] = self._region

        try:
            response = self._client.post(
                f"{self._endpoint}/translate",
                params={
                    "api-version": "3.0",
                    "from": source_language,
                    "to": target_language,
                },
                headers=headers,
                json=[{"text": text}],
            )
        except httpx.TransportError as exc:
            raise ProviderTransientError("Azure Translator network failure") from exc

        self._raise_for_status(response)
        translated = self._parse_response(response)
        self._validator.validate(text, translated)
        return TranslationResult(
            translated_text=translated,
            provider_id=self.provider_id,
            model_id=self.model_id,
            input_units=len(text),
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code in {401, 403}:
            raise ProviderAuthenticationError("Azure Translator authentication failed")
        if response.status_code == 429:
            raise ProviderRateLimitError("Azure Translator rate limit or quota exceeded")
        if response.status_code >= 500:
            raise ProviderTransientError(
                f"Azure Translator temporary failure: HTTP {response.status_code}"
            )
        if response.is_error:
            raise ProviderInvalidResponseError(
                f"Azure Translator rejected the request: HTTP {response.status_code}"
            )

    @staticmethod
    def _parse_response(response: httpx.Response) -> str:
        try:
            payload: Any = response.json()
            translated = payload[0]["translations"][0]["text"]
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            raise ProviderInvalidResponseError(
                "Azure Translator returned an unexpected response shape"
            ) from exc
        if not isinstance(translated, str) or not translated.strip():
            raise ProviderInvalidResponseError("Azure Translator returned empty text")
        return translated.strip()


__all__ = ["AzureTextTranslationProvider", "PlaceholderValidationError"]
