# Project context

**Snapshot:** 2026-08-29  
**Product:** All_to_PDF  
**Goal:** dịch PDF có text layer sang tiếng Việt, giữ gần nguyên layout, có quality gates trước khi publish.

## Trạng thái hiện tại

Dự án đang ở **M1 — PDF engine integration**.

- M0 foundation nằm trong draft PR [#1](https://github.com/chiendeptraiBTEC/All_to_PDF/pull/1).
- M1 runner/worker nằm trong stacked draft PR [#2](https://github.com/chiendeptraiBTEC/All_to_PDF/pull/2), base là `feat/production-foundation`.
- Code gate đã được xác nhận tại commit `7af93844531a287f8c6e7c0cc9f043426f7e9ef6` bằng GitHub Actions run `33243746819`.
- Worker lifecycle, subprocess JSONL protocol, provider factory, output publication và basic PDF gate đã có deterministic tests.
- **BabelDOC thật chưa được chạy end-to-end trên fixture EN→VI trong engine image.** Không gọi M1 hoàn thành trước gate đó.

## Kiến trúc đã khóa

```text
API / job orchestration
        ↓
worker application service
        ↓
TranslationRunner port
        ↓
isolated subprocess + JSONL
        ↓
BabelDOC PDF engine
        ↓
PDFMathTranslate-next translator contract
        ↓
Azure Translator hoặc OpenAI-compatible LLM
```

Upstream pins:

- BabelDOC: `38d3896dcde9b5a940c62cf5563cadea673a64d3`
- PDFMathTranslate-next: `f8dffcf4c3a33b254391d43514439b975ce8d966`

## Quyết định quan trọng

- Domain/application không import BabelDOC, FastAPI, Redis, database hoặc cloud SDK.
- API key không được ghi vào command line hoặc request manifest; chỉ truyền vào child environment.
- Stdout của engine process chỉ chứa JSONL machine protocol; log/traceback đi stderr.
- Azure NMT là provider mặc định; OpenAI-compatible LLM là lựa chọn chủ động.
- Không dùng adapter Google mobile không chính thức.
- Không hạ coverage gate để đưa code qua CI.
- Output chỉ publish atomically sau quality gate.
- Memory của dự án nằm trong `docs/memory/`; trạng thái không được dựa vào lịch sử chat.

## Thứ tự đọc cho phiên làm việc mới

1. `docs/memory/CONTEXT.md`
2. `docs/memory/PROGRESS.md`
3. `docs/memory/NEXT.md`
4. `docs/memory/RISKS.md`
5. `docs/memory/FILE_MAP.md`
6. `docs/engineering/ENGINE_INTEGRATION.md`
7. `README.md`
