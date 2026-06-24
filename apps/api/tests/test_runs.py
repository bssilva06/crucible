from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from crucible_api.main import app
from crucible_api.services.run_service import reset_run_service_for_tests
from crucible_api.settings import ApiSettings


def _settings(tmp_path: Path) -> ApiSettings:
    return ApiSettings(
        root=tmp_path,
        config_root=Path("configs"),
        local_storage_root=tmp_path / "storage",
        cors_origins=["http://localhost:3000"],
        dry_run_default=True,
        allow_dry_run=True,
        max_prompt_chars=80,
    )


def test_health_does_not_expose_secrets() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "ok", "service": "crucible-api"}
    assert "key" not in str(body).lower()


def test_create_and_fetch_dry_run(tmp_path: Path) -> None:
    reset_run_service_for_tests(_settings(tmp_path))
    client = TestClient(app)

    create = client.post("/runs", json={"prompt": "Centered bottle on white", "dry_run": True})

    assert create.status_code == 200
    created = create.json()
    assert created["status"] == "COMPLETED"
    assert created["verification_status"] == "verified"
    assert created["provider"] == "dry-run"

    fetched = client.get(f"/runs/{created['run_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["run_id"] == created["run_id"]


def test_asset_proxy_returns_image(tmp_path: Path) -> None:
    reset_run_service_for_tests(_settings(tmp_path))
    client = TestClient(app)

    created = client.post("/runs", json={"prompt": "Centered bottle on white", "dry_run": True}).json()
    asset = client.get(f"/runs/{created['run_id']}/asset")

    assert asset.status_code == 200
    assert asset.headers["content-type"].startswith("image/png")
    assert asset.content.startswith(b"\x89PNG")


def test_rejects_long_prompt(tmp_path: Path) -> None:
    reset_run_service_for_tests(_settings(tmp_path))
    client = TestClient(app)

    response = client.post("/runs", json={"prompt": "x" * 81, "dry_run": True})

    assert response.status_code == 400
    assert "80 characters or fewer" in response.json()["detail"]


def test_missing_run_returns_404(tmp_path: Path) -> None:
    reset_run_service_for_tests(_settings(tmp_path))
    client = TestClient(app)

    response = client.get("/runs/run_missing")

    assert response.status_code == 404
