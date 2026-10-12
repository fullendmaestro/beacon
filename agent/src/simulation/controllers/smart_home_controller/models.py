from __future__ import annotations

from pydantic import BaseModel, Field


class LightStateUpdateRequest(BaseModel):
    power_state: str | None = Field(None, description="'on' or 'off'")
    brightness: int | None = Field(None, ge=0, le=100, description="0 to 100 percentage")
    color: str | None = Field(None, description="Color name like 'warm white' or hex '#FF0000'")
