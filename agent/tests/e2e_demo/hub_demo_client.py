from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import httpx

SMART_HOME_HUB_URL = os.getenv("SMART_HOME_HUB_URL", "http://127.0.0.1:8000")


class WebotsDemoClient:
    """Modular client for controlling Webots Viewpoint cinematography, MP4 recording, and state verification."""

    def __init__(self, base_url: str = SMART_HOME_HUB_URL) -> None:
        self.base_url = base_url.rstrip("/")

    async def is_online(self) -> bool:
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=2.0) as client:
                resp = await client.get("/api/home/summary")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def set_environment(self, time_of_day: str) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0) as client:
            resp = await client.post("/api/home/environment", json={"time_of_day": time_of_day})
            resp.raise_for_status()
            return resp.json()

    async def focus_on_device(
        self,
        target_name: str,
        target_type: str = "light",
        duration: float = 1.0,
        offset: list[float] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "mode": "focus",
            "target_type": target_type,
            "target_name": target_name,
            "duration": duration,
        }
        if offset:
            payload["offset"] = offset
        async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0) as client:
            resp = await client.post("/api/demo/camera/focus", json=payload)
            resp.raise_for_status()
            res = resp.json()
        await asyncio.sleep(duration + 0.25)
        return res

    async def focus_preset(self, preset: str, duration: float = 1.0) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0) as client:
            resp = await client.post(
                "/api/demo/camera/focus",
                json={"mode": "focus", "preset": preset, "duration": duration},
            )
            resp.raise_for_status()
            res = resp.json()
        await asyncio.sleep(duration + 0.25)
        return res

    async def follow_rover(self, duration: float = 0.8, offset: list[float] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"mode": "follow_rover", "duration": duration}
        if offset:
            payload["offset"] = offset
        async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0) as client:
            resp = await client.post("/api/demo/camera/focus", json=payload)
            resp.raise_for_status()
            res = resp.json()
        await asyncio.sleep(duration + 0.2)
        return res

    async def start_recording(
        self,
        label: str,
        filename: str | None = None,
        width: int = 1920,
        height: int = 1080,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "label": label,
            "width": width,
            "height": height,
            "quality": 95,
            "acceleration": 1,
        }
        if filename:
            payload["filename"] = filename
        async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0) as client:
            resp = await client.post("/api/demo/recording/start", json=payload)
            resp.raise_for_status()
            return resp.json()

    async def stop_recording(self, wait_for_encoding: float = 15.0) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0) as client:
            resp = await client.post("/api/demo/recording/stop")
            resp.raise_for_status()
            result = resp.json()

            # Poll until Webots finishes flushing the MP4 file to disk
            deadline = asyncio.get_event_loop().time() + wait_for_encoding
            while asyncio.get_event_loop().time() < deadline:
                status_resp = await client.get("/api/demo/status")
                status = status_resp.json()
                video_path = result.get("video_path")
                if status.get("movie_ready") and video_path and Path(video_path).exists():
                    break
                await asyncio.sleep(0.4)

            return result

    async def get_lights(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0) as client:
            resp = await client.get("/api/lights")
            resp.raise_for_status()
            return resp.json()

    async def set_light_direct(
        self,
        name_query: str,
        power_state: str,
        brightness: int = 100,
        color: str = "white",
    ) -> dict[str, Any]:
        lights = await self.get_lights()
        target = next((l for l in lights if name_query.lower() in l["name"].lower()), None)
        if not target:
            raise ValueError(f"Light '{name_query}' not found")
        async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0) as client:
            resp = await client.post(
                f"/api/lights/{target['id']}/state",
                json={"power_state": power_state, "brightness": brightness, "color": color},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_rover(self) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0) as client:
            resp = await client.get("/api/rover")
            resp.raise_for_status()
            return resp.json()