from __future__ import annotations

from typing import Any

import httpx
import pytest

from all_to_pdf.engine.errors import EngineProcessError
from all_to_pdf.engine.provider_clients import build_provider_client


class FakeResponse:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload
        self.is_error = status_code >= 400

    def json(self) -> object:
        return self._payload


class FakeClient:
    response = FakeResponse(200, {})
    last_request: dict[str, Any] | None = None
    closed = False

    def __init__(self, timeout: float) -> None:
        self.timeout = timeout

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        type(self).last_request = {"url": url, **kwargs}
        return type(self).response

    def close(self) -> None:
        type(self).closed = True


def test_deterministic_provider() -> None:
    provider = build_provider_client(
        "deterministic_test",
        source_language="en",
        target_language="vi",
    )

    assert provider.translate("Hello world.") == "Xin chào thế giới."
    assert provider.translate("Unknown {v1}") == "[VI] Unknown {v1}"


def test_unsupported_provider() -> None:
    with pytest.raises(EngineProcessError) as raised:
        build_provider_client("missing", source_language="en", target_language="vi")
    assert raised.value.code == "PROVIDER_NOT_CONFIGURED"


def test_azure_provider_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.setenv("ATP_AZURE_TRANSLATOR_ENDPOINT", "https://azure.example")
    monkeypatch.setenv("ATP_AZURE_TRANSLATOR_API_KEY", "secret")
    monkeypatch.setenv("ATP_AZURE_TRANSLATOR_REGION", "southeastasia")
    FakeClient.response = FakeResponse(
        200,
        [{"translations": [{"text": "Xin chào"}]}],
    )

    provider = build_provider_client("azure_nmt", source_language="en", target_language="vi")
    assert provider.translate("Hello") == "Xin chào"
    provider.close()

    assert FakeClient.last_request is not None
    assert FakeClient.last_request["url"] == "https://azure.example/translate"
    assert FakeClient.last_request["params"]["from"] == "en"
    assert FakeClient.last_request["params"]["to"] == "vi"
    assert FakeClient.closed is True


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, "PROVIDER_AUTH_FAILED"),
        (429, "PROVIDER_RATE_LIMITED"),
        (500, "PROVIDER_SERVER_ERROR"),
        (400, "PROVIDER_INVALID_REQUEST"),
    ],
)
def test_azure_provider_classifies_http_errors(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    code: str,
) -> None:
    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.setenv("ATP_AZURE_TRANSLATOR_ENDPOINT", "https://azure.example")
    monkeypatch.setenv("ATP_AZURE_TRANSLATOR_API_KEY", "secret")
    FakeClient.response = FakeResponse(status, {})
    provider = build_provider_client("azure_nmt", source_language="en", target_language="vi")

    with pytest.raises(EngineProcessError) as raised:
        provider.translate("Hello")
    assert raised.value.code == code


def test_openai_compatible_provider_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.setenv("ATP_LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("ATP_LLM_API_KEY", "secret")
    monkeypatch.setenv("ATP_LLM_MODEL", "small-model")
    FakeClient.response = FakeResponse(
        200,
        {"choices": [{"message": {"content": "Xin chào"}}]},
    )

    provider = build_provider_client(
        "openai_compatible_llm",
        source_language="en",
        target_language="vi",
    )

    assert provider.translate("Hello") == "Xin chào"
    assert FakeClient.last_request is not None
    assert FakeClient.last_request["url"] == "https://llm.example/v1/chat/completions"
    assert FakeClient.last_request["json"]["temperature"] == 0


def test_provider_requires_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ATP_AZURE_TRANSLATOR_API_KEY", raising=False)
    monkeypatch.setenv("ATP_AZURE_TRANSLATOR_ENDPOINT", "https://azure.example")

    with pytest.raises(EngineProcessError) as raised:
        build_provider_client("azure_nmt", source_language="en", target_language="vi")
    assert raised.value.code == "PROVIDER_NOT_CONFIGURED"
