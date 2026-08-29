# Progress

## M0 — Production foundation

### Hoàn thành trong `feat/production-foundation`

- [x] Tạo cấu trúc clean architecture: domain, application, infrastructure, API.
- [x] Tạo job lifecycle có kiểm soát transition.
- [x] Tạo upload PDF theo stream, giới hạn dung lượng, kiểm tra `%PDF-`, atomic rename.
- [x] Tạo API submit/get/cancel với idempotency.
- [x] Tạo provider contract và protected-token validator.
- [x] Tạo Azure Translator V3 adapter dùng API chính thức.
- [x] Tạo OpenAI-compatible adapter với base URL/API key/model.
- [x] Tạo UI tách biệt, responsive, keyboard accessible và không nhận raw API key.
- [x] Tạo CI, test strategy, workflow, quality gates và project-memory protocol.
- [x] Tạo Docker baseline chạy non-root.

### Bằng chứng hiện có

- [x] `pytest`: 28 tests pass.
- [x] Branch coverage: 89.40%, vượt gate 85%.
- [x] `python -m compileall` pass.
- [x] `node --check frontend/app.js` pass.
- [x] Editable package build/install pass bằng setuptools.
- [x] Uvicorn smoke test: `/health/live` và static UI trả thành công.
- [ ] CI Ruff/Mypy/Docker pass trên pull request; chưa chạy local vì tool không có sẵn và môi trường không cho tải thêm package.
- [ ] Review hình ảnh desktop/mobile; Chromium headless của môi trường tạo scaffold bị treo nên chưa có screenshot đáng tin cậy.

## Không được hiểu nhầm

Milestone này là nền móng chạy được cho upload và job orchestration; chưa phải engine dịch PDF hoàn chỉnh.
Không đánh dấu production-ready trước khi hoàn thành M1–M4 trong `NEXT.md`.
