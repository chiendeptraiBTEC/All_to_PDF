# Engineering handoff

**Cập nhật:** 2026-08-29  
**Milestone:** M0 — Production foundation

## Trạng thái xác minh

- 28 test cục bộ pass.
- Branch coverage: 89%+; hard gate hiện tại là 85%.
- `python -m compileall` pass.
- `node --check frontend/app.js` pass.
- Editable package build/install pass với build isolation tắt trong môi trường không có Internet.
- Uvicorn smoke test pass cho `/health/live` và giao diện `/`.
- Chưa chạy Ruff và Mypy cục bộ vì môi trường không có hai binary và không có Internet;
  CI đã cấu hình để chạy cả hai khi code ở GitHub.
- Headless Chromium trong container không tạo được screenshot ổn định; visual QA thủ công vẫn là
  cổng chưa hoàn tất.

## Những gì M0 thực sự cung cấp

- Clean architecture và dependency direction rõ.
- Upload PDF streaming có size/signature guard và atomic publish.
- Job state machine, idempotent submit, get và cancel.
- Azure Translator V3 và OpenAI-compatible provider adapter.
- Protected-token validation có kiểm tra thứ tự.
- Translation Studio responsive, không thu raw API key.
- CI, Docker baseline, test strategy, security baseline và Git-based project memory.

## Những gì chưa được phép gọi là production-ready

- Chưa có BabelDOC/PDFMathTranslate-next worker end-to-end.
- Chưa có PostgreSQL, Redis-compatible queue hoặc S3-compatible storage.
- Chưa có quality engine cho PDF output.
- Chưa benchmark Azure/LLM trên corpus English → Vietnamese.
- Chưa hoàn tất AGPL/legal gate, threat model và visual accessibility review.

Đường găng tiếp theo là M1 trong `NEXT.md`: worker + BabelDOC runner + một fixture PDF end-to-end.
