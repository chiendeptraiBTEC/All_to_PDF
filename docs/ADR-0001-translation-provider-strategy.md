# ADR-0001 — Chiến lược nhà cung cấp dịch

**Trạng thái:** ACCEPTED  
**Ngày:** 2026-08-29  
**Phạm vi:** All_to_PDF production v1  
**Liên quan:** [Kiến trúc production](../README.md)

## 1. Quyết định

Hệ thống cung cấp hai lựa chọn dịch:

1. **Mặc định: Azure AI Translator — Text Translation, SKU F0/S1.**
2. **Tùy chọn: LLM tương thích OpenAI API**, cấu hình bằng `base_url`, `api_key` và `model`.

Không tự động chuyển từ Azure sang LLM nếu người dùng chưa bật `allow_paid_fallback`, vì LLM có thể phát sinh chi phí và cho kết quả ít ổn định hơn NMT.

```text
translator_profile = azure_nmt                 # mặc định
translator_profile = openai_compatible_llm    # người dùng chủ động chọn
```

## 2. Vì sao chọn Azure Translator làm provider chính

### Dữ kiện đã xác minh

- Azure Translator F0 cấp **2 triệu ký tự mỗi tháng miễn phí** cho standard translation. Nguồn: [Azure Translator pricing](https://azure.microsoft.com/en-gb/pricing/details/translator/).
- Free tier không hết hạn và mỗi Azure subscription có một F0 resource. Nguồn: [Create and configure Azure resources for Translator](https://learn.microsoft.com/azure/ai-services/translator/how-to/create-translator-resource).
- Azure Translator hỗ trợ English và Vietnamese (`vi`) cho cloud text translation. Nguồn: [Azure Translator language support](https://learn.microsoft.com/azure/ai-services/translator/language-support).
- F0 không hỗ trợ Document Translation đầy đủ, nhưng pipeline này **không gửi nguyên PDF cho Azure**. BabelDOC tách paragraph rồi gọi **Text Translation**, nên giới hạn đó không cản trở kiến trúc.
- API chính thức hỗ trợ key/region và global endpoint `https://api.cognitive.microsofttranslator.com`. Nguồn: [Translator authentication](https://learn.microsoft.com/azure/ai-services/translator/text-translation/reference/authentication) và [Translator V3 reference](https://learn.microsoft.com/azure/ai-services/translator/text-translation/reference/v3/reference).

### Lý do kiến trúc

- Hạn mức miễn phí cao hơn Google Cloud Translation NMT: Google hiện miễn phí 500.000 ký tự/tháng dưới dạng credit, sau đó tính phí. Nguồn: [Google Cloud Translation pricing](https://cloud.google.com/products/translate/pricing).
- Là API chính thức, có quota, key rotation, region, retry semantics và tài liệu production.
- Phù hợp workload paragraph ngắn của BabelDOC.
- PDFMathTranslate-next đã có `AzureTranslator` tại [`pdf2zh_next/translator/translator_impl/azure.py`](https://github.com/PDFMathTranslate-next/PDFMathTranslate-next/blob/f8dffcf4c3a33b254391d43514439b975ce8d966/pdf2zh_next/translator/translator_impl/azure.py).

### Điều chưa được chứng minh

Chất lượng English → Vietnamese của Azure so với Google, DeepL và LLM trên corpus PDF của dự án là **CHƯA XÁC MINH**. Azure được chọn mặc định vì quota miễn phí, API chính thức và khả năng vận hành; không tuyên bố đây là engine có BLEU/COMET hoặc đánh giá con người tốt nhất.

## 3. Vì sao không chọn Google làm mặc định

Google Cloud Translation NMT là dịch vụ chính thức và đáng tin, nhưng quota miễn phí hiện là 500.000 ký tự/tháng; phần vượt quota có giá niêm yết 20 USD cho mỗi một triệu ký tự. Nguồn: [Google Cloud Translation pricing](https://cloud.google.com/products/translate/pricing).

Quan trọng: adapter `GoogleTranslator` có sẵn trong PDFMathTranslate-next **không phải Google Cloud Translation API**. File [`translator_impl/google.py::GoogleTranslator`](https://github.com/PDFMathTranslate-next/PDFMathTranslate-next/blob/f8dffcf4c3a33b254391d43514439b975ce8d966/pdf2zh_next/translator/translator_impl/google.py):

- gọi trang mobile `https://translate.google.com/m`;
- parse HTML bằng regex;
- cắt đầu vào bằng `text[:5000]`;
- không dùng Google Cloud credential/quota contract.

**Quyết định:** không sử dụng adapter này trong production. Nếu sau này thêm Google, phải viết adapter riêng cho Google Cloud Translation API chính thức.

## 4. Vì sao không chọn DeepL Free làm mặc định

DeepL từng cho API Free 500.000 ký tự/tháng, nhưng tài liệu hiện tại ghi gói API Free không còn được bán/đăng ký mới. Nguồn: [DeepL API plans](https://support.deepl.com/hc/en-us/articles/360021200939-DeepL-API-plans).

DeepL có hỗ trợ Vietnamese trong API hiện tại, nhưng khả năng truy cập theo plan/model và chất lượng trên corpus dự án vẫn **CHƯA XÁC MINH**. Do đó DeepL không phải dependency mặc định của v1.

## 5. Patch bắt buộc cho Azure adapter upstream

Adapter upstream hiện có vấn đề production:

```python
self.client = TextTranslationClient(
    endpoint=endpoint,
    credential=credential,
    region="chinaeast2",
)
```

Nguồn: [`azure.py::AzureTranslator.__init__`](https://github.com/PDFMathTranslate-next/PDFMathTranslate-next/blob/f8dffcf4c3a33b254391d43514439b975ce8d966/pdf2zh_next/translator/translator_impl/azure.py).

Ngoài ra cấu hình upstream mặc định dùng endpoint Azure China. Hai giá trị này không đúng cho Azure public cloud toàn cầu.

### Yêu cầu triển khai

Tạo adapter của dự án hoặc patch upstream để nhận:

```yaml
azure_translator:
  endpoint: https://api.cognitive.microsofttranslator.com
  api_key_secret: azure-translator-key
  region: southeastasia
  source_language: en
  target_language: vi
  request_timeout_seconds: 15
  max_attempts: 5
```

Quy tắc:

- `region` lấy từ Azure resource, không khóa cứng.
- Với global resource, region có thể được bỏ trống theo tài liệu Azure; với regional/multi-service resource phải gửi đúng region.
- API key chỉ đọc từ secret manager.
- Không ghi API key hoặc toàn văn paragraph vào log.
- Phân loại riêng `401/403`, `429`, `5xx`, timeout và invalid request.
- `429/5xx/timeout` dùng exponential backoff + jitter; lỗi xác thực không retry mù quáng.
- Ghi usage theo số ký tự nguồn trước khi request.

## 6. Lựa chọn LLM tương thích OpenAI

PDFMathTranslate-next đã hỗ trợ trực tiếp:

- `openai_base_url`;
- `openai_api_key`;
- `openai_model`;
- timeout;
- temperature;
- reasoning effort;
- JSON mode.

Nguồn:

- [`translator_impl/openai.py::OpenAITranslator`](https://github.com/PDFMathTranslate-next/PDFMathTranslate-next/blob/f8dffcf4c3a33b254391d43514439b975ce8d966/pdf2zh_next/translator/translator_impl/openai.py)
- [`config/translate_engine_model.py::OpenAISettings`](https://github.com/PDFMathTranslate-next/PDFMathTranslate-next/blob/f8dffcf4c3a33b254391d43514439b975ce8d966/pdf2zh_next/config/translate_engine_model.py)

Adapter dùng `openai.OpenAI(base_url=..., api_key=...)` và gọi `client.chat.completions.create(...)`, nên có thể kết nối OpenAI hoặc dịch vụ khác triển khai API tương thích.

### Cấu hình hợp đồng của dự án

```yaml
openai_compatible_llm:
  base_url: https://provider.example.com/v1
  api_key_secret: llm-provider-key
  model: provider-model-id
  timeout_seconds: 60
  temperature: 0
  json_mode: false
  max_attempts: 5
```

Environment mapping:

```text
LLM_BASE_URL
LLM_API_KEY
LLM_MODEL
LLM_TIMEOUT_SECONDS
LLM_TEMPERATURE
LLM_JSON_MODE
```

### Quy tắc LLM

- Prompt phải yêu cầu chỉ trả về bản dịch, không giải thích.
- Formula placeholder, rich-text tag, code, identifier và token bảo vệ phải giữ nguyên.
- Mọi response phải qua placeholder validation của BabelDOC trước khi dùng.
- Tắt chain-of-thought/reasoning output nếu provider hỗ trợ.
- `temperature = 0` khi API hỗ trợ để giảm biến động.
- Cache key phải chứa `base_url host`, `model`, `prompt_version`, `glossary_version` và placeholder schema version.
- Không tự động fallback sang LLM khi Azure hết quota nếu request không có `allow_paid_fallback=true`.

## 7. Provider selection contract

Request API:

```json
{
  "translator_profile": "azure_nmt",
  "allow_paid_fallback": false
}
```

Hoặc:

```json
{
  "translator_profile": "openai_compatible_llm",
  "llm_profile_id": "tenant-default"
}
```

Không nhận raw API key trong request dịch. Người quản trị tạo `llm_profile_id`; key được lưu trong secret manager.

### State và reason code

```text
PROVIDER_QUOTA_EXCEEDED
PROVIDER_RATE_LIMITED
PROVIDER_AUTH_FAILED
PROVIDER_TIMEOUT
PROVIDER_INVALID_RESPONSE
PLACEHOLDER_VALIDATION_FAILED
```

- Azure quota hết và không cho fallback: job chuyển `FAILED_RETRYABLE` hoặc chờ quota window mới.
- Azure quota hết và `allow_paid_fallback=true`: có thể chạy lại các translation unit chưa hoàn thành bằng LLM.
- Không trộn output của hai provider trong cùng paragraph.
- Báo cáo cuối phải ghi provider/model được dùng cho từng translation unit hoặc tối thiểu từng page.

## 8. Provider interface nội bộ

```python
class TranslationProvider(Protocol):
    provider_id: str

    def translate_batch(
        self,
        units: list[TranslationUnit],
        source_language: str,
        target_language: str,
        context: TranslationContext,
    ) -> list[TranslationResult]: ...

    def healthcheck(self) -> ProviderHealth: ...
```

`TranslationResult` tối thiểu gồm:

```text
unit_id
translated_text
provider_id
model_id
cache_hit
latency_ms
input_characters hoặc token usage
placeholder_valid
```

## 9. Acceptance criteria riêng cho provider

Trước production phải benchmark Azure và ít nhất một LLM trên cùng corpus English → Vietnamese:

- placeholder integrity = 100% đối với output được publish;
- thuật ngữ chuyên ngành và công thức không bị thay đổi;
- đánh giá con người về adequacy, fluency và terminology;
- p50/p95 latency;
- tỷ lệ retry và lỗi;
- chi phí trên một triệu ký tự hoặc một tài liệu;
- tỷ lệ paragraph dài thêm gây scale thấp sau typesetting.

Chất lượng dịch, QPS tối ưu và giới hạn worker cụ thể tiếp tục được ghi **CHƯA XÁC MINH** cho đến khi benchmark hoàn tất.

## 10. Kết luận triển khai

```text
DEFAULT_PROVIDER = azure_nmt
OPTIONAL_PROVIDER = openai_compatible_llm
UNOFFICIAL_GOOGLE_ADAPTER = disabled
AUTOMATIC_PAID_FALLBACK = disabled by default
```

Azure F0 phù hợp để bắt đầu và thử nghiệm production nhỏ nhờ 2 triệu ký tự miễn phí mỗi tháng. Khi lưu lượng vượt quota, chuyển Azure resource sang S1 hoặc cho tenant chủ động chọn LLM; không phụ thuộc vào endpoint dịch miễn phí không chính thức.
