from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Brief:
    brief_id: str
    prompt: str
    vertical: str = "ecommerce_product_shot"
    required_text: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> "Brief":
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return cls(
            brief_id=data["brief_id"],
            prompt=data["prompt"],
            vertical=data.get("vertical", "ecommerce_product_shot"),
            required_text=list(data.get("required_text", [])),
            constraints=dict(data.get("constraints", {})),
        )
