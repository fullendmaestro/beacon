"""Pydantic models, SQLite DDL schema, and color utilities for Beacon Hub."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

SCHEMA_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS rooms (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    polygon_2d TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    wbt_name TEXT UNIQUE NOT NULL,
    wbt_def TEXT UNIQUE,
    domain TEXT NOT NULL,
    proto_type TEXT NOT NULL,
    room_id TEXT REFERENCES rooms(id),
    translation TEXT NOT NULL,
    rotation TEXT NOT NULL,
    config_json TEXT NOT NULL,
    controller_name TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS device_states (
    device_id TEXT PRIMARY KEY REFERENCES devices(id) ON DELETE CASCADE,
    online BOOLEAN NOT NULL DEFAULT 1,
    desired_state TEXT NOT NULL,
    reported_state TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS nav_nodes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    room_id TEXT REFERENCES rooms(id),
    x REAL NOT NULL,
    y REAL NOT NULL,
    default_theta REAL NOT NULL DEFAULT 0.0,
    is_dock BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS nav_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_node TEXT NOT NULL REFERENCES nav_nodes(id) ON DELETE CASCADE,
    to_node TEXT NOT NULL REFERENCES nav_nodes(id) ON DELETE CASCADE,
    blocking_device_id TEXT REFERENCES devices(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS robots (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    model TEXT NOT NULL,
    pose_x REAL NOT NULL DEFAULT -3.10,
    pose_y REAL NOT NULL DEFAULT -7.62,
    theta REAL NOT NULL DEFAULT 1.5708,
    battery_pct REAL NOT NULL DEFAULT 95.0,
    status TEXT NOT NULL DEFAULT 'Docked',
    task_description TEXT NOT NULL DEFAULT 'idle',
    arm_pose TEXT NOT NULL DEFAULT 'home',
    gripper TEXT NOT NULL DEFAULT 'open',
    held_object TEXT NOT NULL DEFAULT '',
    target_destination TEXT,
    active_waypoints_json TEXT NOT NULL DEFAULT '[]',
    doors_to_clear_json TEXT NOT NULL DEFAULT '[]',
    online BOOLEAN NOT NULL DEFAULT 1,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS errands (
    task_id TEXT PRIMARY KEY,
    robot_id TEXT NOT NULL DEFAULT 'tiago',
    errand_type TEXT NOT NULL,
    item TEXT NOT NULL DEFAULT '',
    from_location TEXT NOT NULL DEFAULT '',
    to_location TEXT NOT NULL DEFAULT '',
    current_step INTEGER NOT NULL DEFAULT 0,
    total_steps INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'idle',
    message TEXT NOT NULL DEFAULT '',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS environment_config (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

COLOR_NAMES_MAP: dict[str, list[float]] = {
    "white": [1.0, 1.0, 1.0],
    "warm white": [1.0, 0.9, 0.7],
    "soft white": [1.0, 0.85, 0.65],
    "cool white": [0.85, 0.92, 1.0],
    "daylight": [0.95, 0.98, 1.0],
    "red": [1.0, 0.0, 0.0],
    "green": [0.0, 1.0, 0.0],
    "blue": [0.0, 0.2, 1.0],
    "cyan": [0.0, 1.0, 1.0],
    "magenta": [1.0, 0.0, 1.0],
    "yellow": [1.0, 1.0, 0.0],
    "orange": [1.0, 0.5, 0.0],
    "purple": [0.6, 0.1, 0.9],
    "pink": [1.0, 0.4, 0.7],
}


class ColorUtils:
    """Helper utilities for RGB/Hex/Named color conversion."""

    @staticmethod
    def parse(color: str | list[float]) -> list[float]:
        if isinstance(color, list) and len(color) == 3:
            return [round(max(0.0, min(1.0, float(c))), 3) for c in color]

        if not isinstance(color, str):
            return [1.0, 1.0, 1.0]

        color_clean = color.strip().lower()
        if color_clean in COLOR_NAMES_MAP:
            return list(COLOR_NAMES_MAP[color_clean])

        hex_match = re.match(r"^#?([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})$", color_clean)
        if hex_match:
            r = int(hex_match.group(1), 16) / 255.0
            g = int(hex_match.group(2), 16) / 255.0
            b = int(hex_match.group(3), 16) / 255.0
            return [round(r, 3), round(g, 3), round(b, 3)]

        return [1.0, 1.0, 1.0]

    @staticmethod
    def to_hex(rgb: list[float]) -> str:
        if not rgb or len(rgb) < 3:
            return "#ffffff"
        r = int(max(0.0, min(1.0, float(rgb[0]))) * 255)
        g = int(max(0.0, min(1.0, float(rgb[1]))) * 255)
        b = int(max(0.0, min(1.0, float(rgb[2]))) * 255)
        return f"#{r:02x}{g:02x}{b:02x}"


DeviceDomain = Literal[
    "light",
    "door",
    "blind",
    "climate",
    "appliance",
    "sensor",
    "camera",
]


class DeviceProvisionRequest(BaseModel):
    id: str | None = Field(None, description="Optional custom immutable slug/UUID")
    wbt_name: str = Field(..., description="Exact Webots node .wbt name field")
    wbt_def: str | None = Field(None, description="Optional Webots DEF identifier")
    domain: DeviceDomain = Field(..., description="IoT device domain")
    proto_type: str = Field(..., description="Webots PROTO or node type")
    room_id: str | None = Field(None, description="Assigned room ID (auto-inferred from polygon if omitted)")
    translation: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0], min_length=3, max_length=3)
    rotation: list[float] = Field(default_factory=lambda: [0.0, 0.0, 1.0, 0.0], min_length=4, max_length=4)
    config: dict[str, Any] = Field(default_factory=dict)
    initial_state: dict[str, Any] = Field(default_factory=dict)
    controller_name: str | None = Field(None)


class CommandRequest(BaseModel):
    action: str = Field(default="set_state")
    params: dict[str, Any] = Field(default_factory=dict)


class NavNodeProvisionRequest(BaseModel):
    id: str
    name: str
    room_id: str | None = None
    x: float
    y: float
    default_theta: float = 0.0
    is_dock: bool = False
    connect_to: list[str] = Field(default_factory=list)


class DeviceRecord(BaseModel):
    id: str
    wbt_name: str
    wbt_def: str | None = None
    domain: str
    proto_type: str
    room_id: str | None = None
    room_name: str | None = None
    translation: list[float]
    rotation: list[float]
    config: dict[str, Any]
    controller_name: str
    online: bool = True
    desired_state: dict[str, Any]
    reported_state: dict[str, Any]
