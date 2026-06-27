from __future__ import annotations

import os
import tempfile
from pathlib import Path
from uuid import uuid4


def pytest_configure(config):
    root = Path(__file__).resolve().parent
    temp_root = root / ".pytest-temp"
    temp_root.mkdir(exist_ok=True)
    run_root = temp_root / f"run-{uuid4().hex}"
    os.environ["TMP"] = str(temp_root)
    os.environ["TEMP"] = str(temp_root)
    tempfile.tempdir = str(temp_root)
    config.option.basetemp = str(run_root)
