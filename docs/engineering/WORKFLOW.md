# Development workflow

## Nhánh và pull request

- `main` luôn ở trạng thái có thể triển khai.
- Mỗi thay đổi dùng branch nhỏ: `feat/`, `fix/`, `chore/`, `docs/`.
- Không push trực tiếp vào `main`.
- PR phải mô tả mục tiêu, phạm vi, test, rủi ro và rollback.

## Chu trình bắt buộc

```text
Đọc memory docs
-> xác định acceptance criteria
-> viết/điều chỉnh test
-> triển khai nhỏ nhất
-> chạy quality gates
-> cập nhật memory docs
-> mở PR
-> review
-> merge
```

## Quy tắc code

- Tên thể hiện ý nghĩa; tránh viết tắt tùy tiện.
- Hàm ngắn, một mức trừu tượng.
- Không bắt `Exception` nếu có thể phân loại cụ thể.
- Không log secret hoặc toàn văn tài liệu.
- Không thêm dependency khi stdlib hoặc dependency hiện có đủ rõ ràng.
- Không tạo abstraction chỉ để “trông enterprise”; abstraction phải có ranh giới thay thế thật.
- Comment giải thích “vì sao”, code thể hiện “làm gì”.

## Review checklist

- Invariant domain có được giữ không?
- Failure mode có rõ và retry đúng không?
- API có idempotent khi cần không?
- Có test cho happy path và failure path không?
- Tài liệu context/progress/next có đồng bộ không?
- UI có keyboard, focus, loading, error và mobile state không?
