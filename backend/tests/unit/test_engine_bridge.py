from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import ClassVar

import pytest

from all_to_pdf.domain.job import JobStatus, TranslatorProfile
from all_to_pdf.domain.provider import ProviderRateLimitError, TranslationResult
from all_to_pdf.engine import bridge
from all_to_pdf.infrastructure.providers.factory import ProviderConfigurationError

_MINIMAL_PDF = b"%PDF-1.4\ntrailer<<>>\n%%EOF\n"


class FakeProvider:
    provider_id = "fake"
    model_id = "fake-model"

    def __init__(self) -> None:
        self.closed = False
        self.calls: list[str] = []

    def translate(
        self,
        text: str,
        *,
        source_language: str,
        target_language: str,
    ) -> TranslationResult:
        self.calls.append(f"{source_language}:{target_language}:{text}")
        return TranslationResult(f"vi:{text}", self.provider_id, self.model_id, len(text))

    def close(self) -> None:
        self.closed = True


def _package(monkeypatch: pytest.MonkeyPatch, name: str) -> ModuleType:
    module = ModuleType(name)
    module.__dict__["__path__"] = []
    monkeypatch.setitem(sys.modules, name, module)
    return module


def _install_fake_engine_modules(
    monkeypatch: pytest.MonkeyPatch,
    events: list[dict[str, object] | BaseException],
) -> SimpleNamespace:
    _package(monkeypatch, "babeldoc")
    _package(monkeypatch, "babeldoc.babeldoc_exception")
    exception_module = ModuleType("babeldoc.babeldoc_exception.BabelDOCException")
    monkeypatch.setitem(
        sys.modules,
        "babeldoc.babeldoc_exception.BabelDOCException",
        exception_module,
    )
    _package(monkeypatch, "babeldoc.format")
    _package(monkeypatch, "babeldoc.format.pdf")
    high_level_module = ModuleType("babeldoc.format.pdf.high_level")
    config_module = ModuleType("babeldoc.format.pdf.translation_config")
    progress_module = ModuleType("babeldoc.progress_monitor")
    monkeypatch.setitem(sys.modules, "babeldoc.format.pdf.high_level", high_level_module)
    monkeypatch.setitem(sys.modules, "babeldoc.format.pdf.translation_config", config_module)
    monkeypatch.setitem(sys.modules, "babeldoc.progress_monitor", progress_module)

    _package(monkeypatch, "pdf2zh_next")
    _package(monkeypatch, "pdf2zh_next.translator")
    base_translator_module = ModuleType("pdf2zh_next.translator.base_translator")
    monkeypatch.setitem(
        sys.modules,
        "pdf2zh_next.translator.base_translator",
        base_translator_module,
    )

    class ContentFilterError(Exception):
        pass

    class ExtractTextError(Exception):
        pass

    class InputFileGeneratedByBabelDOCError(Exception):
        pass

    class ScannedPDFError(Exception):
        pass

    for exception in (
        ContentFilterError,
        ExtractTextError,
        InputFileGeneratedByBabelDOCError,
        ScannedPDFError,
    ):
        exception_module.__dict__[exception.__name__] = exception

    class FakeTranslationConfig:
        instances: ClassVar[list[FakeTranslationConfig]] = []

        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs
            self.report_interval = 0.1
            self.input_file = kwargs["input_file"]
            self.__class__.instances.append(self)

    class FakeWatermarkOutputMode:
        NoWatermark = "no-watermark"

    class FakeProgressMonitor:
        def __init__(
            self,
            _stages: object,
            *,
            progress_change_callback: object,
            report_interval: float,
        ) -> None:
            self.progress_change_callback = progress_change_callback
            self.report_interval = report_interval

        def __enter__(self) -> FakeProgressMonitor:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    postprocess_calls: list[str] = []

    def get_translation_stage(_config: object) -> list[tuple[str, float]]:
        return [("fake", 1.0)]

    def do_translate_single(monitor: FakeProgressMonitor, _config: object) -> object:
        for event in events:
            if isinstance(event, BaseException):
                raise event
            event_type = event.get("type")
            if event_type in {"progress_start", "progress_update", "progress_end"}:
                callback = monitor.progress_change_callback
                assert callable(callback)
                callback(**event)
            elif event_type == "error":
                error = event.get("error")
                if isinstance(error, BaseException):
                    raise error
                raise RuntimeError(str(error))
            elif event_type == "finish":
                return event.get("translate_result")
        return None

    def fix_cmap(_result: object, _config: object) -> None:
        postprocess_calls.append("fix_cmap")

    def add_metadata(_result: object, _config: object) -> None:
        postprocess_calls.append("add_metadata")

    class FakeBaseTranslator:
        pass

    high_level_module.__dict__.update(
        {
            "_do_translate_single": do_translate_single,
            "add_metadata": add_metadata,
            "fix_cmap": fix_cmap,
            "get_translation_stage": get_translation_stage,
        }
    )
    config_module.__dict__["TranslationConfig"] = FakeTranslationConfig
    config_module.__dict__["WatermarkOutputMode"] = FakeWatermarkOutputMode
    progress_module.__dict__["ProgressMonitor"] = FakeProgressMonitor
    base_translator_module.__dict__["BaseTranslator"] = FakeBaseTranslator
    return SimpleNamespace(
        ContentFilterError=ContentFilterError,
        ExtractTextError=ExtractTextError,
        InputFileGeneratedByBabelDOCError=InputFileGeneratedByBabelDOCError,
        ScannedPDFError=ScannedPDFError,
        TranslationConfig=FakeTranslationConfig,
        postprocess_calls=postprocess_calls,
    )


