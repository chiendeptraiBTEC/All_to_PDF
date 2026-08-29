"""Isolated BabelDOC process entry point.

Stdout is reserved for the JSONL protocol. Diagnostics go to stderr so the parent
worker can distinguish machine events from logs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

from all_to_pdf.config import Settings
from all_to_pdf.domain.job import JobStatus, TranslatorProfile
from all_to_pdf.domain.provider import TextTranslationProvider, TranslationProviderError
from all_to_pdf.infrastructure.providers.factory import (
    ProviderConfigurationError,
    TranslationProviderFactory,
)

BABELDOC_COMMIT = "38d3896dcde9b5a940c62cf5563cadea673a64d3"
PDFMATH_TRANSLATE_NEXT_COMMIT = "f8dffcf4c3a33b254391d43514439b975ce8d966"


class BridgeFailure(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class BridgeRequest:
    workspace: Path
    input_path: Path
    output_path: Path
    source_language: str
    target_language: str
    translator_profile: TranslatorProfile
    llm_profile_id: str | None

    @classmethod
    def load(cls, manifest_path: Path) -> BridgeRequest:
        try:
            payload: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
            if payload.get("schema_version") != 1:
                raise ValueError("unsupported engine request schema")
            workspace = Path(str(payload["workspace"])).resolve()
            input_path = Path(str(payload["input_path"])).resolve()
            output_path = Path(str(payload["output_path"])).resolve()
            profile = TranslatorProfile(str(payload["translator_profile"]))
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise BridgeFailure("ENGINE_REQUEST_INVALID", "invalid engine request") from exc
        if not input_path.is_file():
            raise BridgeFailure("ENGINE_INPUT_MISSING", "engine input PDF does not exist")
        if not input_path.is_relative_to(workspace) or not output_path.is_relative_to(workspace):
            raise BridgeFailure(
                "ENGINE_REQUEST_INVALID",
                "engine paths must stay inside the job workspace",
            )
        return cls(
            workspace=workspace,
            input_path=input_path,
            output_path=output_path,
            source_language=str(payload["source_language"]),
            target_language=str(payload["target_language"]),
            translator_profile=profile,
            llm_profile_id=payload.get("llm_profile_id"),
        )


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _fail(error: BridgeFailure) -> NoReturn:
    _emit(
        {
            "type": "error",
            "code": error.code,
            "message": str(error),
            "retryable": error.retryable,
        }
    )
    raise SystemExit(20 if error.code == "OCR_REQUIRED" else 1)


def _normalized_status(stage: str) -> JobStatus:
    lowered = stage.casefold()
    if "translate" in lowered and "term" not in lowered:
        return JobStatus.TRANSLATING
    if "typesetting" in lowered:
        return JobStatus.TYPESETTING
    if any(token in lowered for token in ("font", "drawing", "subset", "save pdf", "generate")):
        return JobStatus.GENERATING_PDF
    return JobStatus.PARSING


class _ProgressRelay:
    """Convert BabelDOC's synchronous progress callback into bridge JSONL events."""

    def __init__(self) -> None:
        self.last_percent = 10.0

    def __call__(self, **event: Any) -> None:
        if event.get("type") not in {"progress_start", "progress_update", "progress_end"}:
            return
        stage = str(event.get("stage", "Parse PDF"))
        try:
            raw_percent = float(event.get("overall_progress", self.last_percent))
        except (TypeError, ValueError):
            raw_percent = self.last_percent
        self.last_percent = max(self.last_percent, min(raw_percent, 93.0))
        _emit(
            {
                "type": "progress",
                "status": _normalized_status(stage).value,
                "percent": self.last_percent,
                "stage": stage,
            }
        )

    def finalizing(self) -> None:
        self.last_percent = max(self.last_percent, 94.0)
        _emit(
            {
                "type": "progress",
                "status": JobStatus.GENERATING_PDF.value,
                "percent": self.last_percent,
                "stage": "Finalize CMap and metadata",
            }
        )


