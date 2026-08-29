# Session log

## 2026-08-29 — M0 production foundation

- Tạo clean architecture, API/upload/job lifecycle, provider adapters, UI foundation, CI và Git memory.
- Mở draft PR #1.
- GitHub Actions M0 vượt quality và non-root Docker gates.

## 2026-08-29 — M1 runner/worker integration

- Tạo branch `feat/m1-babeldoc-runner` và stacked draft PR #2.
- Chọn subprocess JSONL boundary thay vì import BabelDOC trong API/worker.
- Thêm worker lifecycle, progress, failure mapping, atomic output publish và basic quality gate.
- Thêm bridge dùng PDFMathTranslate-next `BaseTranslator` contract bọc Azure/LLM providers riêng của dự án.
- Khóa BabelDOC/PDFMathTranslate-next commits và ghi rõ PyMuPDF dependency conflict.
- CI phát hiện async-I/O lint, formatter và type issues; sửa tận gốc, không tắt rule.
- Coverage ban đầu giảm còn 68.53% do bridge/factory chưa có tests.
- Không hạ gate 85%; bổ sung tests cho bridge, process protocol, timeout, worker failures, provider factory và quality gate.
- Code gate commit `7af93844531a287f8c6e7c0cc9f043426f7e9ef6` vượt:
  - 79 tests;
  - 88.53% coverage;
  - Ruff lint/format;
  - Mypy strict;
  - JavaScript syntax;
  - Docker build và non-root runtime.
- Live BabelDOC fixture vẫn là gate mở; M1 chưa được đánh dấu hoàn tất.
