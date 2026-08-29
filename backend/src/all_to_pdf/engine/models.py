"""Typed messages exchanged with the isolated PDF engine process."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Mapping


class EngineStage(StrEnum):
    """Stable stage names understood by the application and the UI."""

    STARTING = "starting"
    PREFLIGHT = "preflight"
    PARSING = "parsing"
    LAYOUT = "layout"
    TRANSLATING = "translating"
    TYPESETTING = "typesetting"
    GENERATING_PDF = "generating_pdf"
    QUALITY_CHECK = "quality_check"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class EngineRequest:
    """Everything the engine needs to translate one immutable input artifact."""

    job_id: str
    input_pdf: Path
    output_directory: Path
    source_language: str
    target_language: str
    translator_profile: str
    llm_profile_id: str | None = None
    allow_paid_fallback: bool = False
    timeout_seconds: float = 1800.0
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.job_id.strip():
            raise ValueError("job_id must not be blank")
        if not self.source_language.strip() or not self.target_language.strip():
            raise ValueError("source and target languages are required")
        if self.source_language.casefold() == self.target_language.casefold():
            raise ValueError("source and target languages must be different")
        if not self.translator_profile.strip():
            raise ValueError("translator_profile must not be blank")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")

    def to_payload(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "input_pdf": str(self.input_pdf),
            "output_directory": str(self.output_directory),
            "source_language": self.source_language,
            "target_language": self.target_language,
            "translator_profile": self.translator_profile,
            "llm_profile_id": self.llm_profile_id,
            "allow_paid_fallback": self.allow_paid_fallback,
            "timeout_seconds": self.timeout_seconds,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> EngineRequest:
        metadata_value = payload.get("metadata", {})
        if not isinstance(metadata_value, Mapping):
            raise ValueError("metadata must be an object")
        metadata: dict[str, str] = {}
        for key, value in metadata_value.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("metadata keys and values must be strings")
            metadata[key] = value

        return cls(
            job_id=_required_string(payload, "job_id"),
            input_pdf=Path(_required_string(payload, "input_pdf")),
            output_directory=Path(_required_string(payload, "output_directory")),
            source_language=_required_string(payload, "source_language"),
            target_language=_required_string(payload, "target_language"),
            translator_profile=_required_string(payload, "translator_profile"),
            llm_profile_id=_optional_string(payload, "llm_profile_id"),
            allow_paid_fallback=_optional_bool(payload, "allow_paid_fallback", False),
            timeout_seconds=_optional_float(payload, "timeout_seconds", 1800.0),
            metadata=metadata,
        )


@dataclass(frozen=True, slots=True)
class EngineProgress:
    """A monotonic progress event emitted by the engine."""

    stage: EngineStage
    percent: float
    message: str
    page_number: int | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.percent <= 100.0:
            raise ValueError("percent must be between 0 and 100")
        if self.page_number is not None and self.page_number < 1:
            raise ValueError("page_number must be positive")

    def to_payload(self) -> dict[str, object]:
        return {
            "stage": self.stage.value,
            "percent": self.percent,
            "message": self.message,
            "page_number": self.page_number,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> EngineProgress:
        return cls(
            stage=EngineStage(_required_string(payload, "stage")),
            percent=_required_float(payload, "percent"),
            message=_required_string(payload, "message"),
            page_number=_optional_int(payload, "page_number"),
        )


@dataclass(frozen=True, slots=True)
class EngineResult:
    """Validated engine output before the application publishes it."""

    output_pdf: Path
    elapsed_seconds: float
    engine_name: str
    engine_version: str
    report: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.elapsed_seconds < 0:
            raise ValueError("elapsed_seconds must not be negative")
        if not self.engine_name.strip() or not self.engine_version.strip():
            raise ValueError("engine name and version are required")

    def to_payload(self) -> dict[str, object]:
        return {
            "output_pdf": str(self.output_pdf),
            "elapsed_seconds": self.elapsed_seconds,
            "engine_name": self.engine_name,
            "engine_version": self.engine_version,
            "report": dict(self.report),
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> EngineResult:
        report_value = payload.get("report", {})
        if not isinstance(report_value, Mapping):
            raise ValueError("report must be an object")
        report: dict[str, object] = {str(key): value for key, value in report_value.items()}
        return cls(
            output_pdf=Path(_required_string(payload, "output_pdf")),
            elapsed_seconds=_required_float(payload, "elapsed_seconds"),
            engine_name=_required_string(payload, "engine_name"),
            engine_version=_required_string(payload, "engine_version"),
            report=report,
        )


def _required_string(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _optional_string(payload: Mapping[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string or null")
    return value


def _required_float(payload: Mapping[str, object], key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{key} must be a number")
    return float(value)


def _optional_float(payload: Mapping[str, object], key: str, default: float) -> float:
    value = payload.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{key} must be a number")
    return float(value)


def _optional_bool(payload: Mapping[str, object], key: str, default: bool) -> bool:
    value = payload.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def _optional_int(payload: Mapping[str, object], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer or null")
    return value
