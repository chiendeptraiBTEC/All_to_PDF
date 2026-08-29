# System architecture

## Ranh giới

```text
HTTP/UI
  -> application use cases
      -> domain
      -> ports
          <- infrastructure adapters
```

### Domain

Chứa state machine, invariants và provider-neutral types. Không import framework.

### Application

Điều phối use case qua Protocol. Không biết dữ liệu được lưu trong RAM, PostgreSQL hay S3.

### Infrastructure

Triển khai ports: provider HTTP, storage, repository, queue và sau này BabelDOC runner.

### API

Chuyển HTTP request thành command; map lỗi domain/application sang status code. Không chứa business rule.

### UI

Thư mục riêng, không chứa secret và không biết chi tiết BabelDOC. Giao tiếp qua API contract.

## SOLID áp dụng

- **S:** Mỗi module có một trách nhiệm rõ.
- **O:** Thêm provider/storage/repository bằng adapter mới.
- **L:** Adapter phải tuân cùng contract và error semantics.
- **I:** Ports nhỏ theo use case, không tạo interface khổng lồ.
- **D:** Application phụ thuộc Protocol, không phụ thuộc implementation.
