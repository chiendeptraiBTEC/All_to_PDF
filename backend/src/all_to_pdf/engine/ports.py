"""Ports used by application code to run a PDF translation engine."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from all_to_pdf.engine.models import EngineProgress, EngineRequest, EngineResult

ProgressCallback = Callable[[EngineProgress], None]
CancellationProbe = Callable[[], bool]


class TranslationRunner(Protocol):
    """Runs one request and returns only after a validated output is available."""

    def run(
        self,
        request: EngineRequest,
        on_progress: ProgressCallback,
        is_cancelled: CancellationProbe,
    ) -> EngineResult: ...
