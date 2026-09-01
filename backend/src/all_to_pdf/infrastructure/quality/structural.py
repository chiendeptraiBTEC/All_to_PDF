"""Structural/readability gate run before translated PDF publication."""

from __future__ import annotations

import asyncio
import importlib
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from all_to_pdf.application.engine import ReviewRequiredError
from all_to_pdf.infrastructure.quality.basic import BasicPdfQualityGate


@dataclass(frozen=True, slots=True)
class PageMetrics:
    mediabox: tuple[float, float, float, float]
    cropbox: tuple[float, float, float, float]
    rotation: int
    text_characters: int
    image_count: int
    drawing_count: int
    median_font_size: float | None


class StructuralPdfQualityGate:
    """Block publication when geometry, object inventory, or readability regresses."""

    def __init__(
        self,
        *,
        minimum_readable_scale: float = 0.62,
        geometry_tolerance_points: float = 0.5,
    ) -> None:
        if not 0.1 < minimum_readable_scale <= 1.0:
            raise ValueError("minimum_readable_scale must be in (0.1, 1.0]")
        self._minimum_readable_scale = minimum_readable_scale
        self._geometry_tolerance = geometry_tolerance_points
        self._basic = BasicPdfQualityGate()

    async def validate(self, source_path: Path, output_path: Path) -> None:
        await self._basic.validate(source_path, output_path)
        source, output = await asyncio.gather(
            asyncio.to_thread(self._inspect_sync, source_path),
            asyncio.to_thread(self._inspect_sync, output_path),
        )
        self._compare(source, output)

    def _compare(
        self,
        source: tuple[PageMetrics, ...],
        output: tuple[PageMetrics, ...],
    ) -> None:
        if len(source) != len(output):
            raise ReviewRequiredError(
                "output page count differs from source",
                code="OUTPUT_PAGE_COUNT_CHANGED",
            )
        for number, (before, after) in enumerate(zip(source, output, strict=True), start=1):
            self._compare_page(number, before, after)

    def _compare_page(self, number: int, source: PageMetrics, output: PageMetrics) -> None:
        if not self._boxes_close(source.mediabox, output.mediabox):
            self._raise(number, "MediaBox changed", "OUTPUT_MEDIABOX_CHANGED")
        if not self._boxes_close(source.cropbox, output.cropbox):
            self._raise(number, "CropBox changed", "OUTPUT_CROPBOX_CHANGED")
        if source.rotation != output.rotation:
            self._raise(number, "rotation changed", "OUTPUT_ROTATION_CHANGED")
        if source.text_characters > 0 and output.text_characters == 0:
            self._raise(number, "text layer disappeared", "OUTPUT_TEXT_LAYER_MISSING")
        if source.image_count != output.image_count:
            self._raise(number, "image inventory changed", "OUTPUT_IMAGE_COUNT_CHANGED")
        if source.drawing_count != output.drawing_count:
            self._raise(number, "vector inventory changed", "OUTPUT_VECTOR_COUNT_CHANGED")
        if source.median_font_size and output.median_font_size:
            scale = output.median_font_size / source.median_font_size
            if scale < self._minimum_readable_scale:
                self._raise(
                    number,
                    f"median text scale dropped to {scale:.3f}",
                    "OUTPUT_TEXT_TOO_SMALL",
                )

    def _boxes_close(
        self,
        left: tuple[float, float, float, float],
        right: tuple[float, float, float, float],
    ) -> bool:
        return all(abs(a - b) <= self._geometry_tolerance for a, b in zip(left, right, strict=True))

    @staticmethod
    def _raise(number: int, message: str, code: str) -> None:
        raise ReviewRequiredError(f"page {number}: {message}", code=code)

    @staticmethod
    def _inspect_sync(path: Path) -> tuple[PageMetrics, ...]:
        pymupdf = importlib.import_module("pymupdf")
        document = pymupdf.open(path)
        try:
            return tuple(StructuralPdfQualityGate._page_metrics(page) for page in document)
        finally:
            document.close()

    @staticmethod
    def _page_metrics(page: Any) -> PageMetrics:
        payload = page.get_text("dict")
        font_sizes: list[float] = []
        text_characters = 0
        for block in payload.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = str(span.get("text", ""))
                    text_characters += len(text.strip())
                    size = span.get("size")
                    if text.strip() and isinstance(size, (int, float)) and size > 0:
                        font_sizes.append(float(size))
        media = page.mediabox
        crop = page.cropbox
        return PageMetrics(
            mediabox=(float(media[0]), float(media[1]), float(media[2]), float(media[3])),
            cropbox=(float(crop[0]), float(crop[1]), float(crop[2]), float(crop[3])),
            rotation=int(page.rotation),
            text_characters=text_characters,
            image_count=len(page.get_images(full=True)),
            drawing_count=len(page.get_drawings()),
            median_font_size=statistics.median(font_sizes) if font_sizes else None,
        )
