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
from crucible.phase0.spine import build_storage, verify_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a Crucible Phase 0 manifest against its stored asset.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--run-id")
    source.add_argument("--manifest-uri")
    parser.add_argument("--dry-run", action="store_true", help="Read from local temp storage instead of B2.")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    settings = Phase0Settings.from_env()
    local_root = ROOT / "tmp" / "phase0-storage"

    try:
        storage = build_storage(dry_run=args.dry_run, settings=settings, local_root=local_root)
        manifest = verify_manifest(storage=storage, run_id=args.run_id, manifest_uri=args.manifest_uri)
    except (ConfigError, ValueError, FileNotFoundError) as exc:
        print(f"Manifest verification failed: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": "verified",
                "run_id": manifest.run_id,
                "asset_uri": manifest.asset_uri,
                "asset_sha256": manifest.asset_sha256,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
