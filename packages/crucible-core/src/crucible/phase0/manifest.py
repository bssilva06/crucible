from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Phase0Manifest:
    schema_version: str
    run_id: str
    created_at: str
    brief_id: str
    provider: str
    model: str
    asset_uri: str
    asset_sha256: str
    genblaze: dict[str, Any]

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        brief_id: str,
        provider: str,
        model: str,
        asset_uri: str,
        asset_sha256: str,
        genblaze: dict[str, Any] | None = None,
    ) -> "Phase0Manifest":
        return cls(
            schema_version="phase0.1",
            run_id=run_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            brief_id=brief_id,
            provider=provider,
            model=model,
            asset_uri=asset_uri,
            asset_sha256=asset_sha256,
            genblaze=genblaze or {},
        )

    def to_json_bytes(self) -> bytes:
        return json.dumps(asdict(self), indent=2, sort_keys=True).encode("utf-8")

    @classmethod
    def from_json_bytes(cls, data: bytes) -> "Phase0Manifest":
        loaded = json.loads(data.decode("utf-8"))
        return cls(**loaded)
