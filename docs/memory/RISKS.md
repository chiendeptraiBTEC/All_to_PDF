# Risk register

## R-01 — Layout quality chưa có benchmark chung

- **Mức:** cao.
- **Trạng thái:** mở.
- **Giảm thiểu:** M3 quality engine + M4 corpus/benchmark; không publish output chỉ vì PDF mở được.

## R-02 — Chữ bị co xuống mức không đọc được

- **Mức:** cao.
- **Trạng thái:** mở.
- **Giảm thiểu:** `MIN_READABLE_SCALE`, box expansion có collision check, source fallback hoặc `NEEDS_REVIEW`.

## R-03 — Placeholder bị mất/đảo/thêm

- **Mức:** cao.
- **Trạng thái:** giảm một phần.
- **Giảm thiểu hiện có:** provider-level protected-token validator và bridge error mapping.
- **Còn thiếu:** kiểm tra report sau BabelDOC translation và corpus formula/rich-text thật.

## R-04 — Untrusted PDF gây crash/OOM hoặc path abuse

- **Mức:** cao.
- **Trạng thái:** giảm một phần.
- **Giảm thiểu hiện có:** upload size/signature guard, workspace path confinement, child-process isolation, timeout/terminate/kill, non-root container.
- **Còn thiếu:** sandbox/seccomp, decompression limits, malware scan và engine-image threat model.

## R-05 — Provider cost/quota ngoài dự kiến

- **Mức:** trung bình–cao.
- **Trạng thái:** giảm một phần.
- **Giảm thiểu:** Azure mặc định, paid LLM fallback opt-in, profile-managed secrets, typed quota/rate-limit errors.
- **Còn thiếu:** shared cache, budget ledger và tenant quotas.

## R-06 — AGPL nghĩa vụ khi cung cấp dịch vụ mạng

- **Mức:** cao.
- **Trạng thái:** mở / release blocker.
- **Giảm thiểu:** legal review trước public production; giữ upstream pins và patch inventory.

## R-07 — In-memory state mất khi restart

- **Mức:** cao.
- **Trạng thái:** mở.
- **Giảm thiểu kế hoạch:** PostgreSQL, Redis-compatible queue và S3 trong M2.

## R-08 — Job được queue nhưng không có consumer

- **Mức:** cao.
- **Trạng thái:** giảm cho local, mở cho production.
- **Giảm thiểu hiện có:** embedded worker option và queue-consumer contract.
- **Còn thiếu:** worker service độc lập, durable queue, heartbeat và recovery.

## R-09 — UI chưa được manual visual review

- **Mức:** trung bình.
- **Trạng thái:** mở; giữ PR #1 ở draft.
- **Giảm thiểu:** browser review desktop/tablet/mobile và Playwright states.

## R-10 — Upstream dependency conflict

- **Mức:** cao.
- **Trạng thái:** mở đến khi live smoke pass.
- **Bằng chứng:** selected PDFMathTranslate-next commit khai báo `pymupdf<1.25.3`; BabelDOC 0.6.4 cần `pymupdf>=1.26.7`.
- **Giảm thiểu hiện tại:** BabelDOC sở hữu PDF dependency graph; PDFMathTranslate-next được cài `--no-deps` và chỉ dùng translator contract.
- **Release gate:** worker image phải cài được và chạy fixture thật.

## R-11 — Deterministic tests không thay thế live BabelDOC run

- **Mức:** cao.
- **Trạng thái:** mở.
- **Giảm thiểu:** M1.1 engine smoke bằng pinned commits, real text-layer PDF và output text assertion.

## R-12 — JSONL child protocol drift

- **Mức:** trung bình.
- **Trạng thái:** giảm một phần.
- **Giảm thiểu:** schema version, allowed statuses, strict unknown-event rejection, output-path equality check và protocol tests.
- **Còn thiếu:** compatibility ADR khi schema version tăng.
