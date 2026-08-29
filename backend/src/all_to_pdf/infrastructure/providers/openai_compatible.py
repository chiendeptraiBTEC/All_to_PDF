"""OpenAI-compatible chat-completions translation adapter."""

from __future__ import annotations

from typing import Any

import httpx

from all_to_pdf.domain.provider import (
    ProtectedTokenValidator,
    ProviderAuthenticationError,
    ProviderInvalidResponseError,
    ProviderRateLimitError,
    ProviderTransientError,
    TranslationResult,
)


_SYSTEM_PROMPT = (
    "You are a deterministic professional translation engine. Preserve every formula "
    "placeholder, rich-text tag, code token, identifier, and protected token exactly. "
    "Return only the translation. Do not add notes, Markdown, or explanations."
)


class OpenAICompatibleTranslationProvider:
    provider_id = "openai_compatible_llm"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 60.0,
        client: httpx.Client | None = None,
        validator: ProtectedTokenValidator | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("LLM base URL is required")
        if not api_key.strip():
            raise ValueError("LLM API key is required")
        if not model.strip():
            raise ValueError("LLM model is required")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.model_id = model
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout_seconds)
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

        try:
            response = self._client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_id,
                    "temperature": 0,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": (
                                f"Translate from {source_language} to {target_language}. "
                                f"Output only the translation.\n\n{text}"
                            ),
                        },
                    ],
                },
            )
        except httpx.TransportError as exc:
            raise ProviderTransientError("LLM provider network failure") from exc

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
            raise ProviderAuthenticationError("LLM provider authentication failed")
        if response.status_code == 429:
            raise ProviderRateLimitError("LLM provider rate limit or quota exceeded")
        if response.status_code >= 500:
            raise ProviderTransientError(
                f"LLM provider temporary failure: HTTP {response.status_code}"
            )
        if response.is_error:
            raise ProviderInvalidResponseError(
                f"LLM provider rejected the request: HTTP {response.status_code}"
            )

    @staticmethod
    def _parse_response(response: httpx.Response) -> str:
        try:
            payload: Any = response.json()
            translated = payload["choices"][0]["message"]["content"]
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            raise ProviderInvalidResponseError(
                "LLM provider returned an unexpected response shape"
            ) from exc
        if not isinstance(translated, str) or not translated.strip():
            raise ProviderInvalidResponseError("LLM provider returned empty text")
        return translated.strip()
