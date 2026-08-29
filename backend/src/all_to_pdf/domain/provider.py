"""Provider-neutral translation contracts and errors."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol


class TranslationProviderError(RuntimeError):
    code = "PROVIDER_ERROR"
    retryable = False


class ProviderAuthenticationError(TranslationProviderError):
    code = "PROVIDER_AUTH_FAILED"


class ProviderRateLimitError(TranslationProviderError):
    code = "PROVIDER_RATE_LIMITED"
    retryable = True


class ProviderTransientError(TranslationProviderError):
    code = "PROVIDER_TRANSIENT_ERROR"
    retryable = True


class ProviderInvalidResponseError(TranslationProviderError):
    code = "PROVIDER_INVALID_RESPONSE"


class PlaceholderValidationError(TranslationProviderError):
    code = "PLACEHOLDER_VALIDATION_FAILED"


@dataclass(frozen=True, slots=True)
class TranslationResult:
    translated_text: str
    provider_id: str
    model_id: str
    input_units: int


class TextTranslationProvider(Protocol):
    provider_id: str
    model_id: str

    def translate(
        self,
        text: str,
        *,
        source_language: str,
        target_language: str,
    ) -> TranslationResult: ...


class ProtectedTokenValidator:
    """Reject translations that lose, invent, duplicate, or reorder protected tokens.

    BabelDOC may use ``{vN}``, ``<bN>...</bN>`` or
    ``<style id='N'>...</style>`` around formula and rich-text content. A valid
    translation must preserve the normalized token sequence exactly.
    """

    _token_pattern = re.compile(
        r"(?:"
        r"\{\s*v\s*\d+\s*\}"
        r"|<\s*b\s*\d+\s*>"
        r"|<\s*/\s*b\s*\d+\s*>"
        r"|<\s*style\s+id\s*=\s*['\"]?\s*\d+\s*['\"]?\s*>"
        r"|<\s*/\s*style\s*>"
        r"|\[\[[^\]]+\]\]"
        r"|%%[^%]+%%"
        r"|%(?:s|d)"
        r")",
        re.IGNORECASE,
    )

    def validate(self, source: str, translated: str) -> None:
        expected = self._extract(source)
        actual = self._extract(translated)
        if expected != actual:
            raise PlaceholderValidationError(
                f"protected token sequence mismatch: expected={expected}, actual={actual}"
            )

    def _extract(self, value: str) -> list[str]:
        return [self._normalize(match.group(0)) for match in self._token_pattern.finditer(value)]

    @staticmethod
    def _normalize(token: str) -> str:
        normalized = re.sub(r"\s+", "", token).lower()
        return normalized.replace('"', "'")
