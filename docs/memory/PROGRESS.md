# Progress

## M0 — Production foundation

Đã hoàn thành và kiểm định trên nhánh `feat/production-foundation`:

- clean architecture: domain, application, infrastructure, API;
- upload PDF theo stream, signature/size guard, atomic write;
- submit/get/cancel job có idempotency;
- Azure Translator V3 và OpenAI-compatible provider;
- protected-token validation;
- UI foundation, CI và non-root Docker baseline;
- Git-based project memory.

M0 vẫn ở draft PR #1 vì manual desktop/mobile visual review chưa hoàn tất.

## M1 — Runner/worker foundation

### Đã triển khai

- [x] `TranslationRunner` và `PdfQualityGate` application contracts.
- [x] Worker lifecycle từ queue đến atomic output publish.
- [x] Progress state/percent có monotonic guard.
- [x] Mapping `OCR_REQUIRED`, `NEEDS_REVIEW`, retryable và permanent failure.
- [x] Queue consumer contract và local in-memory consumer.
- [x] Object storage materialize/publish và path-traversal guard.
- [x] Isolated subprocess runner có timeout/terminate/kill fallback.
- [x] JSONL protocol: `progress`, `error`, `finish`.
- [x] Engine manifest không chứa secrets.
- [x] Lazy BabelDOC bridge để API image vẫn nhẹ.
- [x] Provider-backed PDFMathTranslate-next translator contract.
- [x] Azure/LLM provider factory cho child process.
- [x] Basic structural PDF gate: source/output existence, signature, size và EOF marker.
- [x] Upstream install script khóa đúng hai commit.
- [x] Tài liệu `docs/engineering/ENGINE_INTEGRATION.md`.

### Bằng chứng đã xác minh

GitHub Actions run [`33243746819`](https://github.com/chiendeptraiBTEC/All_to_PDF/actions/runs/33243746819) trên code gate commit `7af93844531a287f8c6e7c0cc9f043426f7e9ef6`:

- Ruff lint: pass;
- Ruff format: pass;
- Mypy strict: pass, 39 source files;
- Pytest: **79 passed**;
- Total coverage: **88.53%**, gate 85%;
- frontend JavaScript syntax: pass;
- Docker build: pass;
- runtime non-root verification: pass.

Các test mới bao phủ bridge thực qua fake upstream modules, worker state/failure paths, timeout/non-JSON/nonzero exit, provider factory, structural quality gate và atomic publication.

## Chưa được đánh dấu hoàn thành

- [ ] Cài pinned BabelDOC/PDFMathTranslate-next trong worker image thật.
- [ ] Chạy fixture PDF có text layer EN→VI qua BabelDOC thật.
- [ ] Xác minh output mở được, giữ số trang và có text tiếng Việt.
- [ ] Lưu reproducible smoke artifact/report.
- [ ] Chạy với Azure credential hoặc provider profile được phê duyệt.
- [ ] PostgreSQL, Redis-compatible queue và S3-compatible storage.
- [ ] Full structural/geometry/visual quality engine.
- [ ] Readability guard `MIN_READABLE_SCALE`.
- [ ] AGPL/legal gate và threat-model review.

Không gọi sản phẩm production-ready trước khi các gate còn mở được hoàn tất.
