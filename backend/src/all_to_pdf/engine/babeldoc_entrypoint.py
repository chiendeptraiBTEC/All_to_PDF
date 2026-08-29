"""Command-line boundary executed only by the PDF worker subprocess."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Mapping

from all_to_pdf.engine.babeldoc_driver import BabelDocDriver
from all_to_pdf.engine.errors import EngineError
from all_to_pdf.engine.models import EngineRequest
from all_to_pdf.engine.protocol import error_line, progress_line, result_line

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one isolated BabelDOC translation")
    parser.add_argument("--request", required=True, type=Path)
    arguments = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)

    try:
        payload = json.loads(arguments.request.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("request payload must be an object")
        request = EngineRequest.from_payload(payload)
        result = BabelDocDriver().run(
            request,
            emit=lambda progress: _emit(progress_line(progress)),
        )
        _emit(result_line(result))
        return 0
    except EngineError as exc:
        logger.exception("PDF engine failed")
        _emit(error_line(code=exc.code, message=str(exc), retryable=exc.retryable))
        return 2
    except Exception as exc:
        logger.exception("Unexpected PDF engine failure")
        _emit(
            error_line(
                code="ENGINE_UNEXPECTED_ERROR",
                message=str(exc),
                retryable=False,
            )
        )
        return 3


def _emit(line: str) -> None:
    print(line, flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
