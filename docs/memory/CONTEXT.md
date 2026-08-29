# Current context summary

**Cập nhật:** 2026-08-29  
**Milestone:** M0 — Production foundation  
**Branch đang triển khai:** `feat/production-foundation`

## Mục tiêu sản phẩm

Xây dịch vụ dịch PDF có text layer sang tiếng Việt trong khi giữ gần nguyên bố cục, công thức,
ảnh và vector. Kết quả chỉ được phát hành sau quality gates.

## Kiến trúc đã chốt

- BabelDOC là lõi parse/layout/typesetting/PDF writer.
- PDFMathTranslate-next là lớp translator integration và subprocess isolation.
- Provider mặc định: Azure AI Translator F0/S1.
- Provider tùy chọn: OpenAI-compatible LLM qua `base_url`, `api_key`, `model`.
- Adapter Google mobile không chính thức bị cấm trong production.
- Job API bất đồng bộ; production dùng PostgreSQL, Redis-compatible queue và S3-compatible storage.
- UI và API tách thư mục. UI v1 là zero-build web app để giảm thời gian triển khai và bề mặt lỗi.

## Nguyên tắc kỹ thuật

- Domain/application không import FastAPI, Redis, SQLAlchemy hoặc cloud SDK.
- Adapter thay thế qua Protocol; composition chỉ nằm tại `bootstrap.py`.
- Không lưu secret trong request/job/log.
- Mọi provider response phải kiểm tra protected placeholders.
- Không chấp nhận output chỉ vì PDF mở được.
- Giá trị chưa benchmark phải ghi `CHƯA XÁC MINH`.

## Trạng thái hiện tại

Foundation có vertical slice cho:

- kiểm tra readiness/liveness;
- upload PDF streaming vào local object storage;
- tạo job idempotent;
- đọc và hủy job;
- cấu hình hai provider;
- adapter Azure Text Translation và OpenAI-compatible có placeholder guard;
- UI upload/chọn provider/theo dõi job;
- test domain, service, provider và API.

Chưa có worker production, BabelDOC runner, persistence PostgreSQL/Redis/S3 hoặc PDF quality engine.
