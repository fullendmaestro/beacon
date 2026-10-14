from __future__ import annotations

from typing import Any, Literal

from fastmcp import FastMCP

from ..services.climate_service import ClimateService


def register_climate_tools(
    mcp: FastMCP, climate_service: ClimateService | None = None
) -> None:
    service = climate_service or ClimateService()

    @mcp.tool()
    async def get_climate_zones() -> list[dict[str, Any]]:
        """
        List all room radiator and HVAC thermostat zones, including current and target temperatures in Celsius.
        """
        return await service.list_zones()

    @mcp.tool()
    async def set_climate_state(
        zone_id: str,
        target_temp: float | None = None,
        mode: Literal["heat", "cool", "eco", "off"] | None = None,
        power_state: Literal["on", "off"] | None = None,
    ) -> dict[str, Any]:
        """
        Update the target temperature, HVAC mode, or power state for a room climate zone.

        Args:
            zone_id: The ID or room name of the radiator/thermostat (e.g. 'Living Room Radiator', 'Master Bedroom').
            target_temp: Target temperature in Celsius between 15.0 and 30.0.
            mode: Operating mode ('heat', 'cool', 'eco', or 'off').
            power_state: 'on' or 'off'.
        """
        return await service.update_zone(
            identifier=zone_id,
            target_temp=target_temp,
            mode=mode,
            power_state=power_state,
        )