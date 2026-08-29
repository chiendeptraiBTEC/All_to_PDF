# User flows

## Dịch bằng Azure mặc định

```text
Mở studio
-> chọn/thả PDF
-> hệ thống upload và kiểm tra chữ ký PDF
-> chọn hướng dịch
-> giữ Azure Translator
-> tạo job
-> theo dõi pipeline
-> tải output khi SUCCEEDED
```

## Dịch bằng LLM profile

```text
Chọn OpenAI-compatible
-> nhập llm_profile_id đã được quản trị viên cấp
-> không nhập API key
-> tạo job
-> placeholder validation chạy trước khi typesetting
```

## Hết quota

```text
Azure trả quota/rate limit
-> retry theo policy
-> nếu allow_paid_fallback=false: FAILED_RETRYABLE/chờ quota
-> nếu true: worker có thể dùng LLM cho unit chưa hoàn thành
-> không trộn provider trong cùng paragraph
```
