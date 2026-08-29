"""Versioned JSON Lines protocol for the isolated engine process."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping

from all_to_pdf.engine.errors import EngineProtocolError
from all_to_pdf.engine.models import EngineProgress, EngineResult

PROTOCOL_VERSION = 1


@dataclass(frozen=True, slots=True)
class EngineFailure:
    code: str
    message: str
    retryable: bool


@dataclass(frozen=True, slots=True)
class ParsedMessage:
    progress: EngineProgress | None = None
    result: EngineResult | None = None
    failure: EngineFailure | None = None


def progress_line(progress: EngineProgress) -> str:
    return _encode("progress", progress.to_payload())


def result_line(result: EngineResult) -> str:
    return _encode("result", result.to_payload())


def error_line(*, code: str, message: str, retryable: bool) -> str:
    return _encode(
        "error",
        {"code": code, "message": message, "retryable": retryable},
    )


def parse_line(line: str) -> ParsedMessage:
    try:
        decoded = json.loads(line)
    except json.JSONDecodeError as exc:
        raise EngineProtocolError("engine emitted invalid JSON") from exc
    if not isinstance(decoded, Mapping):
        raise EngineProtocolError("engine message must be a JSON object")

    version = decoded.get("version")
    if version != PROTOCOL_VERSION:
        raise EngineProtocolError(f"unsupported engine protocol version: {version!r}")
    message_type = decoded.get("type")
    payload = decoded.get("payload")
    if not isinstance(message_type, str) or not isinstance(payload, Mapping):
        raise EngineProtocolError("engine message requires string type and object payload")

    try:
        if message_type == "progress":
            return ParsedMessage(progress=EngineProgress.from_payload(payload))
        if message_type == "result":
            return ParsedMessage(result=EngineResult.from_payload(payload))
        if message_type == "error":
            code = payload.get("code")
            message = payload.get("message")
            retryable = payload.get("retryable")
            if not isinstance(code, str) or not isinstance(message, str):
                raise ValueError("error code and message must be strings")
            if not isinstance(retryable, bool):
                raise ValueError("error retryable must be boolean")
            return ParsedMessage(failure=EngineFailure(code, message, retryable))
    except (TypeError, ValueError) as exc:
        raise EngineProtocolError(f"invalid {message_type} payload: {exc}") from exc

    raise EngineProtocolError(f"unknown engine message type: {message_type}")


def _encode(message_type: str, payload: Mapping[str, object]) -> str:
    return json.dumps(
        {"version": PROTOCOL_VERSION, "type": message_type, "payload": dict(payload)},
        ensure_ascii=False,
        separators=(",", ":"),
    )
