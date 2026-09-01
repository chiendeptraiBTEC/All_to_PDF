# File map

Bản đồ này giúp developer mới tìm đúng nơi trước khi sửa code.

## Entry points

- `backend/src/all_to_pdf/main.py` — FastAPI app, lifespan và embedded-worker option cho local development.
- `backend/src/all_to_pdf/bootstrap.py` — composition root; nơi duy nhất chọn concrete adapters.
- `backend/src/all_to_pdf/engine/bridge.py` — isolated BabelDOC child-process entry point và JSONL emitter.
- `scripts/install_pdf_engine.sh` — cài hai upstream theo commit pin.

## Domain

- `domain/job.py` — job states, allowed transitions, progress monotonicity và terminal rules.
- `domain/provider.py` — provider protocol, translation result, protected-token validation và provider errors.

## Application

- `application/jobs.py` — submit/get/cancel use cases.
- `application/uploads.py` — upload use case.
- `application/engine.py` — `TranslationRunner`, `PdfQualityGate`, progress/request/result và engine errors.
- `application/worker.py` — queue-to-engine-to-quality-to-publish lifecycle.
- `application/ports.py` — repository, queue producer/consumer và object-storage contracts.

## Infrastructure

- `infrastructure/runners/subprocess.py` — process spawn, JSONL parsing, timeout, terminate/kill và protocol validation.
- `infrastructure/providers/factory.py` — map provider profile sang Azure/LLM adapter.
- `infrastructure/providers/azure.py` — official Azure Translator V3 adapter.
- `infrastructure/providers/openai_compatible.py` — OpenAI-compatible chat-completions adapter.
- `infrastructure/quality/basic.py` — temporary structural gate; không thay thế full M3 quality engine.
- `infrastructure/storage/local.py` — local streamed upload, materialize và atomic publish.
- `infrastructure/queues/in_memory.py` — local/test queue only.
- `infrastructure/repositories/in_memory.py` — local/test repository only.

## API/UI

- `api/router.py` và `api/routes/` — HTTP endpoints.
- `api/schemas.py` — public request/response contracts, gồm progress fields.
- `frontend/` — UI tách biệt khỏi backend domain.

## Tests

- `test_engine_bridge.py` — bridge lifecycle với fake upstream modules.
- `test_subprocess_runner.py` — success/OCR JSONL process contract.
- `test_subprocess_runner_failures.py` — timeout, malformed protocol, nonzero exit và error mapping.
- `test_worker.py` — success, OCR, review, retryable/permanent/unexpected worker paths.
- `test_provider_factory.py` — profile configuration và secret handoff environment.
- `test_quality_gate.py` — structural gate acceptance/rejection.

## Documentation

- `docs/engineering/ENGINE_INTEGRATION.md` — isolation boundary, protocol, upstream pins và dependency conflict.
- `docs/ADR-0001-translation-provider-strategy.md` — provider decision.
- `docs/memory/` — project context, verified progress, next work, risks và handoff.
