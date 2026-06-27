from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from crucible.domain.evaluation import CriterionResult
from crucible.domain.rubric import EvaluatorKind
from crucible.judge.fake import FakeJudge
from crucible_api.main import app
from crucible_api.services import run_service as run_service_module
from crucible_api.services.run_service import reset_run_service_for_tests
from crucible_api.settings import ApiSettings


def _settings(tmp_path: Path) -> ApiSettings:
    return ApiSettings(
        root=tmp_path,
        config_root=Path.cwd() / "configs",
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
    assert created["evaluation_status"] == "FAILED"
    assert created["judge_status"] == "SKIPPED"
    assert created["candidate_count"] == 2
    assert len(created["candidates"]) == 2
    assert created["selected_attempt_id"] is None
    assert created["asset_uri"] is None
    assert created["failed_hard_gates"] == ["minimum_resolution"]
    assert created["verdict"]["passed"] is False
    assert created["verdict"]["criterion_failures"] == ["minimum_resolution"]
    assert "No eligible candidate" in created["verdict"]["feedback"]
    assert created["criterion_results"] == []
    assert created["provider"] is None

    fetched = client.get(f"/runs/{created['run_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["run_id"] == created["run_id"]


def test_asset_proxy_returns_image(tmp_path: Path, monkeypatch) -> None:
    reset_run_service_for_tests(_settings(tmp_path))
    monkeypatch.setattr(run_service_module, "run_deterministic_checks", _passing_deterministic_checks)
    monkeypatch.setattr(run_service_module, "build_judge", lambda _: FakeJudge())
    client = TestClient(app)
    created = _create_passing_run(client)

    asset = client.get(f"/runs/{created['run_id']}/asset")

    assert asset.status_code == 200
    assert asset.headers["content-type"].startswith("image/png")
    assert asset.content.startswith(b"\x89PNG")


def test_dry_run_includes_deterministic_gate_results(tmp_path: Path) -> None:
    reset_run_service_for_tests(_settings(tmp_path))
    client = TestClient(app)

    created = client.post("/runs", json={"prompt": "Centered bottle on white", "dry_run": True}).json()

    criterion_ids = [result["criterion_id"] for result in created["candidates"][0]["criterion_results"]]
    assert criterion_ids == [
        "file_integrity",
        "minimum_resolution",
        "aspect_ratio",
        "white_background_edges",
    ]
    assert created["candidates"][0]["criterion_results"][0]["passed"] is True
    assert "minimum_resolution" in created["failed_hard_gates"]
    assert created["judge_status"] == "SKIPPED"


def test_dry_run_verdict_preserves_completed_transport_status(tmp_path: Path) -> None:
    reset_run_service_for_tests(_settings(tmp_path))
    client = TestClient(app)

    created = client.post("/runs", json={"prompt": "Centered bottle on white", "dry_run": True}).json()

    assert created["status"] == "COMPLETED"
    assert created["evaluation_status"] == "FAILED"
    assert created["verdict"]["passed"] is False
    assert created["verdict"]["quality_score"] == 0.0
    assert created["verdict"]["confidence"] == 0.0


def test_dry_run_with_passing_fake_judge_can_pass_evaluation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    reset_run_service_for_tests(_settings(tmp_path))
    monkeypatch.setattr(run_service_module, "run_deterministic_checks", _passing_deterministic_checks)
    monkeypatch.setattr(run_service_module, "build_judge", lambda _: FakeJudge())
    client = TestClient(app)

    created = client.post("/runs", json={"prompt": "Centered bottle on white", "dry_run": True}).json()

    assert created["status"] == "COMPLETED"
    assert created["evaluation_status"] == "PASSED"
    assert created["judge_status"] == "PASSED"
    assert created["judge_provider"] == "fake"
    assert created["judge_model"] == "fake-vlm"
    assert created["failed_hard_gates"] == []
    assert created["verdict"]["passed"] is True
    assert created["verdict"]["confidence"] == 0.8
    assert len(created["criterion_results"]) == 9
    assert created["candidate_count"] == 2
    assert created["selected_attempt_id"] == "attempt_001"
    assert created["asset_uri"] == created["candidates"][0]["asset"]["uri"]


def test_dry_run_with_failing_fake_judge_populates_failed_gate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    reset_run_service_for_tests(_settings(tmp_path))
    monkeypatch.setattr(run_service_module, "run_deterministic_checks", _passing_deterministic_checks)
    monkeypatch.setattr(run_service_module, "build_judge", lambda _: FakeJudge(failing_ids={"product_centered"}))
    client = TestClient(app)

    created = client.post("/runs", json={"prompt": "Centered bottle on white", "dry_run": True}).json()

    assert created["status"] == "COMPLETED"
    assert created["evaluation_status"] == "FAILED"
    assert created["selected_attempt_id"] is None
    assert created["judge_status"] == "FAILED"
    assert created["failed_hard_gates"] == ["product_centered"]
    assert "No eligible candidate" in created["verdict"]["feedback"]


def test_missing_gemini_credentials_skip_judge_without_leaking_env_names(
    tmp_path: Path,
    monkeypatch,
) -> None:
    reset_run_service_for_tests(_settings(tmp_path))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(run_service_module, "run_deterministic_checks", _passing_deterministic_checks)
    client = TestClient(app)

    created = client.post("/runs", json={"prompt": "Centered bottle on white", "dry_run": True}).json()

    assert created["status"] == "COMPLETED"
    assert created["judge_status"] == "SKIPPED"
    assert created["selected_attempt_id"] is None
    assert "ai_judge_available" in created["failed_hard_gates"]
    assert "GEMINI_API_KEY" not in str(created)
    assert "GOOGLE_API_KEY" not in str(created)


def test_dry_run_best_of_two_selects_passing_candidate(tmp_path: Path, monkeypatch) -> None:
    reset_run_service_for_tests(_settings(tmp_path))
    monkeypatch.setattr(run_service_module, "run_deterministic_checks", _first_candidate_fails_second_passes)
    monkeypatch.setattr(run_service_module, "build_judge", lambda _: FakeJudge())
    client = TestClient(app)

    created = client.post("/runs", json={"prompt": "Centered bottle on white", "dry_run": True}).json()

    assert created["status"] == "COMPLETED"
    assert created["selected_attempt_id"] == "attempt_002"
    assert created["provider"] == "dry-run"
    assert created["asset_uri"] == created["candidates"][1]["asset"]["uri"]
    assert created["candidates"][0]["status"] == "REJECTED"
    assert created["candidates"][1]["status"] == "ELIGIBLE"


def test_candidate_asset_endpoint_returns_requested_candidate_image(tmp_path: Path, monkeypatch) -> None:
    reset_run_service_for_tests(_settings(tmp_path))
    monkeypatch.setattr(run_service_module, "run_deterministic_checks", _passing_deterministic_checks)
    monkeypatch.setattr(run_service_module, "build_judge", lambda _: FakeJudge())
    client = TestClient(app)

    created = client.post("/runs", json={"prompt": "Centered bottle on white", "dry_run": True}).json()
    asset = client.get(f"/runs/{created['run_id']}/candidates/attempt_002/asset")

    assert asset.status_code == 200
    assert asset.headers["content-type"].startswith("image/png")
    assert asset.content.startswith(b"\x89PNG")


def test_candidate_asset_endpoint_returns_rejected_candidate_image(tmp_path: Path) -> None:
    reset_run_service_for_tests(_settings(tmp_path))
    client = TestClient(app)

    created = client.post("/runs", json={"prompt": "Centered bottle on white", "dry_run": True}).json()
    asset = client.get(f"/runs/{created['run_id']}/candidates/attempt_001/asset")

    assert created["selected_attempt_id"] is None
    assert asset.status_code == 200
    assert asset.headers["content-type"].startswith("image/png")


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


def _passing_deterministic_checks(**_: object) -> list[CriterionResult]:
    return [
        CriterionResult(
            criterion_id="file_integrity",
            passed=True,
            score=1.0,
            hard_gate=True,
            evaluator=EvaluatorKind.DETERMINISTIC,
        ),
        CriterionResult(
            criterion_id="minimum_resolution",
            passed=True,
            score=1.0,
            hard_gate=True,
            evaluator=EvaluatorKind.DETERMINISTIC,
        ),
        CriterionResult(
            criterion_id="aspect_ratio",
            passed=True,
            score=1.0,
            hard_gate=True,
            evaluator=EvaluatorKind.DETERMINISTIC,
        ),
        CriterionResult(
            criterion_id="white_background_edges",
            passed=True,
            score=1.0,
            hard_gate=True,
            evaluator=EvaluatorKind.DETERMINISTIC,
        ),
    ]


def _first_candidate_fails_second_passes(**kwargs: object) -> list[CriterionResult]:
    asset_uri = str(kwargs.get("asset_uri", ""))
    if "attempt_001" in asset_uri:
        return [
            CriterionResult(
                criterion_id="minimum_resolution",
                passed=False,
                score=0.0,
                hard_gate=True,
                evaluator=EvaluatorKind.DETERMINISTIC,
            )
        ]
    return _passing_deterministic_checks(**kwargs)


def _create_passing_run(client: TestClient):
    return client.post("/runs", json={"prompt": "Centered bottle on white", "dry_run": True}).json()
