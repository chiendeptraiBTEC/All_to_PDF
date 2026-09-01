# Remote status

**Snapshot:** 2026-08-29  
**Repository:** `chiendeptraiBTEC/All_to_PDF`

## Pull requests

### PR #1 — M0 foundation

- Branch: `feat/production-foundation`
- URL: https://github.com/chiendeptraiBTEC/All_to_PDF/pull/1
- State: draft, open.
- Open gate: manual visual review desktop/mobile.

### PR #2 — M1 runner/worker

- Branch: `feat/m1-babeldoc-runner`
- Base: `feat/production-foundation`
- URL: https://github.com/chiendeptraiBTEC/All_to_PDF/pull/2
- State: draft, open.
- Verified code gate commit: `7af93844531a287f8c6e7c0cc9f043426f7e9ef6`.

## Verified GitHub Actions

Workflow run [`33243746819`](https://github.com/chiendeptraiBTEC/All_to_PDF/actions/runs/33243746819):

### `quality` — passed

- dependency installation;
- Ruff lint and format;
- Mypy strict, 39 source files;
- Pytest: 79 passed;
- coverage: 88.53%, gate 85%;
- frontend JavaScript syntax.

### `container` — passed

- Docker image build;
- runtime user verified non-root.

## Open M1 merge gate

A live smoke test must install the pinned BabelDOC/PDFMathTranslate-next commits and translate a real text-layer PDF fixture to Vietnamese. Deterministic fake-engine tests are necessary but not sufficient.

This status file is a documentation follow-up. GitHub Actions on the current PR head remains the source of truth after this commit.
