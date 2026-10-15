from __future__ import annotations

import os
from typing import Any

import httpx

SMART_HOME_HUB_URL = os.getenv("SMART_HOME_HUB_URL", "http://127.0.0.1:8000")


class RoverService:
    """HTTP client service communicating with the Webots Rover Manager endpoints."""

    def __init__(self, base_url: str = SMART_HOME_HUB_URL) -> None:
        self.base_url = base_url

    async def get_status(self) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0) as client:
            resp = await client.get("/api/rover")
            resp.raise_for_status()
            return resp.json()

    async def navigate_to_room(self, destination: str) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0) as client:
            resp = await client.post("/api/rover/navigate", json={"destination": destination})
            resp.raise_for_status()
            return resp.json()

    async def navigate_to_coordinates(self, x: float, y: float, yaw: float = 0.0) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0) as client:
            resp = await client.post("/api/rover/goto_pose", json={"x": x, "y": y, "yaw": yaw})
            resp.raise_for_status()
            return resp.json()

    async def control(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0) as client:
            resp = await client.post("/api/rover/control", json=payload)
            resp.raise_for_status()
            return resp.json()