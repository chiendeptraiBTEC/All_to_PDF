# Project memory protocol

Thư mục này là bộ nhớ chính thức của dự án.

## Quy tắc

1. Không dựa vào chat history để khôi phục quyết định hoặc tiến độ.
2. Mỗi phiên làm việc bắt đầu bằng việc đọc `CONTEXT.md`, `PROGRESS.md`, `NEXT.md`.
3. Khi thay đổi kiến trúc hoặc phạm vi, cập nhật tài liệu trong cùng pull request.
4. `PROGRESS.md` chỉ ghi việc đã có bằng chứng: commit, test, PR hoặc artifact.
5. `NEXT.md` phải có thứ tự ưu tiên và acceptance criteria.
6. `CONTEXT.md` được tóm tắt lại khi dài hoặc khi hoàn thành một milestone.
7. Không lưu secret, API key, dữ liệu PDF hoặc nội dung khách hàng trong tài liệu.

## File và tác dụng

- `CONTEXT.md`: ảnh chụp ngữ cảnh tổng hiện tại.
- `PROGRESS.md`: trạng thái triển khai có bằng chứng.
- `NEXT.md`: hàng đợi công việc tiếp theo.
- `FILE_MAP.md`: bản đồ file để người mới định hướng nhanh.
- `RISKS.md`: rủi ro, mức độ và biện pháp giảm thiểu.
- `SESSION_LOG.md`: nhật ký ngắn, append-only theo ngày/commit.
- `HANDOFF.md`: trạng thái xác minh và giới hạn để bàn giao kỹ thuật.
- `REMOTE_STATUS.md`: branch, commit, PR và trạng thái CI thực tế trên GitHub.
