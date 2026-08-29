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
translator contract; BabelDOC owns the PDF dependency graph.

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

## Verification status

The subprocess protocol, state mapping, output publication and basic PDF gate have
deterministic unit tests. A live BabelDOC EN-to-VI fixture still requires the heavy
engine image and provider credentials; it remains an explicit M1 release gate rather
than being represented as completed.
