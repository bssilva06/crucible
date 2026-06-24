from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CrucibleModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        populate_by_name=True,
        validate_assignment=True,
    )
