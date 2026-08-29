# PDF engine integration

## Boundary

The API/worker process never imports BabelDOC. `BabelDocSubprocessRunner` writes a
non-secret manifest and starts `all_to_pdf.engine.bridge`. The child emits JSONL on
stdout and sends diagnostics to stderr.

```text
worker -> engine-request.json -> subprocess
worker <- progress/error/finish JSONL <- subprocess
```

Benefits:

- a native-library crash does not terminate the API process;
- timeout and cancellation can terminate the entire engine process;
- secrets stay in the child environment, not command arguments or manifest files;
- unit tests replace the child with a deterministic fake executable;
- upgrading the PDF engine does not change domain or application code.

## Locked upstream

- BabelDOC: `38d3896dcde9b5a940c62cf5563cadea673a64d3`
- PDFMathTranslate-next: `f8dffcf4c3a33b254391d43514439b975ce8d966`

Use `scripts/install_pdf_engine.sh`. PDFMathTranslate-next is installed with
`--no-deps` because its selected commit declares `pymupdf<1.25.3`, while BabelDOC
0.6.4 requires `pymupdf>=1.26.7`. The runtime imports only the PDFMathTranslate-next
translator contract; BabelDOC remains the source of truth for PDF dependencies.

At the selected PDFMathTranslate-next commit, `pdf2zh_next/config/main.py` imports
`tomlkit`, but `tomlkit` is absent from the upstream `pyproject.toml` dependency list.
The install script therefore declares `tomlkit>=0.13,<1` explicitly. This exception
must be removed or revalidated whenever the upstream commit changes.

## Protocol

Request schema version 1 contains workspace paths, language pair, provider profile
and an administrator-managed LLM profile ID. It never contains API keys.

Child events:

```json
{"type":"progress","status":"parsing","percent":20,"stage":"Parse Page Layout"}
{"type":"error","code":"OCR_REQUIRED","message":"...","retryable":false}
{"type":"finish","output_path":"...","engine_name":"...","engine_version":"..."}
```

Only `parsing`, `translating`, `typesetting` and `generating_pdf` may be emitted by
the engine. The application owns preflight, quality review and final publication.

## Verification layers

### Deterministic unit/integration layer

The subprocess protocol, state mapping, timeout/error handling, output publication,
provider factory and basic PDF gate use fakes and do not require heavy PDF packages.
This layer runs in the `quality` CI job and must keep coverage above 85%.

### Real-engine smoke layer

`scripts/smoke_pdf_engine.py` creates a real text-layer PDF with PyMuPDF, injects a
deterministic EN-to-VI text provider and runs the production bridge against the
pinned BabelDOC/PDFMathTranslate-next packages. It asserts:

- the provider was called;
- one finish event was emitted;
- source/output page count matches;
- Vietnamese target text appears in extracted output;
- output artifacts and a checksum report are produced.

The deterministic provider removes external API cost and credentials; it does not
replace later Azure/LLM quality benchmarks. The CI `engine-smoke` job uploads the
source PDF, translated PDF and JSON report as evidence.
