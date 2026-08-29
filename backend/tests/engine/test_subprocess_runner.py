from __future__ import annotations

import sys
from pathlib import Path

import pytest

from all_to_pdf.engine.errors import (
    EngineCancelledError,
    EngineProcessError,
    EngineProtocolError,
    EngineTimeoutError,
)
from all_to_pdf.engine.models import EngineRequest, EngineStage
from all_to_pdf.engine.subprocess_runner import (
    SubprocessRunnerConfig,
    SubprocessTranslationRunner,
)


def _request(tmp_path: Path, *, timeout: float = 2.0) -> EngineRequest:
    source = tmp_path / "input.pdf"
    source.write_bytes(b"%PDF-1.4\n%%EOF\n")
    return EngineRequest(
        job_id="job-1",
        input_pdf=source,
        output_directory=tmp_path / "output",
        source_language="en",
        target_language="vi",
        translator_profile="deterministic_test",
        timeout_seconds=timeout,
    )


def _script(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "fake_engine.py"
    path.write_text(
        "import argparse, json, pathlib, shutil, sys, time\n"
        "parser=argparse.ArgumentParser(); parser.add_argument('--request'); "
        "args=parser.parse_args()\n"
        "request=json.loads(pathlib.Path(args.request).read_text())\n"
        + body,
        encoding="utf-8",
    )
    return path


def _runner(script: Path) -> SubprocessTranslationRunner:
    return SubprocessTranslationRunner(
        SubprocessRunnerConfig(
            command=(sys.executable, str(script)),
            poll_interval_seconds=0.01,
            terminate_grace_seconds=0.2,
        )
    )


def test_runner_returns_result_and_progress(tmp_path: Path) -> None:
    script = _script(
        tmp_path,
        "out=pathlib.Path(request['output_directory'])/'translated.pdf'\n"
        "out.parent.mkdir(parents=True, exist_ok=True); "
        "shutil.copyfile(request['input_pdf'], out)\n"
        "print(json.dumps({'version':1,'type':'progress','payload':"
        "{'stage':'translating','percent':50,'message':'half','page_number':1}}), "
        "flush=True)\n"
        "print(json.dumps({'version':1,'type':'result','payload':"
        "{'output_pdf':str(out),'elapsed_seconds':0.1,'engine_name':'fake',"
        "'engine_version':'1','report':{'pages':1}}}), flush=True)\n",
    )
    events = []

    result = _runner(script).run(_request(tmp_path), events.append, lambda: False)

    assert result.output_pdf.is_file()
    assert result.engine_name == "fake"
    assert [event.stage for event in events] == [EngineStage.TRANSLATING]


def test_runner_propagates_structured_error(tmp_path: Path) -> None:
    script = _script(
        tmp_path,
        "print(json.dumps({'version':1,'type':'error','payload':"
        "{'code':'PROVIDER_RATE_LIMITED','message':'slow down','retryable':True}}), "
        "flush=True)\n"
        "sys.exit(2)\n",
    )

    with pytest.raises(EngineProcessError) as raised:
        _runner(script).run(_request(tmp_path), lambda _: None, lambda: False)

    assert raised.value.code == "PROVIDER_RATE_LIMITED"
    assert raised.value.retryable is True


def test_runner_rejects_invalid_protocol(tmp_path: Path) -> None:
    script = _script(tmp_path, "print('not-json', flush=True)\n")

    with pytest.raises(EngineProtocolError):
        _runner(script).run(_request(tmp_path), lambda _: None, lambda: False)


def test_runner_times_out(tmp_path: Path) -> None:
    script = _script(tmp_path, "time.sleep(5)\n")

    with pytest.raises(EngineTimeoutError):
        _runner(script).run(
            _request(tmp_path, timeout=0.05),
            lambda _: None,
            lambda: False,
        )


def test_runner_honours_cancellation(tmp_path: Path) -> None:
    script = _script(tmp_path, "time.sleep(5)\n")
    probes = 0

    def is_cancelled() -> bool:
        nonlocal probes
        probes += 1
        return probes > 2

    with pytest.raises(EngineCancelledError):
        _runner(script).run(_request(tmp_path), lambda _: None, is_cancelled)


def test_runner_rejects_missing_input(tmp_path: Path) -> None:
    script = _script(tmp_path, "pass\n")
    request = _request(tmp_path)
    request.input_pdf.unlink()

    with pytest.raises(EngineProcessError) as raised:
        _runner(script).run(request, lambda _: None, lambda: False)

    assert raised.value.code == "INPUT_PDF_NOT_FOUND"


def test_runner_rejects_missing_reported_output(tmp_path: Path) -> None:
    script = _script(
        tmp_path,
        "out=pathlib.Path(request['output_directory'])/'missing.pdf'\n"
        "print(json.dumps({'version':1,'type':'result','payload':"
        "{'output_pdf':str(out),'elapsed_seconds':0,'engine_name':'fake',"
        "'engine_version':'1','report':{}}}), flush=True)\n",
    )

    with pytest.raises(EngineProtocolError):
        _runner(script).run(_request(tmp_path), lambda _: None, lambda: False)
