from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from all_to_pdf.application.engine import ReviewRequiredError
from all_to_pdf.infrastructure.quality.basic import BasicPdfQualityGate

_VALID_PDF = b"%PDF-1.4\ntrailer<<>>\n%%EOF\n"


async def _write(path: Path, content: bytes) -> None:
    await asyncio.to_thread(path.write_bytes, content)


async def test_basic_quality_gate_accepts_structural_pdf(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    output = tmp_path / "output.pdf"
    await _write(source, _VALID_PDF)
    await _write(output, _VALID_PDF)

    await BasicPdfQualityGate().validate(source, output)


@pytest.mark.parametrize(
    ("source_content", "output_content", "expected_code"),
    [
        (None, _VALID_PDF, "NEEDS_REVIEW"),
        (_VALID_PDF, None, "NEEDS_REVIEW"),
        (_VALID_PDF, b"%PDF-", "OUTPUT_PDF_TOO_SMALL"),
        (_VALID_PDF, b"NOTPDF but long enough %%EOF", "OUTPUT_INVALID_PDF_SIGNATURE"),
        (_VALID_PDF, b"%PDF-1.4 without an eof marker", "OUTPUT_PDF_EOF_MISSING"),
    ],
)
async def test_basic_quality_gate_rejects_invalid_artifacts(
    tmp_path: Path,
    source_content: bytes | None,
    output_content: bytes | None,
    expected_code: str,
) -> None:
    source = tmp_path / "source.pdf"
    output = tmp_path / "output.pdf"
    if source_content is not None:
        await _write(source, source_content)
    if output_content is not None:
        await _write(output, output_content)

    with pytest.raises(ReviewRequiredError) as captured:
        await BasicPdfQualityGate().validate(source, output)

    assert captured.value.code == expected_code
