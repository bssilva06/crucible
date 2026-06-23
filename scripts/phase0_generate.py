from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "packages" / "crucible-core" / "src"
sys.path.insert(0, str(SRC))

from crucible.phase0.config import ConfigError, Phase0Settings
from crucible.phase0.env import load_dotenv
from crucible.phase0.spine import build_generator, build_storage, run_phase0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Crucible Phase 0 generation and manifest spine.")
    parser.add_argument("--brief", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true", help="Use fake image bytes and local temp storage.")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    settings = Phase0Settings.from_env()
    local_root = ROOT / "tmp" / "phase0-storage"

    try:
        storage = build_storage(dry_run=args.dry_run, settings=settings, local_root=local_root)
        generator = build_generator(dry_run=args.dry_run, settings=settings, config_root=ROOT / "configs")
        result = run_phase0(
            brief_path=args.brief,
            config_root=ROOT / "configs",
            storage=storage,
            generator=generator,
            run_id=args.run_id,
        )
    except (ConfigError, ValueError, FileNotFoundError) as exc:
        print(f"Phase 0 generation failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result.__dict__, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
