from __future__ import annotations

from typing import Any, Literal

from fastmcp import FastMCP

from ..services.home_service import HomeService


def register_home_tools(
    mcp: FastMCP, home_service: HomeService | None = None
) -> None:
    service = home_service or HomeService()

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