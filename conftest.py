from __future__ import annotations

import os
import tempfile
from pathlib import Path


def pytest_configure(config):
    root = Path(__file__).resolve().parent
    temp_root = root / ".pytest-temp"
    temp_root.mkdir(exist_ok=True)
    os.environ["TMP"] = str(temp_root)
    os.environ["TEMP"] = str(temp_root)
    tempfile.tempdir = str(temp_root)
