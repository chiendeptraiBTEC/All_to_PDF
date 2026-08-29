from pathlib import Path

import pytest

from all_to_pdf.engine.errors import EngineProtocolError
from all_to_pdf.engine.models import EngineProgress, EngineRequest, EngineResult, EngineStage
from all_to_pdf.engine.protocol import error_line, parse_line, progress_line, result_line


def test_engine_request_round_trip(tmp_path: Path) -> None:
    request = EngineRequest(
        job_id="job-1",
        input_pdf=tmp_path / "input.pdf",
        output_directory=tmp_path / "output",
        source_language="en",
        target_language="vi",
        translator_profile="azure_nmt",
        metadata={"tenant": "demo"},
    )

    assert EngineRequest.from_payload(request.to_payload()) == request


@pytest.mark.parametrize(
    "overrides",
    [
        {"job_id": ""},
        {"source_language": "vi", "target_language": "vi"},
        {"translator_profile": ""},
        {"timeout_seconds": 0},
    ],
)
def test_engine_request_rejects_invalid_values(
    tmp_path: Path,
    overrides: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "job_id": "job-1",
        "input_pdf": tmp_path / "input.pdf",
        "output_directory": tmp_path / "output",
        "source_language": "en",
        "target_language": "vi",
        "translator_profile": "azure_nmt",
    }
    values.update(overrides)

    with pytest.raises(ValueError):
        EngineRequest(**values)  # type: ignore[arg-type]


def test_protocol_round_trip(tmp_path: Path) -> None:
    progress = EngineProgress(EngineStage.TRANSLATING, 45.5, "Translating", 1)
    result = EngineResult(tmp_path / "output.pdf", 1.25, "fake", "1", {"pages": 1})

    assert parse_line(progress_line(progress)).progress == progress
    assert parse_line(result_line(result)).result == result
    failure = parse_line(error_line(code="E", message="failed", retryable=True)).failure
    assert failure is not None
    assert failure.code == "E"
    assert failure.retryable is True


@pytest.mark.parametrize(
    "line",
    [
        "not-json",
        "[]",
        '{"version":99,"type":"progress","payload":{}}',
        '{"version":1,"type":"unknown","payload":{}}',
        '{"version":1,"type":"error","payload":{"code":1}}',
    ],
)
def test_protocol_rejects_invalid_messages(line: str) -> None:
    with pytest.raises(EngineProtocolError):
        parse_line(line)


def test_progress_validation() -> None:
    with pytest.raises(ValueError):
        EngineProgress(EngineStage.STARTING, 101, "bad")
    with pytest.raises(ValueError):
        EngineProgress(EngineStage.STARTING, 0, "bad", 0)
