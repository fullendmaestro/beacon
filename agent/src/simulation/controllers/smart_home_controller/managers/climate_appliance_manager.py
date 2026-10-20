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
            "power_watts": 185.0,
            "metadata": "Eco • 21.5°C → 22.0°C",
        }

    def step_climate(self, dt_sec: float) -> None:
        """Advance thermal simulation so current_temp converges toward target_temp or ambient."""
        tod = self.environment_state.get("time_of_day", "day")
        ambient_temp = 20.5 if tod == "day" else (18.5 if tod == "sunset" else 16.0)
        # Thermal convergence rate (°C per second of simulation time)
        active_rate = 0.08
        passive_rate = 0.02

        for zone in self.climate_states.values():
            curr = float(zone["current_temp"])
            target = float(zone["target_temp"])
            mode = str(zone.get("mode", "eco")).lower()
            is_on = zone.get("state") == "On" and mode != "off"

            if is_on:
                diff = target - curr
                if mode == "heat" and diff < 0:
                    diff = 0.0
                elif mode == "cool" and diff > 0:
                    diff = 0.0
                rate_mult = 0.65 if mode == "eco" else 1.0
                step_delta = max(-active_rate * dt_sec * rate_mult, min(active_rate * dt_sec * rate_mult, diff))
                new_temp = round(curr + step_delta, 2)
                abs_gap = abs(target - new_temp)
                base_draw = 140.0 if mode == "eco" else 220.0
                zone["power_watts"] = round(min(650.0, base_draw + abs_gap * 95.0), 1)
            else:
                diff = ambient_temp - curr
                step_delta = max(-passive_rate * dt_sec, min(passive_rate * dt_sec, diff))
                new_temp = round(curr + step_delta, 2)
                zone["power_watts"] = 0.0

            zone["current_temp"] = round(new_temp, 1)
            zone["metadata"] = f"{zone['mode'].title()} • {zone['current_temp']:.1f}°C → {zone['target_temp']:.1f}°C"

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
        if zone["state"] == "Off":
            zone["power_watts"] = 0.0
        else:
            abs_gap = abs(float(zone["target_temp"]) - float(zone["current_temp"]))
            base_draw = 140.0 if zone["mode"] == "eco" else 220.0
            zone["power_watts"] = round(min(650.0, base_draw + abs_gap * 95.0), 1)
        zone["metadata"] = f"{zone['mode'].title()} • {zone['current_temp']:.1f}°C → {zone['target_temp']:.1f}°C"
        return dict(zone)

    @staticmethod
    def _compute_appliance_watts(rated: float, is_on: bool, mode: str) -> float:
        if not is_on or mode.lower() in ("off", "standby", "idle"):
            return 2.5
        m_low = mode.lower()
        if any(k in m_low for k in ("eco", "vacation", "simmer", "warm", "ambient", "low")):
            return round(rated * 0.6, 1)
        if any(k in m_low for k in ("boost", "sear", "fast freeze", "broil")):
            return round(rated * 1.15, 1)
        return round(rated, 1)

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
            if not is_on:
                app["mode"] = "Off"
            elif app["mode"] in ("Off", "Standby", "Idle"):
                app["mode"] = "Active"
        if mode is not None:
            app["mode"] = mode
            if mode.lower() in ("off", "standby", "idle"):
                app["state"] = "Off"
            else:
                app["state"] = "On"
        app["power_watts"] = self._compute_appliance_watts(
            float(app["rated_watts"]),
            app["state"] == "On",
            str(app["mode"]),
        )
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