def _patch_factory(monkeypatch: pytest.MonkeyPatch, provider: FakeProvider) -> None:
    class FakeFactory:
        def __init__(self, _settings: object) -> None:
            pass

        def build(
            self,
            profile: TranslatorProfile,
            *,
            llm_profile_id: str | None,
        ) -> FakeProvider:
            del profile, llm_profile_id
            return provider

    monkeypatch.setattr(bridge, "TranslationProviderFactory", FakeFactory)


async def _request(
    tmp_path: Path,
    *,
    profile: TranslatorProfile = TranslatorProfile.AZURE_NMT,
) -> bridge.BridgeRequest:
    workspace = tmp_path / "workspace"
    await asyncio.to_thread(workspace.mkdir, parents=True)
    input_path = workspace / "source.pdf"
    await asyncio.to_thread(input_path.write_bytes, _MINIMAL_PDF)
    return bridge.BridgeRequest(
        workspace=workspace,
        input_path=input_path,
        output_path=workspace / "translated.pdf",
        source_language="en",
        target_language="vi",
        translator_profile=profile,
        llm_profile_id="default" if profile is TranslatorProfile.OPENAI_COMPATIBLE_LLM else None,
    )


async def test_translate_bridge_emits_progress_and_copies_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[dict[str, object] | BaseException] = []
    runtime = _install_fake_engine_modules(monkeypatch, events)
    provider = FakeProvider()
    _patch_factory(monkeypatch, provider)
    request = await _request(tmp_path)
    generated = request.workspace / "generated.pdf"
    await asyncio.to_thread(generated.write_bytes, _MINIMAL_PDF)
    events.extend(
        [
            {
                "type": "progress_update",
                "stage": "Parse Page Layout",
                "overall_progress": 15,
            },
            {
                "type": "progress_update",
                "stage": "Translate Paragraphs",
                "overall_progress": 55,
            },
            {
                "type": "progress_update",
                "stage": "Typesetting",
                "overall_progress": 80,
            },
            {
                "type": "progress_update",
                "stage": "Save PDF",
                "overall_progress": 99,
            },
            {
                "type": "finish",
                "translate_result": SimpleNamespace(
                    no_watermark_mono_pdf_path=generated,
                    mono_pdf_path=None,
                ),
            },
        ]
    )
    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(bridge, "_emit", emitted.append)

    await bridge._translate(request)

    assert await asyncio.to_thread(request.output_path.read_bytes) == _MINIMAL_PDF
    assert [item["status"] for item in emitted[:-1]] == [
        "parsing",
        "translating",
        "typesetting",
        "generating_pdf",
        "generating_pdf",
    ]
    assert emitted[-2]["percent"] == 94.0
    assert emitted[-1]["type"] == "finish"
    config = runtime.TranslationConfig.instances[0]
    assert config.kwargs["no_dual"] is True
    assert config.kwargs["auto_extract_glossary"] is False
    assert runtime.postprocess_calls == ["fix_cmap", "add_metadata"]
    assert provider.closed is True


