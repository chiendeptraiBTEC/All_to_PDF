from __future__ import annotations

import json
from pathlib import Path

import pytest

from all_to_pdf.engine import babeldoc_entrypoint
from all_to_pdf.engine.models import EngineResult
from all_to_pdf.engine.protocol import parse_line


def test_entrypoint_emits_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "input.pdf"
    source.write_bytes(b"%PDF-1.4\n%%EOF\n")
    output = tmp_path / "output" / "translated.pdf"
    output.parent.mkdir()
    output.write_bytes(b"%PDF-1.4\n%%EOF\n")
    request_file = tmp_path / "request.json"
    request_file.write_text(
        json.dumps(
            {
                "job_id": "job-1",
                "input_pdf": str(source),
                "output_directory": str(output.parent),
                "source_language": "en",
                "target_language": "vi",
                "translator_profile": "deterministic_test",
            }
        )
    )

    monkeypatch.setattr(
        babeldoc_entrypoint.BabelDocDriver,
        "run",
        lambda self, request, emit: EngineResult(output, 0.1, "fake", "1"),
    )

    assert babeldoc_entrypoint.main(["--request", str(request_file)]) == 0
    parsed = parse_line(capsys.readouterr().out.strip())
    assert parsed.result is not None
    assert parsed.result.output_pdf == output
