# Next work

Công việc được xếp theo đường găng để ra production nhanh nhưng không bỏ quality gates.

## P0 — M1.1: Live BabelDOC smoke gate

1. Tạo worker CLI riêng và `Dockerfile.worker`; API image không mang PDF engine nặng.
2. Cài BabelDOC/PDFMathTranslate-next bằng `scripts/install_pdf_engine.sh` trong worker image.
3. Tạo PDF fixture có text layer bằng PyMuPDF.
4. Chạy bridge với deterministic test provider để kiểm tra engine, không phụ thuộc credential bên ngoài.
5. Xác minh output:
   - mở được bằng PyMuPDF;
   - số trang không đổi;
   - text tiếng Việt xuất hiện;
   - file có signature/EOF hợp lệ;
   - child process trả `finish` đúng protocol.
6. Thêm CI engine-smoke hoặc workflow riêng có cache và timeout.
7. Lưu report chứa upstream commits, engine version, duration và output checksum.

**Acceptance:** một fixture EN→VI chạy qua BabelDOC thật và tạo mono PDF tái lập được. Chỉ sau đó mới đánh dấu M1 hoàn thành.

## P0 — M2: Persistence production

1. PostgreSQL job repository + migrations + optimistic concurrency/unique idempotency.
2. Redis-compatible queue có visibility timeout, retry budget và dead-letter handling.
3. S3-compatible storage có checksum, atomic publish và presigned download.
4. Worker heartbeat/recovery; restart không làm mất hoặc xử lý trùng job.

**Acceptance:** API/worker restart không mất job; một idempotency key không tạo hai jobs; output không publish dở.

## P0 — M3: PDF quality engine

1. Parse source/output bằng hai parser độc lập.
2. Page count, MediaBox/CropBox và page-boundary checks.
3. Placeholder hard gate.
4. Readability guard và source fallback policy.
5. Geometry overflow/collision report.
6. Image/Form XObject/link inventory comparison.
7. Risk-based visual diff.

**Acceptance:** corpus lỗi chủ động bị chặn; output lỗi không chuyển `SUCCEEDED`.

## P1 — M4: Benchmark và hardening

- Corpus EN→VI: single/multi-column, table, formula, image overlap, rotated text, XObject, long document và scanned PDF.
- Benchmark Azure và ít nhất một LLM.
- Đo p50/p95 latency, peak RSS, request count, cost, fallback rate và scale histogram.
- Chốt worker sizing, timeout, quota và SLA.
- Hoàn tất AGPL/legal và threat model.

## UI/UX gate còn mở

- Manual visual review desktop/tablet/mobile.
- Keyboard/focus review bằng browser thật.
- Playwright cho empty/loading/error/success states sau khi API worker flow ổn định.
