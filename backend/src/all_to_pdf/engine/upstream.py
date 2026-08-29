"""Reviewed upstream versions used by the PDF engine image."""

from __future__ import annotations

import re
from dataclasses import dataclass

_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class UpstreamPin:
    name: str
    repository: str
    commit: str

    def __post_init__(self) -> None:
        if not self.repository.startswith("https://github.com/"):
            raise ValueError("upstream repository must be an HTTPS GitHub URL")
        if not _COMMIT_PATTERN.fullmatch(self.commit):
            raise ValueError("upstream commit must be a full lowercase SHA-1")


BABELDOC_PIN = UpstreamPin(
    name="BabelDOC",
    repository="https://github.com/funstory-ai/BabelDOC.git",
    commit="38d3896dcde9b5a940c62cf5563cadea673a64d3",
)

PDFMATH_TRANSLATE_NEXT_PIN = UpstreamPin(
    name="PDFMathTranslate-next",
    repository="https://github.com/PDFMathTranslate-next/PDFMathTranslate-next.git",
    commit="f8dffcf4c3a33b254391d43514439b975ce8d966",
)

ALL_UPSTREAM_PINS = (BABELDOC_PIN, PDFMATH_TRANSLATE_NEXT_PIN)
