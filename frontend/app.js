const state = {
  uploadedObjectKey: null,
  activeJob: null,
  pollTimer: null,
};

const elements = {
  form: document.querySelector("#translation-form"),
  fileInput: document.querySelector("#pdf-file"),
  dropZone: document.querySelector("#drop-zone"),
  fileLedger: document.querySelector("#file-ledger"),
  fileName: document.querySelector("#file-name"),
  fileSize: document.querySelector("#file-size"),
  objectKey: document.querySelector("#object-key"),
  submitButton: document.querySelector("#submit-button"),
  formMessage: document.querySelector("#form-message"),
  sourceLanguage: document.querySelector("#source-language"),
  targetLanguage: document.querySelector("#target-language"),
  llmProfileField: document.querySelector("#llm-profile-field"),
  llmProfileId: document.querySelector("#llm-profile-id"),
  paidFallback: document.querySelector("#paid-fallback"),
  systemStatus: document.querySelector("#system-status"),
  systemPulse: document.querySelector(".pulse"),
  azureState: document.querySelector("#azure-state"),
  llmState: document.querySelector("#llm-state"),
  emptyJob: document.querySelector("#empty-job"),
  activeJobPanel: document.querySelector("#active-job"),
  jobId: document.querySelector("#job-id"),
  jobStatusBadge: document.querySelector("#job-status-badge"),
  timeline: document.querySelector("#job-timeline"),
  cancelJob: document.querySelector("#cancel-job"),
  outputLink: document.querySelector("#output-link"),
};

const statusOrder = [
  "queued",
  "preflight",
  "parsing",
  "translating",
  "typesetting",
  "generating_pdf",
  "quality_check",
  "succeeded",
];

