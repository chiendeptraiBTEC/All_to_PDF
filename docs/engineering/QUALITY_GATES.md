# Quality gates

Không merge khi một hard gate thất bại.

## Source gate

- Ruff lint và format check.
- Mypy strict.
- Không secret trong repository.
- Dependency pin theo range/commit được duyệt.

## Test gate

- Unit + integration pass.
- Branch coverage tối thiểu 85% cho foundation; module critical hướng tới 95%.
- Provider test không gọi Internet; dùng mock transport.
- Bug fix phải có regression test.

## Build gate

- Python package build được.
- Docker image build được và chạy non-root.
- `node --check frontend/app.js` pass.
- Healthcheck trả đúng.

## Product gate

- Upload, validation, submit, get và cancel chạy end-to-end.
- Error message không lộ secret/internal stack.
- UI dùng được bằng keyboard và ở chiều rộng 360 px.

## PDF production gate — áp dụng từ M3

- PDF mở bằng hai parser.
- Page count/box đúng.
- Placeholder integrity 100%.
- Không overflow ngoài tolerance.
- Không paragraph dưới readability threshold mà không fallback/review.
- Image/vector/link inventory không mất bất thường.
