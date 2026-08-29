from pathlib import Path

from fastapi.testclient import TestClient

from all_to_pdf.bootstrap import build_container
from all_to_pdf.config import Settings
from all_to_pdf.main import create_app


def build_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        web_directory=tmp_path / "missing-web",
        local_storage_directory=tmp_path / "storage",
        max_upload_bytes=1024 * 1024,
    )
    return TestClient(create_app(container=build_container(settings)))


def test_upload_submit_get_and_cancel_flow(tmp_path: Path) -> None:
    client = build_client(tmp_path)

    upload = client.post(
        "/v1/uploads",
        files={"file": ("paper.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
    )
    assert upload.status_code == 201
    object_key = upload.json()["object_key"]

    submit = client.post(
        "/v1/pdf-translations",
        json={
            "input_object_key": object_key,
            "source_language": "en",
            "target_language": "vi",
            "translator_profile": "azure_nmt",
            "idempotency_key": "integration-test-key",
            "allow_paid_fallback": False,
        },
    )
    assert submit.status_code == 202
    job = submit.json()
    assert job["status"] == "queued"

    fetched = client.get(f"/v1/pdf-translations/{job['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == job["id"]

    cancelled = client.post(f"/v1/pdf-translations/{job['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_upload_rejects_non_pdf_content(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    response = client.post(
        "/v1/uploads",
        files={"file": ("fake.pdf", b"not a pdf", "application/pdf")},
    )
    assert response.status_code == 415


def test_submit_requires_llm_profile_id(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    response = client.post(
        "/v1/pdf-translations",
        json={
            "input_object_key": "uploads/input.pdf",
            "source_language": "en",
            "target_language": "vi",
            "translator_profile": "openai_compatible_llm",
            "idempotency_key": "integration-test-key",
        },
    )
    assert response.status_code == 422


def test_health_and_provider_configuration(tmp_path: Path) -> None:
    settings = Settings(
        web_directory=tmp_path / "missing-web",
        local_storage_directory=tmp_path / "storage",
        azure_translator_api_key="azure-secret",
        llm_base_url="https://llm.example/v1",
        llm_api_key="llm-secret",
        llm_model="model-1",
    )
    client = TestClient(create_app(container=build_container(settings)))

    assert client.get("/health/live").json() == {"status": "ok"}
    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"

    providers = {item["id"]: item for item in client.get("/v1/providers").json()}
    assert providers["azure_nmt"]["configured"] is True
    assert providers["openai_compatible_llm"]["configured"] is True


def test_missing_job_returns_404(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    assert client.get("/v1/pdf-translations/missing").status_code == 404
    assert client.post("/v1/pdf-translations/missing/cancel").status_code == 404


def test_upload_rejects_wrong_extension_and_too_large(tmp_path: Path) -> None:
    settings = Settings(
        web_directory=tmp_path / "missing-web",
        local_storage_directory=tmp_path / "storage",
        max_upload_bytes=1024,
    )
    client = TestClient(create_app(container=build_container(settings)))

    wrong_extension = client.post(
        "/v1/uploads",
        files={"file": ("notes.txt", b"%PDF-1.4", "text/plain")},
    )
    assert wrong_extension.status_code == 415

    too_large = client.post(
        "/v1/uploads",
        files={"file": ("large.pdf", b"%PDF-1.4" + b"x" * 2048, "application/pdf")},
    )
    assert too_large.status_code == 413


def test_submit_same_idempotency_key_returns_same_job(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    payload = {
        "input_object_key": "uploads/input.pdf",
        "source_language": "en",
        "target_language": "vi",
        "translator_profile": "azure_nmt",
        "idempotency_key": "same-integration-key",
    }

    first = client.post("/v1/pdf-translations", json=payload)
    second = client.post("/v1/pdf-translations", json=payload)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
