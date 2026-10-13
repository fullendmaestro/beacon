from __future__ import annotations

from typing import Any, Literal

from fastmcp import FastMCP

from ..services.light_service import LightService


def register_light_tools(mcp: FastMCP, light_service: LightService | None = None) -> None:
    """
    Registers the light-specific tools on the given FastMCP instance.
    Each tool maps directly to principles in mcp.md:
      1. get_lights (Device discovery for lights)
      2. get_light_state (Device state query for a specific light)
      3. set_power_state (Turn light on / off)
      4. set_brightness (Dimmer / brightness control: 0-100%)
      5. set_color (Color control: named colors or hex)
    """
    service = light_service or LightService()

    @mcp.tool()
    async def get_lights() -> list[dict[str, Any]]:
        """
        List all smart lights in the simulated home.

        Returns:
            List of light devices containing device_id, name, type, power_state ('on' | 'off'),
            brightness (0-100), color (hex code), and metadata.
        """
        return await service.list_lights()

    @mcp.tool()
    async def get_light_state(device_id: str) -> dict[str, Any]:
        """
        Retrieve the current state of a specific light device.

        Args:
            device_id: The unique ID or name of the light (e.g. '123' or 'CeilingLight').

        Returns:
            Current state including device_id, name, type, power_state ('on' | 'off'),
            brightness (0-100), color, and metadata.
        """
        light = await service.get_light(device_id)
        if not light:
            return {
                "isError": True,
                "error": f"Light '{device_id}' was not found.",
                "device_id": device_id,
            }
        return light

    @mcp.tool()
    async def set_power_state(device_id: str, power_state: Literal["on", "off"]) -> dict[str, Any]:
        """
        Turn a smart light device on or off.

        Args:
            device_id: The unique ID or name of the light (e.g. '123' or 'CeilingLight').
            power_state: Desired power state, either 'on' or 'off'.

        Returns:
            Result of the power change operation with updated device state.
        """
        return await service.set_power(device_id, power_state)

    @mcp.tool()
    async def set_brightness(device_id: str, brightness_level: int) -> dict[str, Any]:
        """
        Set the brightness level of a light.

        Args:
            device_id: The unique ID or name of the light (e.g. '123' or 'CeilingLight').
            brightness_level: Brightness percentage from 0 (off) to 100 (maximum brightness).

        Returns:
            Result of the brightness change operation with updated device state.
        """
        return await service.set_brightness(device_id, brightness_level)

    @mcp.tool()
    async def set_color(device_id: str, color: str) -> dict[str, Any]:
        """
        Set the color of a smart light.

        Args:
            device_id: The unique ID or name of the light (e.g. '123' or 'CeilingLight').
            color: Color name (e.g. 'warm white', 'cool white', 'soft white', 'red', 'green', 'blue', 'orange', 'purple')
                   or hex code (e.g. '#FF9900').

        Returns:
            Result of the color change operation with updated device state.
        """
        return await service.set_color(device_id, color)
