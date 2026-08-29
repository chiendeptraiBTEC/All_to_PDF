# UX strategy

## Ý tưởng bố cục

Giao diện được thiết kế như một **bàn biên tập/kiểm định tài liệu**, không phải dashboard SaaS gồm
nhiều card bo tròn và gradient. Ba vùng có vai trò cố định:

1. **Briefing:** giải thích nguyên tắc và tạo niềm tin.
2. **Studio:** luồng tuyến tính Document → Language → Engine → Commit.
3. **Job desk:** trạng thái kiểm định theo thời gian thực.

## Nguyên tắc

- Editorial grid, đường kẻ và typography tạo cấu trúc thay cho card decoration.
- Mỗi màn hình có một hành động chính.
- Không yêu cầu người dùng hiểu BabelDOC hoặc placeholder.
- Không nhận raw API key trong browser.
- Trạng thái luôn trung thực; không hiển thị “hoàn tất” trước QA.
- Loading/error/empty/cancel là first-class states.
- Màu không phải tín hiệu duy nhất; luôn có text/shape.
- Focus rõ, semantic HTML và reduced motion.

## Vì sao zero-build UI ở M0

- Khởi chạy nhanh, không thêm dependency chain frontend.
- Dễ audit và dễ hiểu với fresher.
- Đủ cho upload/job workflow.
- Chỉ chuyển sang framework khi state/product complexity chứng minh nhu cầu.