def _build_translator(provider: TextTranslationProvider, request: BridgeRequest) -> Any:
    try:
        from pdf2zh_next.translator.base_translator import BaseTranslator
    except ImportError as exc:
        raise BridgeFailure(
            "ENGINE_DEPENDENCY_MISSING",
            "PDFMathTranslate-next is not installed in the engine image",
        ) from exc

    supports_llm = request.translator_profile is TranslatorProfile.OPENAI_COMPATIBLE_LLM

    class ProviderBackedTranslator(BaseTranslator):  # type: ignore[misc]
        name = "alltopdf"

        def __init__(self) -> None:
            self._provider = provider
            self.lang_in = request.source_language
            self.lang_out = request.target_language
            self.model = provider.model_id
            self.translate_call_count = 0
            self.translate_cache_call_count = 0

        def translate(
            self,
            text: str,
            ignore_cache: bool = False,
            rate_limit_params: dict[str, Any] | None = None,
        ) -> str:
            del ignore_cache, rate_limit_params
            self.translate_call_count += 1
            return self.do_translate(text)

        def llm_translate(
            self,
            text: str,
            ignore_cache: bool = False,
            rate_limit_params: dict[str, Any] | None = None,
        ) -> str:
            del ignore_cache, rate_limit_params
            self.translate_call_count += 1
            result = self.do_llm_translate(text)
            if result is None:
                raise RuntimeError("LLM translation unexpectedly returned None")
            return result

        def do_translate(
            self,
            text: str,
            rate_limit_params: dict[str, Any] | None = None,
        ) -> str:
            del rate_limit_params
            result = self._provider.translate(
                text,
                source_language=self.lang_in,
                target_language=self.lang_out,
            )
            return result.translated_text

        def do_llm_translate(
            self,
            text: str | None,
            rate_limit_params: dict[str, Any] | None = None,
        ) -> str | None:
            del rate_limit_params
            if not supports_llm:
                raise NotImplementedError
            if text is None:
                return None
            return self.do_translate(text)

    return ProviderBackedTranslator()


def _run_babeldoc_core(config: Any) -> Any:
    """Run the pinned synchronous core and bounded mono-PDF post-processing.

    BabelDOC's public async wrapper produced a valid mono PDF but did not terminate
    for the selected commit in CI. The pinned private core returned the artifact
    before that wrapper's finish path. This adapter intentionally owns the stable
    boundary and is protected by the real-engine smoke test.
    """

    try:
        from babeldoc.format.pdf.high_level import (
            _do_translate_single,
            add_metadata,
            fix_cmap,
            get_translation_stage,
        )
        from babeldoc.progress_monitor import ProgressMonitor
    except ImportError as exc:
        raise BridgeFailure(
            "ENGINE_DEPENDENCY_MISSING",
            "BabelDOC is not installed in the engine image",
        ) from exc

    progress = _ProgressRelay()
    started = time.perf_counter()
    with ProgressMonitor(
        get_translation_stage(config),
        progress_change_callback=progress,
        report_interval=config.report_interval,
    ) as monitor:
        result = _do_translate_single(monitor, config)
    if result is None:
        raise BridgeFailure(
            "ENGINE_OUTPUT_MISSING",
            "BabelDOC core returned no translation result",
        )

    result.total_seconds = time.perf_counter() - started
    result.original_pdf_path = config.input_file
    result.peak_memory_usage = 0
    progress.finalizing()
    fix_cmap(result, config)
    add_metadata(result, config)
    return result


