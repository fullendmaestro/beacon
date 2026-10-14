# agent/src/smarthome_mcp/services/appliance_service.py
from __future__ import annotations

from typing import Any

from ..util.matcher import match_device
from .hub_client import HubConnectionError, SmartHomeHubClient


class ApplianceService:
    """Service layer for smart kitchen appliances, TV, washer, grill, and wall plugs."""

    def __init__(self, hub_client: SmartHomeHubClient | None = None):
        self.hub_client = hub_client or SmartHomeHubClient()

    async def list_appliances(self) -> list[dict[str, Any]]:
        return await self.hub_client.get_appliances()

    async def update_appliance(
        self,
        identifier: str,
        power_state: str | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        appliances = await self.list_appliances()
        target = match_device(appliances, identifier)
        if not target:
            return {
                "success": False,
                "error": f"Appliance or smart plug '{identifier}' was not found.",
            }

        try:
            updated = await self.hub_client.set_appliance_state(
                appliance_id=str(target["id"]),
                power_state=power_state,
                mode=mode,
            )
            return {
                "success": True,
                "message": (
                    f"Updated '{target['name']}' -> state: {updated.get('state')}, "
                    f"mode: {updated.get('mode')} ({updated.get('power_watts')}W)."
                ),
                **updated,
            }
        except HubConnectionError as e:
            return {"success": False, "error": str(e)}