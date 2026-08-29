from __future__ import annotations

import asyncio
import sys
import textwrap
from pathlib import Path

import pytest

from all_to_pdf.application.engine import (
    EngineProcessError,
    EngineProtocolError,
    EngineTimeoutError,
    EngineUnavailableError,
    ReviewRequiredError,
    TranslationEngineError,
    TranslationRunRequest,
)
from all_to_pdf.domain.job import JobStatus, TranslatorProfile
from all_to_pdf.infrastructure.runners.subprocess import BabelDocSubprocessRunner

_MINIMAL_PDF = b"%PDF-1.4\ntrailer<<>>\n%%EOF\n"


async def _request(tmp_path: Path) -> TranslationRunRequest:
    workspace = tmp_path / "workspace"
    await asyncio.to_thread(workspace.mkdir)
    source = workspace / "source.pdf"
    await asyncio.to_thread(source.write_bytes, _MINIMAL_PDF)
    return TranslationRunRequest(
        input_path=source,
        output_path=workspace / "output.pdf",
        workspace=workspace,
        source_language="en",
        target_language="vi",
        translator_profile=TranslatorProfile.AZURE_NMT,
        llm_profile_id=None,
    )


async def _script(tmp_path: Path, source: str) -> Path:
    script = tmp_path / "engine.py"
    await asyncio.to_thread(script.write_text, textwrap.dedent(source), encoding="utf-8")
    return script


async def _ignore(_event: object) -> None:
    pass


@pytest.mark.parametrize(
    "source",
    [
        """\
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--request")
        parser.parse_args()
        """,
        """\
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--request")
        parser.parse_args()
        print("not-json", flush=True)
        """,
    ],
)
async def test_runner_rejects_missing_finish_or_non_json(
    tmp_path: Path,
    source: str,
) -> None:
    script = await _script(tmp_path, source)
    request = await _request(tmp_path)
    runner = BabelDocSubprocessRunner(command=(sys.executable, str(script)), timeout_seconds=5)

    with pytest.raises(EngineProtocolError):
        await runner.run(request, _ignore)


async def test_runner_maps_nonzero_exit_and_stderr(tmp_path: Path) -> None:
    script = await _script(
        tmp_path,
        """\
        import argparse
        import sys
        parser = argparse.ArgumentParser()
        parser.add_argument("--request")
        parser.parse_args()
        print("engine boom", file=sys.stderr)
        raise SystemExit(3)
        """,
    )
    request = await _request(tmp_path)
    runner = BabelDocSubprocessRunner(command=(sys.executable, str(script)), timeout_seconds=5)

    with pytest.raises(EngineProcessError, match="engine boom"):
        await runner.run(request, _ignore)


async def test_runner_rejects_finish_for_unexpected_path(tmp_path: Path) -> None:
    script = await _script(
        tmp_path,
        """\
        import argparse
        import json
        parser = argparse.ArgumentParser()
        parser.add_argument("--request")
        args = parser.parse_args()
        with open(args.request, encoding="utf-8") as stream:
            request = json.load(stream)
        print(
            json.dumps(
                {
                    "type": "finish",
                    "output_path": request["input_path"],
                    "engine_name": "fake",
                    "engine_version": "1",
                }
            ),
            flush=True,
        )
        """,
    )
    request = await _request(tmp_path)
    runner = BabelDocSubprocessRunner(command=(sys.executable, str(script)), timeout_seconds=5)

    with pytest.raises(EngineProtocolError, match="unexpected output path"):
        await runner.run(request, _ignore)


async def test_runner_terminates_timed_out_process(tmp_path: Path) -> None:
    script = await _script(
        tmp_path,
        """\
        import argparse
        import time
        parser = argparse.ArgumentParser()
        parser.add_argument("--request")
        parser.parse_args()
        time.sleep(5)
        """,
    )
    request = await _request(tmp_path)
    runner = BabelDocSubprocessRunner(command=(sys.executable, str(script)), timeout_seconds=0.05)

    with pytest.raises(EngineTimeoutError):
        await runner.run(request, _ignore)


@pytest.mark.parametrize(
    ("event", "expected_type"),
    [
        ({"code": "NEEDS_REVIEW", "message": "review"}, ReviewRequiredError),
        (
            {"code": "ENGINE_DEPENDENCY_MISSING", "message": "missing"},
            EngineUnavailableError,
        ),
        (
            {"code": "CUSTOM", "message": "custom", "retryable": True},
            TranslationEngineError,
        ),
    ],
)
def test_runner_maps_reported_error_types(
    event: dict[str, object],
    expected_type: type[TranslationEngineError],
) -> None:
    error = BabelDocSubprocessRunner._parse_reported_error(event)
    assert isinstance(error, expected_type)


@pytest.mark.parametrize(
    "event",
    [
        {},
        {"status": "quality_check", "percent": 50, "stage": "bad"},
        {"status": "parsing", "percent": 101, "stage": "bad"},
        {"status": "parsing", "percent": 20, "stage": ""},
    ],
)
def test_runner_rejects_malformed_progress(event: dict[str, object]) -> None:
    with pytest.raises(EngineProtocolError):
        BabelDocSubprocessRunner._parse_progress(event)


def test_runner_accepts_well_formed_progress() -> None:
    progress = BabelDocSubprocessRunner._parse_progress(
        {"status": "translating", "percent": 45, "stage": "Translate Paragraphs"}
    )
    assert progress.status is JobStatus.TRANSLATING
    assert progress.percent == 45
