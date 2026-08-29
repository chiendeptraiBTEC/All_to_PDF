# PDF engine contract

## Purpose

Keep the HTTP/API process independent from BabelDOC, ONNX, PyMuPDF and provider SDKs. The application speaks to a `TranslationRunner`; the production implementation starts one isolated child process per document.

## Process boundary

```text
TranslationWorker
  -> TranslationRunner
      -> child process
          -> BabelDocDriver
              -> BabelDOC
              -> provider client
```

The child receives a request JSON file using `--request <path>`. It writes only versioned JSON Lines to stdout. Logs and tracebacks go to stderr.

## Protocol version 1

Every line has:

```json
{
  "version": 1,
  "type": "progress | result | error",
  "payload": {}
}
```

### Progress

```json
{
  "stage": "translating",
  "percent": 42.5,
  "message": "Translate Paragraphs",
  "page_number": 3
}
```

Progress must be monotonic. A regression is treated as a worker failure rather than silently corrupting state.

### Result

```json
{
  "output_pdf": "/work/job/output.pdf",
  "elapsed_seconds": 8.4,
  "engine_name": "BabelDOC",
  "engine_version": "<commit>",
  "report": {
    "provider": "azure_nmt",
    "model": "text-translation-v3"
  }
}
```

The parent verifies that the reported output exists before returning success. Publishing is a later quality-gate responsibility.

### Error

```json
{
  "code": "PROVIDER_RATE_LIMITED",
  "message": "translation provider rate limit or quota exceeded",
  "retryable": true
}
```

The child must exit non-zero after an error message. The structured message is authoritative; stderr is diagnostic and capped before being attached to an exception.

## Cancellation and timeout

- The parent polls a cancellation probe.
- On cancellation or timeout it sends terminate, waits a bounded grace period, then kills the child.
- Each attempt uses a unique temporary request directory.
- A partial PDF is never treated as a result unless the child emits exactly one result message and the file exists.

## Upstream isolation

`requirements/pdf-engine.lock.txt` pins full commit SHAs. Heavy dependencies are installed only in the worker image. The API image and domain tests do not import BabelDOC.

## Test tiers

1. **Unit:** payload validation, state and error classification.
2. **Contract:** fake subprocess covers success, invalid JSON, structured failure, timeout and cancellation.
3. **Driver compatibility:** fake BabelDOC modules verify the adapter contract without network/model downloads.
4. **Real-engine smoke:** installs pinned dependencies, generates a searchable fixture PDF and produces a mono PDF artifact.
5. **Corpus regression:** required before production; includes multi-column, formula, table, image overlap and XObject cases.

## Completion rule

M1 is not complete when contract tests pass. It is complete only after the real-engine smoke produces an inspectable artifact and the evidence is written to `docs/memory/M1_STATUS.md` and `docs/memory/PROGRESS.md`.
