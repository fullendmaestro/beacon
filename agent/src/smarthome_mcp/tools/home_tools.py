from __future__ import annotations

from typing import Any, Literal

from fastmcp import FastMCP

from ..services.home_service import HomeService


def register_home_tools(
    mcp: FastMCP, home_service: HomeService | None = None
) -> None:
    service = home_service or HomeService()

    @mcp.tool()
    async def get_devices(
        domain: str | None = None,
        room_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Unified device discovery tool returning exact 'id' and 'wbt_name' pairs from the SQLite registry.
        Call this before mutating any device if you do not have its exact 'id' or 'wbt_name'.

        Args:
            domain: Optional filter ('light' | 'door' | 'blind' | 'climate' | 'appliance' | 'sensor' | 'camera').
            room_id: Optional room filter (e.g. 'kitchen', 'living_room', 'foyer', 'master_bedroom').
        """
        return await service.list_devices(domain=domain, room_id=room_id)

    @mcp.tool()
    async def provision_device(
        wbt_name: str,
        domain: Literal["light", "door", "blind", "climate", "appliance", "sensor", "camera"],
        proto_type: str,
        translation: list[float],
        room_id: str | None = None,
        initial_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Dynamically provision and spawn a new smart home device into SQLite and the live Webots scene.
        """
        return await service.provision_device({
            "wbt_name": wbt_name,
            "domain": domain,
            "proto_type": proto_type,
            "room_id": room_id,
            "translation": translation,
            "initial_state": initial_state or {},
        })

    @mcp.tool()
    async def remove_device(identifier: str) -> dict[str, Any]:
        """
        Remove a dynamically provisioned device by exact 'id' or 'wbt_name'.
        """
        return await service.remove_device(identifier)

    @mcp.tool()
    async def get_home_summary() -> dict[str, Any]:
        """
        Get an overall status summary of the smart home, including active lights count,
        open doors count, real-time total power consumption in Watts, and exterior time of day.
        """
        return await service.get_summary()

    @mcp.tool()
    async def get_sensors() -> list[dict[str, Any]]:
        """
        Get live telemetry from all motion/presence sensors (Front Porch, Living Room, Hallway, Driveway Gate)
        and the roof ambient daylight sensor.
        """
        return await service.list_sensors()

    @mcp.tool()
    async def get_cameras() -> list[dict[str, Any]]:
        """
        List all 6 interior and exterior security cameras and their online status.
        """
        return await service.list_cameras()

    @mcp.tool()
    async def trigger_scene(
        scene: Literal["morning", "away", "movie", "night"]
    ) -> dict[str, Any]:
        """
        Trigger a whole-home automation scene preset:
        - 'morning': Daylight sky, open all blinds, turn on interior lights.
        - 'movie': Sunset sky, close all blinds, dim living room lights to warm white, turn on Smart TV.
        - 'away': Turn off all lights, close all blinds, close and lock all doors and gates.
        - 'night': Night sky, close blinds, lock all doors/gates, turn on exterior bollard & porch lights.
        """
        return await service.trigger_scene(scene)

    @mcp.tool()
    async def set_environment(
        time_of_day: Literal["day", "sunset", "night"]
    ) -> dict[str, Any]:
        """
        Change the simulated exterior sun luminosity and time of day ('day', 'sunset', or 'night').
        """
        return await service.set_environment(time_of_day)