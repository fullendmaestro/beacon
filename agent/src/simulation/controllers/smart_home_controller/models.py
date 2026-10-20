from __future__ import annotations

from typing import Any, Literal

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


class HumanControlRequest(BaseModel):
    human_id: Literal["resident", "guest"] = Field("resident", description="'resident' (Alex) or 'guest' (Sam)")
    action: Literal["goto_location", "goto_coords", "step", "patrol_loop", "stop"] = Field(
        "goto_location", description="Human control action"
    )
    location: str | None = Field(None, description="Named room/sensor location key")
    x: float | None = Field(None, description="Target X coordinate in meters")
    y: float | None = Field(None, description="Target Y coordinate in meters")
    dx: float | None = Field(None, description="Step delta X in meters")
    dy: float | None = Field(None, description="Step delta Y in meters")
    teleport: bool | None = Field(False, description="Teleport immediately instead of walking")


class ObjectMoveRequest(BaseModel):
    object_name: str = Field(..., description="Household object name (e.g. 'cup', 'bottle', 'keys')")
    surface: str | None = Field(None, description="Named surface preset (e.g. 'kitchen_island', 'coffee_table')")
    x: float | None = Field(None, description="Optional explicit X coordinate")
    y: float | None = Field(None, description="Optional explicit Y coordinate")
    z: float | None = Field(None, description="Optional explicit Z coordinate")


class TaskCreateRequest(BaseModel):
    title: str = Field(..., description="Short task title")
    description: str = Field(..., description="Detailed explanation of what the AI proposes or executed")
    category: Literal["security", "comfort", "errand", "energy", "safety"] = Field("errand")
    mode: Literal["ambient", "hitl"] = Field("hitl")
    trigger_source: str = Field("Beacon AI Agent")
    room: str = Field("Living Room")
    proposed_actions: list[dict[str, Any]] = Field(default_factory=list)


class TaskSettingsRequest(BaseModel):
    ambient_enabled: bool | None = None
    hitl_enabled: bool | None = None


class ScenarioTriggerRequest(BaseModel):
    scenario: str = Field(..., description="Scenario identifier e.g. 'visitor_front_door', 'driveway_arrival', 'nightfall_lockdown'")
