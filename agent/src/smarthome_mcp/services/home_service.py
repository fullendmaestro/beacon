from __future__ import annotations

from typing import Any

from .hub_client import HubConnectionError, SmartHomeHubClient


class HomeService:
    """Service layer for whole-home telemetry, scenes, sensors, cameras, and sun/sky."""

    def __init__(self, hub_client: SmartHomeHubClient | None = None):
        self.hub_client = hub_client or SmartHomeHubClient()

    async def get_summary(self) -> dict[str, Any]:
        try:
            return await self.hub_client.get_summary()
        except HubConnectionError as e:
            return {"success": False, "error": str(e)}

    async def list_devices(
        self, domain: str | None = None, room_id: str | None = None
    ) -> list[dict[str, Any]]:
        devices = await self.hub_client.get_devices(domain=domain, room_id=room_id)
        return [
            {
                "id": d["id"],
                "wbt_name": d["wbt_name"],
                "domain": d["domain"],
                "proto_type": d["proto_type"],
                "room_id": d["room_id"],
                "translation": d["translation"],
                "reported_state": d["reported_state"],
            }
            for d in devices
        ]

    async def provision_device(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return await self.hub_client.provision_device(payload)
        except HubConnectionError as e:
            return {"success": False, "error": str(e)}

    async def remove_device(self, identifier: str) -> dict[str, Any]:
        try:
            return await self.hub_client.delete_device(identifier)
        except HubConnectionError as e:
            return {"success": False, "error": str(e)}

    async def list_sensors(self) -> list[dict[str, Any]]:
        return await self.hub_client.get_sensors()

    async def list_cameras(self) -> list[dict[str, Any]]:
        return await self.hub_client.get_cameras()

    async def trigger_scene(self, scene: str) -> dict[str, Any]:
        clean_scene = scene.strip().lower()
        if clean_scene not in ("morning", "away", "movie", "night"):
            return {
                "success": False,
                "error": f"Invalid scene '{scene}'. Valid scenes: 'morning', 'away', 'movie', 'night'.",
            }
        try:
            res = await self.hub_client.trigger_scene(clean_scene)
            return {
                "success": True,
                "message": f"Activated smart home scene '{clean_scene}'.",
                **res,
            }
        except HubConnectionError as e:
            return {"success": False, "error": str(e)}

    async def set_environment(self, time_of_day: str) -> dict[str, Any]:
        clean_tod = time_of_day.strip().lower()
        if clean_tod not in ("day", "sunset", "night"):
            return {
                "success": False,
                "error": f"Invalid time_of_day '{time_of_day}'. Must be 'day', 'sunset', or 'night'.",
            }
        try:
            res = await self.hub_client.set_environment(clean_tod)
            return {
                "success": True,
                "message": f"Updated exterior environment to '{clean_tod}'.",
                **res,
            }
        except HubConnectionError as e:
            return {"success": False, "error": str(e)}