function formatBytes(value) {
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  return `${(value / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function selectedProvider() {
  return document.querySelector('input[name="translator_profile"]:checked').value;
}

function updateSubmitState() {
  const llmIsValid =
    selectedProvider() !== "openai_compatible_llm" || elements.llmProfileId.value.trim();
  elements.submitButton.disabled = !state.uploadedObjectKey || !llmIsValid;
}

function showMessage(message, kind = "error") {
  elements.formMessage.textContent = message;
  elements.formMessage.style.color = kind === "success" ? "var(--green)" : "var(--red)";
}

async function readJson(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(payload.detail)
      ? payload.detail.map((item) => item.msg).join("; ")
      : payload.detail;
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return payload;
}

async function checkSystem() {
  try {
    const health = await readJson(await fetch("/health/ready"));
    elements.systemStatus.textContent = "Hệ thống sẵn sàng";
    elements.systemPulse.classList.add("ready");
    elements.systemPulse.classList.remove("failed");
    return health;
  } catch (error) {
    elements.systemStatus.textContent = "Hệ thống chưa sẵn sàng";
    elements.systemPulse.classList.add("failed");
    console.error(error);
  }
}

function setProviderState(element, configured) {
  element.textContent = configured ? "Đã cấu hình" : "Chưa cấu hình";
  element.classList.toggle("ready", configured);
  element.classList.toggle("missing", !configured);
}

async function loadProviders() {
  try {
    const providers = await readJson(await fetch("/v1/providers"));
    const azure = providers.find((provider) => provider.id === "azure_nmt");
    const llm = providers.find((provider) => provider.id === "openai_compatible_llm");
    setProviderState(elements.azureState, Boolean(azure?.configured));
    setProviderState(elements.llmState, Boolean(llm?.configured));
  } catch (error) {
    setProviderState(elements.azureState, false);
    setProviderState(elements.llmState, false);
    console.error(error);
  }
}

async function uploadPdf(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    showMessage("Chỉ chấp nhận tệp PDF.");
    return;
  }

  state.uploadedObjectKey = null;
  updateSubmitState();
  elements.fileLedger.hidden = false;
  elements.fileName.textContent = file.name;
  elements.fileSize.textContent = formatBytes(file.size);
  elements.objectKey.textContent = "Đang tải lên…";
  showMessage("Đang tải PDF lên kho tạm…", "success");

  const body = new FormData();
  body.append("file", file);

  try {
    const uploaded = await readJson(
      await fetch("/v1/uploads", {
        method: "POST",
        body,
      }),
    );
    state.uploadedObjectKey = uploaded.object_key;
    elements.objectKey.textContent = uploaded.object_key;
    elements.fileSize.textContent = formatBytes(uploaded.size_bytes);
    showMessage("PDF đã được tiếp nhận. Có thể tạo job.", "success");
  } catch (error) {
    elements.objectKey.textContent = "Tải lên thất bại";
    showMessage(error.message);
  } finally {
    updateSubmitState();
  }
}

function renderJob(job) {
  state.activeJob = job;
  elements.emptyJob.hidden = true;
  elements.activeJobPanel.hidden = false;
  elements.jobId.textContent = job.id;
  elements.jobStatusBadge.textContent = job.status.toUpperCase();

  const currentIndex = statusOrder.indexOf(job.status);
  const terminalFailure = [
    "cancelled",
    "ocr_required",
    "needs_review",
    "failed_retryable",
    "failed_permanent",
  ].includes(job.status);

  for (const item of elements.timeline.querySelectorAll("li")) {
    const index = statusOrder.indexOf(item.dataset.status);
    item.classList.toggle("complete", !terminalFailure && currentIndex >= 0 && index < currentIndex);
    item.classList.toggle("current", item.dataset.status === job.status);
  }

  elements.cancelJob.hidden = [
    "succeeded",
    "cancelled",
    "ocr_required",
    "needs_review",
    "failed_retryable",
    "failed_permanent",
  ].includes(job.status);

  if (job.status === "succeeded" && job.output_object_key) {
    elements.outputLink.href = `/v1/pdf-translations/${job.id}/artifacts/output`;
    elements.outputLink.hidden = false;
  } else {
    elements.outputLink.hidden = true;
  }

  if (terminalFailure && job.failure_message) {
    showMessage(`${job.failure_code || job.status}: ${job.failure_message}`);
  }
}

async function pollJob(jobId) {
  clearTimeout(state.pollTimer);
  try {
    const job = await readJson(await fetch(`/v1/pdf-translations/${jobId}`));
    renderJob(job);
    const terminal = [
      "succeeded",
      "cancelled",
      "ocr_required",
      "needs_review",
      "failed_retryable",
      "failed_permanent",
    ].includes(job.status);
    if (!terminal) {
      state.pollTimer = setTimeout(() => pollJob(jobId), 2000);
    }
  } catch (error) {
    showMessage(`Không đọc được trạng thái job: ${error.message}`);
  }
}

for (const radio of document.querySelectorAll('input[name="translator_profile"]')) {
  radio.addEventListener("change", () => {
    elements.llmProfileField.hidden = selectedProvider() !== "openai_compatible_llm";
    updateSubmitState();
  });
}

elements.llmProfileId.addEventListener("input", updateSubmitState);
elements.fileInput.addEventListener("change", () => uploadPdf(elements.fileInput.files[0]));

for (const eventName of ["dragenter", "dragover"]) {
  elements.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    elements.dropZone.classList.add("is-dragging");
  });
}

for (const eventName of ["dragleave", "drop"]) {
  elements.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    elements.dropZone.classList.remove("is-dragging");
  });
}

elements.dropZone.addEventListener("drop", (event) => {
  const file = event.dataTransfer.files[0];
  uploadPdf(file);
});

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.uploadedObjectKey) return;

  elements.submitButton.disabled = true;
  showMessage("Đang tạo translation job…", "success");

  const provider = selectedProvider();
  const request = {
    input_object_key: state.uploadedObjectKey,
    source_language: elements.sourceLanguage.value,
    target_language: elements.targetLanguage.value,
    translator_profile: provider,
    idempotency_key: crypto.randomUUID(),
    allow_paid_fallback: elements.paidFallback.checked,
    llm_profile_id:
      provider === "openai_compatible_llm" ? elements.llmProfileId.value.trim() : null,
  };

  try {
    const job = await readJson(
      await fetch("/v1/pdf-translations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      }),
    );
    renderJob(job);
    showMessage("Job đã vào hàng đợi.", "success");
    pollJob(job.id);
  } catch (error) {
    showMessage(error.message);
  } finally {
    updateSubmitState();
  }
});

elements.cancelJob.addEventListener("click", async () => {
  if (!state.activeJob) return;
  try {
    const job = await readJson(
      await fetch(`/v1/pdf-translations/${state.activeJob.id}/cancel`, { method: "POST" }),
    );
    renderJob(job);
    showMessage("Job đã được hủy.", "success");
  } catch (error) {
    showMessage(error.message);
  }
});

checkSystem();
loadProviders();
