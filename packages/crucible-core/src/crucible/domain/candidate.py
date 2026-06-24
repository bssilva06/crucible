from __future__ import annotations

from pydantic import Field

from crucible.domain.base import CrucibleModel


class AssetRef(CrucibleModel):
    uri: str
    sha256: str | None = Field(default=None, min_length=64, max_length=64)
    mime_type: str | None = None
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    bytes_size: int | None = Field(default=None, ge=0)
