# File map

## Gốc repository

| File | Tác dụng |
|---|---|
| `README.md` | Kiến trúc production và pipeline đã chọn. |
| `pyproject.toml` | Dependency, build, lint, typecheck, test và coverage. |
| `Dockerfile` | Container API baseline non-root. |
| `compose.yaml` | Chạy local nhanh. |
| `CONTRIBUTING.md` | Điểm vào cho contributor. |

## Backend

| File/thư mục | Tác dụng |
|---|---|
| `backend/src/all_to_pdf/domain/job.py` | Job state machine và invariants. |
| `backend/src/all_to_pdf/domain/provider.py` | Provider contract, lỗi và placeholder validator. |
| `backend/src/all_to_pdf/application/` | Use case, không phụ thuộc framework. |
| `backend/src/all_to_pdf/infrastructure/providers/` | Azure và OpenAI-compatible adapters. |
| `backend/src/all_to_pdf/infrastructure/storage/local.py` | Local object storage streaming/atomic. |
| `backend/src/all_to_pdf/infrastructure/repositories/` | Job repository adapters. |
| `backend/src/all_to_pdf/infrastructure/queues/` | Queue adapters. |
| `backend/src/all_to_pdf/api/` | HTTP schemas, routes và dependencies. |
| `backend/src/all_to_pdf/bootstrap.py` | Composition root; chọn adapter cụ thể. |
| `backend/src/all_to_pdf/main.py` | Khởi tạo FastAPI và phục vụ UI. |

## Frontend

| File | Tác dụng |
|---|---|
| `frontend/index.html` | Cấu trúc semantic của Translation Studio. |
| `frontend/styles.css` | Design system, responsive và accessibility. |
| `frontend/app.js` | Upload, submit, polling, cancel và provider state. |

## Bộ nhớ dự án

| File | Tác dụng |
|---|---|
| `docs/memory/CONTEXT.md` | Tóm tắt ngữ cảnh tổng. |
| `docs/memory/PROGRESS.md` | Việc đã làm có bằng chứng. |
| `docs/memory/NEXT.md` | Đường găng tiếp theo. |
| `docs/memory/RISKS.md` | Risk register. |
| `docs/memory/SESSION_LOG.md` | Nhật ký phiên/commit ngắn. |
| `docs/memory/HANDOFF.md` | Bàn giao kỹ thuật và giới hạn đã xác minh. |
| `docs/memory/REMOTE_STATUS.md` | Trạng thái branch, PR và CI trên GitHub. |
