from __future__ import annotations

from typing import Any

import httpx

from ..util.config import SMART_HOME_HUB_URL


class HubConnectionError(Exception):
    """Raised when communication with the simulated hub controller fails."""


def strict_not_found_error(identifier: str, domain: str | None = None) -> dict[str, Any]:
    domain_arg = f"domain='{domain}'" if domain else ""
    return {
        "success": False,
        "error_code": "DEVICE_NOT_FOUND_STRICT",
        "message": (
            f"No device matched exact id or wbt_name '{identifier}'. "
            f"Fuzzy matching is disabled. Call get_devices({domain_arg}) first "
            "to retrieve exact 'id' or 'wbt_name' values."
        ),
    }


def strict_match(devices: list[dict[str, Any]], identifier: str) -> dict[str, Any] | None:
    """Case-sensitive exact match on id, device_id, wbt_name, or name. Zero fuzzy matching."""
    if not identifier:
        return None
    for d in devices:
        if (
            d.get("id") == identifier
            or d.get("device_id") == identifier
            or d.get("wbt_name") == identifier
            or d.get("name") == identifier
        ):
            return d
    return None


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

    async def _delete(self, path: str) -> Any:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.delete(url)
                response.raise_for_status()
                return response.json()
        except httpx.RequestError as e:
            raise HubConnectionError(
                f"Failed to send DELETE to hub controller at {self.base_url}: {e}"
            ) from e
        except httpx.HTTPStatusError as e:
            raise HubConnectionError(
                f"Hub returned error status {e.response.status_code}: {e.response.text}"
            ) from e

    # --- V2 Unified Registry & Provisioning ---

    async def get_devices(
        self, domain: str | None = None, room_id: str | None = None
    ) -> list[dict[str, Any]]:
        params: list[str] = []
        if domain:
            params.append(f"domain={domain}")
        if room_id:
            params.append(f"room_id={room_id}")
        q = f"?{'&'.join(params)}" if params else ""
        return await self._get(f"/api/v2/devices{q}")

    async def provision_device(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._post("/api/v2/devices", payload)

    async def delete_device(self, identifier: str) -> dict[str, Any]:
        import urllib.parse

        enc = urllib.parse.quote(identifier, safe="")
        return await self._delete(f"/api/v2/devices/{enc}")

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

    async def get_light(self, node_id: str | int) -> dict[str, Any]:
        import urllib.parse

        enc = urllib.parse.quote(str(node_id), safe="")
        return await self._get(f"/api/lights/{enc}")

    async def toggle_light(self, node_id: str | int) -> dict[str, Any]:
        import urllib.parse

        enc = urllib.parse.quote(str(node_id), safe="")
        return await self._post(f"/api/lights/{enc}/toggle")

    async def set_light_state(
        self,
        node_id: str | int,
        power_state: str | None = None,
        brightness_level: int | None = None,
        color: str | None = None,
    ) -> dict[str, Any]:
        import urllib.parse

        enc = urllib.parse.quote(str(node_id), safe="")
        payload: dict[str, Any] = {}
        if power_state is not None:
            payload["power_state"] = power_state.lower()
        if brightness_level is not None:
            payload["brightness"] = brightness_level
        if color is not None:
            payload["color"] = color
        return await self._post(f"/api/lights/{enc}/state", payload)

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
        import urllib.parse

        enc = urllib.parse.quote(str(door_id), safe="")
        payload: dict[str, Any] = {}
        if open_state is not None:
            payload["open_state"] = open_state.lower()
        if locked is not None:
            payload["locked"] = locked
        if position is not None:
            payload["position"] = position
        return await self._post(f"/api/doors/{enc}/state", payload)

    # --- Motorized Window Blinds ---

    async def get_blinds(self) -> list[dict[str, Any]]:
        return await self._get("/api/blinds")

    async def set_blind_state(self, blind_id: str, position: int) -> dict[str, Any]:
        import urllib.parse

        enc = urllib.parse.quote(str(blind_id), safe="")
        return await self._post(f"/api/blinds/{enc}/state", {"position": position})

    # --- Climate / HVAC Zones ---

    async def get_climate_zones(self) -> list[dict[str, Any]]:
        return await self._get("/api/climate")

    async def set_climate_state(
        self,
        zone_id: str | int,
        power_state: str | None = None,
        target_temp: float | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        import urllib.parse

        enc = urllib.parse.quote(str(zone_id), safe="")
        payload: dict[str, Any] = {}
        if power_state is not None:
            payload["power_state"] = power_state.lower()
        if target_temp is not None:
            payload["target_temp"] = target_temp
        if mode is not None:
            payload["mode"] = mode.lower()
        return await self._post(f"/api/climate/{enc}/state", payload)

    # --- Smart Appliances & Wall Plugs ---

    async def get_appliances(self) -> list[dict[str, Any]]:
        return await self._get("/api/appliances")

    async def set_appliance_state(
        self,
        appliance_id: str,
        power_state: str | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        import urllib.parse

        enc = urllib.parse.quote(str(appliance_id), safe="")
        payload: dict[str, Any] = {}
        if power_state is not None:
            payload["power_state"] = power_state.lower()
        if mode is not None:
            payload["mode"] = mode
        return await self._post(f"/api/appliances/{enc}/state", payload)

    # --- Sensors & Cameras ---

    async def get_sensors(self) -> list[dict[str, Any]]:
        return await self._get("/api/sensors")

    async def get_cameras(self) -> list[dict[str, Any]]:
        return await self._get("/api/cameras")