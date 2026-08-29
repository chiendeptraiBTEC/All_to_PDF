# Progress

## M0 — Production foundation

### Hoàn thành trong `feat/production-foundation`

- [x] Tạo cấu trúc clean architecture: domain, application, infrastructure, API.
- [x] Tạo job lifecycle có kiểm soát transition.
- [x] Tạo upload PDF theo stream, giới hạn dung lượng, kiểm tra `%PDF-`, atomic rename.
- [x] Tạo API submit/get/cancel với idempotency.
- [x] Tạo provider contract và protected-token validator có kiểm tra thứ tự token.
- [x] Tạo Azure Translator V3 adapter dùng API chính thức.
- [x] Tạo OpenAI-compatible adapter với base URL/API key/model.
- [x] Phân loại lỗi authentication, rate limit, server và transport của provider.
- [x] Tạo UI tách biệt, responsive, semantic và không nhận raw API key.
- [x] Tạo CI, test strategy, workflow, quality gates và project-memory protocol.
- [x] Tạo Docker baseline chạy non-root.

### Bằng chứng hiện có

- [x] `pytest`: 28 tests pass.
- [x] Branch coverage cục bộ: 89.40%, vượt gate 85%.
- [x] `python -m compileall` pass.
- [x] `node --check frontend/app.js` pass.
- [x] Editable package build/install pass bằng setuptools.
- [x] Uvicorn smoke test: `/health/live` và static UI trả thành công.
- [x] GitHub Actions run `33242200985`: Ruff lint/format, Mypy, tests/coverage và frontend syntax pass.
- [x] Docker image build pass; runtime user được xác nhận non-root.
- [ ] Manual visual review desktop/mobile; môi trường scaffold chưa tạo được screenshot Chromium đáng tin cậy.

## Không được hiểu nhầm

Milestone này là nền móng chạy được cho upload, provider contract và job orchestration; chưa phải engine dịch PDF hoàn chỉnh.
Không đánh dấu production-ready trước khi hoàn thành M1–M4 trong `NEXT.md`.
