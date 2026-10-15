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


class RoverNavigateRequest(BaseModel):
    destination: Literal[
        "foyer",
        "living_room",
        "dining_room",
        "kitchen",
        "hallway",
        "master_bedroom",
        "study_bedroom",
        "patrol",
    ] = Field(..., description="Target room key or 'patrol' to tour the estate")


class RoverPoseRequest(BaseModel):
    x: float = Field(..., description="Target Webots X coordinate in meters")
    y: float = Field(..., description="Target Webots Y coordinate in meters")
    yaw: float = Field(0.0, description="Target heading angle in radians")


class RoverControlRequest(BaseModel):
    action: Literal["stop", "arm", "gripper", "velocity"] = Field(..., description="Rover control action")
    arm_pose: Literal[
        "reset",
        "front_floor",
        "front_box",
        "front_plate",
        "back_plate_high",
        "back_plate_low",
        "inspect_high",
    ] | None = Field(None, description="5-DOF arm preset pose")
    gripper_state: Literal["grip", "release"] | None = Field(None, description="Gripper finger state")
    vx: float | None = Field(None, ge=-0.3, le=0.3, description="Forward speed m/s")
    vy: float | None = Field(None, ge=-0.3, le=0.3, description="Strafe left speed m/s")
    omega: float | None = Field(None, ge=-1.0, le=1.0, description="Angular velocity rad/s")