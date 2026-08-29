# Definition of Done

Một hạng mục chỉ hoàn thành khi:

1. Acceptance criteria được ghi trước khi code.
2. Code nằm đúng layer và không phá dependency direction.
3. Happy path, validation và failure path có test.
4. Lint, typecheck, coverage và build pass.
5. Security/privacy impact đã xem xét.
6. Observability đủ để vận hành và điều tra lỗi.
7. Tài liệu/API contract được cập nhật.
8. `PROGRESS.md`, `NEXT.md` và `RISKS.md` phản ánh trạng thái mới.
9. Có rollback hoặc thay đổi tương thích ngược được mô tả.
10. PR được review; không tự coi code chưa kiểm định là production-ready.
