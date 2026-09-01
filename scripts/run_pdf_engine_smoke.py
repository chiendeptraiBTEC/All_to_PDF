"""Run an offline, reproducible smoke test against the pinned BabelDOC engine."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from all_to_pdf.engine.models import EngineRequest
from all_to_pdf.engine.subprocess_runner import (
    SubprocessRunnerConfig,
    SubprocessTranslationRunner,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-directory", type=Path, required=True)
    arguments = parser.parse_args()
    work_directory = arguments.work_directory.resolve()
    work_directory.mkdir(parents=True, exist_ok=True)

    source_pdf = work_directory / "source.pdf"
    output_directory = work_directory / "output"
    _generate_fixture(source_pdf)

    events: list[dict[str, object]] = []
    runner = SubprocessTranslationRunner(
        SubprocessRunnerConfig(
            command=(sys.executable, "-m", "all_to_pdf.engine.babeldoc_entrypoint"),
            poll_interval_seconds=0.1,
            terminate_grace_seconds=10.0,
        )
    )
    result = runner.run(
        EngineRequest(
            job_id="engine-smoke",
            input_pdf=source_pdf,
            output_directory=output_directory,
            source_language="en",
            target_language="vi",
            translator_profile="deterministic_test",
            timeout_seconds=900,
        ),
        on_progress=lambda progress: events.append(progress.to_payload()),
        is_cancelled=lambda: False,
    )

    validation = _validate_pdf(result.output_pdf)
    report = {
        "source_pdf": str(source_pdf),
        "output_pdf": str(result.output_pdf),
        "source_sha256": _sha256(source_pdf),
        "output_sha256": _sha256(result.output_pdf),
        "engine": result.to_payload(),
        "progress_events": events,
        "validation": validation,
    }
    (work_directory / "smoke-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, default=str))


def _generate_fixture(destination: Path) -> None:
    from generate_fixture_pdf import build_pdf

    destination.write_bytes(build_pdf("Hello world."))


def _validate_pdf(path: Path) -> dict[str, object]:
    import pikepdf
    import pymupdf

    with pikepdf.Pdf.open(path) as parsed:
        pikepdf_pages = len(parsed.pages)
    document = pymupdf.open(path)
    try:
        text = "\n".join(page.get_text("text") for page in document)
        pymupdf_pages = document.page_count
    finally:
        document.close()

    if pikepdf_pages != 1 or pymupdf_pages != 1:
        raise RuntimeError(
            f"unexpected page count: pikepdf={pikepdf_pages}, pymupdf={pymupdf_pages}"
        )
    if not text.strip():
        raise RuntimeError("translated PDF has an empty text layer")
    return {
        "pikepdf_pages": pikepdf_pages,
        "pymupdf_pages": pymupdf_pages,
        "extracted_text": text.strip(),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
