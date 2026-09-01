"""Subprocess implementation of the translation runner port."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import tempfile
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from all_to_pdf.engine.errors import (
    EngineCancelledError,
    EngineProcessError,
    EngineProtocolError,
    EngineTimeoutError,
)
from all_to_pdf.engine.models import EngineRequest, EngineResult
from all_to_pdf.engine.ports import CancellationProbe, ProgressCallback
from all_to_pdf.engine.protocol import parse_line

_STREAM_CLOSED = object()
_MAX_DIAGNOSTIC_CHARS = 16_000


@dataclass(frozen=True, slots=True)
class SubprocessRunnerConfig:
    """Immutable process policy for one worker image."""

    command: Sequence[str]
    poll_interval_seconds: float = 0.05
    terminate_grace_seconds: float = 3.0
    environment: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if not self.command:
            raise ValueError("engine command must not be empty")
        if self.poll_interval_seconds <= 0:
            raise ValueError("poll interval must be greater than zero")
        if self.terminate_grace_seconds <= 0:
            raise ValueError("terminate grace must be greater than zero")


class SubprocessTranslationRunner:
    """Runs the heavy PDF engine in a replaceable child process.

    The child writes versioned JSON Lines to stdout. Stderr is diagnostic only and
    is capped before inclusion in errors so a broken engine cannot exhaust memory.
    """

    def __init__(self, config: SubprocessRunnerConfig) -> None:
        self._config = config

    def run(
        self,
        request: EngineRequest,
        on_progress: ProgressCallback,
        is_cancelled: CancellationProbe,
    ) -> EngineResult:
        request.output_directory.mkdir(parents=True, exist_ok=True)
        if not request.input_pdf.is_file():
            raise EngineProcessError(
                f"input PDF does not exist: {request.input_pdf}",
                code="INPUT_PDF_NOT_FOUND",
            )

        with tempfile.TemporaryDirectory(prefix=f"all-to-pdf-{request.job_id}-") as temp_dir:
            request_path = Path(temp_dir) / "request.json"
            request_path.write_text(
                json.dumps(request.to_payload(), ensure_ascii=False),
                encoding="utf-8",
            )
            return self._run_process(request, request_path, on_progress, is_cancelled)

    def _run_process(
        self,
        request: EngineRequest,
        request_path: Path,
        on_progress: ProgressCallback,
        is_cancelled: CancellationProbe,
    ) -> EngineResult:
        environment = os.environ.copy()
        if self._config.environment:
            environment.update(self._config.environment)

        process = subprocess.Popen(
            [*self._config.command, "--request", str(request_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=environment,
            start_new_session=os.name != "nt",
        )
        if process.stdout is None or process.stderr is None:
            self._terminate(process)
            raise EngineProcessError("failed to capture engine process streams")

        stdout_queue: queue.Queue[str | object] = queue.Queue()
        stderr_queue: queue.Queue[str | object] = queue.Queue()
        stdout_thread = _start_reader(process.stdout, stdout_queue)
        stderr_thread = _start_reader(process.stderr, stderr_queue)

        started_at = time.monotonic()
        result: EngineResult | None = None
        failure: EngineProcessError | None = None
        stdout_closed = False

        try:
            while True:
                if is_cancelled():
                    self._terminate(process)
                    raise EngineCancelledError()
                if time.monotonic() - started_at > request.timeout_seconds:
                    self._terminate(process)
                    raise EngineTimeoutError(
                        f"engine exceeded {request.timeout_seconds:.1f} seconds"
                    )

                stdout_closed, result, failure = self._drain_stdout(
                    stdout_queue,
                    stdout_closed=stdout_closed,
                    current_result=result,
                    current_failure=failure,
                    on_progress=on_progress,
                )
                if process.poll() is not None and stdout_closed:
                    break
                time.sleep(self._config.poll_interval_seconds)
        except BaseException:
            if process.poll() is None:
                self._terminate(process)
            raise
        finally:
            stdout_thread.join(timeout=self._config.terminate_grace_seconds)
            stderr_thread.join(timeout=self._config.terminate_grace_seconds)

        diagnostics = _collect_diagnostics(stderr_queue)
        return_code = process.returncode
        if failure is not None:
            if diagnostics:
                failure.add_note(diagnostics)
            raise failure
        if return_code != 0:
            detail = f"engine exited with code {return_code}"
            if diagnostics:
                detail = f"{detail}: {diagnostics}"
            raise EngineProcessError(detail)
        if result is None:
            detail = "engine exited without a result message"
            if diagnostics:
                detail = f"{detail}: {diagnostics}"
            raise EngineProtocolError(detail)
        if not result.output_pdf.is_file():
            raise EngineProtocolError(f"engine reported a missing output PDF: {result.output_pdf}")
        return result

    def _drain_stdout(
        self,
        messages: queue.Queue[str | object],
        *,
        stdout_closed: bool,
        current_result: EngineResult | None,
        current_failure: EngineProcessError | None,
        on_progress: ProgressCallback,
    ) -> tuple[bool, EngineResult | None, EngineProcessError | None]:
        result = current_result
        failure = current_failure
        while True:
            try:
                line = messages.get_nowait()
            except queue.Empty:
                return stdout_closed, result, failure
            if line is _STREAM_CLOSED:
                stdout_closed = True
                continue
            if not isinstance(line, str):
                raise EngineProtocolError("unexpected engine stream item")
            stripped = line.strip()
            if not stripped:
                continue
            parsed = parse_line(stripped)
            if parsed.progress is not None:
                on_progress(parsed.progress)
            elif parsed.result is not None:
                if result is not None:
                    raise EngineProtocolError("engine emitted more than one result")
                result = parsed.result
            elif parsed.failure is not None:
                failure = EngineProcessError(
                    parsed.failure.message,
                    code=parsed.failure.code,
                )
                failure.retryable = parsed.failure.retryable

    def _terminate(self, process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=self._config.terminate_grace_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=self._config.terminate_grace_seconds)


def _start_reader(stream: TextIO, target: queue.Queue[str | object]) -> threading.Thread:
    def read_stream() -> None:
        try:
            for line in stream:
                target.put(line)
        finally:
            target.put(_STREAM_CLOSED)
            stream.close()

    thread = threading.Thread(target=read_stream, daemon=True)
    thread.start()
    return thread


def _collect_diagnostics(messages: queue.Queue[str | object]) -> str:
    chunks: list[str] = []
    current_length = 0
    while True:
        try:
            item = messages.get_nowait()
        except queue.Empty:
            break
        if item is _STREAM_CLOSED or not isinstance(item, str):
            continue
        remaining = _MAX_DIAGNOSTIC_CHARS - current_length
        if remaining <= 0:
            break
        chunks.append(item[:remaining])
        current_length += min(len(item), remaining)
    return "".join(chunks).strip()
