# agent/src/simulation/controllers/smart_home_controller/constants.py
from __future__ import annotations

import re
from typing import Any

MAX_LIGHT_INTENSITY = 3.0
SUPPORTED_LIGHT_TYPES = {"CeilingLight", "FloorLight", "CeilingSpotLight"}

CAMERA_NAMES = [
    "Living Room Camera",
    "Kitchen Camera",
    "Bedroom Camera",
    "Front Door Camera",
    "Driveway Camera",
    "Backyard Patio Camera",
]

MOTION_SENSOR_NAMES = [
    "Front Porch Motion Sensor",
    "Living Room Motion Sensor",
    "Hallway Motion Sensor",
    "Driveway Gate Motion Sensor",
]

LIGHT_SENSOR_NAMES = [
    "Exterior Daylight Sensor",
]

BLIND_DEFS: dict[str, dict[str, float | str]] = {
    "BLIND_LIVING_WEST": {
        "name": "Living Room West Blind",
        "room": "Living Room",
        "closed_z": 1.25,
        "open_z": 2.28,
    },
    "BLIND_LIVING_NORTH": {
        "name": "Living Room North Blind",
        "room": "Living Room",
        "closed_z": 1.25,
        "open_z": 2.28,
    },
    "BLIND_MASTER_BEDROOM": {
        "name": "Master Bedroom Blind",
        "room": "Master Bedroom",
        "closed_z": 1.25,
        "open_z": 2.28,
    },
    "BLIND_STUDY_BEDROOM": {
        "name": "Study Bedroom Blind",
        "room": "Study Bedroom",
        "closed_z": 1.25,
        "open_z": 2.28,
    },
}

EXTERIOR_BARRIER_DEFS: dict[str, dict[str, float | str]] = {
    "DRIVEWAY_GATE": {
        "name": "Driveway Gate",
        "type": "SlidingGate",
        "axis": "x",
        "closed_pos": 2.1,
        "open_pos": -1.6,
    },
    "GARAGE_DOOR": {
        "name": "Garage Door",
        "type": "OverheadGarageDoor",
        "axis": "z",
        "closed_pos": 1.15,
        "open_pos": 2.30,
    },
}

APPLIANCE_DEFAULTS: dict[str, dict[str, str | float]] = {
    "Living Room Smart TV": {"type": "Television", "room": "Living Room", "mode": "Standby", "wattage": 120.0},
    "Smart Fridge": {"type": "Fridge", "room": "Kitchen", "mode": "Eco Cooling (3°C)", "wattage": 180.0},
    "Smart Oven": {"type": "Oven", "room": "Kitchen", "mode": "Off", "wattage": 2400.0},
    "Smart Microwave": {"type": "Microwave", "room": "Kitchen", "mode": "Ready", "wattage": 1100.0},
    "Induction Cooktop": {"type": "Cooktop", "room": "Kitchen", "mode": "Off", "wattage": 1800.0},
    "Smart Washer": {"type": "WashingMachine", "room": "Utility", "mode": "Idle", "wattage": 850.0},
    "Smart Patio Grill": {"type": "Barbecue", "room": "Patio", "mode": "Off", "wattage": 1500.0},
    "Dining Smart Plug": {"type": "WallPlug", "room": "Dining Room", "mode": "On", "wattage": 45.0},
    "Living Room Smart Plug": {"type": "WallPlug", "room": "Living Room", "mode": "On", "wattage": 60.0},
    "Kitchen Island Smart Plug": {"type": "WallPlug", "room": "Kitchen", "mode": "On", "wattage": 90.0},
    "Foyer Smart Plug": {"type": "WallPlug", "room": "Foyer", "mode": "On", "wattage": 25.0},
}

# Strictly Orthogonal Manhattan Navigation Graph (All segments are 90-degree straight lines)
NAV_NODES: dict[str, dict[str, Any]] = {
    # --- East-West Corridor Spine (Strictly y = -7.62 for radiator clearance) ---
    "front_door": {
        "name": "Front Entrance",
        "room": "Foyer",
        "pose": [-0.91, -7.62, 0.0],
    },
    "master_junction": {
        "name": "Master Bedroom Junction",
        "room": "Foyer",
        "pose": [-2.15, -7.62, -1.5708],
    },
    "foyer": {
        "name": "Foyer Dock",
        "room": "Foyer",
        "pose": [-3.10, -7.62, 3.1416],
    },
    "bathroom_junction": {
        "name": "Bathroom Junction",
        "room": "Corridor",
        "pose": [-4.94, -7.62, -1.5708],
    },
    "hallway": {
        "name": "West Corridor Corner",
        "room": "Corridor",
        "pose": [-5.35, -7.62, 1.5708],
    },
    "study_junction": {
        "name": "Study Bedroom Junction",
        "room": "Corridor",
        "pose": [-6.24, -7.62, -1.5708],
    },
    # --- Rooms Branching Vertically Off Corridor ---
    "utility_room": {
        "name": "Utility Closet",
        "room": "Utility",
        "pose": [-0.91, -5.90, 1.5708],
    },
    "master_bedroom": {
        "name": "Master Bedroom",
        "room": "Master Bedroom",
        "pose": [-2.15, -9.80, -1.5708],
    },
    "bathroom": {
        "name": "Main Bathroom",
        "room": "Bathroom",
        "pose": [-4.94, -9.30, -1.5708],
    },
    "study_bedroom": {
        "name": "Study Bedroom",
        "room": "Study Bedroom",
        "pose": [-6.24, -9.80, -1.5708],
    },
    # --- North-South Living Room Spine (Strictly x = -5.35) ---
    "kitchen_approach": {
        "name": "Kitchen Door Approach",
        "room": "Living Room",
        "pose": [-5.35, -3.95, 0.0],
    },
    "living_room": {
        "name": "Living Room",
        "room": "Living Room",
        "pose": [-5.35, -1.80, 1.5708],
    },
    # --- Kitchen Branch (Strictly y = -3.95) ---
    "kitchen": {
        "name": "Kitchen",
        "room": "Kitchen",
        "pose": [-2.35, -3.95, 0.0],
    },
    # --- Dining Room Branch (Strictly y = -1.80) ---
    "dining_room": {
        "name": "Dining Room",
        "room": "Dining Room",
        "pose": [-9.20, -1.80, 3.1416],
    },
}


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
    """Helper utilities for color conversion and parsing."""

    @staticmethod
    def parse(color: str | list[float]) -> list[float]:
        if isinstance(color, list) and len(color) == 3:
            return [max(0.0, min(1.0, float(c))) for c in color]

        if not isinstance(color, str):
            return [1.0, 1.0, 1.0]

        color_clean = color.strip().lower()
        if color_clean in COLOR_NAMES_MAP:
            return COLOR_NAMES_MAP[color_clean]

        hex_match = re.match(r"^#?([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})$", color_clean)
        if hex_match:
            r = int(hex_match.group(1), 16) / 255.0
            g = int(hex_match.group(2), 16) / 255.0
            b = int(hex_match.group(3), 16) / 255.0
            return [round(r, 3), round(g, 3), round(b, 3)]

        return [1.0, 1.0, 1.0]

    @staticmethod
    def to_hex(rgb: list[float]) -> str:
        r = int(max(0.0, min(1.0, rgb[0])) * 255)
        g = int(max(0.0, min(1.0, rgb[1])) * 255)
        b = int(max(0.0, min(1.0, rgb[2])) * 255)
        return f"#{r:02x}{g:02x}{b:02x}"