# Test strategy

## Test pyramid

- Unit: domain transitions, placeholder guard, error classification.
- Application: idempotency, enqueue-once, cancellation.
- Adapter: provider contract qua `httpx.MockTransport`; storage qua temp directory.
- API integration: upload → submit → get → cancel.
- E2E PDF từ M1: fixture PDF → BabelDOC → output → quality report.
- UI từ M2: Playwright cho keyboard/mobile/error states.

## Corpus PDF tối thiểu

- single column;
- two/three columns;
- inline/display formula;
- table có/không border;
- text trên ảnh/nền màu;
- rotated text;
- Form XObject;
- subset font/missing ToUnicode;
- tài liệu dài;
- scanned PDF để xác nhận `OCR_REQUIRED`.

## Không dùng snapshot thay cho assertion quan trọng

Snapshot chỉ hỗ trợ review. Invariant như page count, placeholder, box và provider error phải được assert rõ.
