from __future__ import annotations

import asyncio
import sys
import textwrap
from pathlib import Path

import pytest

from all_to_pdf.application.engine import OcrRequiredError, TranslationRunRequest
from all_to_pdf.domain.job import JobStatus, TranslatorProfile
from all_to_pdf.infrastructure.runners.subprocess import BabelDocSubprocessRunner

_MINIMAL_PDF = b"%PDF-1.4\ntrailer<<>>\n%%EOF\n"


async def _write_script(path: Path, content: str) -> None:
    await asyncio.to_thread(path.write_text, content, encoding="utf-8")


async def test_subprocess_runner_consumes_jsonl_and_validates_output(tmp_path: Path) -> None:
    script = tmp_path / "fake_engine.py"
    await _write_script(
        script,
        textwrap.dedent(
            """\
            import argparse
            import json
            import shutil

            parser = argparse.ArgumentParser()
            parser.add_argument("--request")
            args = parser.parse_args()
            with open(args.request, encoding="utf-8") as stream:
                request = json.load(stream)
            print(
                json.dumps(
                    {
                        "type": "progress",
                        "status": "parsing",
                        "percent": 20,
                        "stage": "parse",
                    }
                ),
                flush=True,
            )
            shutil.copyfile(request["input_path"], request["output_path"])
            print(
                json.dumps(
                    {
                        "type": "finish",
                        "output_path": request["output_path"],
                        "engine_name": "fake",
                        "engine_version": "1",
                    }
                ),
                flush=True,
            )
            """
        ),
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    input_path = workspace / "source.pdf"
    await asyncio.to_thread(input_path.write_bytes, _MINIMAL_PDF)
    request = TranslationRunRequest(
        input_path=input_path,
        output_path=workspace / "translated.pdf",
        workspace=workspace,
        source_language="en",
        target_language="vi",
        translator_profile=TranslatorProfile.AZURE_NMT,
        llm_profile_id=None,
    )
    events: list[JobStatus] = []
    runner = BabelDocSubprocessRunner(command=(sys.executable, str(script)), timeout_seconds=10)

    result = await runner.run(request, lambda event: _collect(events, event.status))

    assert events == [JobStatus.PARSING]
    assert await asyncio.to_thread(result.output_path.read_bytes) == _MINIMAL_PDF
    assert result.engine_name == "fake"


async def test_subprocess_runner_maps_reported_ocr_error(tmp_path: Path) -> None:
    script = tmp_path / "error_engine.py"
    await _write_script(
        script,
        textwrap.dedent(
            """\
            import argparse
            import json

            parser = argparse.ArgumentParser()
            parser.add_argument("--request")
            parser.parse_args()
            print(
                json.dumps(
                    {
                        "type": "error",
                        "code": "OCR_REQUIRED",
                        "message": "scan",
                        "retryable": False,
                    }
                ),
                flush=True,
            )
            raise SystemExit(20)
            """
        ),
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    input_path = workspace / "source.pdf"
    await asyncio.to_thread(input_path.write_bytes, _MINIMAL_PDF)
    request = TranslationRunRequest(
        input_path=input_path,
        output_path=workspace / "translated.pdf",
        workspace=workspace,
        source_language="en",
        target_language="vi",
        translator_profile=TranslatorProfile.AZURE_NMT,
        llm_profile_id=None,
    )
    runner = BabelDocSubprocessRunner(command=(sys.executable, str(script)), timeout_seconds=10)

    with pytest.raises(OcrRequiredError):
        await runner.run(request, _ignore_progress)


async def _collect(events: list[JobStatus], status: JobStatus) -> None:
    events.append(status)


async def _ignore_progress(event: object) -> None:
    del event
