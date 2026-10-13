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

    async def get_lights(self) -> list[dict[str, Any]]:
        """Fetch all light devices from the hub controller."""
        url = f"{self.base_url}/api/lights"
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

    async def get_light(self, node_id: int) -> dict[str, Any]:
        """Fetch a single light device by node ID from the hub controller."""
        url = f"{self.base_url}/api/lights/{node_id}"
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

    async def toggle_light(self, node_id: int) -> dict[str, Any]:
        """Toggle power state for a specific light node ID."""
        url = f"{self.base_url}/api/lights/{node_id}/toggle"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url)
                response.raise_for_status()
                return response.json()
        except httpx.RequestError as e:
            raise HubConnectionError(
                f"Failed to toggle light {node_id} on hub controller at {self.base_url}: {e}"
            ) from e
        except httpx.HTTPStatusError as e:
            raise HubConnectionError(
                f"Hub returned error status {e.response.status_code}: {e.response.text}"
            ) from e

    async def set_light_state(
        self,
        node_id: int,
        power_state: str | None = None,
        brightness_level: int | None = None,
        color: str | None = None,
    ) -> dict[str, Any]:
        """Set explicit light state (power, brightness, color) on the hub controller."""
        payload: dict[str, Any] = {}
        if power_state is not None:
            payload["power_state"] = power_state.lower()
        if brightness_level is not None:
            payload["brightness"] = brightness_level
        if color is not None:
            payload["color"] = color

        url = f"{self.base_url}/api/lights/{node_id}/state"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                if response.status_code in (404, 405):
                    # Fallback for older controllers only exposing /toggle
                    return await self.toggle_light(node_id)
                response.raise_for_status()
                return response.json()
        except httpx.RequestError as e:
            raise HubConnectionError(
                f"Failed to set light state on hub controller at {self.base_url}: {e}"
            ) from e
        except httpx.HTTPStatusError as e:
            raise HubConnectionError(
                f"Hub returned error status {e.response.status_code}: {e.response.text}"
            ) from e
