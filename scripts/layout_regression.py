#!/usr/bin/env python3
"""Run a deterministic multi-page layout regression through the real PDF engine."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

import pymupdf

from all_to_pdf.domain.job import TranslatorProfile
from all_to_pdf.domain.provider import TextTranslationProvider, TranslationResult
from all_to_pdf.engine import bridge

_REPLACEMENTS = (
    ("Executive summary", "Tóm tắt điều hành"),
    ("Left column", "Cột trái"),
    ("Right column", "Cột phải"),
    ("Revenue", "Doanh thu"),
    ("Cost", "Chi phí"),
    ("Formula caption", "Chú thích công thức"),
)
_EXPECTED = tuple(target for _, target in _REPLACEMENTS)


class RegressionProvider:
    provider_id = "deterministic_layout_regression"
    model_id = "deterministic-en-vi-v1"

    def __init__(self) -> None:
        self.calls = 0

    def translate(
        self,
        text: str,
        *,
        source_language: str,
        target_language: str,
    ) -> TranslationResult:
        if source_language != "en" or target_language != "vi":
            raise ValueError("layout regression supports only en-to-vi")
        self.calls += 1
        translated = text
        for source, target in _REPLACEMENTS:
            translated = translated.replace(source, target)
        return TranslationResult(
            translated_text=translated,
            provider_id=self.provider_id,
            model_id=self.model_id,
            input_units=len(text),
        )

    def close(self) -> None:
        return None


_PROVIDER = RegressionProvider()


class RegressionProviderFactory:
    def __init__(self, _settings: object) -> None:
        pass

    def build(
        self,
        profile: TranslatorProfile,
        *,
        llm_profile_id: str | None,
    ) -> TextTranslationProvider:
        if profile is not TranslatorProfile.AZURE_NMT or llm_profile_id is not None:
            raise ValueError("unexpected regression provider profile")
        return _PROVIDER


def _textbox(page: pymupdf.Page, rect: pymupdf.Rect, text: str, size: float = 11) -> None:
    remaining = page.insert_textbox(rect, text, fontname="helv", fontsize=size, lineheight=1.2)
    if remaining < 0:
        raise RuntimeError(f"fixture text did not fit: {text}")


def _create_fixture(path: Path) -> None:
    document = pymupdf.open()
    try:
        first = document.new_page(width=595, height=842)
        _textbox(first, pymupdf.Rect(55, 55, 540, 95), "Executive summary", 17)
        _textbox(
            first,
            pymupdf.Rect(55, 120, 280, 300),
            "Left column explains the operating model and service boundary.",
        )
        _textbox(
            first,
            pymupdf.Rect(315, 120, 540, 300),
            "Right column describes the quality gate and publishing policy.",
        )
        first.draw_line(pymupdf.Point(297, 110), pymupdf.Point(297, 320), width=0.7)

        second = document.new_page(width=595, height=842)
        table = pymupdf.Rect(80, 100, 515, 260)
        second.draw_rect(table, width=0.8)
        for y in (153, 206):
            second.draw_line(pymupdf.Point(80, y), pymupdf.Point(515, y), width=0.5)
        second.draw_line(pymupdf.Point(300, 100), pymupdf.Point(300, 260), width=0.5)
        _textbox(second, pymupdf.Rect(95, 113, 280, 145), "Revenue")
        _textbox(second, pymupdf.Rect(320, 113, 490, 145), "100")
        _textbox(second, pymupdf.Rect(95, 166, 280, 198), "Cost")
        _textbox(second, pymupdf.Rect(320, 166, 490, 198), "40")

        third = document.new_page(width=595, height=842)
        _textbox(third, pymupdf.Rect(70, 90, 525, 130), "Formula caption", 14)
        _textbox(third, pymupdf.Rect(70, 160, 525, 220), "E = mc²", 18)
        third.draw_rect(pymupdf.Rect(60, 70, 535, 240), width=0.8)
        document.save(path)
    finally:
        document.close()


def _inspect(path: Path) -> dict[str, Any]:
    document = pymupdf.open(path)
    try:
        return {
            "page_count": document.page_count,
            "pages": [
                {
                    "mediabox": [round(float(value), 3) for value in page.mediabox],
                    "cropbox": [round(float(value), 3) for value in page.cropbox],
                    "rotation": page.rotation,
                    "drawing_count": len(page.get_drawings()),
                    "text": " ".join(page.get_text("text").split()),
                }
                for page in document
            ],
        }
    finally:
        document.close()


def _validate(source: dict[str, Any], output: dict[str, Any]) -> None:
    if source["page_count"] != output["page_count"]:
        raise AssertionError("layout regression changed page count")
    for index, (before, after) in enumerate(
        zip(source["pages"], output["pages"], strict=True),
        start=1,
    ):
        for key in ("mediabox", "cropbox", "rotation", "drawing_count"):
            if before[key] != after[key]:
                raise AssertionError(f"page {index}: {key} changed")
    output_text = " ".join(str(page["text"]) for page in output["pages"])
    for marker in _EXPECTED:
        if marker not in output_text:
            raise AssertionError(f"missing translated regression marker: {marker}")
    if "E = mc" not in output_text:
        raise AssertionError("formula text was not preserved")


async def _run(directory: Path) -> dict[str, Any]:
    source_path = directory / "layout-source.pdf"
    output_path = directory / "layout-translated.pdf"
    workspace = directory / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    _create_fixture(source_path)
    bridge.TranslationProviderFactory = RegressionProviderFactory
    started = time.perf_counter()
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
    source = _inspect(source_path)
    output = _inspect(output_path)
    _validate(source, output)
    return {
        "status": "passed",
        "duration_seconds": round(time.perf_counter() - started, 3),
        "provider_calls": _PROVIDER.calls,
        "babeldoc_commit": bridge.BABELDOC_COMMIT,
        "pdfmathtranslate_next_commit": bridge.PDFMATH_TRANSLATE_NEXT_COMMIT,
        "source": source,
        "output": output,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("artifacts/layout-regression"),
    )
    args = parser.parse_args()
    directory = args.output_directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    report = asyncio.run(_run(directory))
    report_path = directory / "report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
