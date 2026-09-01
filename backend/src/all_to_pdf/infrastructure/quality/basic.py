"""Fast structural gate used before the full PDF quality engine is implemented."""

from __future__ import annotations

import asyncio
from pathlib import Path

from all_to_pdf.application.engine import ReviewRequiredError


class BasicPdfQualityGate:
    """Reject obviously incomplete output without pretending to prove layout quality."""

    async def validate(self, source_path: Path, output_path: Path) -> None:
        await asyncio.to_thread(self._validate_sync, source_path, output_path)

    @staticmethod
    def _validate_sync(source_path: Path, output_path: Path) -> None:
        if not source_path.is_file():
            raise ReviewRequiredError("source PDF disappeared before quality review")
        if not output_path.is_file():
            raise ReviewRequiredError("PDF engine did not create an output file")
        if output_path.stat().st_size < 12:
            raise ReviewRequiredError(
                "output PDF is unexpectedly small",
                code="OUTPUT_PDF_TOO_SMALL",
            )
        with output_path.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise ReviewRequiredError(
                    "output does not start with a PDF signature",
                    code="OUTPUT_INVALID_PDF_SIGNATURE",
                )
            stream.seek(max(0, output_path.stat().st_size - 4096))
            if b"%%EOF" not in stream.read():
                raise ReviewRequiredError(
                    "output PDF has no EOF marker in its final block",
                    code="OUTPUT_PDF_EOF_MISSING",
                )
