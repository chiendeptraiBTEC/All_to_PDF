# Risk register

| ID | Rủi ro | Mức | Giảm thiểu | Trạng thái |
|---|---|---:|---|---|
| R-01 | BabelDOC/PDFMathTranslate-next dùng AGPL-3.0 | Critical | Legal gate trước network service; công bố source/patch theo tư vấn | Open |
| R-02 | Adapter Azure upstream khóa cứng China region | High | Dùng adapter riêng, endpoint/region cấu hình | Mitigated in foundation |
| R-03 | Scale thấp giữ layout nhưng làm chữ không đọc được | High | Readability guard + fallback + QA | Planned M3 |
| R-04 | PDF độc hại hoặc decompression bomb | High | Sandbox worker, limits, malware scan | Planned M2/M4 |
| R-05 | In-memory queue/repository mất dữ liệu | High | Chỉ dùng local; thay PostgreSQL/Redis trước production | Planned M2 |
| R-06 | Chất lượng EN→VI chưa benchmark | High | Human evaluation + Azure/LLM benchmark | Planned M4 |
| R-07 | Placeholder bị provider sửa | High | Hard validator, bounded retry, source fallback | Partially implemented |
| R-08 | UI hiển thị queued mãi khi chưa có worker | Medium | Hiển thị trạng thái trung thực; hoàn thành M1 | Open |
| R-09 | Source/output chứa dữ liệu nhạy cảm | High | Encryption, retention, no-content logs, egress policy | Planned M2/M4 |
