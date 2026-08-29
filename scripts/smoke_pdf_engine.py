#!/usr/bin/env python3
"""Run a real BabelDOC EN-to-VI smoke test without external provider credentials.

The script uses the production bridge and pinned upstream packages. Only the text
provider is deterministic so the test remains reproducible and free of network API
cost. BabelDOC still performs PDF parse, paragraph analysis, typesetting and output
creation.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
import traceback
from pathlib import Path
from typing import Any

import pymupdf

from all_to_pdf.domain.job import TranslatorProfile
from all_to_pdf.domain.provider import TextTranslationProvider, TranslationResult
from all_to_pdf.engine import bridge

_SOURCE_TEXT = "Hello world. This PDF keeps its layout."
_EXPECTED_TEXT = "Xin chào thế giới. PDF này giữ nguyên bố cục."


class DeterministicSmokeProvider:
    """Small fixture provider that changes only known English fragments."""

    provider_id = "deterministic_smoke"
    model_id = "deterministic-en-vi-v1"

    def __init__(self) -> None:
        self.call_count = 0

    def translate(
        self,
        text: str,
        *,
        source_language: str,
        target_language: str,
    ) -> TranslationResult:
        if source_language != "en" or target_language != "vi":
            raise ValueError("smoke provider supports only en-to-vi")
        self.call_count += 1
        translated = text
        replacements = (
            ("This PDF keeps its layout", "PDF này giữ nguyên bố cục"),
            ("Hello", "Xin chào"),
            ("world", "thế giới"),
        )
        for source, target in replacements:
            translated = translated.replace(source, target)
        return TranslationResult(
            translated_text=translated,
            provider_id=self.provider_id,
            model_id=self.model_id,
            input_units=len(text),
        )

    def close(self) -> None:
        return None


class SmokeProviderFactory:
    """Factory matching the production factory shape used by the bridge."""

    provider: DeterministicSmokeProvider

    def __init__(self, _settings: object) -> None:
        self.provider = _SMOKE_PROVIDER

    def build(
        self,
        profile: TranslatorProfile,
        *,
        llm_profile_id: str | None,
    ) -> TextTranslationProvider:
        if profile is not TranslatorProfile.AZURE_NMT or llm_profile_id is not None:
            raise ValueError("unexpected smoke provider profile")
        return self.provider


_SMOKE_PROVIDER = DeterministicSmokeProvider()


def _create_source_pdf(path: Path) -> None:
    document = pymupdf.open()
    try:
        page = document.new_page(width=595, height=842)
        page.draw_rect(pymupdf.Rect(60, 60, 535, 155), color=(0, 0, 0), width=0.8)
        inserted = page.insert_textbox(
            pymupdf.Rect(78, 85, 515, 135),
            _SOURCE_TEXT,
            fontname="helv",
            fontsize=13,
            lineheight=1.25,
        )
        if inserted < 0:
            raise RuntimeError("fixture text did not fit its source box")
        document.set_metadata(
            {
                "title": "All_to_PDF engine smoke fixture",
                "producer": "All_to_PDF deterministic smoke",
            }
        )
        document.save(path)
    finally:
        document.close()


def _inspect_pdf(path: Path) -> dict[str, Any]:
    document = pymupdf.open(path)
    try:
        text = "\n".join(page.get_text("text") for page in document)
        drawings = sum(len(page.get_drawings()) for page in document)
        return {
            "page_count": document.page_count,
            "text": text.strip(),
            "drawing_count": drawings,
        }
    finally:
        document.close()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _run(output_directory: Path) -> dict[str, Any]:
    workspace = output_directory / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    source_path = output_directory / "source.pdf"
    output_path = output_directory / "translated.pdf"
    _create_source_pdf(source_path)

    bridge.TranslationProviderFactory = SmokeProviderFactory
    emitted: list[dict[str, Any]] = []
    original_emit = bridge._emit
    bridge._emit = emitted.append
    started = time.perf_counter()
    try:
        await bridge._translate(
            bridge.BridgeRequest(
                workspace=workspace,
                input_path=source_path,
                output_path=output_path,
                source_language="en",
                target_language="vi",
                translator_profile=TranslatorProfile.AZURE_NMT,
                llm_profile_id=None,
            )
        )
    finally:
        bridge._emit = original_emit
    duration_seconds = time.perf_counter() - started

    source = _inspect_pdf(source_path)
    output = _inspect_pdf(output_path)
    if source["page_count"] != output["page_count"]:
        raise AssertionError("page count changed during engine smoke translation")
    output_text = str(output["text"])
    if "Xin chào thế giới" not in output_text or "giữ nguyên bố cục" not in output_text:
        raise AssertionError(f"Vietnamese target text was not found: {output_text!r}")
    if _SMOKE_PROVIDER.call_count < 1:
        raise AssertionError("BabelDOC never called the deterministic provider")
    finish_events = [event for event in emitted if event.get("type") == "finish"]
    if len(finish_events) != 1:
        raise AssertionError("engine bridge did not emit exactly one finish event")

    return {
        "status": "passed",
        "duration_seconds": round(duration_seconds, 3),
        "babeldoc_commit": bridge.BABELDOC_COMMIT,
        "pdfmathtranslate_next_commit": bridge.PDFMATH_TRANSLATE_NEXT_COMMIT,
        "provider_id": _SMOKE_PROVIDER.provider_id,
        "provider_calls": _SMOKE_PROVIDER.call_count,
        "source": {
            "path": source_path.name,
            "sha256": _sha256(source_path),
            "page_count": source["page_count"],
            "drawing_count": source["drawing_count"],
            "text": source["text"],
        },
        "output": {
            "path": output_path.name,
            "sha256": _sha256(output_path),
            "page_count": output["page_count"],
            "drawing_count": output["drawing_count"],
            "text": output["text"],
        },
        "events": emitted,
        "expected_text": _EXPECTED_TEXT,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("artifacts/engine-smoke"),
    )
    args = parser.parse_args()
    output_directory = args.output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    report_path = output_directory / "report.json"
    try:
        report = asyncio.run(_run(output_directory))
    except Exception as exc:
        report = {
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "babeldoc_commit": bridge.BABELDOC_COMMIT,
            "pdfmathtranslate_next_commit": bridge.PDFMATH_TRANSLATE_NEXT_COMMIT,
        }
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        raise
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
