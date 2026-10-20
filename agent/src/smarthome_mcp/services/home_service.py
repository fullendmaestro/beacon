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

    async def list_humans(self) -> list[dict[str, Any]]:
        try:
            return await self.hub_client.get_humans()
        except HubConnectionError as e:
            return [{"error": str(e)}]

    async def control_human(self, human_id: str, action: str, location: str | None = None) -> dict[str, Any]:
        try:
            payload: dict[str, Any] = {"human_id": human_id, "action": action}
            if location:
                payload["location"] = location
            return await self.hub_client.control_human(payload)
        except HubConnectionError as e:
            return {"success": False, "error": str(e)}

    async def list_objects(self) -> list[dict[str, Any]]:
        try:
            return await self.hub_client.get_objects()
        except HubConnectionError as e:
            return [{"error": str(e)}]

    async def list_tasks(self) -> dict[str, Any]:
        try:
            return await self.hub_client.get_tasks()
        except HubConnectionError as e:
            return {"success": False, "error": str(e)}

    async def create_task(
        self,
        title: str,
        description: str,
        category: str = "errand",
        mode: str = "hitl",
        room: str = "Living Room",
        proposed_actions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        try:
            return await self.hub_client.create_task({
                "title": title,
                "description": description,
                "category": category,
                "mode": mode,
                "trigger_source": "Beacon AI Agent",
                "room": room,
                "proposed_actions": proposed_actions or [],
            })
        except HubConnectionError as e:
            return {"success": False, "error": str(e)}

    async def approve_task(self, task_id: str) -> dict[str, Any]:
        try:
            return await self.hub_client.approve_task(task_id)
        except HubConnectionError as e:
            return {"success": False, "error": str(e)}