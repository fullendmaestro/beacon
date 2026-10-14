# agent/src/smarthome_mcp/services/climate_service.py
from __future__ import annotations

from typing import Any

from ..util.matcher import match_device
from .hub_client import HubConnectionError, SmartHomeHubClient


class ClimateService:
    """Service layer for room radiators and HVAC thermostat zones."""

    def __init__(self, hub_client: SmartHomeHubClient | None = None):
        self.hub_client = hub_client or SmartHomeHubClient()

    async def list_zones(self) -> list[dict[str, Any]]:
        return await self.hub_client.get_climate_zones()

    async def update_zone(
        self,
        identifier: str,
        target_temp: float | None = None,
        mode: str | None = None,
        power_state: str | None = None,
    ) -> dict[str, Any]:
        zones = await self.list_zones()
        target = match_device(zones, identifier)
        if not target:
            return {
                "success": False,
                "error": f"Climate zone '{identifier}' was not found.",
            }

        if target_temp is not None and not (15.0 <= target_temp <= 30.0):
            return {
                "success": False,
                "error": f"Target temperature must be between 15.0°C and 30.0°C, got {target_temp}°C.",
            }

        try:
            updated = await self.hub_client.set_climate_state(
                zone_id=int(target["id"]),
                power_state=power_state,
                target_temp=target_temp,
                mode=mode,
            )
            return {
                "success": True,
                "message": f"Updated climate zone '{target['name']}' ({updated.get('metadata')}).",
                **updated,
            }
        except HubConnectionError as e:
            return {"success": False, "error": str(e)}