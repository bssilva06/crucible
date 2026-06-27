from __future__ import annotations

import os

import pytest


@pytest.mark.skipif(
    os.getenv("CRUCIBLE_RUN_LIVE_FANOUT_TESTS", "").lower() not in {"1", "true", "yes", "on"},
    reason="live fan-out tests are opt-in",
)
def test_live_fanout_tests_are_opt_in() -> None:
    pytest.skip("Live fan-out smoke should be run manually through the API until Phase 2 async progress lands.")
