from __future__ import annotations

from typing import Any

from constants import MAX_LIGHT_INTENSITY, SUPPORTED_LIGHT_TYPES, ColorUtils
from fastapi import HTTPException


class LightingManager:
    """Manages smart interior and exterior lighting nodes and states."""

    def __init__(self) -> None:
        self.light_nodes: dict[int, Any] = {}
        self.light_states: dict[int, dict[str, Any]] = {}

    @staticmethod
    def get_light_fields(node: Any) -> tuple[Any, Any]:
        type_name = node.getTypeName()
        if type_name == "CeilingSpotLight":
            return node.getField("spotLightIntensity"), node.getField("spotLightColor")
        return node.getField("pointLightIntensity"), node.getField("pointLightColor")

    def register_node(self, node: Any, node_id: int, name: str, type_name: str) -> None:
        if type_name not in SUPPORTED_LIGHT_TYPES:
            return
        self.light_nodes[node_id] = node
        i_field, c_field = self.get_light_fields(node)
        raw_intensity = i_field.getSFFloat() if i_field else 0.0
        raw_color = c_field.getSFColor() if c_field else [1.0, 1.0, 1.0]
        is_on = raw_intensity > 0
        brightness_pct = round(min(100.0, (raw_intensity / MAX_LIGHT_INTENSITY) * 100)) if is_on else 0

        self.light_states[node_id] = {
            "id": node_id,
            "name": name,
            "type": type_name,
            "state": "On" if is_on else "Off",
            "intensity": raw_intensity,
            "brightness": brightness_pct if brightness_pct > 0 else 100,
            "color_rgb": raw_color,
            "color_hex": ColorUtils.to_hex(raw_color),
            "metadata": f"Intensity at {raw_intensity:.1f}",
        }

    def list_lights(self) -> list[dict[str, Any]]:
        return [
            {
                "id": s["id"],
                "name": s["name"],
                "state": s["state"],
                "type": s["type"],
                "brightness": s["brightness"] if s["state"] == "On" else 0,
                "color": s["color_hex"],
                "color_rgb": s["color_rgb"],
                "metadata": f"Intensity at {s['intensity']:.1f}",
            }
            for s in self.light_states.values()
        ]

    def get_light(self, node_id: int) -> dict[str, Any]:
        s = self.light_states.get(node_id)
        if not s:
            raise HTTPException(status_code=404, detail="Light not found")
        return {
            "id": s["id"],
            "name": s["name"],
            "state": s["state"],
            "type": s["type"],
            "brightness": s["brightness"] if s["state"] == "On" else 0,
            "color": s["color_hex"],
            "color_rgb": s["color_rgb"],
            "metadata": f"Intensity at {s['intensity']:.1f}",
        }

    def execute_cmd(self, cmd: dict[str, Any]) -> dict[str, Any]:
        node_id = cmd["node_id"]
        node = self.light_nodes.get(node_id)
        if not node:
            return {"error": "Light not found"}

        i_field, c_field = self.get_light_fields(node)
        action = cmd.get("action")
        state = self.light_states[node_id]
        current_intensity = i_field.getSFFloat() if i_field else 0.0
        current_brightness = state.get("brightness", 100)

        if action == "toggle":
            new_is_on = not (current_intensity > 0)
            target_intensity = (MAX_LIGHT_INTENSITY * (current_brightness / 100.0)) if new_is_on else 0.0
            if i_field:
                i_field.setSFFloat(target_intensity)
            state["state"] = "On" if new_is_on else "Off"
            state["intensity"] = target_intensity
            state["metadata"] = f"Intensity at {target_intensity:.1f}"

        elif action == "set_state":
            target_is_on = state.get("state") == "On"
            if cmd.get("power_state"):
                target_is_on = cmd["power_state"].lower() == "on"
            if cmd.get("brightness") is not None:
                b_val = max(0, min(100, int(cmd["brightness"])))
                if b_val == 0:
                    target_is_on = False
                else:
                    target_is_on = True
                    current_brightness = b_val
                state["brightness"] = current_brightness
            if cmd.get("color"):
                parsed_rgb = ColorUtils.parse(cmd["color"])
                if c_field:
                    c_field.setSFColor(parsed_rgb)
                state["color_rgb"] = parsed_rgb
                state["color_hex"] = ColorUtils.to_hex(parsed_rgb)

            target_intensity = (MAX_LIGHT_INTENSITY * (current_brightness / 100.0)) if target_is_on else 0.0
            if i_field:
                i_field.setSFFloat(target_intensity)
            state["state"] = "On" if target_is_on else "Off"
            state["intensity"] = target_intensity
            state["metadata"] = f"Intensity at {target_intensity:.1f}"

        return {
            "success": True,
            "id": node_id,
            "state": state["state"],
            "brightness": state["brightness"] if state["state"] == "On" else 0,
            "color": state["color_hex"],
            "intensity": state["intensity"],
        }