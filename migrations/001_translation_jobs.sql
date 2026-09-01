CREATE TABLE IF NOT EXISTS translation_jobs (
    id TEXT PRIMARY KEY,
    input_object_key TEXT NOT NULL,
    source_language TEXT NOT NULL,
    target_language TEXT NOT NULL,
    translator_profile TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    allow_paid_fallback BOOLEAN NOT NULL,
    llm_profile_id TEXT,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    progress_percent DOUBLE PRECISION NOT NULL,
    progress_stage TEXT,
    output_object_key TEXT,
    failure_code TEXT,
    failure_message TEXT,
    revision BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_translation_jobs_status_updated
ON translation_jobs(status, updated_at);
