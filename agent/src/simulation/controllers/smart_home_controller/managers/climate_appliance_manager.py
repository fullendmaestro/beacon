from __future__ import annotations

from typing import Any

from constants import APPLIANCE_DEFAULTS
from fastapi import HTTPException


class ClimateApplianceManager:
    """Manages HVAC radiators, smart kitchen/home appliances, wall plugs, and sky lighting."""

    def __init__(self) -> None:
        self.climate_nodes: dict[int, Any] = {}
        self.climate_states: dict[int, dict[str, Any]] = {}
        self.appliance_nodes: dict[str, Any] = {}
        self.appliance_states: dict[str, dict[str, Any]] = {}
        self.sun_node: Any = None
        self.environment_state: dict[str, Any] = {
            "time_of_day": "day",
            "sun_luminosity": 0.8,
        }

    def register_radiator(self, node: Any, node_id: int, name: str) -> None:
        self.climate_nodes[node_id] = node
        self.climate_states[node_id] = {
            "id": node_id,
            "name": name,
            "type": "Radiator",
            "state": "On",
            "mode": "eco",
            "current_temp": 21.5,
            "target_temp": 22.0,
            "metadata": "Eco • Target 22.0°C",
        }

    def register_appliance(self, node: Any | None, name: str) -> None:
        if name not in APPLIANCE_DEFAULTS:
            return
        app_id = name.lower().replace(" ", "_")
        defaults = APPLIANCE_DEFAULTS[name]
        if node is not None:
            self.appliance_nodes[app_id] = node
        is_active = defaults["mode"] not in ("Off", "Standby", "Idle")
        self.appliance_states[app_id] = {
            "id": app_id,
            "name": name,
            "type": str(defaults["type"]),
            "room": str(defaults["room"]),
            "state": "On" if is_active else "Off",
            "mode": str(defaults["mode"]),
            "power_watts": float(defaults["wattage"]) if is_active else 2.5,
            "rated_watts": float(defaults["wattage"]),
        }

    def ensure_all_default_appliances(self) -> None:
        for app_name in APPLIANCE_DEFAULTS:
            app_id = app_name.lower().replace(" ", "_")
            if app_id not in self.appliance_states:
                self.register_appliance(None, app_name)

    def update_climate(
        self,
        zone_id: int,
        power_state: str | None = None,
        target_temp: float | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        zone = self.climate_states.get(zone_id)
        if not zone:
            raise HTTPException(status_code=404, detail="Climate zone not found")
        if power_state is not None:
            zone["state"] = "On" if power_state.lower() == "on" else "Off"
        if mode is not None:
            zone["mode"] = mode.lower()
            zone["state"] = "Off" if zone["mode"] == "off" else "On"
        if target_temp is not None:
            zone["target_temp"] = round(float(target_temp), 1)
        zone["metadata"] = f"{zone['mode'].title()} • Target {zone['target_temp']:.1f}°C"
        return dict(zone)

    def update_appliance(
        self,
        appliance_id: str,
        power_state: str | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        app = self.appliance_states.get(appliance_id)
        if not app:
            raise HTTPException(status_code=404, detail="Appliance not found")
        if power_state is not None:
            is_on = power_state.lower() == "on"
            app["state"] = "On" if is_on else "Off"
            app["power_watts"] = app["rated_watts"] if is_on else 2.5
            if not is_on:
                app["mode"] = "Off"
            elif app["mode"] == "Off":
                app["mode"] = "Active"
        if mode is not None:
            app["mode"] = mode
            if mode.lower() not in ("off", "standby", "idle"):
                app["state"] = "On"
                app["power_watts"] = app["rated_watts"]
        return dict(app)

    def execute_environment_cmd(self, cmd: dict[str, Any]) -> dict[str, Any]:
        tod = cmd["time_of_day"]
        lum_map = {"day": 0.85, "sunset": 0.3, "night": 0.04}
        lum = lum_map.get(tod, 0.85)
        if self.sun_node:
            lum_field = self.sun_node.getField("luminosity")
            if lum_field:
                lum_field.setSFFloat(lum)
        self.environment_state["time_of_day"] = tod
        self.environment_state["sun_luminosity"] = lum
        return dict(self.environment_state)