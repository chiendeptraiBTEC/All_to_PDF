# Handoff

## Hiện trạng bàn giao

- Branch: `feat/m1-babeldoc-runner`
- Draft PR: [#2](https://github.com/chiendeptraiBTEC/All_to_PDF/pull/2)
- Base: `feat/production-foundation`
- Verified code gate: `7af93844531a287f8c6e7c0cc9f043426f7e9ef6`
- Verified workflow: [`33243746819`](https://github.com/chiendeptraiBTEC/All_to_PDF/actions/runs/33243746819)

## Điều đã chạy được và được test

- job queue consumer → worker → fake engine → quality gate → atomic output publish;
- progress/status updates và failure classifications;
- subprocess JSONL success/error/timeout/malformed/nonzero-exit paths;
- engine bridge orchestration với fake BabelDOC/PDFMath modules;
- Azure/LLM provider factory;
- basic structural PDF gate;
- API/UI regression suite từ M0;
- Docker base image và non-root runtime.

## Điều chưa được chứng minh

- selected upstream commits cài và chạy cùng nhau trong worker image;
- real BabelDOC layout/model/assets trên fixture PDF;
- text tiếng Việt thật trong mono output;
- Azure credential path end-to-end;
- layout quality, readability, tables/formulas và resource usage.

## Local commands

```bash
python -m pip install -e ".[dev]"
make check
```

Cài engine nặng:

```bash
./scripts/install_pdf_engine.sh
```

Chạy API local không worker:

```bash
make run
```

Chạy local với embedded worker sau khi engine đã cài:

```bash
ATP_EMBEDDED_WORKER_ENABLED=true \
ATP_AZURE_TRANSLATOR_API_KEY=... \
uvicorn all_to_pdf.main:app --app-dir backend/src --reload
```

## Quy tắc tiếp tục

1. Đọc `CONTEXT.md`, `PROGRESS.md`, `NEXT.md`, `RISKS.md`.
2. Không merge PR #2 trước live engine smoke.
3. Không ghi credential vào Git, manifest hoặc command arguments.
4. Không hạ coverage gate; test behavior mới.
5. Mọi tuyên bố hoàn thành phải trỏ tới CI run/artifact.
