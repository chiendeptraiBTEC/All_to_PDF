# Session log

Nhật ký này chỉ tóm tắt thay đổi và trỏ tới commit/PR; không thay thế `PROGRESS.md`.

## 2026-08-29 — Foundation bootstrap

- Chọn branch `feat/production-foundation` thay vì commit thẳng vào `main`.
- Tạo clean architecture, API vertical slice, provider adapters, UI và quality workflow.
- Bổ sung kiểm tra thứ tự placeholder và phân loại lỗi mạng của provider.
- Tạo project-memory protocol để mọi ngữ cảnh quan trọng nằm trong Git.
- Chưa tích hợp BabelDOC runner; công việc tiếp theo được ghi trong `NEXT.md`.

## 2026-08-29 — Verification and remote delivery

- 28 test pass, branch coverage cục bộ 89.40%.
- Compile, JavaScript syntax, package install và HTTP smoke test pass.
- Đẩy foundation lên branch và mở draft PR [#1](https://github.com/chiendeptraiBTEC/All_to_PDF/pull/1).
- CI phát hiện tuần tự lỗi lint, format và thiếu `aiofiles` type stubs; từng lỗi được sửa bằng commit riêng thay vì hạ gate.
- Code gate commit `707abbca21791af800d1b0674cdd492e3ba5ab34` vượt GitHub Actions run `33242200985`.
- Quality job và container job đều pass; manual visual review vẫn là merge gate.
