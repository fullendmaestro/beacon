# agent/src/simulation/controllers/smart_home_controller/constants.py
"""
All static device and navigation dictionaries (BLIND_DEFS, EXTERIOR_BARRIER_DEFS,
APPLIANCE_DEFAULTS, NAV_NODES, NAV_EDGES, CAMERA_NAMES) have been eliminated and
migrated to the relational SQLite WAL database (`beacon_state.db`) managed by `beacon_hub`.
"""
from __future__ import annotations

from beacon_hub.database.models import COLOR_NAMES_MAP, ColorUtils

MAX_LIGHT_INTENSITY = 3.0
SUPPORTED_LIGHT_TYPES = {"CeilingLight", "FloorLight", "CeilingSpotLight"}

__all__ = ["COLOR_NAMES_MAP", "ColorUtils", "MAX_LIGHT_INTENSITY", "SUPPORTED_LIGHT_TYPES"]
