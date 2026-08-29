"""Structured failures crossing the engine/application boundary."""

from __future__ import annotations


class EngineError(RuntimeError):
    """Base class for translation engine failures."""

    def __init__(self, message: str, *, code: str, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class EngineProtocolError(EngineError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="ENGINE_PROTOCOL_ERROR", retryable=False)


class EngineProcessError(EngineError):
    def __init__(self, message: str, *, code: str = "ENGINE_PROCESS_ERROR") -> None:
        super().__init__(message, code=code, retryable=True)


class EngineTimeoutError(EngineError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="ENGINE_TIMEOUT", retryable=True)


class EngineCancelledError(EngineError):
    def __init__(self, message: str = "translation was cancelled") -> None:
        super().__init__(message, code="ENGINE_CANCELLED", retryable=False)
