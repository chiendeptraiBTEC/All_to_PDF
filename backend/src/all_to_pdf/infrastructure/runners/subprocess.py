"""JSONL subprocess adapter for the pinned BabelDOC engine bridge."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from all_to_pdf.application.engine import (
    EngineProcessError,
    EngineProgress,
    EngineProtocolError,
    EngineTimeoutError,
    EngineUnavailableError,
    OcrRequiredError,
    ProgressCallback,
    ReviewRequiredError,
    TranslationEngineError,
    TranslationRunRequest,
    TranslationRunResult,
)
from all_to_pdf.domain.job import JobStatus

_ALLOWED_PROGRESS_STATUSES = frozenset(
    {
        JobStatus.PARSING,
        JobStatus.TRANSLATING,
        JobStatus.TYPESETTING,
        JobStatus.GENERATING_PDF,
    }
)


class BabelDocSubprocessRunner:
    def __init__(
        self,
        *,
        command: Sequence[str] | None = None,
        timeout_seconds: float = 30 * 60,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self._command = tuple(
            command or (sys.executable, "-m", "all_to_pdf.engine.bridge")
        )
        self._timeout_seconds = timeout_seconds
        self._environment = dict(environment or {})

    async def run(
        self,
        request: TranslationRunRequest,
        on_progress: ProgressCallback,
    ) -> TranslationRunResult:
        await asyncio.to_thread(request.workspace.mkdir, parents=True, exist_ok=True)
        workspace, input_path, output_path = await asyncio.to_thread(
            self._resolve_request_paths,
            request,
        )
        manifest_path = workspace / "engine-request.json"
        payload = {
            "schema_version": 1,
            "workspace": str(workspace),
            "input_path": str(input_path),
            "output_path": str(output_path),
            "source_language": request.source_language,
            "target_language": request.target_language,
            "translator_profile": request.translator_profile.value,
            "llm_profile_id": request.llm_profile_id,
        }
        await asyncio.to_thread(
            manifest_path.write_text,
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        environment = os.environ.copy()
        environment.update(self._environment)
        process = await asyncio.create_subprocess_exec(
            *self._command,
            "--request",
            str(manifest_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=environment,
        )
        try:
            return await asyncio.wait_for(
                self._consume_process(process, request, on_progress),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            await self._stop_process(process)
            raise EngineTimeoutError(
                f"PDF engine exceeded {self._timeout_seconds:g} seconds"
            ) from exc
        except BaseException:
            await self._stop_process(process)
            raise

    async def _consume_process(
        self,
        process: asyncio.subprocess.Process,
        request: TranslationRunRequest,
        on_progress: ProgressCallback,
    ) -> TranslationRunResult:
        if process.stdout is None or process.stderr is None:
            raise EngineProtocolError("engine process streams were not created")
        stderr_task = asyncio.create_task(process.stderr.read())
        finish_payload: dict[str, Any] | None = None
        reported_error: TranslationEngineError | None = None

        while line := await process.stdout.readline():
            try:
                event: dict[str, Any] = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise EngineProtocolError("engine emitted a non-JSONL stdout record") from exc
            event_type = event.get("type")
            if event_type == "progress":
                await on_progress(self._parse_progress(event))
            elif event_type == "finish":
                finish_payload = event
            elif event_type == "error":
                reported_error = self._parse_reported_error(event)
            else:
                raise EngineProtocolError(f"unknown engine event type: {event_type!r}")

        return_code = await process.wait()
        stderr = (await stderr_task).decode("utf-8", errors="replace").strip()
        if reported_error is not None:
            raise reported_error
        if return_code != 0:
            detail = stderr[-1000:] if stderr else "no stderr detail"
            raise EngineProcessError(
                f"PDF engine exited with code {return_code}: {detail}"
            )
        if finish_payload is None:
            raise EngineProtocolError("engine exited successfully without a finish event")

        output_path, expected_path, output_exists = await asyncio.to_thread(
            self._resolve_and_check_output,
            finish_payload,
            request,
        )
        if output_path != expected_path:
            raise EngineProtocolError("engine finish event referenced an unexpected output path")
        if not output_exists:
            raise EngineProtocolError("engine finish event referenced a missing output file")
        return TranslationRunResult(
            output_path=output_path,
            engine_name=str(finish_payload.get("engine_name", "BabelDOC")),
            engine_version=str(finish_payload.get("engine_version", "unknown")),
        )

    @staticmethod
    def _resolve_request_paths(request: TranslationRunRequest) -> tuple[Path, Path, Path]:
        return (
            request.workspace.resolve(),
            request.input_path.resolve(),
            request.output_path.resolve(),
        )

    @staticmethod
    def _resolve_and_check_output(
        finish_payload: Mapping[str, Any],
        request: TranslationRunRequest,
    ) -> tuple[Path, Path, bool]:
        output_path = Path(str(finish_payload.get("output_path", ""))).resolve()
        expected_path = request.output_path.resolve()
        return output_path, expected_path, output_path.is_file()

    @staticmethod
    def _parse_progress(event: Mapping[str, Any]) -> EngineProgress:
        try:
            status = JobStatus(str(event["status"]))
            percent = float(event["percent"])
            stage = str(event["stage"])
        except (KeyError, TypeError, ValueError) as exc:
            raise EngineProtocolError("engine progress event is malformed") from exc
        if status not in _ALLOWED_PROGRESS_STATUSES:
            raise EngineProtocolError(f"engine progress status is not allowed: {status}")
        if not 0.0 <= percent <= 100.0 or not stage.strip():
            raise EngineProtocolError("engine progress values are invalid")
        return EngineProgress(status=status, percent=percent, stage=stage.strip())

    @staticmethod
    def _parse_reported_error(event: Mapping[str, Any]) -> TranslationEngineError:
        code = str(event.get("code", "ENGINE_ERROR"))
        message = str(event.get("message", "PDF engine reported an error"))
        retryable = bool(event.get("retryable", False))
        if code == "OCR_REQUIRED":
            return OcrRequiredError(message)
        if code == "NEEDS_REVIEW":
            return ReviewRequiredError(message)
        if code == "ENGINE_DEPENDENCY_MISSING":
            return EngineUnavailableError(message)
        return TranslationEngineError(message, code=code, retryable=retryable)

    @staticmethod
    async def _stop_process(process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except TimeoutError:
            process.kill()
            await process.wait()