async def _translate(request: BridgeRequest) -> None:
    try:
        from babeldoc.babeldoc_exception.BabelDOCException import (
            ContentFilterError,
            ExtractTextError,
            InputFileGeneratedByBabelDOCError,
            ScannedPDFError,
        )
        from babeldoc.format.pdf.translation_config import (
            TranslationConfig,
            WatermarkOutputMode,
        )
    except ImportError as exc:
        raise BridgeFailure(
            "ENGINE_DEPENDENCY_MISSING",
            "BabelDOC is not installed in the engine image",
        ) from exc

    settings = Settings()
    try:
        provider = TranslationProviderFactory(settings).build(
            request.translator_profile,
            llm_profile_id=request.llm_profile_id,
        )
    except ProviderConfigurationError as exc:
        raise BridgeFailure("PROVIDER_NOT_CONFIGURED", str(exc)) from exc

    translator = _build_translator(provider, request)
    output_directory = request.workspace / "babeldoc-output"
    working_directory = request.workspace / "babeldoc-work"
    config = TranslationConfig(
        translator=translator,
        input_file=request.input_path,
        lang_in=request.source_language,
        lang_out=request.target_language,
        doc_layout_model=None,
        output_dir=output_directory,
        working_dir=working_directory,
        debug=False,
        no_dual=True,
        no_mono=False,
        qps=settings.translation_qps,
        pool_max_workers=settings.translation_pool_max_workers,
        watermark_output_mode=WatermarkOutputMode.NoWatermark,
        auto_extract_glossary=False,
        save_auto_extracted_glossary=False,
        table_model=None,
        metadata_extra_data="all-to-pdf",
    )
    try:
        finish_result = await asyncio.to_thread(_run_babeldoc_core, config)
        generated = getattr(finish_result, "no_watermark_mono_pdf_path", None) or getattr(
            finish_result, "mono_pdf_path", None
        )
        generated_path = Path(generated) if generated is not None else None
        generated_exists = generated_path is not None and await asyncio.to_thread(
            generated_path.is_file
        )
        if not generated_exists or generated_path is None:
            raise BridgeFailure(
                "ENGINE_OUTPUT_MISSING",
                "BabelDOC did not produce a mono PDF",
            )
        await asyncio.to_thread(request.output_path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copyfile, generated_path, request.output_path)
        _emit(
            {
                "type": "finish",
                "output_path": str(request.output_path),
                "engine_name": "BabelDOC core + PDFMathTranslate-next translator contract",
                "engine_version": f"{BABELDOC_COMMIT[:12]}+{PDFMATH_TRANSLATE_NEXT_COMMIT[:12]}",
            }
        )
    except BridgeFailure:
        raise
    except ScannedPDFError as exc:
        raise BridgeFailure("OCR_REQUIRED", str(exc)) from exc
    except ExtractTextError as exc:
        raise BridgeFailure("PDF_TEXT_EXTRACTION_FAILED", str(exc)) from exc
    except InputFileGeneratedByBabelDOCError as exc:
        raise BridgeFailure("PDF_ALREADY_TRANSLATED", str(exc)) from exc
    except ContentFilterError as exc:
        raise BridgeFailure("PROVIDER_CONTENT_FILTERED", str(exc)) from exc
    except TranslationProviderError as exc:
        raise BridgeFailure(exc.code, str(exc), retryable=exc.retryable) from exc
    except Exception as exc:
        raise BridgeFailure(
            "ENGINE_UNEXPECTED_ERROR",
            type(exc).__name__,
            retryable=True,
        ) from exc
    finally:
        # The parent worker owns the entire per-job TemporaryDirectory. Avoid the
        # selected upstream wrapper's non-terminating cleanup/finish path.
        close = getattr(provider, "close", None)
        if callable(close):
            await asyncio.to_thread(close)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the isolated BabelDOC engine bridge")
    parser.add_argument("--request", required=True, type=Path)
    args = parser.parse_args()
    try:
        request = BridgeRequest.load(args.request)
        asyncio.run(_translate(request))
    except BridgeFailure as exc:
        _fail(exc)
    except Exception as exc:  # never serialize a traceback into the JSONL channel
        traceback.print_exc(file=sys.stderr)
        _fail(BridgeFailure("ENGINE_UNEXPECTED_ERROR", type(exc).__name__, retryable=True))


if __name__ == "__main__":
    main()
