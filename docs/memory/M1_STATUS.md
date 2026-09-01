# M1 status — BabelDOC runner and worker

**Snapshot:** 2026-08-29  
**Branch:** `feat/m1-babeldoc-runner`  
**Parent:** `feat/production-foundation`  
**State:** IN PROGRESS

## Goal

Create the first production-oriented execution path from a queued translation job to a layout-preserving PDF engine while keeping upstream dependencies isolated behind a small, testable contract.

## Scope for this milestone

1. Add an engine-neutral `TranslationRunner` contract.
2. Add a JSON Lines subprocess protocol for progress, result and structured errors.
3. Add a worker orchestrator that maps engine progress to job progress without importing BabelDOC.
4. Pin BabelDOC and PDFMathTranslate-next to reviewed commit SHAs.
5. Add a BabelDOC driver with lazy imports so the API image remains lightweight.
6. Add deterministic contract tests that do not call external providers.
7. Add an opt-in real-engine smoke path with a generated text-layer PDF fixture.
8. Record every verified result here and in `PROGRESS.md`; do not mark M1 complete before a real PDF artifact is produced and inspected.

## Architectural constraint

The service must not embed PDFMathTranslate-next's GUI or process lifecycle. Our worker owns orchestration and uses BabelDOC through an adapter. PDFMathTranslate-next remains pinned as the reviewed reference for provider/config behaviour. Any deviation from the original architecture is documented as an implementation refinement, not hidden.

## Verification plan

### Required on every pull request

- Ruff lint and format.
- Mypy strict.
- Unit and contract tests with branch coverage gate.
- Subprocess success, error, timeout and cancellation tests.
- Protocol compatibility tests.
- Docker non-root baseline.

### Required before M1 is complete

- Install pinned PDF engine dependencies.
- Generate a deterministic source PDF with a real text layer.
- Run BabelDOC in a worker subprocess.
- Produce a mono PDF artifact.
- Open the artifact with two independent PDF readers/parsers where practical.
- Verify page count, non-empty text layer and protected-token integrity.
- Save the command, versions, checksums and result in Git-based memory.

## Current truth

M0 is green and remains in draft PR #1. M1 has started on a stacked branch. No claim is made yet that end-to-end PDF translation works in this branch.
