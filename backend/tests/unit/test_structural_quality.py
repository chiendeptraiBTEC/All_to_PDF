from dataclasses import replace

import pytest

from all_to_pdf.application.engine import ReviewRequiredError
from all_to_pdf.infrastructure.quality.structural import (
    PageMetrics,
    StructuralPdfQualityGate,
)

_BASE = PageMetrics(
    mediabox=(0.0, 0.0, 595.0, 842.0),
    cropbox=(0.0, 0.0, 595.0, 842.0),
    rotation=0,
    text_characters=200,
    image_count=1,
    drawing_count=4,
    median_font_size=12.0,
)


def test_structural_gate_accepts_readable_text_and_small_geometry_noise() -> None:
    gate = StructuralPdfQualityGate(minimum_readable_scale=0.62)
    output = replace(_BASE, mediabox=(0.1, 0.0, 595.2, 842.0), median_font_size=8.0)
    gate._compare((_BASE,), (output,))


@pytest.mark.parametrize(
    ("output", "code"),
    [
        (replace(_BASE, rotation=90), "OUTPUT_ROTATION_CHANGED"),
        (replace(_BASE, text_characters=0), "OUTPUT_TEXT_LAYER_MISSING"),
        (replace(_BASE, image_count=0), "OUTPUT_IMAGE_COUNT_CHANGED"),
        (replace(_BASE, drawing_count=3), "OUTPUT_VECTOR_COUNT_CHANGED"),
        (replace(_BASE, median_font_size=6.0), "OUTPUT_TEXT_TOO_SMALL"),
    ],
)
def test_structural_gate_blocks_material_regression(output: PageMetrics, code: str) -> None:
    gate = StructuralPdfQualityGate(minimum_readable_scale=0.62)
    with pytest.raises(ReviewRequiredError) as captured:
        gate._compare((_BASE,), (output,))
    assert captured.value.code == code


def test_structural_gate_blocks_page_count_change() -> None:
    gate = StructuralPdfQualityGate()
    with pytest.raises(ReviewRequiredError) as captured:
        gate._compare((_BASE,), (_BASE, _BASE))
    assert captured.value.code == "OUTPUT_PAGE_COUNT_CHANGED"
