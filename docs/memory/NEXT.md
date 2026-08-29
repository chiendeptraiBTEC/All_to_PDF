# Next work

Công việc được xếp theo đường găng để ra production nhanh nhưng không bỏ quality gates.

## P0 — M1: Worker và BabelDOC runner

1. Pin BabelDOC/PDFMathTranslate-next trong container bằng commit đã duyệt.
2. Tạo worker process và `TranslationRunner` port.
3. Map provider profile sang BabelDOC translator.
4. Chạy một PDF fixture end-to-end và lưu artifact test.
5. Ghi progress event vào job state.

**Acceptance:** một PDF text-layer nhỏ EN→VI tạo được mono PDF; placeholder không hỏng; test tích hợp tái lập được.

## P0 — M2: Persistence production

1. PostgreSQL job repository với migration.
2. Redis-compatible queue có visibility timeout và retry budget.
3. S3-compatible object storage với checksum và presigned download.
4. Idempotency có transaction/unique constraint.

**Acceptance:** restart API/worker không mất job; không xử lý trùng; artifact publish atomic.

## P0 — M3: Quality engine

1. Structural PDF checks.
2. Page box/page count checks.
3. Placeholder hard gate.
4. Readability guard `MIN_READABLE_SCALE`.
5. Geometry overflow/collision report.
6. Risk-based visual diff.

**Acceptance:** corpus lỗi chủ động bị chặn; output lỗi không chuyển `SUCCEEDED`.

## P1 — M4: Benchmark và hardening

1. Corpus English→Vietnamese có multi-column, table, formula, image overlap, XObject.
2. Benchmark Azure và ít nhất một LLM.
3. Đo p50/p95 latency, peak RSS, cost, fallback rate và scale histogram.
4. Chốt quota, worker size, timeout và SLA.
5. Hoàn tất AGPL/legal gate và threat model review.

## P1 — UX tiếp theo

- Presigned/direct upload cho file lớn.
- Job history có filter và quality report.
- Trang review cho paragraph bị fallback.
- Empty/error/loading states được test bằng Playwright.
