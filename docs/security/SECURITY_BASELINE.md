# Security baseline

- PDF là dữ liệu không tin cậy.
- Upload có size limit, signature check và filename sanitization.
- Production thêm malware scan, decompression/object limits và sandbox worker.
- Container chạy non-root, read-only root filesystem và egress allowlist.
- API key nằm trong secret manager; không nhận qua translation request.
- Không log nội dung paragraph mặc định.
- Object storage mã hóa, có retention và tenant isolation.
- Output chỉ publish sau validation; file tạm có TTL.
- Dependency và container được scan trong CI/release.
- Request có ID để audit nhưng không dùng PII làm ID.