@pytest.mark.parametrize(
    ("stage", "expected"),
    [
        ("Parse Formulas and Styles", JobStatus.PARSING),
        ("Translate Paragraphs", JobStatus.TRANSLATING),
        ("Extract Terms", JobStatus.PARSING),
        ("Typesetting", JobStatus.TYPESETTING),
        ("Subset font", JobStatus.GENERATING_PDF),
    ],
)
def test_normalized_status(stage: str, expected: JobStatus) -> None:
    assert bridge._normalized_status(stage) is expected


def test_progress_relay_ignores_non_progress_and_bad_percent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(bridge, "_emit", emitted.append)
    relay = bridge._ProgressRelay()

    relay(type="stage_summary")
    relay(type="progress_update", stage="Parse PDF", overall_progress="bad")
    relay.finalizing()

    assert len(emitted) == 2
    assert emitted[0]["percent"] == 10.0
    assert emitted[1]["percent"] == 94.0


def test_bridge_request_loads_valid_manifest(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = workspace / "source.pdf"
    source.write_bytes(_MINIMAL_PDF)
    manifest = workspace / "request.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "workspace": str(workspace),
                "input_path": str(source),
                "output_path": str(workspace / "out.pdf"),
                "source_language": "en",
                "target_language": "vi",
                "translator_profile": "azure_nmt",
                "llm_profile_id": None,
            }
        ),
        encoding="utf-8",
    )

    request = bridge.BridgeRequest.load(manifest)

    assert request.input_path == source.resolve()
    assert request.translator_profile is TranslatorProfile.AZURE_NMT


def test_bridge_request_rejects_invalid_schema_and_path_escape(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"schema_version":2}', encoding="utf-8")
    with pytest.raises(bridge.BridgeFailure, match="invalid engine request"):
        bridge.BridgeRequest.load(invalid)

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = workspace / "source.pdf"
    source.write_bytes(_MINIMAL_PDF)
    escaped = workspace / "escaped.json"
    escaped.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "workspace": str(workspace),
                "input_path": str(source),
                "output_path": str(tmp_path / "outside.pdf"),
                "source_language": "en",
                "target_language": "vi",
                "translator_profile": "azure_nmt",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(bridge.BridgeFailure, match="inside the job workspace"):
        bridge.BridgeRequest.load(escaped)


async def test_provider_backed_translator_supports_both_profiles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[dict[str, object] | BaseException] = []
    _install_fake_engine_modules(monkeypatch, events)
    provider = FakeProvider()
    azure_request = await _request(tmp_path)

    azure = bridge._build_translator(provider, azure_request)

    assert azure.translate("Energy") == "vi:Energy"
    with pytest.raises(NotImplementedError):
        azure.do_llm_translate(None)

    llm_workspace = tmp_path / "llm"
    await asyncio.to_thread(llm_workspace.mkdir)
    llm_request = bridge.BridgeRequest(
        workspace=llm_workspace,
        input_path=llm_workspace / "source.pdf",
        output_path=llm_workspace / "out.pdf",
        source_language="en",
        target_language="vi",
        translator_profile=TranslatorProfile.OPENAI_COMPATIBLE_LLM,
        llm_profile_id="default",
    )
    llm = bridge._build_translator(provider, llm_request)
    assert llm.do_llm_translate(None) is None
    assert llm.llm_translate("Model") == "vi:Model"
    assert llm.translate_call_count == 1


