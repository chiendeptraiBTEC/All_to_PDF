# Contributing

Đọc theo thứ tự:

1. `docs/memory/CONTEXT.md`
2. `docs/memory/PROGRESS.md`
3. `docs/memory/NEXT.md`
4. `docs/engineering/WORKFLOW.md`
5. `docs/engineering/QUALITY_GATES.md`

Mọi thay đổi phải đi qua branch và pull request. Không commit trực tiếp vào `main`.

Trước khi mở PR:

```bash
make check
```

PR phải cập nhật `docs/memory/PROGRESS.md` và `docs/memory/NEXT.md` nếu trạng thái dự án thay đổi. Quyết định kiến trúc không hiển nhiên phải có ADR trong `docs/`.
