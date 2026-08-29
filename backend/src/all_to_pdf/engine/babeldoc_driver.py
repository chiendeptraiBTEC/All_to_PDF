"""Lazy BabelDOC integration used inside the dedicated worker image."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import re
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from all_to_pdf.engine.errors import EngineProcessError
from all_to_pdf.engine.models import EngineProgress, EngineRequest, EngineResult, EngineStage
from all_to_pdf.engine.provider_clients import ProviderClient, build_provider_client
from all_to_pdf.engine.upstream import BABELDOC_PIN

ProgressEmitter = Callable[[EngineProgress], None]

_STAGE_RULES: tuple[tuple[str, EngineStage], ...] = (
    ("parse pdf", EngineStage.PARSING),
    ("scanned", EngineStage.PREFLIGHT),
    ("layout", EngineStage.LAYOUT),
    ("paragraph", EngineStage.PARSING),
    ("formula", EngineStage.PARSING),
    ("translate", EngineStage.TRANSLATING),
    ("typesetting", EngineStage.TYPESETTING),
    ("drawing", EngineStage.GENERATING_PDF),
    ("font", EngineStage.GENERATING_PDF),
    ("save pdf", EngineStage.GENERATING_PDF),
)


class BabelDocDriver:
    """Translates one PDF with BabelDOC and a service-owned provider bridge."""

    def run(self, request: EngineRequest, emit: ProgressEmitter) -> EngineResult:
        started_at = time.monotonic()
        _validate_paths(request)
        emit(EngineProgress(EngineStage.STARTING, 0.0, "Loading pinned PDF engine"))

        high_level = _load_module("babeldoc.format.pdf.high_level")
        translation_config_module = _load_module("babeldoc.format.pdf.translation_config")
        translator_module = _load_module("babeldoc.translator.translator")

        provider = build_provider_client(
            request.translator_profile,
            source_language=request.source_language,
            target_language=request.target_language,
        )
        try:
            translator = _build_babeldoc_translator(
                translator_module,
                provider,
                source_language=request.source_language,
                target_language=request.target_language,
            )
            config = _build_translation_config(
                translation_config_module,
                request=request,
                translator=translator,
            )
            output_pdf, engine_report = asyncio.run(
                _run_async_translation(high_level, config, emit)
            )
        finally:
            provider.close()

        elapsed = time.monotonic() - started_at
        report: dict[str, object] = {
            "babeldoc_commit": BABELDOC_PIN.commit,
            "provider": provider.provider_name,
            "model": provider.model_name,
            **engine_report,
        }
        emit(EngineProgress(EngineStage.COMPLETED, 100.0, "PDF engine completed"))
        return EngineResult(
            output_pdf=output_pdf,
            elapsed_seconds=elapsed,
            engine_name="BabelDOC",
            engine_version=BABELDOC_PIN.commit,
            report=report,
        )


async def _run_async_translation(
    high_level: Any,
    config: Any,
    emit: ProgressEmitter,
) -> tuple[Path, dict[str, object]]:
    async_translate = getattr(high_level, "async_translate", None)
    if async_translate is None:
        raise EngineProcessError(
            "pinned BabelDOC does not expose async_translate",
            code="ENGINE_API_INCOMPATIBLE",
        )

    output_pdf: Path | None = None
    report: dict[str, object] = {}
    async for raw_event in async_translate(config):
        if not isinstance(raw_event, Mapping):
            continue
        event = {str(key): value for key, value in raw_event.items()}
        event_type = event.get("type")
        if event_type in {"progress_start", "progress_update", "progress_end"}:
            emit(_progress_from_babeldoc(event))
            continue
        if event_type == "error":
            raise EngineProcessError(
                f"BabelDOC failed: {event.get('error', 'unknown error')}",
                code="BABELDOC_TRANSLATION_FAILED",
            )
        if event_type == "finish":
            output_pdf = _extract_mono_output(event.get("translate_result"))
            token_usage = event.get("token_usage")
            if isinstance(token_usage, Mapping):
                report["token_usage"] = dict(token_usage)

    if output_pdf is None:
        raise EngineProcessError(
            "BabelDOC completed without a mono PDF result",
            code="ENGINE_PROTOCOL_ERROR",
        )
    if not output_pdf.is_file():
        raise EngineProcessError(
            f"BabelDOC output does not exist: {output_pdf}",
            code="ENGINE_OUTPUT_MISSING",
        )
    return output_pdf, report


def _progress_from_babeldoc(event: Mapping[str, object]) -> EngineProgress:
    stage_text = str(event.get("stage", "Working"))
    lowered = stage_text.casefold()
    stage = EngineStage.STARTING
    for fragment, candidate in _STAGE_RULES:
        if fragment in lowered:
            stage = candidate
            break

    raw_percent = event.get("overall_progress", event.get("stage_progress", 0.0))
    percent = float(raw_percent) if isinstance(raw_percent, int | float) else 0.0
    percent = min(99.9, max(0.0, percent))
    return EngineProgress(stage=stage, percent=percent, message=stage_text)


def _extract_mono_output(translate_result: object) -> Path:
    if translate_result is None:
        raise EngineProcessError(
            "BabelDOC finish event has no translate_result",
            code="ENGINE_PROTOCOL_ERROR",
        )
    mono_path = getattr(translate_result, "mono_pdf_path", None)
    if mono_path is None and isinstance(translate_result, Mapping):
        mono_path = translate_result.get("mono_pdf_path")
    if not isinstance(mono_path, str | Path):
        raise EngineProcessError(
            "BabelDOC finish event has no mono_pdf_path",
            code="ENGINE_PROTOCOL_ERROR",
        )
    return Path(mono_path)


def _build_translation_config(
    module: Any,
    *,
    request: EngineRequest,
    translator: Any,
) -> Any:
    config_class = getattr(module, "TranslationConfig", None)
    watermark_mode_class = getattr(module, "WatermarkOutputMode", None)
    if config_class is None:
        raise EngineProcessError(
            "pinned BabelDOC does not expose TranslationConfig",
            code="ENGINE_API_INCOMPATIBLE",
        )

    watermark_mode = None
    if watermark_mode_class is not None:
        watermark_mode = getattr(watermark_mode_class, "NoWatermark", None)

    candidates: dict[str, object] = {
        "input_file": request.input_pdf,
        "font": None,
        "pages": None,
        "output_dir": request.output_directory,
        "doc_layout_model": None,
        "translator": translator,
        "debug": False,
        "lang_in": request.source_language,
        "lang_out": request.target_language,
        "no_dual": True,
        "no_mono": False,
        "qps": 5,
        "watermark_output_mode": watermark_mode,
        "report_interval": 0.1,
        "skip_clean": False,
        "split_strategy": None,
        "table_model": None,
        "skip_scanned_detection": False,
        "ocr_workaround": False,
        "auto_enable_ocr_workaround": False,
        "pool_max_workers": 4,
        "auto_extract_glossary": False,
        "only_include_translated_page": False,
        "term_extraction_translator": translator,
        "term_pool_max_workers": 1,
    }
    if watermark_mode is None:
        candidates.pop("watermark_output_mode")

    signature = inspect.signature(config_class)
    parameters = signature.parameters
    accepts_arbitrary_keywords = any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )
    kwargs = (
        candidates
        if accepts_arbitrary_keywords
        else {key: value for key, value in candidates.items() if key in parameters}
    )

    required_missing = [
        name
        for name, parameter in parameters.items()
        if name not in kwargs
        and name != "self"
        and parameter.default is inspect.Parameter.empty
        and parameter.kind
        in {inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY}
    ]
    if required_missing:
        raise EngineProcessError(
            "unsupported BabelDOC TranslationConfig; missing values for: "
            + ", ".join(required_missing),
            code="ENGINE_API_INCOMPATIBLE",
        )
    try:
        return config_class(**kwargs)
    except Exception as exc:
        raise EngineProcessError(
            f"failed to construct BabelDOC TranslationConfig: {exc}",
            code="ENGINE_API_INCOMPATIBLE",
        ) from exc


def _build_babeldoc_translator(
    module: Any,
    provider: ProviderClient,
    *,
    source_language: str,
    target_language: str,
) -> Any:
    base_class = getattr(module, "BaseTranslator", None)
    if base_class is None:
        raise EngineProcessError(
            "pinned BabelDOC does not expose BaseTranslator",
            code="ENGINE_API_INCOMPATIBLE",
        )

    class ServiceTranslator(base_class):  # type: ignore[misc, valid-type]
        name = "atp_bridge"

        def __init__(self) -> None:
            super().__init__(source_language, target_language, True)
            self.model = provider.model_name
            self.add_cache_impact_parameters("provider", provider.provider_name)
            self.add_cache_impact_parameters("model", provider.model_name)

        def do_translate(
            self,
            text: str,
            rate_limit_params: dict[str, object] | None = None,
        ) -> str:
            del rate_limit_params
            return provider.translate(text)

        def do_llm_translate(
            self,
            text: str | None,
            rate_limit_params: dict[str, object] | None = None,
        ) -> str | None:
            del rate_limit_params
            return None if text is None else provider.translate(text)

        def get_formular_placeholder(self, placeholder_id: int | str) -> tuple[str, str]:
            value = str(placeholder_id)
            return f"{{v{value}}}", rf"{{\s*v\s*{re.escape(value)}\s*}}"

        def get_rich_text_left_placeholder(
            self,
            placeholder_id: int | str,
        ) -> tuple[str, str]:
            value = str(placeholder_id)
            return (
                f"<style id='{value}'>",
                rf"<\s*style\s*id\s*=\s*'\s*{re.escape(value)}\s*'\s*>",
            )

        def get_rich_text_right_placeholder(
            self,
            placeholder_id: int | str,
        ) -> tuple[str, str]:
            del placeholder_id
            return "</style>", r"<\s*\/\s*style\s*>"

    return ServiceTranslator()


def _load_module(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise EngineProcessError(
            f"PDF engine dependency is missing: {name}",
            code="ENGINE_DEPENDENCY_MISSING",
        ) from exc


def _validate_paths(request: EngineRequest) -> None:
    if not request.input_pdf.is_file():
        raise EngineProcessError(
            f"input PDF does not exist: {request.input_pdf}",
            code="INPUT_PDF_NOT_FOUND",
        )
    with request.input_pdf.open("rb") as source_file:
        signature = source_file.read(5)
    if signature != b"%PDF-":
        raise EngineProcessError(
            "input artifact is not a PDF",
            code="INPUT_PDF_INVALID",
        )
    request.output_directory.mkdir(parents=True, exist_ok=True)