@pytest.mark.parametrize(
    ("error_factory", "expected_code", "retryable"),
    [
        (lambda runtime: runtime.ScannedPDFError("scan"), "OCR_REQUIRED", False),
        (lambda _runtime: ProviderRateLimitError("rate"), "PROVIDER_RATE_LIMITED", True),
        (lambda _runtime: RuntimeError("bad"), "ENGINE_UNEXPECTED_ERROR", True),
    ],
)
async def test_translate_bridge_maps_core_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_factory: object,
    expected_code: str,
    retryable: bool,
) -> None:
    events: list[dict[str, object] | BaseException] = []
    runtime = _install_fake_engine_modules(monkeypatch, events)
    provider = FakeProvider()
    _patch_factory(monkeypatch, provider)
    request = await _request(tmp_path)
    factory = error_factory
    assert callable(factory)
    events.append(factory(runtime))

    with pytest.raises(bridge.BridgeFailure) as captured:
        await bridge._translate(request)

    assert captured.value.code == expected_code
    assert captured.value.retryable is retryable
    assert provider.closed is True


async def test_translate_bridge_maps_extract_error_and_missing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raised_events: list[dict[str, object] | BaseException] = []
    runtime = _install_fake_engine_modules(monkeypatch, raised_events)
    provider = FakeProvider()
    _patch_factory(monkeypatch, provider)
    request = await _request(tmp_path)
    raised_events.append(runtime.ExtractTextError("no text"))

    with pytest.raises(bridge.BridgeFailure) as captured:
        await bridge._translate(request)
    assert captured.value.code == "PDF_TEXT_EXTRACTION_FAILED"

    missing_events: list[dict[str, object] | BaseException] = []
    runtime = _install_fake_engine_modules(monkeypatch, missing_events)
    provider = FakeProvider()
    _patch_factory(monkeypatch, provider)
    request = await _request(tmp_path / "second")
    missing_events.append(
        {
            "type": "finish",
            "translate_result": SimpleNamespace(
                no_watermark_mono_pdf_path=None,
                mono_pdf_path=None,
            ),
        }
    )
    with pytest.raises(bridge.BridgeFailure) as missing:
        await bridge._translate(request)
    assert missing.value.code == "ENGINE_OUTPUT_MISSING"
    assert runtime.postprocess_calls == ["fix_cmap", "add_metadata"]


async def test_translate_bridge_rejects_unconfigured_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[dict[str, object] | BaseException] = []
    _install_fake_engine_modules(monkeypatch, events)

    class FailingFactory:
        def __init__(self, _settings: object) -> None:
            pass

        def build(self, *_args: object, **_kwargs: object) -> FakeProvider:
            raise ProviderConfigurationError("missing key")

    monkeypatch.setattr(bridge, "TranslationProviderFactory", FailingFactory)
    request = await _request(tmp_path)

    with pytest.raises(bridge.BridgeFailure) as captured:
        await bridge._translate(request)

    assert captured.value.code == "PROVIDER_NOT_CONFIGURED"


def test_fail_emits_machine_error(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(bridge, "_emit", emitted.append)

    with pytest.raises(SystemExit) as captured:
        bridge._fail(bridge.BridgeFailure("OCR_REQUIRED", "scan"))

    assert captured.value.code == 20
    assert emitted == [
        {
            "type": "error",
            "code": "OCR_REQUIRED",
            "message": "scan",
            "retryable": False,
        }
    ]
