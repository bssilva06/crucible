from __future__ import annotations

from pathlib import Path

import pytest

from crucible.phase0.brief import Brief
from crucible.phase0.config import ConfigError, Phase0Settings
from crucible.phase0.crypto import sha256_bytes
from crucible.phase0.env import load_dotenv
from crucible.phase0.generator import DryRunGenerator
from crucible.phase0.spine import persist_generated_asset, verify_manifest
from crucible.phase0.storage import LocalStorage, object_key


def test_sha256_bytes_is_stable() -> None:
    assert sha256_bytes(b"crucible") == "340d6bb972c2bc1eb7e627ff505ae4fa90c8de05ea0c9903da7c161942b13cec"


def test_object_key_uses_phase0_layout() -> None:
    assert object_key("run_123", "manifest.json") == "runs/local/run_123/manifest.json"


def test_require_b2_reports_missing_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [
        "B2_APPLICATION_KEY_ID",
        "B2_KEY_ID",
        "B2_APPLICATION_KEY",
        "B2_APP_KEY",
        "B2_APPLICATION_KEY_VALUE",
        "B2_SECRET_KEY",
        "B2_SECRET_ACCESS_KEY",
        "AWS_SECRET_ACCESS_KEY",
        "B2_BUCKET_NAME",
        "B2_ENDPOINT_URL",
    ]:
        monkeypatch.delenv(name, raising=False)

    settings = Phase0Settings.from_env()

    with pytest.raises(ConfigError, match="Missing required B2 environment variables"):
        settings.require_b2()


def test_env_aliases_for_b2_and_provider_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("B2_APPLICATION_KEY_ID", raising=False)
    monkeypatch.delenv("B2_APPLICATION_KEY", raising=False)
    monkeypatch.setenv("B2_KEY_ID", "key-id")
    monkeypatch.setenv("B2_APP_KEY", "app-key")
    monkeypatch.setenv("B2_BUCKET_NAME", "bucket")
    monkeypatch.setenv("B2_ENDPOINT_URL", "https://example.invalid")
    monkeypatch.setenv("GMI_API_KEY", "gmi-key")

    settings = Phase0Settings.from_env()

    assert settings.b2_application_key_id == "key-id"
    assert settings.b2_application_key == "app-key"
    assert settings.require_provider_key("GMICLOUD_API_KEY") == "gmi-key"


def test_load_dotenv_sets_missing_values_without_overriding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# comment",
                "CRUCIBLE_TEST_SECRET=from-file",
                "CRUCIBLE_TEST_EXISTING=from-file",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("CRUCIBLE_TEST_SECRET", raising=False)
    monkeypatch.setenv("CRUCIBLE_TEST_EXISTING", "from-env")

    load_dotenv(env_file)

    assert __import__("os").getenv("CRUCIBLE_TEST_SECRET") == "from-file"
    assert __import__("os").getenv("CRUCIBLE_TEST_EXISTING") == "from-env"


def test_dry_run_manifest_round_trip(tmp_path: Path) -> None:
    brief = Brief(
        brief_id="test-brief",
        prompt="Generate a centered product shot on white.",
    )
    generated = DryRunGenerator().generate(brief)
    storage = LocalStorage(tmp_path)

    result = persist_generated_asset(run_id="run_test", brief=brief, generated=generated, storage=storage)
    manifest = verify_manifest(storage=storage, run_id="run_test")

    assert result.asset_sha256 == manifest.asset_sha256
    assert manifest.asset_uri == result.asset_uri
    assert manifest.provider == "dry-run"


@pytest.mark.skipif(
    __import__("os").getenv("CRUCIBLE_RUN_LIVE_PROVIDER_TESTS", "false").lower() != "true",
    reason="live provider tests are opt-in",
)
def test_live_provider_tests_are_opt_in() -> None:
    assert True
