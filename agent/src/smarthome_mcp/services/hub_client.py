from __future__ import annotations

from typing import Any

import httpx

from ..util.config import SMART_HOME_HUB_URL


class HubConnectionError(Exception):
    """Raised when communication with the simulated hub controller fails."""


class SmartHomeHubClient:
    """Client for communicating with the simulated Smart Home Hub controller."""

    def __init__(self, base_url: str = SMART_HOME_HUB_URL, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def _get(self, path: str) -> Any:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
        except httpx.RequestError as e:
            raise HubConnectionError(
                f"Failed to connect to simulated hub controller at {self.base_url}: {e}"
            ) from e
        except httpx.HTTPStatusError as e:
            raise HubConnectionError(
                f"Hub returned error status {e.response.status_code}: {e.response.text}"
            ) from e

    async def _post(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.RequestError as e:
            raise HubConnectionError(
                f"Failed to send command to hub controller at {self.base_url}: {e}"
            ) from e
        except httpx.HTTPStatusError as e:
            raise HubConnectionError(
                f"Hub returned error status {e.response.status_code}: {e.response.text}"
            ) from e

    # --- Home Summary, Scenes & Environment ---

    async def get_summary(self) -> dict[str, Any]:
        return await self._get("/api/home/summary")

    async def trigger_scene(self, scene: str) -> dict[str, Any]:
        return await self._post("/api/home/scene", {"scene": scene})

    async def set_environment(self, time_of_day: str) -> dict[str, Any]:
        return await self._post("/api/home/environment", {"time_of_day": time_of_day})

    # --- Lights ---

    async def get_lights(self) -> list[dict[str, Any]]:
        return await self._get("/api/lights")

    async def get_light(self, node_id: int) -> dict[str, Any]:
        return await self._get(f"/api/lights/{node_id}")

    async def toggle_light(self, node_id: int) -> dict[str, Any]:
        return await self._post(f"/api/lights/{node_id}/toggle")

    async def set_light_state(
        self,
        node_id: int,
        power_state: str | None = None,
        brightness_level: int | None = None,
        color: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if power_state is not None:
            payload["power_state"] = power_state.lower()
        if brightness_level is not None:
            payload["brightness"] = brightness_level
        if color is not None:
            payload["color"] = color
        return await self._post(f"/api/lights/{node_id}/state", payload)

    # --- Doors, Locks, Garage Door & Driveway Gate ---

    async def get_doors(self) -> list[dict[str, Any]]:
        return await self._get("/api/doors")

    async def set_door_state(
        self,
        door_id: str,
        open_state: str | None = None,
        locked: bool | None = None,
        position: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if open_state is not None:
            payload["open_state"] = open_state.lower()
        if locked is not None:
            payload["locked"] = locked
        if position is not None:
            payload["position"] = position
        return await self._post(f"/api/doors/{door_id}/state", payload)

    # --- Motorized Window Blinds ---

    async def get_blinds(self) -> list[dict[str, Any]]:
        return await self._get("/api/blinds")

    async def set_blind_state(self, blind_id: str, position: int) -> dict[str, Any]:
        return await self._post(f"/api/blinds/{blind_id}/state", {"position": position})

    # --- Climate / HVAC Zones ---

    async def get_climate_zones(self) -> list[dict[str, Any]]:
        return await self._get("/api/climate")

    async def set_climate_state(
        self,
        zone_id: int,
        power_state: str | None = None,
        target_temp: float | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if power_state is not None:
            payload["power_state"] = power_state.lower()
        if target_temp is not None:
            payload["target_temp"] = target_temp
        if mode is not None:
            payload["mode"] = mode.lower()
        return await self._post(f"/api/climate/{zone_id}/state", payload)

    # --- Smart Appliances & Wall Plugs ---

    async def get_appliances(self) -> list[dict[str, Any]]:
        return await self._get("/api/appliances")

    async def set_appliance_state(
        self,
        appliance_id: str,
        power_state: str | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if power_state is not None:
            payload["power_state"] = power_state.lower()
        if mode is not None:
            payload["mode"] = mode
        return await self._post(f"/api/appliances/{appliance_id}/state", payload)

    # --- Sensors & Cameras ---

    async def get_sensors(self) -> list[dict[str, Any]]:
        return await self._get("/api/sensors")

    async def get_cameras(self) -> list[dict[str, Any]]:
        return await self._get("/api/cameras")

    # --- Humans, Household Objects & AI Tasks ---

    async def get_humans(self) -> list[dict[str, Any]]:
        return await self._get("/api/humans")

    async def control_human(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._post("/api/humans/control", payload)

    async def get_objects(self) -> list[dict[str, Any]]:
        return await self._get("/api/objects")

    async def move_object(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._post("/api/objects/move", payload)

    async def get_tasks(self) -> dict[str, Any]:
        return await self._get("/api/tasks")

    async def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._post("/api/tasks", payload)

    async def approve_task(self, task_id: str) -> dict[str, Any]:
        return await self._post(f"/api/tasks/{task_id}/approve")

    async def reject_task(self, task_id: str) -> dict[str, Any]:
        return await self._post(f"/api/tasks/{task_id}/reject")