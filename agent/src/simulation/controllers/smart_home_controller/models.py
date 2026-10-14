from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class LightStateUpdateRequest(BaseModel):
    power_state: str | None = Field(None, description="'on' or 'off'")
    brightness: int | None = Field(None, ge=0, le=100, description="0 to 100 percentage")
    color: str | None = Field(None, description="Color name like 'warm white' or hex '#FF0000'")


class DoorUpdateRequest(BaseModel):
    open_state: Literal["open", "closed"] | None = Field(None, description="'open' or 'closed'")
    locked: bool | None = Field(None, description="Lock or unlock the door/barrier")
    position: int | None = Field(None, ge=0, le=100, description="0 (closed) to 100 (fully open)")


class BlindUpdateRequest(BaseModel):
    position: int = Field(..., ge=0, le=100, description="0 (closed/down) to 100 (open/up)")


class ClimateUpdateRequest(BaseModel):
    power_state: Literal["on", "off"] | None = Field(None, description="'on' or 'off'")
    target_temp: float | None = Field(None, ge=15.0, le=30.0, description="Target temperature in Celsius")
    mode: Literal["heat", "cool", "eco", "off"] | None = Field(None, description="HVAC operating mode")


class ApplianceUpdateRequest(BaseModel):
    power_state: Literal["on", "off"] | None = Field(None, description="'on' or 'off'")
    mode: str | None = Field(None, description="Operating mode (e.g., 'Eco', 'Movie Mode', 'Bake 180C')")


class EnvironmentUpdateRequest(BaseModel):
    time_of_day: Literal["day", "sunset", "night"] = Field(..., description="Preset exterior sky & sun lighting")


class SceneTriggerRequest(BaseModel):
    scene: Literal["morning", "away", "movie", "night"] = Field(
        ..., description="Smart home automation scene preset"
    )