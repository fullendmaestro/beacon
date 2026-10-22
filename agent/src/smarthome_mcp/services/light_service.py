from __future__ import annotations

from typing import Any

from .hub_client import HubConnectionError, SmartHomeHubClient, strict_match, strict_not_found_error


class LightService:
    """Service layer that manages smart light business logic with strict ID/wbt_name lookup."""

    def __init__(self, hub_client: SmartHomeHubClient | None = None):
        self.hub_client = hub_client or SmartHomeHubClient()

    def _normalize_light(self, dev: dict[str, Any]) -> dict[str, Any]:
        """Normalize raw hub payload into standardized light schema."""
        power_state = "on" if str(dev.get("state", dev.get("power_state", ""))).lower() == "on" else "off"
        return {
            "id": str(dev.get("id")),
            "device_id": str(dev.get("id")),
            "wbt_name": dev.get("wbt_name", dev.get("name", "Unknown Light")),
            "name": dev.get("name", dev.get("wbt_name", "Unknown Light")),
            "room_id": dev.get("room_id"),
            "type": dev.get("type", "Light"),
            "power_state": power_state,
            "brightness": dev.get("brightness", 100 if power_state == "on" else 0),
            "color": dev.get("color", "#ffffff"),
            "color_rgb": dev.get("color_rgb", [1.0, 1.0, 1.0]),
            "metadata": dev.get("metadata", ""),
        }

    async def list_lights(self) -> list[dict[str, Any]]:
        """List all discovered smart lights in the simulated home."""
        devices = await self.hub_client.get_lights()
        return [self._normalize_light(dev) for dev in devices]

    async def get_light(self, device_id: str) -> dict[str, Any] | None:
        """Get state for a specific light by strict exact ID or wbt_name match."""
        lights = await self.list_lights()
        return strict_match(lights, device_id)

    async def set_power(self, device_id: str, power_state: str) -> dict[str, Any]:
        """Set the power state ('on' or 'off') of a light using strict lookup."""
        target = await self.get_light(device_id)
        if not target:
            return strict_not_found_error(device_id, domain="light")

        desired_state = power_state.lower().strip()
        if desired_state not in ("on", "off"):
            return {
                "success": False,
                "error": f"Invalid power_state '{power_state}'. Must be 'on' or 'off'.",
                "device_id": target["device_id"],
            }

        try:
            res = await self.hub_client.set_light_state(
                node_id=target["device_id"],
                power_state=desired_state,
            )
            return {
                "success": True,
                "message": f"Turned {desired_state} light '{target['name']}'.",
                "device_id": target["device_id"],
                "wbt_name": target["wbt_name"],
                "name": target["name"],
                "power_state": desired_state,
                "brightness": res.get("brightness", target["brightness"]),
                "color": res.get("color", target["color"]),
            }
        except HubConnectionError as e:
            return {
                "success": False,
                "error": str(e),
                "device_id": target["device_id"],
            }

    async def set_brightness(self, device_id: str, brightness_level: int) -> dict[str, Any]:
        """Set the brightness level (0-100) of a light using strict lookup."""
        target = await self.get_light(device_id)
        if not target:
            return strict_not_found_error(device_id, domain="light")

        if not (0 <= brightness_level <= 100):
            return {
                "success": False,
                "error": f"Brightness level must be between 0 and 100, received {brightness_level}.",
                "device_id": target["device_id"],
            }

        try:
            power_state = "off" if brightness_level == 0 else "on"
            res = await self.hub_client.set_light_state(
                node_id=target["device_id"],
                power_state=power_state,
                brightness_level=brightness_level,
            )
            return {
                "success": True,
                "message": f"Set brightness of '{target['name']}' to {brightness_level}%.",
                "device_id": target["device_id"],
                "wbt_name": target["wbt_name"],
                "name": target["name"],
                "power_state": power_state,
                "brightness_level": brightness_level,
                "color": res.get("color", target["color"]),
            }
        except HubConnectionError as e:
            return {
                "success": False,
                "error": str(e),
                "device_id": target["device_id"],
            }

    async def set_color(self, device_id: str, color: str) -> dict[str, Any]:
        """Set the color of a light using strict lookup."""
        target = await self.get_light(device_id)
        if not target:
            return strict_not_found_error(device_id, domain="light")

        try:
            res = await self.hub_client.set_light_state(
                node_id=target["device_id"],
                color=color,
            )
            return {
                "success": True,
                "message": f"Set color of '{target['name']}' to '{color}'.",
                "device_id": target["device_id"],
                "wbt_name": target["wbt_name"],
                "name": target["name"],
                "power_state": str(res.get("state", target["power_state"])).lower(),
                "color": res.get("color", color),
            }
        except HubConnectionError as e:
            return {
                "success": False,
                "error": str(e),
                "device_id": target["device_id"],
            }
