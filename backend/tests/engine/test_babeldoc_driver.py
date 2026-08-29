from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from all_to_pdf.engine import babeldoc_driver
from all_to_pdf.engine.babeldoc_driver import BabelDocDriver
from all_to_pdf.engine.errors import EngineProcessError
from all_to_pdf.engine.models import EngineRequest, EngineStage
from all_to_pdf.engine.provider_clients import ProviderClient


class FakeBaseTranslator:
    def __init__(self, lang_in: str, lang_out: str, ignore_cache: bool) -> None:
        self.lang_in = lang_in
        self.lang_out = lang_out
        self.ignore_cache = ignore_cache
        self.cache_parameters: dict[str, object] = {}

    def add_cache_impact_parameters(self, key: str, value: object) -> None:
        self.cache_parameters[key] = value


class FakeTranslationConfig:
    def __init__(
        self,
        input_file: Path,
        output_dir: Path,
        translator: object,
        lang_in: str,
        lang_out: str,
        no_dual: bool,
        no_mono: bool,
    ) -> None:
        self.input_file = input_file
        self.output_dir = output_dir
        self.translator = translator
        self.lang_in = lang_in
        self.lang_out = lang_out
        self.no_dual = no_dual
        self.no_mono = no_mono


class FakeWatermarkMode:
    NoWatermark = "none"


def _request(tmp_path: Path) -> EngineRequest:
    source = tmp_path / "input.pdf"
    source.write_bytes(b"%PDF-1.4\n%%EOF\n")
    return EngineRequest(
        "job-1",
        source,
        tmp_path / "output",
        "en",
        "vi",
        "deterministic_test",
    )


def test_driver_runs_with_compatible_babeldoc_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    output = request.output_directory / "translated.pdf"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"%PDF-1.4\n%%EOF\n")

    async def async_translate(config: FakeTranslationConfig):
        assert config.input_file == request.input_pdf
        assert config.lang_out == "vi"
        yield {
            "type": "progress_update",
            "stage": "Translate Paragraphs",
            "overall_progress": 55,
        }
        yield {
            "type": "finish",
            "translate_result": SimpleNamespace(mono_pdf_path=output),
            "token_usage": {"main": {"total": 5}},
        }

    modules: dict[str, Any] = {
        "babeldoc.format.pdf.high_level": SimpleNamespace(async_translate=async_translate),
        "babeldoc.format.pdf.translation_config": SimpleNamespace(
            TranslationConfig=FakeTranslationConfig,
            WatermarkOutputMode=FakeWatermarkMode,
        ),
        "babeldoc.translator.translator": SimpleNamespace(BaseTranslator=FakeBaseTranslator),
    }
    monkeypatch.setattr(babeldoc_driver, "_load_module", modules.__getitem__)
    monkeypatch.setattr(
        babeldoc_driver,
        "build_provider_client",
        lambda *args, **kwargs: ProviderClient(
            translate=lambda text: f"VI:{text}",
            close=lambda: None,
            provider_name="fake",
            model_name="fake-v1",
        ),
    )
    events = []

    result = BabelDocDriver().run(request, events.append)

    assert result.output_pdf == output
    assert result.report["provider"] == "fake"
    assert any(event.stage is EngineStage.TRANSLATING for event in events)
    assert events[-1].stage is EngineStage.COMPLETED


def test_driver_rejects_invalid_pdf(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request.input_pdf.write_text("not a pdf")

    with pytest.raises(EngineProcessError) as raised:
        BabelDocDriver().run(request, lambda _: None)
    assert raised.value.code == "INPUT_PDF_INVALID"


def test_load_module_classifies_missing_dependency() -> None:
    with pytest.raises(EngineProcessError) as raised:
        babeldoc_driver._load_module("this.module.does.not.exist")
    assert raised.value.code == "ENGINE_DEPENDENCY_MISSING"


def test_translation_config_reports_incompatible_signature(tmp_path: Path) -> None:
    class IncompatibleConfig:
        def __init__(self, required_unknown: str) -> None:
            self.required_unknown = required_unknown

    with pytest.raises(EngineProcessError) as raised:
        babeldoc_driver._build_translation_config(
            SimpleNamespace(TranslationConfig=IncompatibleConfig),
            request=_request(tmp_path),
            translator=object(),
        )
    assert raised.value.code == "ENGINE_API_INCOMPATIBLE"
